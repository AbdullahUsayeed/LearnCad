# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""The LearnCad coach panel.

One left panel and one job: state, the single next step, and one mentor note.
The engine writes into structured widgets; the constraint panel only appears
while a sketch or feature task is active. There is one slim Ask bar.
"""

from __future__ import annotations

import html
import os
import re
import shutil
import time
from datetime import datetime, timezone
from typing import Any, Optional

from .compat import QtCore, QtGui, QtWidgets, blocking_modal

from . import actions, ai_client, branding, cloud_ai, coach, course, course_package, guide, render_bridge, secret_store, settings, simple_mode, studio, suggest
from .engine import MentorEngine
from .model import Analysis, Snapshot


_DOCK: Optional[QtWidgets.QDockWidget] = None
_PANEL: Optional["MentorPanel"] = None


SEVERITY_COLOR = {
    "critical": "#d64545",
    "warn": "#c47f17",
    "good": "#2f8f5b",
    "info": "#ff9a3c",
}


# Control names the coach/AI is allowed to point at. The first match in an
# answer gets highlighted so "what do I press?" also glows the right button.
_HINT_KEYWORDS = (
    ("rectangle", "sketch:Rect"),
    ("rect", "sketch:Rect"),
    ("circle", "sketch:Circle"),
    ("arc", "sketch:Arc"),
    ("polyline", "sketch:Line"),
    ("line", "sketch:Line"),
    ("coincident", "sketch:Coincident"),
    ("horizontal", "sketch:Horiz"),
    ("horiz", "sketch:Horiz"),
    ("vertical", "sketch:Vert"),
    ("vert", "sketch:Vert"),
    ("dimension", "sketch:Dim"),
    ("dim", "sketch:Dim"),
    ("radius", "sketch:Radius"),
    ("done", "sketch:Done"),
    ("finish", "sketch:Done"),
    ("pad", "main:Pad"),
    ("pocket", "main:Pocket"),
    ("hole", "main:Hole"),
    ("fillet", "main:Fillet"),
    ("chamfer", "main:Fillet"),
    ("export", "main:Export"),
    ("stl", "main:Export"),
    ("render", "main:Render"),
    ("studio", "panel:studio"),
    ("setup", "panel:setup"),
    ("settings", "panel:setup"),
    ("click sketch", "main:Sketch"),
    ("new sketch", "main:Sketch"),
    ("create sketch", "main:Sketch"),
    ("start a sketch", "main:Sketch"),
    ("body + sketch", "main:Sketch"),
    ("guide me", "panel:primary"),
    ("do this next", "panel:primary"),
    ("course", "panel:course"),
    ("lesson", "panel:course"),
)


def _hint_targets(text: str) -> list[str]:
    low = str(text or "").lower()
    found: list[tuple[int, int, str]] = []
    for keyword, target in _HINT_KEYWORDS:
        match = re.search(r"\b" + re.escape(keyword) + r"\b", low)
        if match is not None:
            found.append((match.start(), -len(keyword), target))
    found.sort()
    ordered: list[str] = []
    for _pos, _length, target in found:
        if target not in ordered:
            ordered.append(target)
    return ordered



def _esc(text: Any) -> str:
    return html.escape(str(text or ""))


def _fmt(value: float, digits: int = 1) -> str:
    text = f"{value:.{digits}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _score_color(score: int) -> str:
    if score >= 85:
        return "#2f8f5b"
    if score >= 65:
        return "#c47f17"
    return "#d64545"


def _status_word(score: int, doc) -> str:
    if doc is None or doc.is_empty:
        return "Ready"
    if doc.bodies and not any(body.feature_count for body in doc.bodies) and not doc.features:
        return "Ready"
    if score >= 85:
        return "On track"
    if score >= 65:
        return "Needs work"
    return "Fix first"


class _AskWorker(QtCore.QThread):
    done = QtCore.Signal(str)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        config: dict[str, Any],
        question: str,
        snapshot: Snapshot,
        analysis: Analysis,
        parent=None,
        history: list[dict[str, str]] | None = None,
    ):
        super().__init__(parent)
        self._config = config
        self._question = question
        self._snapshot = snapshot
        self._analysis = analysis
        self._history = list(history or [])

    def run(self) -> None:
        try:
            answer = ai_client.ask(
                self._config, self._question, self._snapshot, self._analysis, self._history
            )
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.done.emit(answer)


class _RenderWorker(QtCore.QThread):
    done = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, config: dict[str, Any], parent=None):
        super().__init__(parent)
        self._config = dict(config)

    def run(self) -> None:
        try:
            resolution = self._config.get("render_resolution", [1200, 800])
            if not isinstance(resolution, (list, tuple)) or len(resolution) != 2:
                resolution = (1200, 800)
            result = render_bridge.render_preview(
                engine=str(self._config.get("render_engine", "CYCLES")),
                resolution=(int(resolution[0]), int(resolution[1])),
                samples=int(self._config.get("render_samples", 64)),
                material=str(self._config.get("render_material", "aluminum")),
            )
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.done.emit(result)


class _ActivateWorker(QtCore.QThread):
    done = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, base_url: str, email: str, code: str, device: str, parent=None):
        super().__init__(parent)
        self._base_url = base_url
        self._email = email
        self._code = code
        self._device = device

    def run(self) -> None:
        try:
            result = cloud_ai.activate(self._base_url, self._email, self._code, self._device)
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.done.emit(result)


class _TestWorker(QtCore.QThread):
    done = QtCore.Signal(bool, str)

    def __init__(self, config: dict[str, Any], parent=None):
        super().__init__(parent)
        self._config = config

    def run(self) -> None:
        ok, message = ai_client.test_connection(self._config)
        self.done.emit(ok, message)


class _CourseDialog(QtWidgets.QDialog):
    """Guided courses, their lessons, and an import button."""

    def __init__(self, courses, completed, on_start, on_import=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LearnCad Courses")
        self.setMinimumWidth(560)
        self.resize(600, 720)
        self._on_start = on_start
        self._on_import = on_import

        outer = QtWidgets.QVBoxLayout(self)
        outer.setSpacing(10)
        lesson_count = sum(len(item.lessons) for item in courses)
        intro = QtWidgets.QLabel(
            f"{len(courses)} courses, {lesson_count} lessons. Each lesson highlights "
            "the next control and checks the model as you go. Progress is saved. "
            "Import a .learncad package to add a community course."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)
        layout.setSpacing(10)

        done_ids = set(completed or [])
        self._buttons = {}
        for course in courses:
            heading = QtWidgets.QLabel(course.title)
            heading.setObjectName("courseSection")
            layout.addWidget(heading)
            description = QtWidgets.QLabel(course.summary)
            description.setWordWrap(True)
            description.setObjectName("courseText")
            layout.addWidget(description)

            for index, lesson in enumerate(course.lessons, 1):
                done = lesson.id in done_ids
                card = QtWidgets.QFrame()
                card.setObjectName("courseCard")
                inner = QtWidgets.QVBoxLayout(card)
                inner.setContentsMargins(12, 10, 12, 10)
                inner.setSpacing(4)

                title = QtWidgets.QLabel(
                    f"{index}. {lesson.title}" + ("   \u2713 done" if done else "")
                )
                title.setObjectName("courseTitle")
                inner.addWidget(title)

                summary = QtWidgets.QLabel(lesson.summary)
                summary.setWordWrap(True)
                summary.setObjectName("courseText")
                inner.addWidget(summary)

                goal = QtWidgets.QLabel("Goal: " + lesson.outcome)
                goal.setWordWrap(True)
                goal.setObjectName("courseGoal")
                inner.addWidget(goal)

                row = QtWidgets.QHBoxLayout()
                row.addStretch(1)
                button = QtWidgets.QPushButton("Review lesson" if done else "Start lesson")
                button.setCursor(QtCore.Qt.PointingHandCursor)
                button.clicked.connect(
                    lambda checked=False, lesson_id=lesson.id: self._start(lesson_id)
                )
                self._buttons[lesson.id] = button
                row.addWidget(button)
                inner.addLayout(row)
                layout.addWidget(card)

        layout.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        bottom = QtWidgets.QHBoxLayout()
        import_button = QtWidgets.QPushButton("Import course...")
        import_button.setCursor(QtCore.Qt.PointingHandCursor)
        import_button.clicked.connect(self._import)
        bottom.addWidget(import_button)
        bottom.addStretch(1)
        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(self.reject)
        bottom.addWidget(close)
        outer.addLayout(bottom)

    def _start(self, lesson_id: str) -> None:
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self._on_start(lesson_id))

    def _import(self) -> None:
        if self._on_import is not None and self._on_import():
            self.accept()


class MentorPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = settings.load()
        try:
            self._courses_dir = os.path.join(settings.config_dir(), "courses")
        except Exception:
            self._courses_dir = ""
        self._load_installed_courses()
        self._snapshot: Optional[Snapshot] = None
        self._analysis: Optional[Analysis] = None
        self._worker: Optional[_AskWorker] = None
        self._test_worker: Optional[_TestWorker] = None
        self._activate_worker: Optional[_ActivateWorker] = None
        self._suggestion = None
        self._walkthrough = None
        self._walkthrough_steps: list = []
        self._walkthrough_index = 0
        self._course_lesson = None
        self._target_widget = None
        self._target_clicked = False
        self._highlighted = None
        self._highlight_timer = None
        self._pulse_on = False
        self._render_cache = None
        self._suggestion_cache = None
        self._history: list[dict[str, str]] = []
        self._engine = MentorEngine(
            int(self._config.get("poll_ms", 900)),
            self,
            goal=str(self._config.get("goal", "")),
        )
        self._engine.updated.connect(self._on_update)
        self._engine.failed.connect(self._on_failed)
        self._build_ui()
        self._engine.start()

    # ---------------------------------------------------------------- UI

    def _set_answer(self, speaker: str, text: str) -> None:
        try:
            self._answer_card.setVisible(True)
        except Exception:
            pass
        safe = _esc(text).replace("\n", "<br>")
        self._answer.setHtml(
            f'<div style="color:#ff9a3c;font-size:9px;font-weight:700;'
            f'letter-spacing:1px;margin-bottom:5px;">{_esc(speaker).upper()}</div>'
            f'<div style="color:#f5f5f5;font-size:12px;line-height:1.5;">{safe}</div>'
        )
        try:
            self._answer.verticalScrollBar().setValue(0)
        except Exception:
            pass

    def _build_ui(self) -> None:
        self.setObjectName("MentorPanel")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 12)
        outer.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(11)
        logo = QtWidgets.QLabel()
        icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "resources", "icons", "learncad.svg"
        )
        pixmap = QtGui.QIcon(icon_path).pixmap(30, 30)
        if not pixmap.isNull():
            logo.setPixmap(pixmap)
        logo.setFixedSize(30, 30)
        header.addWidget(logo)

        brand = QtWidgets.QVBoxLayout()
        brand.setSpacing(0)
        title = QtWidgets.QLabel("LearnCad")
        title.setObjectName("brandTitle")
        brand.addWidget(title)
        header.addLayout(brand)
        header.addStretch(1)

        self._score = QtWidgets.QLabel("Ready")
        self._score.setObjectName("statusPill")
        self._score.setAlignment(QtCore.Qt.AlignCenter)
        self._score.setMinimumWidth(86)
        header.addWidget(self._score)

        self._menu_btn = QtWidgets.QToolButton()
        self._menu_btn.setObjectName("menuButton")
        self._menu_btn.setText("\u22ef")
        self._menu_btn.setToolTip("LearnCad options")
        self._menu_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(self._menu_btn)
        menu.addAction("Courses", self._open_course)
        menu.addAction("Import course...", self._import_course)
        menu.addAction("All tools", self._open_all_tools)
        menu.addAction("Studio look", self._studio)
        menu.addAction("Render studio", self._render_preview)
        menu.addAction("Setup", self._open_settings)
        menu.addSeparator()
        menu.addAction("Collapse coach", self._collapse_coach)
        self._menu_btn.setMenu(menu)
        header.addWidget(self._menu_btn)
        outer.addLayout(header)

        # Legacy controls kept as hidden objects for the existing methods and
        # target resolver. The visible front is intentionally just the menu.
        self._studio_btn = QtWidgets.QToolButton(self)
        self._studio_btn.setText("Studio")
        self._studio_btn.clicked.connect(self._studio)
        self._studio_btn.hide()
        self._render_btn = QtWidgets.QToolButton(self)
        self._render_btn.setText("Render")
        self._render_btn.clicked.connect(self._render_preview)
        self._render_btn.hide()
        self._settings_btn = QtWidgets.QToolButton(self)
        self._settings_btn.setText("Setup")
        self._settings_btn.clicked.connect(self._open_settings)
        self._settings_btn.hide()
        self._tools_btn = QtWidgets.QToolButton(self)
        self._tools_btn.setText("\u25b6")
        self._tools_btn.clicked.connect(self._toggle_tools)
        self._tools_btn.hide()
        self._collapse_btn = QtWidgets.QToolButton(self)
        self._collapse_btn.clicked.connect(self._collapse_coach)
        self._collapse_btn.hide()
        self._details_btn = QtWidgets.QToolButton(self)
        self._details_btn.setCheckable(True)
        self._details_btn.hide()

        self._status = QtWidgets.QLabel("No document yet")
        self._status.setObjectName("statusLine")
        self._status.setWordWrap(True)
        outer.addWidget(self._status)

        self._course_btn = QtWidgets.QPushButton("Courses")
        self._course_btn.setObjectName("courseButton")
        self._course_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._course_btn.setToolTip("Open the LearnCad courses")
        self._course_btn.clicked.connect(self._open_course)
        outer.addWidget(self._course_btn)
        self._update_course_button()

        answer_card = QtWidgets.QFrame()
        answer_card.setObjectName("coachAnswerCard")
        answer_layout = QtWidgets.QVBoxLayout(answer_card)
        answer_layout.setContentsMargins(13, 11, 13, 11)
        answer_layout.setSpacing(6)
        self._answer = QtWidgets.QTextBrowser()
        self._answer.setObjectName("coachAnswer")
        self._answer.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._answer.setOpenExternalLinks(False)
        self._answer.setMinimumHeight(0)
        self._answer.setMaximumHeight(170)
        answer_layout.addWidget(self._answer, 1)
        self._answer_card = answer_card
        answer_card.setVisible(False)

        self._guided_frame = QtWidgets.QFrame()
        self._guided_frame.setObjectName("guidedStep")
        guided_layout = QtWidgets.QVBoxLayout(self._guided_frame)
        guided_layout.setContentsMargins(10, 8, 10, 9)
        guided_layout.setSpacing(4)
        guided_head = QtWidgets.QHBoxLayout()
        guided_label = QtWidgets.QLabel("GUIDED WALKTHROUGH")
        guided_label.setObjectName("sectionLabel")
        self._guided_count = QtWidgets.QLabel("")
        self._guided_count.setObjectName("guidedCount")
        guided_head.addWidget(guided_label)
        guided_head.addStretch(1)
        guided_head.addWidget(self._guided_count)
        self._guided_title = QtWidgets.QLabel("")
        self._guided_title.setObjectName("guidedTitle")
        self._guided_text = QtWidgets.QLabel("")
        self._guided_text.setObjectName("guidedText")
        self._guided_text.setWordWrap(True)
        self._guided_text.setMinimumWidth(0)
        self._guided_text.setMaximumWidth(600)
        guided_buttons = QtWidgets.QHBoxLayout()
        guided_buttons.addStretch(1)
        self._guided_stop = QtWidgets.QToolButton()
        self._guided_stop.setObjectName("ghostButton")
        self._guided_stop.setText("Stop")
        self._guided_stop.clicked.connect(self._stop_walkthrough)
        self._guided_next = QtWidgets.QPushButton("Next")
        self._guided_next.setObjectName("primarySmall")
        self._guided_next.setCursor(QtCore.Qt.PointingHandCursor)
        self._guided_next.clicked.connect(self._walkthrough_next)
        guided_buttons.addWidget(self._guided_stop)
        guided_buttons.addWidget(self._guided_next)
        guided_layout.addLayout(guided_head)
        guided_layout.addWidget(self._guided_title)
        guided_layout.addWidget(self._guided_text)
        guided_layout.addLayout(guided_buttons)
        self._guided_frame.setVisible(False)
        outer.addWidget(self._guided_frame)

        self._next_frame = QtWidgets.QFrame()
        next_frame = self._next_frame
        next_frame.setObjectName("nextStep")
        next_layout = QtWidgets.QVBoxLayout(next_frame)
        next_layout.setContentsMargins(10, 8, 10, 9)
        next_layout.setSpacing(4)
        next_label = QtWidgets.QLabel("DO THIS NEXT")
        next_label.setObjectName("sectionLabel")
        self._next = QtWidgets.QLabel("Open a document and I'll start watching.")
        self._next.setObjectName("nextText")
        self._next.setWordWrap(True)
        self._guide_btn = QtWidgets.QPushButton("Guide me")
        self._guide_btn.setObjectName("guideButton")
        self._guide_btn.setMinimumHeight(36)
        self._guide_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._guide_btn.setToolTip("Open the workspace and dialog required for the next step")
        self._guide_btn.clicked.connect(self._guide)
        self._guide_btn.setEnabled(False)
        self._fix_btn = QtWidgets.QPushButton("Fix constraints for me")
        self._fix_btn.setObjectName("fixButton")
        self._fix_btn.setMinimumHeight(30)
        self._fix_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._fix_btn.setToolTip("Add the missing constraints automatically and lock the current shape")
        self._fix_btn.clicked.connect(self._fix_constraints)
        self._fix_btn.setVisible(False)
        next_layout.addWidget(next_label)
        next_layout.addWidget(self._next)
        next_layout.addWidget(self._guide_btn)
        next_layout.addWidget(self._fix_btn)
        outer.addWidget(next_frame)

        self._notes_label = QtWidgets.QLabel("MENTOR")
        self._notes_label.setObjectName("sectionLabel")
        outer.addWidget(self._notes_label)
        self._simple_notes = QtWidgets.QTextBrowser()
        self._simple_notes.setObjectName("notesView")
        self._simple_notes.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._simple_notes.setOpenExternalLinks(False)
        self._simple_notes.setMinimumHeight(0)
        self._simple_notes.setMaximumHeight(92)
        outer.addWidget(self._simple_notes)

        outer.addWidget(self._answer_card)
        outer.addStretch(1)

        input_row = QtWidgets.QHBoxLayout()
        input_row.setSpacing(8)
        self._goal_input = QtWidgets.QLineEdit(str(self._config.get("goal", "")))
        self._goal_input.setObjectName("goalInput")
        self._goal_input.setPlaceholderText("Ask LearnCad...")
        self._goal_input.setToolTip("LearnCad reads the live model and the current selection.")
        self._goal_input.setMinimumHeight(36)
        self._goal_input.returnPressed.connect(self._submit_input)
        self._ask_btn = QtWidgets.QPushButton("Ask")
        self._ask_btn.setObjectName("askButton")
        self._ask_btn.setMinimumHeight(36)
        self._ask_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._ask_btn.clicked.connect(self._ask)
        input_row.addWidget(self._goal_input, 1)
        input_row.addWidget(self._ask_btn)
        outer.addLayout(input_row)

        self._footer = QtWidgets.QLabel()
        self._footer.setObjectName("footerLabel")
        self._footer.setWordWrap(True)
        outer.addWidget(self._footer)

        self._advanced = QtWidgets.QWidget()
        advanced = QtWidgets.QVBoxLayout(self._advanced)
        advanced.setContentsMargins(0, 0, 0, 0)
        advanced.setSpacing(6)
        self._context = QtWidgets.QTextBrowser()
        self._context.setObjectName("contextView")
        self._context.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._context.setOpenExternalLinks(False)
        self._context.setMinimumHeight(86)
        self._context.setMaximumHeight(130)
        advanced.addWidget(self._context)
        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setObjectName("detailsTabs")
        self._tabs.setDocumentMode(True)
        self._plan = QtWidgets.QTextBrowser()
        self._plan.setObjectName("detailView")
        self._plan.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._plan.setOpenExternalLinks(False)
        self._activity = QtWidgets.QTextBrowser()
        self._activity.setObjectName("detailView")
        self._activity.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._activity.setOpenExternalLinks(False)
        self._activity.document().setMaximumBlockCount(400)
        self._review = QtWidgets.QTextBrowser()
        self._review.setObjectName("detailView")
        self._review.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._review.setOpenExternalLinks(False)
        self._review.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        self._tabs.addTab(self._plan, "Plan")
        self._tabs.addTab(self._activity, "Activity")
        self._tabs.addTab(self._review, "Review")
        advanced.addWidget(self._tabs, 1)
        self._advanced.setVisible(False)

        self._activity.append(
            '<div style="color: #888;">LearnCad is local-first. The coach never needs the network. '
            "AI chat is optional and uses the provider you choose in Setup.</div>"
        )
        self._render_footer()
        self._render_empty()

    # ------------------------------------------------------------ engine

    def _on_update(self, snapshot: Snapshot, analysis: Analysis, events: list) -> None:
        self._snapshot = snapshot
        self._analysis = analysis
        self._render()
        for event in events:
            self._append_activity(
                event.get("text", ""),
                event.get("severity", "info"),
                event.get("kind", "info"),
            )
        if self._walkthrough is not None and self._walkthrough_index < len(self._walkthrough_steps):
            step = self._walkthrough_steps[self._walkthrough_index]
            if step.wait_for_sketch and self._walkthrough_state() == "sketch":
                QtCore.QTimer.singleShot(250, self._advance_walkthrough)

    def _on_failed(self, message: str) -> None:
        self._append_activity(message, "warn", "error")

    def _save_goal(self) -> None:
        goal = self._goal_input.text().strip()
        if goal == str(self._config.get("goal", "")):
            return
        self._config["goal"] = goal
        settings.save(self._config)
        self._engine.set_goal(goal)
        if goal:
            self._set_answer(
                "LearnCad",
                f"Got it - I'll keep checking this model against: {goal}.",
            )
        self._append_activity(f"Goal set: {goal}" if goal else "Goal cleared.", "info", "info")

    def _studio(self) -> None:
        ok, message = branding.apply()
        self._append_activity(message, "info" if ok else "warn", "studio")

    def _render_preview(self) -> None:
        snapshot = self._snapshot
        has_solid = False
        if snapshot is not None and snapshot.doc is not None:
            has_solid = any(body.has_solid for body in snapshot.doc.bodies) or any(
                feature.volume > 0 for feature in snapshot.doc.features
            )
        if not has_solid:
            QtWidgets.QMessageBox.information(
                self,
                "No solid yet",
                "Create a closed solid first. LearnCad renders the finished body, not an unfinished sketch.",
            )
            return
        blender = render_bridge.find_blender(str(self._config.get("blender_path", "") or ""))
        if not blender:
            QtWidgets.QMessageBox.information(
                self,
                "Studio engine not found",
                "The studio engine is not configured. Reinstall LearnCad, or set the studio path in Setup.",
            )
            return
        self._render_btn.setEnabled(False)
        self._render_btn.setText("Rendering...")
        self._append_activity("Rendering a studio preview. This can take a moment.", "info", "render")
        worker = _RenderWorker(self._config, self)
        worker.done.connect(self._on_render_done)
        worker.failed.connect(self._on_render_failed)
        worker.finished.connect(worker.deleteLater)
        self._render_worker = worker
        worker.start()

    def _on_render_done(self, result) -> None:
        self._render_btn.setEnabled(True)
        self._render_btn.setText("Render")
        self._append_activity("Studio render saved: " + result.path, "good", "render")
        _RenderDialog(result, self).exec()

    def _on_render_failed(self, error: str) -> None:
        self._render_btn.setEnabled(True)
        self._render_btn.setText("Render")
        self._append_activity("Studio render failed.", "warn", "error")
        QtWidgets.QMessageBox.critical(self, "Render failed", error)

    def _guide(self) -> None:
        if self._snapshot is None or self._suggestion is None:
            return
        ok, message = actions.run_action(self._suggestion.id, self._snapshot)
        self._append_activity(message, "info" if ok else "warn", "guide")
        if ok:
            QtCore.QTimer.singleShot(250, self._engine.force)

    def _fix_constraints(self) -> None:
        if self._snapshot is None:
            return
        ok, message = actions.solve_constraints(self._snapshot)
        self._set_answer("LearnCad", message)
        self._append_activity(message, "good" if ok else "warn", "guide")
        if ok:
            QtCore.QTimer.singleShot(250, self._engine.force)

    def _force_review(self) -> None:
        self._engine.force()
        if self._snapshot is not None and self._analysis is not None:
            self._set_answer(
                "LearnCad", coach.review_report(self._snapshot, self._analysis)
            )
            self._append_activity("Full review refreshed.", "info", "review")

    def _toggle_details(self, checked: bool) -> None:
        self._advanced.setVisible(bool(checked))
        self._details_btn.setArrowType(QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)
        self._details_btn.setText("Hide details" if checked else "More details")

    def _show_details(self, visible: bool) -> None:
        self._details_btn.setChecked(bool(visible))
        self._toggle_details(bool(visible))

    # ------------------------------------------------------------ render

    def _render_empty(self) -> None:
        self._notes_label.setVisible(False)
        self._simple_notes.setVisible(False)
        self._simple_notes.setHtml("")
        self._fix_btn.setVisible(False)
        self._context.setHtml('<div style="color: #888;">No document yet.</div>')
        self._plan.setHtml('<div style="color: #888;">No plan yet.</div>')
        self._review.setPlainText("No model to review yet.")

    def _render(self) -> None:
        snapshot = self._snapshot
        analysis = self._analysis
        if snapshot is None or analysis is None:
            return
        doc = snapshot.doc

        self._suggestion = suggest.suggest_action(snapshot, analysis)
        suggestion_key = (
            self._suggestion.id if self._suggestion is not None else None,
            self._suggestion.label if self._suggestion is not None else "",
        )
        if suggestion_key != self._suggestion_cache:
            self._suggestion_cache = suggestion_key
            if self._suggestion is not None:
                self._guide_btn.setText(self._suggestion.label)
                self._guide_btn.setToolTip(self._suggestion.hint)
                self._guide_btn.setEnabled(True)
            else:
                self._guide_btn.setText("Guide me")
                self._guide_btn.setEnabled(False)

        word = _status_word(analysis.score, doc)
        under = bool(
            doc
            and any(
                not sketch.helper
                and sketch.geometry_count > 0
                and not sketch.fully_constrained
                for sketch in doc.sketches
            )
        )
        if doc is None:
            key = ("no-doc",)
            if key == self._render_cache:
                return
            self._render_cache = key
            self._score.setText(word)
            self._score.setToolTip(f"Model score: {analysis.score}/100")
            self._score.setStyleSheet(
                f"QLabel#statusPill {{ border-radius: 13px; padding: 7px 12px; font-weight: 700; "
                f"color: #080808; background: {_score_color(analysis.score)}; border: 1px solid rgba(255,255,255,0.18); }}"
            )
            self._fix_btn.setVisible(under)
            self._status.setText("No document yet. Start a new part when you are ready.")
            self._next.setText("Press Start a new part, then draw the outer profile.")
            self._render_empty()
            return

        status_text = self._status_line(snapshot)
        has_notes = bool(analysis.critical or analysis.warnings)
        notes_html = self._simple_notes_html(analysis) if has_notes else ""
        critical = bool(analysis.critical)
        key = (
            word,
            analysis.score,
            status_text,
            analysis.next_step,
            critical,
            has_notes,
            notes_html,
            under,
        )
        if key == self._render_cache:
            return
        self._render_cache = key

        self._score.setText(word)
        self._score.setToolTip(f"Model score: {analysis.score}/100")
        color = _score_color(analysis.score)
        self._score.setStyleSheet(
            f"QLabel#statusPill {{ border-radius: 13px; padding: 7px 12px; font-weight: 700; "
            f"color: #080808; background: {color}; border: 1px solid rgba(255,255,255,0.18); }}"
        )
        self._fix_btn.setVisible(under)

        self._status.setText(status_text)
        self._next.setText(analysis.next_step)
        self._next.setStyleSheet("font-weight: 600; color: #d64545;" if critical else "font-weight: 600;")

        color = SEVERITY_COLOR["critical"] if critical else "#ff7a18"
        frame = self.findChild(QtWidgets.QFrame, "nextStep")
        if frame is not None:
            frame.setStyleSheet(f"QFrame#nextStep {{ border-left: 3px solid {color}; }}")

        self._notes_label.setVisible(has_notes)
        self._simple_notes.setVisible(has_notes)
        self._simple_notes.setHtml(notes_html)
        self._context.setHtml(self._context_html(snapshot, analysis))
        self._plan.setHtml(self._plan_html(analysis))
        self._review.setPlainText(coach.review_report(snapshot, analysis))

    def _status_line(self, snapshot: Snapshot) -> str:
        doc = snapshot.doc
        if doc is None:
            return "No document yet"
        if doc.is_empty:
            return "Empty document"
        parts: list[str] = []
        if doc.bodies:
            body = doc.bodies[0]
            dims = body.bbox.dims
            if body.has_solid:
                parts.append(
                    f"{body.label or body.name}: {_fmt(dims[0])} x {_fmt(dims[1])} x {_fmt(dims[2])} mm"
                )
            else:
                parts.append(f"{body.label or body.name}: in progress")
        user_sketches = [sketch for sketch in doc.sketches if not sketch.helper]
        if user_sketches:
            sketch = user_sketches[-1]
            if sketch.is_empty:
                parts.append("empty sketch open")
            elif sketch.fully_constrained:
                parts.append("sketch constrained")
            else:
                parts.append(f"sketch: {sketch.dof} DoF left")
        return " | ".join(parts) if parts else (doc.label or doc.name)

    def _simple_notes_html(self, analysis: Analysis) -> str:
        entries: list[str] = []
        if analysis.critical:
            issue = analysis.critical[0]
            detail = f"<div style='color:#888;'>{_esc(issue.detail)}</div>" if issue.detail else ""
            fix = f"<div style='margin-top:2px;'><b>Do:</b> {_esc(issue.fix)}</div>" if issue.fix else ""
            entries.append(
                f"<div style='margin-bottom:7px;'><span style='color:{SEVERITY_COLOR['critical']}; "
                f"font-weight:700;'>Fix</span> <b>{_esc(issue.title)}</b>{detail}{fix}</div>"
            )
        if analysis.warnings:
            issue = analysis.warnings[0]
            detail = f"<div style='color:#888;'>{_esc(issue.detail)}</div>" if issue.detail else ""
            fix = f"<div style='margin-top:2px;'><b>Do:</b> {_esc(issue.fix)}</div>" if issue.fix else ""
            entries.append(
                f"<div style='margin-bottom:7px;'><span style='color:{SEVERITY_COLOR['warn']}; "
                f"font-weight:700;'>Watch</span> <b>{_esc(issue.title)}</b>{detail}{fix}</div>"
            )
        if analysis.praise:
            praise = analysis.praise[0]
            entries.append(
                f"<div style='margin-bottom:7px;'><span style='color:{SEVERITY_COLOR['good']}; "
                f"font-weight:700;'>Good</span> {_esc(praise.text)}</div>"
            )
        if not entries:
            entries.append(
                "<div>Nothing structural is wrong. Keep going, and I will flag the first thing that will cause trouble.</div>"
            )
        extra = max(0, len(analysis.issues) - (1 if analysis.critical else 0) - (1 if analysis.warnings else 0))
        if extra:
            entries.append(f"<div style='color:#888;'>+ {extra} more note(s) under More details.</div>")
        return "".join(entries)

    def _context_html(self, snapshot: Snapshot, analysis: Analysis) -> str:
        doc = snapshot.doc
        if doc is None:
            return '<div style="color: #888;">No document.</div>'
        rows: list[str] = []
        if snapshot.goal:
            rows.append(f"<b>Goal</b> | {_esc(snapshot.goal)}")
        rows.append(
            f"<b>Intent</b> | {_esc(analysis.intent.description)} "
            f"<span style='color:#888'>({analysis.intent.confidence:.0%})</span>"
        )
        if doc.edit_mode:
            rows.append(f"<b>Editing</b> | {_esc(doc.edit_mode)}")
        for body in doc.bodies[:2]:
            status = "valid solid" if body.shape_valid and body.has_solid else "in progress"
            if body.shape_valid and body.has_solid and not body.shape_closed:
                status = "open shell"
            rows.append(f"<b>{_esc(body.label or body.name)}</b> | {body.feature_count} feature(s) | {status}")
        for sketch in [item for item in doc.sketches if not item.helper][:2]:
            state = "fully constrained" if sketch.fully_constrained else f"{sketch.dof} DoF"
            profile = "closed" if sketch.is_closed else f"{sketch.open_wires} open"
            rows.append(f"<b>{_esc(sketch.label or sketch.name)}</b> | {state} | {profile}")
        if snapshot.warnings:
            rows.append(f"<span style='color:{SEVERITY_COLOR['warn']}'>{_esc(snapshot.warnings[0])}</span>")
        return "<br>".join(rows)

    def _plan_html(self, analysis: Analysis) -> str:
        if not analysis.plan:
            return '<div style="color: #888;">No plan yet.</div>'
        rows = [
            "<div style='margin-bottom:7px;'>"
            f"<span style='color:#ff7a18; font-weight:700;'>{index}.</span> {_esc(step)}"
            "</div>"
            for index, step in enumerate(analysis.plan, 1)
        ]
        return (
            "<div style='color:#888; font-size:10px; margin-bottom:6px;'>SUGGESTED SEQUENCE</div>"
            + "".join(rows)
        )

    def _render_footer(self) -> None:
        if settings.ai_ready(self._config):
            provider = settings.provider(self._config)
            if provider == "ollama":
                self._footer.setText("AI on · everything stays on this machine")
            else:
                self._footer.setText("AI on · question + compact model summary only")
        else:
            self._footer.setText("Local coach · free, no connection")

    def _append_activity(self, text: str, severity: str = "info", kind: str = "info") -> None:
        color = SEVERITY_COLOR.get(severity, "#888")
        prefix = {
            "issue": "!",
            "resolved": "OK",
            "good": "OK",
            "user": ">",
            "ai": "AI",
            "mentor": "LearnCad",
            "review": "R",
            "guide": ">",
            "studio": "S",
            "render": "R",
            "error": "!",
        }.get(kind, "-")
        stamp = time.strftime("%H:%M:%S")
        safe = _esc(text).replace("\n", "<br>")
        self._activity.append(
            f"<div style='margin-bottom:4px;'>"
            f"<span style='color:#888; font-size:9px;'>{stamp}</span> "
            f"<span style='color:{color}; font-weight:700;'>{prefix}</span> {safe}</div>"
        )

    # ---------------------------------------------------------------- ask

    def _submit_input(self) -> None:
        text = self._goal_input.text().strip()
        if not text:
            if str(self._config.get("goal", "") or "").strip():
                self._save_goal()
            return
        lowered = text.lower()
        looks_like_question = "?" in text or lowered.startswith(
            ("how", "what", "why", "where", "when", "who", "can", "could", "should",
             "is", "are", "do", "does", "will", "would", "tell me", "show me")
        ) or any(
            phrase in lowered
            for phrase in (
                "guide me",
                "help me",
                "i'm stuck",
                "im stuck",
                "what next",
                "what now",
                "what do i do",
                "show me where",
                "which control",
                "highlight",
            )
        )
        if looks_like_question:
            self._ask()
        else:
            self._save_goal()

    def _ask(self) -> None:
        question = self._goal_input.text().strip()
        if not question:
            return
        self._goal_input.clear()
        self._set_answer("You", question)
        self._append_activity(question, "info", "user")

        # Refresh once so the answer and the compact AI context see the
        # current selection as well as the current geometry.
        self._engine.force()
        snapshot = self._snapshot
        analysis = self._analysis
        if snapshot is None or analysis is None:
            self._append_activity("No document is open yet.", "warn", "error")
            return

        q_lower = question.lower()
        if "constraint" in q_lower and any(
            word in q_lower for word in ("solve", "fix", "resolve", "auto", "fully")
        ):
            ok, message = actions.solve_constraints(snapshot)
            self._set_answer("LearnCad", message)
            self._append_activity(message, "good" if ok else "warn", "guide")
            self._engine.force()
            return

        local_answer = coach.answer(
            question,
            snapshot,
            analysis,
            simple_mode=bool(self._config.get("simple_mode", True)),
        )
        if guide.looks_like_howto(question):
            specific = _hint_targets(question)
            walkthrough = guide.walkthrough_for(question)
            if walkthrough is not None and not (
                walkthrough.id == "constrain" and specific
            ):
                self._start_walkthrough(walkthrough)
            elif specific:
                # A concrete "how do I use Dimension/Arc/Radius/..." question:
                # glow that exact control instead of starting the generic tour.
                self._highlight_from_text(question)
            elif walkthrough is None:
                default = self._default_walkthrough()
                if default is not None:
                    self._start_walkthrough(default)
        if not settings.ai_ready(self._config):
            self._set_answer("LearnCad", local_answer)
            self._highlight_from_text(local_answer)
            self._history.append({"role": "user", "content": question})
            self._history.append({"role": "assistant", "content": local_answer})
            self._history = self._history[-8:]
            self._append_activity(local_answer, "info", "mentor")
            return

        self._ask_btn.setEnabled(False)
        self._ask_btn.setText("...")
        self._set_answer("LearnCad", "Thinking about your model...")
        self._append_activity("Thinking with the AI coach...", "info", "info")
        history = list(self._history[-8:])
        worker = _AskWorker(self._config, question, snapshot, analysis, self, history)
        worker.done.connect(lambda answer: self._on_ai_done(answer, local_answer, question))
        worker.failed.connect(lambda error: self._on_ai_failed(error, local_answer, question))
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_ai_done(self, answer: str, local_answer: str, question: str = "") -> None:
        self._ask_btn.setEnabled(True)
        self._ask_btn.setText("Ask")
        self._set_answer("LearnCad", answer)
        self._highlight_from_text(answer)
        self._append_activity(answer, "good", "ai")
        if question:
            self._history.append({"role": "user", "content": question})
            self._history.append({"role": "assistant", "content": answer})
            self._history = self._history[-8:]

    def _on_ai_failed(self, error: str, local_answer: str, question: str = "") -> None:
        self._ask_btn.setEnabled(True)
        self._ask_btn.setText("Ask")
        self._set_answer("LearnCad", local_answer)
        self._highlight_from_text(local_answer)
        self._append_activity(f"AI unavailable: {error}", "warn", "error")
        self._append_activity("Local mentor: " + local_answer, "info", "mentor")
        if question:
            self._history.append({"role": "user", "content": question})
            self._history.append({"role": "assistant", "content": local_answer})
            self._history = self._history[-8:]

    # ---------------------------------------------------- guided walkthrough

    def _main_window(self):
        try:
            import FreeCADGui as Gui

            return Gui.getMainWindow()
        except Exception:
            return self.window()

    def _walkthrough_state(self) -> str:
        snapshot = self._snapshot
        doc = snapshot.doc if snapshot is not None else None
        if doc is not None and doc.edit_mode:
            return "sketch"
        return "not_sketch"

    def _start_walkthrough(self, walkthrough) -> None:
        state = self._walkthrough_state()
        steps = []
        for step in walkthrough.steps:
            if not step.when:
                steps.append(step)
            elif step.when == "sketch" and state == "sketch":
                steps.append(step)
            elif step.when == "not_sketch" and state != "sketch":
                steps.append(step)
        if not steps:
            return
        self._stop_walkthrough(announce=False)
        self._walkthrough = walkthrough
        self._walkthrough_steps = steps
        self._walkthrough_index = 0
        self._target_clicked = False
        self._next_frame.setVisible(False)
        self._guided_frame.setVisible(True)
        self._guided_title.setText(walkthrough.title)
        self._append_activity("Guided walkthrough: " + walkthrough.title, "info", "guide")
        self._apply_walkthrough_step()

    def _default_walkthrough(self):
        """Pick a sensible walkthrough when the question has no keyword."""
        snapshot = self._snapshot
        doc = snapshot.doc if snapshot is not None else None
        if doc is not None and doc.edit_mode:
            active = None
            for sketch in doc.sketches:
                if doc.edit_mode in (sketch.name, sketch.label):
                    active = sketch
                    break
            if active is not None and active.geometry_count == 0:
                return guide.WALKTHROUGHS.get("rectangle")
            return guide.WALKTHROUGHS.get("constrain")
        body = doc.bodies[0] if doc is not None and doc.bodies else None
        if body is None or not body.has_solid:
            return guide.WALKTHROUGHS.get("rectangle")
        return guide.WALKTHROUGHS.get("pad")

    def _highlight_from_text(self, text: str) -> None:
        """Glow the first control an answer tells the user to use."""
        if self._walkthrough is not None:
            return
        for target in _hint_targets(text):
            widget = self._find_target(target)
            if widget is None:
                continue
            try:
                if not widget.isVisible():
                    continue
            except Exception:
                pass
            self._highlight(widget)
            self._clear_highlight_later(widget, 9000)
            return

    def _clear_highlight_later(self, widget, delay_ms: int = 9000) -> None:
        def clear():
            if self._highlighted is not None and self._highlighted[0] is widget:
                self._clear_highlight()

        try:
            QtCore.QTimer.singleShot(delay_ms, clear)
        except Exception:
            pass

    def _apply_walkthrough_step(self) -> None:
        self._clear_highlight()
        if self._walkthrough is None:
            return
        if self._walkthrough_index >= len(self._walkthrough_steps):
            self._stop_walkthrough(announce=False)
            return
        step = self._walkthrough_steps[self._walkthrough_index]
        total = len(self._walkthrough_steps)
        self._guided_count.setText(f"{self._walkthrough_index + 1} / {total}")
        self._guided_text.setText(step.text)
        self._guided_next.setText("Finish" if self._walkthrough_index == total - 1 else "Next")
        if not step.target:
            return
        widget = self._find_target(step.target)
        if widget is not None:
            try:
                visible = widget.isVisible()
            except Exception:
                visible = True
            if not visible:
                # The control exists but its toolbar is not on screen yet
                # (for example the sketch bar before entering the sketch).
                self._retry_visible(step.target, 0)
                return
            self._highlight(widget)
            if not step.wait_for_sketch:
                self._wire_target(widget)
        elif step.target.startswith("dialog:"):
            self._retry_dialog(step.target, 0)

    def _retry_visible(self, target: str, attempt: int) -> None:
        if self._walkthrough is None or self._walkthrough_index >= len(self._walkthrough_steps):
            return
        step = self._walkthrough_steps[self._walkthrough_index]
        if step.target != target:
            return
        widget = self._find_target(target)
        if widget is not None:
            try:
                visible = widget.isVisible()
            except Exception:
                visible = True
            if visible:
                self._highlight(widget)
                if not step.wait_for_sketch:
                    self._wire_target(widget)
                return
        if attempt < 12:
            QtCore.QTimer.singleShot(300, lambda: self._retry_visible(target, attempt + 1))

    def _find_target(self, target: str):
        if target.startswith("panel:"):
            mapping = {
                "primary": getattr(self, "_guide_btn", None),
                "course": getattr(self, "_course_btn", None),
                "studio": getattr(self, "_studio_btn", None),
                "render": getattr(self, "_render_btn", None),
                "setup": getattr(self, "_settings_btn", None),
                "more": getattr(self, "_details_btn", None),
                "ask": getattr(self, "_ask_btn", None),
            }
            return mapping.get(target.split(":", 1)[1])
        if target.startswith("dialog:"):
            return self._find_dialog_button(target.split(":", 1)[1])
        if ":" not in target:
            return None
        kind, name = target.split(":", 1)
        bar_name = {"main": "LearnCadSimpleBar", "sketch": "LearnCadSketchBar"}.get(kind)
        if bar_name is None:
            return None
        window = self._main_window()
        if window is None:
            return None
        bar = window.findChild(QtWidgets.QToolBar, bar_name)
        if bar is None:
            try:
                simple_mode._ensure_bars(window)
                bar = window.findChild(QtWidgets.QToolBar, bar_name)
            except Exception:
                bar = None
        if bar is None:
            return None
        aliases = {
            "horizontal": "horiz",
            "vertical": "vert",
            "dimension": "dim",
            "diameter": "dim",
        }
        wanted = name.replace("&", "").strip().lower()
        wanted = aliases.get(wanted, wanted)

        def norm(text: str) -> str:
            return str(text or "").replace("&", "").strip().lower()

        for action in bar.actions():
            if action.isSeparator():
                continue
            if norm(action.text()) == wanted:
                return bar.widgetForAction(action)
        # Some targets live inside the File/Model/More menus. Highlight the
        # menu button so the user can open it.
        for button in bar.findChildren(QtWidgets.QToolButton):
            menu = button.menu()
            if menu is None:
                continue
            for action in menu.actions():
                if norm(action.text()) == wanted:
                    return button
                submenu = action.menu()
                if submenu is not None:
                    for sub in submenu.actions():
                        if norm(sub.text()) == wanted:
                            return button
        try:
            menu = self._menu_btn.menu()
            if menu is not None:
                for action in menu.actions():
                    if norm(action.text()) == wanted:
                        return self._menu_btn
        except Exception:
            pass
        # Fall back to a contains match so labels like "Render studio" still
        # match a "render" hint.
        if wanted:
            for action in bar.actions():
                if action.isSeparator():
                    continue
                if wanted in norm(action.text()):
                    return bar.widgetForAction(action)
            for button in bar.findChildren(QtWidgets.QToolButton):
                menu = button.menu()
                if menu is None:
                    continue
                for action in menu.actions():
                    if wanted in norm(action.text()):
                        return button
                    submenu = action.menu()
                    if submenu is not None:
                        for sub in submenu.actions():
                            if wanted in norm(sub.text()):
                                return button
        return None

    def _find_dialog_button(self, name: str):
        window = self._main_window()
        if window is None:
            return None
        wanted = name.strip().lower()
        buttons = []
        for button in window.findChildren(QtWidgets.QPushButton):
            try:
                text = button.text().replace("&", "").strip().lower()
                if button.isVisible() and button.isEnabled() and text == wanted:
                    buttons.append(button)
            except Exception:
                pass
        return buttons[-1] if buttons else None

    def _retry_dialog(self, target: str, attempt: int) -> None:
        if self._walkthrough is None or self._walkthrough_index >= len(self._walkthrough_steps):
            return
        step = self._walkthrough_steps[self._walkthrough_index]
        if step.target != target:
            return
        widget = self._find_target(target)
        if widget is not None:
            self._highlight(widget)
            self._wire_target(widget)
            return
        if attempt < 8:
            QtCore.QTimer.singleShot(350, lambda: self._retry_dialog(target, attempt + 1))

    def _highlight(self, widget) -> None:
        if widget is None:
            return
        self._clear_highlight()
        try:
            old_style = widget.styleSheet()
        except Exception:
            old_style = ""
        self._highlighted = (widget, old_style)
        self._target_widget = widget
        self._pulse_on = True
        self._set_highlight_style()
        self._highlight_timer = QtCore.QTimer(self)
        self._highlight_timer.setInterval(600)
        self._highlight_timer.timeout.connect(self._pulse_highlight)
        self._highlight_timer.start()

    def _pulse_highlight(self) -> None:
        self._pulse_on = not self._pulse_on
        self._set_highlight_style()

    def _set_highlight_style(self) -> None:
        if self._highlighted is None:
            return
        widget = self._highlighted[0]
        bright = self._pulse_on
        try:
            if isinstance(widget, QtWidgets.QPushButton):
                border = "#ffb347" if bright else "#ff7a18"
                background = "#ffb347" if bright else "#ff7a18"
                widget.setStyleSheet(
                    "QPushButton { border: 3px solid %s; border-radius: 6px; background: %s; "
                    "color: #080808; font-weight: 700; padding: 5px 10px; }" % (border, background)
                )
            else:
                border = "#ffb347" if bright else "#ff7a18"
                background = "rgba(255,179,71,0.38)" if bright else "rgba(255,122,24,0.28)"
                widget.setStyleSheet(
                    "QToolButton { border: 2px solid %s; border-radius: 6px; background: %s; "
                    "color: #ffffff; font-weight: 700; padding: 3px 6px; }" % (border, background)
                )
        except Exception:
            pass

    def _clear_highlight(self) -> None:
        if self._highlight_timer is not None:
            try:
                self._highlight_timer.stop()
                self._highlight_timer.deleteLater()
            except Exception:
                pass
            self._highlight_timer = None
        if self._highlighted is not None:
            widget, old_style = self._highlighted
            try:
                widget.setStyleSheet(old_style)
            except Exception:
                pass
            self._highlighted = None
        self._target_widget = None

    def _wire_target(self, widget) -> None:
        if widget is None:
            return

        def handler(*_args):
            if self._walkthrough is None or self._target_widget is not widget:
                return
            if self._target_clicked:
                return
            self._target_clicked = True
            QtCore.QTimer.singleShot(450, self._advance_walkthrough)

        try:
            widget.clicked.connect(handler)
        except Exception:
            pass

    def _advance_walkthrough(self) -> None:
        if self._walkthrough is None:
            return
        self._target_clicked = False
        self._clear_highlight()
        self._walkthrough_index += 1
        if self._walkthrough_index >= len(self._walkthrough_steps):
            title = self._walkthrough.title
            self._finish_course_lesson()
            self._stop_walkthrough(announce=False)
            self._append_activity(
                f"Guided walkthrough finished: {title}. Nice work.", "good", "guide"
            )
            return
        self._apply_walkthrough_step()

    def _walkthrough_next(self, *_args) -> None:
        if self._walkthrough is not None:
            self._advance_walkthrough()

    def _stop_walkthrough(self, *_args, announce: bool = True) -> None:
        was_active = self._walkthrough is not None
        self._clear_highlight()
        self._walkthrough = None
        self._walkthrough_steps = []
        self._walkthrough_index = 0
        self._course_lesson = None
        self._target_clicked = False
        try:
            self._guided_frame.setVisible(False)
            self._next_frame.setVisible(True)
            self._guided_next.setText("Next")
            self._guided_count.setText("")
            self._guided_title.setText("")
        except Exception:
            pass
        if announce and was_active:
            self._append_activity("Guided walkthrough stopped.", "info", "guide")

    def _course_completed(self) -> set[str]:
        try:
            data = settings.load()
            return {str(item) for item in (data.get("course_progress") or [])}
        except Exception:
            return set()

    def _load_installed_courses(self) -> None:
        if not self._courses_dir:
            return
        try:
            course.register_installed(course_package.load_installed(self._courses_dir))
        except Exception:
            pass

    def _update_course_button(self) -> None:
        try:
            done = self._course_completed()
            lessons = course.all_lessons()
            total = len(lessons)
            count = sum(1 for lesson in lessons if lesson.id in done)
            if total and count >= total:
                self._course_btn.setText("Courses \u00b7 complete \u2713")
            else:
                self._course_btn.setText(f"Courses \u00b7 {count} / {total}")
        except Exception:
            pass

    def _open_course(self, *_args) -> None:
        try:
            self._load_installed_courses()
            dialog = _CourseDialog(
                course.all_courses(),
                self._course_completed(),
                self._start_lesson,
                self._import_course,
                self.window(),
            )
            dialog.exec()
        except Exception as exc:
            self._set_answer("LearnCad", "Could not open the course: " + str(exc))

    def _import_course(self, *_args) -> bool:
        if not self._courses_dir:
            self._set_answer("LearnCad", "The LearnCad courses folder is not available.")
            return False
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self.window(),
            "Import LearnCad course",
            "",
            "LearnCad course (*.learncad)",
        )
        if not path:
            return False
        try:
            manifest = course_package.install_package(path, self._courses_dir)
            self._load_installed_courses()
            self._update_course_button()
            title = str(manifest.get("title") or manifest.get("id") or "course")
            self._append_activity("Course imported: " + title, "good", "guide")
            self._set_answer("LearnCad", "Imported " + title + ". Choose a lesson to start.")
            QtCore.QTimer.singleShot(0, self._open_course)
            return True
        except course_package.CoursePackageError as exc:
            self._set_answer(
                "LearnCad",
                "Could not import that course:\n" + "\n".join(exc.errors[:8]),
            )
            return False
        except Exception as exc:
            self._set_answer("LearnCad", "Could not import that course: " + str(exc))
            return False

    def _start_lesson(self, lesson_id: str) -> None:
        lesson = course.lesson_by_id(lesson_id)
        if lesson is None:
            return
        self._start_walkthrough(lesson.walkthrough)
        if self._walkthrough is not None:
            self._course_lesson = lesson.id
            self._append_activity("Lesson started: " + lesson.title, "info", "guide")
            self._set_answer("LearnCad", lesson.summary)

    def _finish_course_lesson(self) -> None:
        lesson_id = getattr(self, "_course_lesson", None)
        if not lesson_id:
            return
        self._course_lesson = None
        lesson = course.lesson_by_id(lesson_id)
        try:
            data = settings.load()
            done = {str(item) for item in (data.get("course_progress") or [])}
            if lesson_id not in done:
                done.add(lesson_id)
                data["course_progress"] = sorted(done)
                settings.save(data)
        except Exception:
            pass
        self._update_course_button()
        if lesson is not None:
            self._append_activity(
                "Lesson complete: " + lesson.title + ". Open Courses to continue.",
                "good",
                "guide",
            )

    def _open_all_tools(self, *_args) -> None:
        try:
            from . import simple_mode

            simple_mode.show_all_tools(self)
        except Exception:
            pass

    def _toggle_tools(self, *_args) -> None:
        dock = getattr(self, "_inspector_dock", None)
        if dock is None:
            try:
                import FreeCADGui as Gui

                for child in Gui.getMainWindow().findChildren(QtWidgets.QDockWidget):
                    if child.windowTitle().strip().lower() in ("tools", "inspector"):
                        dock = child
                        self._inspector_dock = child
                        break
            except Exception:
                dock = None
        if dock is None:
            return
        try:
            dock.show()
            dock.raise_()
            self._tools_btn.setText("\u25c0")
            self._tools_btn.setToolTip("Show the TOOL tab")
        except Exception:
            pass

    def _collapse_coach(self, *_args) -> None:
        try:
            dock = self.window()
            if dock is not None:
                dock.hide()
        except Exception:
            pass

    # ----------------------------------------------------------- settings

    def _open_settings(self) -> None:
        dialog = _SettingsDialog(self._config, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self._config = dialog.config()
            settings.save(self._config)
            self._engine.set_interval(int(self._config.get("poll_ms", 900)))
            self._render_footer()
            try:
                branding.apply()
            except Exception:
                pass
            self._append_activity("Settings saved.", "info", "info")
            self._engine.force()


class _RenderDialog(QtWidgets.QDialog):
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self._result = result
        self.setWindowTitle("LearnCad Studio Render")
        self.resize(1000, 800)
        layout = QtWidgets.QVBoxLayout(self)
        path = result.path
        image = QtGui.QPixmap(path)
        label = QtWidgets.QLabel()
        label.setAlignment(QtCore.Qt.AlignCenter)
        if not image.isNull():
            label.setPixmap(image.scaled(940, 620, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        else:
            label.setText("The render file could not be loaded.")
        layout.addWidget(label, 1)

        info = QtWidgets.QLabel(os.path.basename(path))
        info.setStyleSheet("color: #888;")
        layout.addWidget(info)

        note = QtWidgets.QLabel(
            "The PNG is a still. Use Advanced scene to orbit, zoom, rotate, change lights or materials, and render again."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #aaa; font-size: 10px;")
        layout.addWidget(note)

        row = QtWidgets.QHBoxLayout()
        save = QtWidgets.QPushButton("Save image")
        save.clicked.connect(lambda: self._save(path))
        folder = QtWidgets.QPushButton("Open folder")
        folder.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.dirname(path))))
        row.addWidget(save)
        row.addWidget(folder)
        if getattr(result, "blend_path", "") and os.path.isfile(result.blend_path):
            blender = QtWidgets.QPushButton("Advanced scene")
            blender.clicked.connect(lambda: self._open_blender())
            row.addWidget(blender)
        row.addStretch(1)
        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)

    def _open_blender(self) -> None:
        try:
            QtCore.QProcess.startDetached(self._result.blender, [self._result.blend_path])
            self.accept()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Could not open the advanced editor", str(exc))

    def _save(self, path: str) -> None:
        target, _filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save render",
            os.path.join(os.path.expanduser("~"), os.path.basename(path)),
            "PNG image (*.png)",
        )
        if not target:
            return
        try:
            shutil.copyfile(path, target)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Save failed", str(exc))


class _ToolsPage(QtWidgets.QWidget):
    """The LearnCad TOOL tab: working model commands, no native task view."""

    def __init__(self, mentor, parent=None):
        super().__init__(parent)
        self._mentor = mentor
        self.setObjectName("LearnCadToolsPage")
        self.setStyleSheet(
            "QWidget#LearnCadToolsPage { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 #15100b, stop:0.55 #1d1108, stop:1 #2a1406); }"
            "QLabel { background: transparent; }"
            "QPushButton { background: #191919; color: #f5f5f5; border: 1px solid #333333;"
            " border-radius: 7px; padding: 10px 12px; text-align: left; font-weight: 600; }"
            "QPushButton:hover { background: #2a1a0c; border-color: #ff7a18; }"
            "QPushButton#primary { background: #ff7a18; color: #080808; border: none; }"
            "QPushButton#primary:hover { background: #ff9a3c; }"
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        title = QtWidgets.QLabel("TOOL")
        title.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #ff9a3c; letter-spacing: 2px;"
        )
        layout.addWidget(title)
        subtitle = QtWidgets.QLabel("Model commands for the active body")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #9aa7b4; font-size: 11px;")
        layout.addWidget(subtitle)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(8)
        buttons = [
            ("All tools", self._all_tools, False),
            ("Model tree", self._tree, False),
            ("Active body", self._activate_body, False),
            ("New body", self._new_body, False),
            ("New sketch", self._sketch, True),
            ("Done", self._done, False),
            ("Pad", self._pad, True),
            ("Pocket", self._pocket, False),
            ("Hole", self._hole, False),
            ("Shell", self._shell, False),
            ("Fillet", self._fillet, False),
            ("Auto-constrain", self._fix_constraints, False),
            ("Export", self._export, False),
            ("Render", self._render, False),
            ("Studio", self._studio, False),
            ("Setup", self._setup, False),
        ]
        for index, (label, handler, primary) in enumerate(buttons):
            button = QtWidgets.QPushButton(label)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            if primary:
                button.setObjectName("primary")
            button.clicked.connect(handler)
            grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(grid)
        layout.addStretch(1)
        hint = QtWidgets.QLabel(
            "Tip: use All tools or the Draw, Constrain, Model and View menus to reach the full tool set."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(hint)

    def _new_body(self) -> None:
        try:
            import FreeCAD as App
            import FreeCADGui as Gui

            if App.ActiveDocument is None:
                App.newDocument()
            Gui.activateWorkbench("PartDesignWorkbench")
            Gui.runCommand("PartDesign_Body")
        except Exception:
            pass

    def _sketch(self) -> None:
        try:
            from . import actions

            ok, message = actions.new_sketch(self._mentor._snapshot)
            if not ok:
                QtWidgets.QMessageBox.information(self, "Sketch", message)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Sketch", "Could not start a sketch: " + str(exc))

    def _all_tools(self) -> None:
        try:
            simple_mode.show_all_tools(self)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Tools", "Could not open the tool search: " + str(exc))

    def _tree(self) -> None:
        try:
            simple_mode.toggle_tree()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Model tree", "Could not show the model tree: " + str(exc))

    def _activate_body(self) -> None:
        self._action("activate_body")

    def _done(self) -> None:
        try:
            import FreeCADGui as Gui

            Gui.runCommand("Sketcher_LeaveSketch")
        except Exception:
            pass

    def _pad(self) -> None:
        show_pad_dialog(self)

    def _native(self, command: str) -> None:
        try:
            import FreeCADGui as Gui

            Gui.activateWorkbench("PartDesignWorkbench")
            Gui.runCommand(command)
            QtCore.QTimer.singleShot(350, self._raise_task)
        except Exception:
            pass

    def _raise_task(self) -> None:
        try:
            import FreeCADGui as Gui

            for dock in Gui.getMainWindow().findChildren(QtWidgets.QDockWidget):
                if dock.windowTitle().strip().lower() in ("task", "tasks"):
                    dock.show()
                    dock.raise_()
                    break
        except Exception:
            pass

    def _action(self, action_id: str) -> None:
        try:
            from . import actions

            ok, message = actions.run_action(action_id, self._mentor._snapshot)
            if not ok:
                QtWidgets.QMessageBox.information(self, "LearnCad", message)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "LearnCad", "Could not run that action: " + str(exc))

    def _pocket(self) -> None:
        self._action("open_pocket")

    def _hole(self) -> None:
        self._action("open_hole")

    def _shell(self) -> None:
        self._action("open_thickness")

    def _fillet(self) -> None:
        self._action("open_fillet")

    def _fix_constraints(self) -> None:
        try:
            from . import actions

            ok, message = actions.solve_constraints(self._mentor._snapshot)
            self._mentor._set_answer("LearnCad", message)
            self._mentor._engine.force()
        except Exception as exc:
            self._mentor._set_answer("LearnCad", "Could not fix constraints: " + str(exc))

    def _export(self) -> None:
        self._action("open_export")

    def _render(self) -> None:
        self._mentor._render_preview()

    def _studio(self) -> None:
        self._mentor._studio()

    def _setup(self) -> None:
        self._mentor._open_settings()


class _PadDialog(QtWidgets.QDialog):
    def __init__(self, sketch_label: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pad")
        self.setMinimumWidth(380)
        layout = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "Set the thickness for '" + sketch_label + "'. The pad grows from the sketch plane."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QtWidgets.QFormLayout()
        self._length = QtWidgets.QDoubleSpinBox()
        self._length.setRange(0.1, 1000.0)
        self._length.setDecimals(2)
        self._length.setSingleStep(1.0)
        self._length.setValue(10.0)
        self._length.setSuffix(" mm")
        form.addRow("Length", self._length)
        self._direction = QtWidgets.QComboBox()
        self._direction.addItem("One side", "one")
        self._direction.addItem("Reverse", "reverse")
        self._direction.addItem("Symmetric", "both")
        form.addRow("Direction", self._direction)
        layout.addLayout(form)
        note = QtWidgets.QLabel("The length is the solid thickness, not the sketch size.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(note)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[float, str]:
        return float(self._length.value()), str(self._direction.currentData() or "one")


def _sketch_geometry_count(sketch) -> int:
    try:
        return int(getattr(sketch, "GeometryCount", 0) or 0)
    except Exception:
        return 0


def _sketch_has_curve(sketch) -> bool:
    try:
        for geometry in sketch.Geometry:
            if hasattr(geometry, "Radius"):
                return True
    except Exception:
        pass
    return False


def _last_sketch(sketches):
    items = [
        obj for obj in sketches
        if str(getattr(obj, "TypeId", "")) == "Sketcher::SketchObject"
    ]
    for sketch in reversed(items):
        if _sketch_geometry_count(sketch) > 0:
            return sketch
    return items[-1] if items else None


def show_pad_dialog(parent=None) -> bool:
    """Pad the sketch the user just worked on, not an arbitrary first sketch."""
    import FreeCAD as App
    import FreeCADGui as Gui

    from . import actions

    doc = App.ActiveDocument
    if doc is None:
        QtWidgets.QMessageBox.information(parent, "Pad", "Create a sketch first.")
        return False

    gdoc = None
    try:
        gdoc = Gui.activeDocument()
    except Exception:
        pass

    sketch = None
    try:
        edit = gdoc.getInEdit() if gdoc is not None else None
        if isinstance(edit, (tuple, list)):
            edit = edit[0] if edit else None
        obj = getattr(edit, "Object", edit)
        if obj is not None and str(getattr(obj, "TypeId", "")) == "Sketcher::SketchObject":
            sketch = obj
    except Exception:
        pass

    if sketch is None:
        try:
            for selection in Gui.Selection.getSelectionEx():
                obj = getattr(selection, "Object", None)
                if obj is not None and str(getattr(obj, "TypeId", "")) == "Sketcher::SketchObject":
                    sketch = obj
                    break
        except Exception:
            pass

    if sketch is None:
        body = actions._selected_body() or actions._active_body() or actions._first_body(doc)
        if body is not None:
            sketch = _last_sketch(list(getattr(body, "Group", []) or []))

    if sketch is None:
        sketch = _last_sketch(list(doc.Objects))

    if sketch is None:
        QtWidgets.QMessageBox.information(
            parent, "Pad", "Finish a sketch first, then click Pad."
        )
        return False

    if _sketch_geometry_count(sketch) <= 0:
        QtWidgets.QMessageBox.information(
            parent,
            "Pad",
            "The sketch is empty. Draw a closed profile first, then click Pad.",
        )
        return False

    body = actions._parent_body(sketch)
    if body is None:
        QtWidgets.QMessageBox.information(
            parent, "Pad", "The sketch must be inside a Body before it can be padded."
        )
        return False

    label = str(getattr(sketch, "Label", None) or getattr(sketch, "Name", "Sketch"))
    dialog = _PadDialog(label, parent)
    if dialog.exec() != QtWidgets.QDialog.Accepted:
        return False
    length, direction = dialog.values()

    try:
        if gdoc is not None and gdoc.getInEdit() is not None:
            Gui.runCommand("Sketcher_LeaveSketch")
    except Exception:
        pass

    try:
        sketch.solve()
    except Exception:
        pass
    try:
        doc.recompute()
    except Exception as exc:
        QtWidgets.QMessageBox.warning(
            parent, "Pad failed", "Could not update the sketch before padding.\n\n" + str(exc)
        )
        return False

    shape = getattr(sketch, "Shape", None)
    if shape is None or shape.isNull():
        QtWidgets.QMessageBox.information(
            parent,
            "Pad",
            f"'{label}' has no profile yet. Draw a closed shape, then click Pad.",
        )
        return False

    try:
        wires = list(shape.Wires)
    except Exception:
        wires = []
    if not wires:
        QtWidgets.QMessageBox.information(
            parent,
            "Pad",
            f"'{label}' has no closed profile. Close the sketch outline first.",
        )
        return False
    try:
        open_wires = [wire for wire in wires if not wire.isClosed()]
    except Exception:
        open_wires = []
    if open_wires:
        QtWidgets.QMessageBox.information(
            parent,
            "Pad",
            f"'{label}' still has an open profile. Close the gap with a Coincident constraint, then try again.",
        )
        return False

    try:
        actions._activate_body(body)
    except Exception:
        pass

    previous_tip = getattr(body, "Tip", None)
    pad = None
    try:
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = sketch
        try:
            pad.Type = "Length"
        except Exception:
            pass
        pad.Length = length
        try:
            pad.Reversed = direction == "reverse"
        except Exception:
            pass
        if direction == "both":
            try:
                pad.SideType = "Symmetric"
            except Exception:
                try:
                    pad.Midplane = True
                except Exception:
                    pass
        else:
            try:
                pad.SideType = "One side"
            except Exception:
                pass
        try:
            body.Tip = pad
        except Exception:
            pass
        doc.recompute()

        state = " ".join(str(value) for value in (getattr(pad, "State", []) or [])).lower()
        pad_shape = getattr(pad, "Shape", None)
        volume = 0.0
        try:
            if pad_shape is not None and not pad_shape.isNull():
                volume = float(pad_shape.Volume)
        except Exception:
            volume = 0.0
        if "invalid" in state or "error" in state or volume <= 0:
            raise RuntimeError("The pad produced an empty or invalid solid.")
    except Exception as exc:
        if pad is not None:
            try:
                if previous_tip is not None:
                    body.Tip = previous_tip
            except Exception:
                pass
            try:
                doc.removeObject(pad.Name)
                doc.recompute()
            except Exception:
                pass
        QtWidgets.QMessageBox.warning(
            parent,
            "Pad failed",
            "Could not create the pad from this sketch. Check that it has one closed profile.\n\n"
            + str(exc),
        )
        return False

    try:
        gdoc = Gui.activeDocument()
        if gdoc is not None and gdoc.activeView() is not None:
            gdoc.activeView().fitAll()
    except Exception:
        pass
    return True


class _FeatureDialog(QtWidgets.QDialog):
    """Small native LearnCad dialog, so we never need the engine task bar."""

    def __init__(self, title: str, intro: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(intro)
        label.setWordWrap(True)
        layout.addWidget(label)
        self._form = QtWidgets.QFormLayout()
        layout.addLayout(self._form)
        self._widgets: dict[str, Any] = {}
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_float(self, key: str, label: str, default: float, minimum: float = 0.1,
                  maximum: float = 1000.0, suffix: str = " mm") -> None:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(1.0)
        spin.setValue(default)
        spin.setSuffix(suffix)
        self._form.addRow(label, spin)
        self._widgets[key] = spin

    def add_bool(self, key: str, label: str, default: bool = False) -> None:
        check = QtWidgets.QCheckBox(label)
        check.setChecked(default)
        self._form.addRow("", check)
        self._widgets[key] = check

    def values(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, widget in self._widgets.items():
            if isinstance(widget, QtWidgets.QCheckBox):
                result[key] = widget.isChecked()
            else:
                result[key] = float(widget.value())
        return result


def _selected_face(target: str = "Face"):
    try:
        import FreeCADGui as Gui

        for selection in Gui.Selection.getSelectionEx():
            obj = getattr(selection, "Object", None)
            names = getattr(selection, "SubElementNames", None) or []
            for name in names:
                if str(name).startswith(target):
                    return obj, str(name)
    except Exception:
        pass
    return None, ""


def _selected_edges():
    try:
        import FreeCADGui as Gui

        for selection in Gui.Selection.getSelectionEx():
            obj = getattr(selection, "Object", None)
            names = [
                str(name)
                for name in (getattr(selection, "SubElementNames", None) or [])
                if str(name).startswith("Edge")
            ]
            if names:
                return obj, names
    except Exception:
        pass
    return None, []


def _selected_faces():
    try:
        import FreeCADGui as Gui

        for selection in Gui.Selection.getSelectionEx():
            obj = getattr(selection, "Object", None)
            names = [
                str(name)
                for name in (getattr(selection, "SubElementNames", None) or [])
                if str(name).startswith("Face")
            ]
            if names:
                return obj, names
    except Exception:
        pass
    return None, []


def _top_face_name(feature) -> str:
    try:
        faces = list(feature.Shape.Faces)
    except Exception:
        return ""
    best_name = ""
    best = (-2.0, -1e9)
    for index, face in enumerate(faces):
        try:
            score = (face.normalAt(0, 0).z, face.BoundBox.ZMax)
        except Exception:
            continue
        if score > best:
            best = score
            best_name = f"Face{index + 1}"
    return best_name


def _feature_ready(feature) -> tuple[bool, str]:
    state = " ".join(str(value) for value in (getattr(feature, "State", []) or [])).lower()
    shape = getattr(feature, "Shape", None)
    volume = 0.0
    try:
        if shape is not None and not shape.isNull():
            volume = float(shape.Volume)
    except Exception:
        volume = 0.0
    if "invalid" in state or "error" in state or volume <= 0:
        return False, "The feature produced an empty or invalid solid."
    return True, ""


def _shape_volume(obj) -> float:
    try:
        shape = getattr(obj, "Shape", None)
        if shape is not None and not shape.isNull():
            return float(shape.Volume)
    except Exception:
        pass
    return 0.0


def _rollback_feature(body, previous_tip, feature) -> None:
    try:
        import FreeCAD as App

        if previous_tip is not None:
            body.Tip = previous_tip
        if feature is not None:
            App.ActiveDocument.removeObject(feature.Name)
        App.ActiveDocument.recompute()
    except Exception:
        pass


def _finish_feature(
    parent,
    body,
    previous_tip,
    feature,
    title: str,
    require_change: bool = False,
    failure_hint: str = "",
) -> bool:
    previous_volume = _shape_volume(previous_tip) if previous_tip is not None else 0.0
    try:
        body.Tip = feature
    except Exception:
        pass
    try:
        import FreeCAD as App

        App.ActiveDocument.recompute()
    except Exception:
        pass
    ok, message = _feature_ready(feature)
    if ok and require_change:
        volume = _shape_volume(feature)
        if previous_volume > 0 and previous_volume - volume <= max(0.5, previous_volume * 0.0005):
            ok = False
            message = "The feature did not remove any material on this shape."
    if not ok:
        _rollback_feature(body, previous_tip, feature)
        if failure_hint:
            message = message + "\n\n" + failure_hint
        QtWidgets.QMessageBox.warning(parent, title + " failed", message)
        return False
    try:
        import FreeCADGui as Gui

        gdoc = Gui.activeDocument()
        if gdoc is not None and gdoc.activeView() is not None:
            gdoc.activeView().fitAll()
    except Exception:
        pass
    return True


def _leave_sketch() -> None:
    try:
        import FreeCADGui as Gui

        gdoc = Gui.activeDocument()
        if gdoc is not None and gdoc.getInEdit() is not None:
            Gui.runCommand("Sketcher_LeaveSketch")
    except Exception:
        pass


def show_pocket_dialog(parent=None) -> bool:
    import FreeCAD as App
    import FreeCADGui as Gui

    from . import actions

    doc = App.ActiveDocument
    if doc is None:
        QtWidgets.QMessageBox.information(parent, "Pocket", "Create a body and sketch first.")
        return False
    body = actions._selected_body() or actions._active_body() or actions._first_body(doc)
    if body is None:
        QtWidgets.QMessageBox.information(parent, "Pocket", "No Body found.")
        return False
    sketch = None
    try:
        edit = Gui.activeDocument().getInEdit() if Gui.activeDocument() else None
        if isinstance(edit, (tuple, list)):
            edit = edit[0] if edit else None
        obj = getattr(edit, "Object", edit)
        if obj is not None and str(getattr(obj, "TypeId", "")) == "Sketcher::SketchObject":
            sketch = obj
    except Exception:
        pass
    if sketch is None:
        for selection in Gui.Selection.getSelectionEx():
            obj = getattr(selection, "Object", None)
            if obj is not None and str(getattr(obj, "TypeId", "")) == "Sketcher::SketchObject":
                sketch = obj
                break
    if sketch is None:
        sketch = _last_sketch(list(getattr(body, "Group", []) or []))
    if sketch is None:
        QtWidgets.QMessageBox.information(parent, "Pocket", "Select or draw the pocket sketch first.")
        return False
    label = str(getattr(sketch, "Label", None) or getattr(sketch, "Name", "Sketch"))
    dialog = _FeatureDialog(
        "Pocket",
        "Cut '" + label + "' into the current solid. The pocket goes into the material.",
        parent,
    )
    dialog.add_float("length", "Depth", 5.0)
    dialog.add_bool("through", "Through all", False)
    if dialog.exec() != QtWidgets.QDialog.Accepted:
        return False
    values = dialog.values()
    _leave_sketch()
    try:
        doc.recompute()
    except Exception:
        pass
    previous_tip = getattr(body, "Tip", None)
    pocket = None
    try:
        actions._activate_body(body)
        pocket = body.newObject("PartDesign::Pocket", "Pocket")
        pocket.Profile = sketch
        if values.get("through"):
            try:
                pocket.Type = "ThroughAll"
            except Exception:
                pocket.Type = "Length"
                pocket.Length = 1000.0
        else:
            pocket.Type = "Length"
            pocket.Length = float(values.get("length", 5.0))
        return _finish_feature(parent, body, previous_tip, pocket, "Pocket", require_change=True)
    except Exception as exc:
        if pocket is not None:
            try:
                if previous_tip is not None:
                    body.Tip = previous_tip
                doc.removeObject(pocket.Name)
                doc.recompute()
            except Exception:
                pass
        QtWidgets.QMessageBox.warning(parent, "Pocket failed", str(exc))
        return False


def show_hole_dialog(parent=None) -> bool:
    import FreeCAD as App
    import FreeCADGui as Gui
    import Part

    from . import actions

    doc = App.ActiveDocument
    if doc is None:
        QtWidgets.QMessageBox.information(parent, "Hole", "Create a body and sketch first.")
        return False
    body = actions._selected_body() or actions._active_body() or actions._first_body(doc)
    if body is None:
        QtWidgets.QMessageBox.information(parent, "Hole", "No Body found.")
        return False
    tip = getattr(body, "Tip", None)
    if tip is None:
        QtWidgets.QMessageBox.information(parent, "Hole", "Create a solid first, then add a hole.")
        return False

    profile = None
    try:
        edit = Gui.activeDocument().getInEdit() if Gui.activeDocument() else None
        if isinstance(edit, (tuple, list)):
            edit = edit[0] if edit else None
        obj = getattr(edit, "Object", edit)
        if obj is not None and str(getattr(obj, "TypeId", "")) == "Sketcher::SketchObject":
            profile = obj
    except Exception:
        pass
    if profile is None:
        for selection in Gui.Selection.getSelectionEx():
            obj = getattr(selection, "Object", None)
            if obj is not None and str(getattr(obj, "TypeId", "")) == "Sketcher::SketchObject":
                profile = obj
                break
    # Only a sketch of circles/arcs can drive a Hole. A selected rectangle
    # sketch would otherwise make the feature fail with "Finding axis failed".
    if profile is not None and not _sketch_has_curve(profile):
        profile = None

    target, face_name = _selected_face()
    if target is None or face_name == "":
        face_name = _top_face_name(tip)
        target = tip
    if target is None or face_name == "":
        QtWidgets.QMessageBox.information(
            parent, "Hole", "Select the face where the hole should start."
        )
        return False

    dialog = _FeatureDialog(
        "Hole",
        "Add a vertical hole. With a sketch of circles selected that sketch is used; "
        "otherwise I place one circle at the center of the selected face.",
        parent,
    )
    dialog.add_float("diameter", "Diameter", 3.4)
    dialog.add_float("depth", "Depth", 10.0)
    dialog.add_bool("through", "Through all", False)
    if dialog.exec() != QtWidgets.QDialog.Accepted:
        return False
    values = dialog.values()
    diameter = float(values.get("diameter", 3.4))
    _leave_sketch()

    previous_tip = getattr(body, "Tip", None)
    created_sketch = None
    hole = None
    try:
        actions._activate_body(body)
        if profile is None:
            created_sketch = body.newObject("Sketcher::SketchObject", "HoleSketch")
            created_sketch.AttachmentSupport = [(target, face_name)]
            created_sketch.MapMode = "FlatFace"
            try:
                created_sketch.addProperty(
                    "App::PropertyBool",
                    "LearnCadHelper",
                    "Base",
                    "Internal LearnCad helper geometry",
                )
                created_sketch.LearnCadHelper = True
            except Exception:
                pass
            doc.recompute()
            face = target.Shape.getElement(face_name)
            local = created_sketch.Placement.inverse().multVec(face.CenterOfMass)
            created_sketch.addGeometry(
                Part.Circle(local, App.Vector(0, 0, 1), diameter / 2.0), False
            )
            doc.recompute()
            try:
                created_sketch.ViewObject.Visibility = False
            except Exception:
                pass
            profile = created_sketch
        hole = body.newObject("PartDesign::Hole", "Hole")
        hole.Profile = profile
        hole.Diameter = diameter
        if values.get("through"):
            hole.DepthType = "ThroughAll"
        else:
            hole.DepthType = "Dimension"
            hole.Depth = float(values.get("depth", 10.0))
        return _finish_feature(parent, body, previous_tip, hole, "Hole", require_change=True)
    except Exception as exc:
        if hole is not None:
            try:
                if previous_tip is not None:
                    body.Tip = previous_tip
                doc.removeObject(hole.Name)
            except Exception:
                pass
        if created_sketch is not None:
            try:
                doc.removeObject(created_sketch.Name)
            except Exception:
                pass
        try:
            doc.recompute()
        except Exception:
            pass
        QtWidgets.QMessageBox.warning(parent, "Hole failed", str(exc))
        return False


def show_fillet_dialog(parent=None) -> bool:
    import FreeCAD as App

    from . import actions

    doc = App.ActiveDocument
    if doc is None:
        QtWidgets.QMessageBox.information(parent, "Fillet", "Create a solid first.")
        return False
    body = actions._selected_body() or actions._active_body() or actions._first_body(doc)
    if body is None:
        QtWidgets.QMessageBox.information(parent, "Fillet", "No Body found.")
        return False
    target, edges = _selected_edges()
    if target is None or not edges:
        QtWidgets.QMessageBox.information(
            parent,
            "Fillet",
            "Select one or more edges in the 3D view, then click Fillet.",
        )
        return False
    if str(getattr(target, "TypeId", "")) == "PartDesign::Body":
        target = getattr(body, "Tip", None)
    if target is None:
        QtWidgets.QMessageBox.information(parent, "Fillet", "No solid to round yet.")
        return False

    dialog = _FeatureDialog("Fillet", "Round the selected edges. Keep it small.", parent)
    dialog.add_float("radius", "Radius", 1.0, minimum=0.05, maximum=100.0)
    if dialog.exec() != QtWidgets.QDialog.Accepted:
        return False
    radius = float(dialog.values().get("radius", 1.0))

    previous_tip = getattr(body, "Tip", None)
    feature = None
    try:
        actions._activate_body(body)
        feature = body.newObject("PartDesign::Fillet", "Fillet")
        feature.Base = (target, edges)
        feature.Radius = radius
        return _finish_feature(parent, body, previous_tip, feature, "Fillet")
    except Exception as exc:
        if feature is not None:
            try:
                if previous_tip is not None:
                    body.Tip = previous_tip
                doc.removeObject(feature.Name)
                doc.recompute()
            except Exception:
                pass
        QtWidgets.QMessageBox.warning(parent, "Fillet failed", str(exc))
        return False


def show_thickness_dialog(parent=None) -> bool:
    import FreeCAD as App

    from . import actions

    doc = App.ActiveDocument
    if doc is None:
        QtWidgets.QMessageBox.information(parent, "Shell", "Create a solid first.")
        return False
    body = actions._selected_body() or actions._active_body() or actions._first_body(doc)
    if body is None:
        QtWidgets.QMessageBox.information(parent, "Shell", "No Body found.")
        return False
    target, faces = _selected_faces()
    if target is None or not faces:
        tip = getattr(body, "Tip", None)
        face = _top_face_name(tip) if tip is not None else ""
        if not face:
            QtWidgets.QMessageBox.information(
                parent, "Shell", "Select the face(s) to open, then click Shell."
            )
            return False
        target = tip
        faces = [face]
    if str(getattr(target, "TypeId", "")) == "PartDesign::Body":
        target = getattr(body, "Tip", None)
    if target is None:
        QtWidgets.QMessageBox.information(parent, "Shell", "No solid to hollow yet.")
        return False

    dialog = _FeatureDialog(
        "Shell", "Hollow the solid and remove the selected face(s).", parent
    )
    dialog.add_float("value", "Wall thickness", 1.5, minimum=0.1, maximum=100.0)
    if dialog.exec() != QtWidgets.QDialog.Accepted:
        return False
    value = float(dialog.values().get("value", 1.5))

    previous_tip = getattr(body, "Tip", None)
    feature = None
    try:
        actions._activate_body(body)
        feature = body.newObject("PartDesign::Thickness", "Thickness")
        feature.Base = (target, faces)
        feature.Value = value
        try:
            feature.Mode = "Skin"
        except Exception:
            pass
        return _finish_feature(
            parent,
            body,
            previous_tip,
            feature,
            "Shell",
            require_change=True,
            failure_hint="Shell works best before Fillet or Pocket. Try a different face, or undo the last feature and shell first.",
        )
    except Exception as exc:
        if feature is not None:
            try:
                if previous_tip is not None:
                    body.Tip = previous_tip
                doc.removeObject(feature.Name)
                doc.recompute()
            except Exception:
                pass
        QtWidgets.QMessageBox.warning(parent, "Shell failed", str(exc))
        return False


class _SettingsDialog(QtWidgets.QDialog):
    def __init__(self, config: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("LearnCad settings")
        self.setMinimumWidth(520)
        self._config = dict(config)
        self._test_worker: Optional[_TestWorker] = None

        layout = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "The coach always runs locally and stays free. AI explanations are optional. "
            "Use DeepSeek V4.1 Flash, your own OpenAI-compatible key, a free local Ollama "
            "model, or a LearnCad subscription."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._simple = QtWidgets.QCheckBox("Simple mode: hide advanced toolbars and menus")
        self._simple.setChecked(bool(self._config.get("simple_mode", True)))
        layout.addWidget(self._simple)

        ai_box = QtWidgets.QGroupBox("AI coach")
        ai_form = QtWidgets.QFormLayout(ai_box)
        self._ai_status = QtWidgets.QLabel("")
        self._ai_status.setWordWrap(True)
        ai_form.addRow("Status", self._ai_status)

        self._enabled = QtWidgets.QCheckBox("Enable AI explanations")
        self._enabled.setChecked(bool(self._config.get("ai_enabled")))
        ai_form.addRow("AI", self._enabled)

        self._provider = QtWidgets.QComboBox()
        self._provider.addItem("LearnCad cloud (subscription)", "learncad")
        self._provider.addItem("DeepSeek (V4.1 Flash)", "deepseek")
        self._provider.addItem("OpenAI or compatible API key", "openai")
        self._provider.addItem("Ollama on this computer (local, free)", "ollama")
        self._provider.addItem("Custom OpenAI-compatible server", "custom")
        current_provider = settings.provider(self._config)
        provider_index = self._provider.findData(current_provider)
        if provider_index >= 0:
            self._provider.setCurrentIndex(provider_index)
        self._provider.currentIndexChanged.connect(self._provider_changed)
        ai_form.addRow("Provider", self._provider)

        self._consent = QtWidgets.QCheckBox(
            "I agree to send a compact model summary and my question to the selected provider"
        )
        self._consent.setChecked(bool(self._config.get("consent_ai")))
        ai_form.addRow("Privacy", self._consent)
        layout.addWidget(ai_box)

        self._direct_box = QtWidgets.QGroupBox("API connection")
        direct_form = QtWidgets.QFormLayout(self._direct_box)
        self._direct_base = QtWidgets.QLineEdit(str(self._config.get("direct_base_url", "")))
        self._direct_base.setPlaceholderText("https://api.openai.com/v1")
        direct_form.addRow("Base URL", self._direct_base)
        self._direct_model = QtWidgets.QLineEdit(str(self._config.get("direct_model", "")))
        self._direct_model.setPlaceholderText("gpt-4o-mini")
        direct_form.addRow("Model", self._direct_model)
        self._direct_key = QtWidgets.QLineEdit()
        self._direct_key.setEchoMode(QtWidgets.QLineEdit.Password)
        saved_key = settings.get_direct_api_key(self._config)
        self._direct_key.setPlaceholderText(
            "Saved key is kept. Type a new key to replace it." if saved_key else "sk-... (not needed for Ollama)"
        )
        direct_form.addRow("API key", self._direct_key)
        layout.addWidget(self._direct_box)

        self._sub_box = QtWidgets.QGroupBox("LearnCad cloud subscription")
        sub_form = QtWidgets.QFormLayout(self._sub_box)
        self._base = QtWidgets.QLineEdit(str(self._config.get("cloud_base_url", "")))
        self._base.setPlaceholderText("https://ai.your-server.example")
        sub_form.addRow("Server", self._base)

        self._subscribe_url = QtWidgets.QLineEdit(str(self._config.get("subscribe_url", "")))
        self._subscribe_url.setPlaceholderText("https://your-server.example/subscribe")
        sub_form.addRow("Subscribe page", self._subscribe_url)

        self._email = QtWidgets.QLineEdit(str(self._config.get("license_email", "")))
        self._email.setPlaceholderText("you@example.com")
        sub_form.addRow("Email", self._email)

        self._license = QtWidgets.QLineEdit()
        self._license.setEchoMode(QtWidgets.QLineEdit.Password)
        self._license.setPlaceholderText("License code from your email")
        sub_form.addRow("License code", self._license)

        ai_buttons = QtWidgets.QHBoxLayout()
        self._activate = QtWidgets.QPushButton("Activate")
        self._activate.clicked.connect(self._activate_license)
        self._subscribe = QtWidgets.QPushButton("Subscribe")
        self._subscribe.clicked.connect(self._open_subscribe)
        ai_buttons.addWidget(self._activate)
        ai_buttons.addWidget(self._subscribe)
        ai_buttons.addStretch(1)
        sub_form.addRow("", ai_buttons)
        layout.addWidget(self._sub_box)

        ai_hint = QtWidgets.QLabel(
            "Your key is stored encrypted on this computer (Windows DPAPI) and is only sent to the provider you choose. "
            "Ollama runs locally, so nothing leaves your machine."
        )
        ai_hint.setWordWrap(True)
        ai_hint.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(ai_hint)
        self._direct_box.setVisible(current_provider != "learncad")
        self._sub_box.setVisible(current_provider == "learncad")

        form = QtWidgets.QFormLayout()
        self._poll = QtWidgets.QSpinBox()
        self._poll.setRange(300, 5000)
        self._poll.setSingleStep(100)
        self._poll.setSuffix(" ms")
        self._poll.setValue(int(self._config.get("poll_ms", 900)))
        form.addRow("Live polling", self._poll)

        self._navigation = QtWidgets.QComboBox()
        self._navigation.addItem("LearnCad (left + right drag pans)", "Gui::OpenInventorNavigationStyle")
        self._navigation.addItem("SolidWorks (middle rotate, Ctrl+middle pans)", "Gui::SolidWorksNavigationStyle")
        self._navigation.addItem("Blender (middle rotate, Shift+middle pans)", "Gui::BlenderNavigationStyle")
        self._navigation.addItem("Inventor (middle pans, Shift+middle rotates)", "Gui::InventorNavigationStyle")
        current_navigation = str(self._config.get("navigation_style", "Gui::OpenInventorNavigationStyle"))
        nav_index = self._navigation.findData(current_navigation)
        if nav_index >= 0:
            self._navigation.setCurrentIndex(nav_index)
        form.addRow("Mouse navigation", self._navigation)

        blender_row = QtWidgets.QHBoxLayout()
        self._blender = QtWidgets.QLineEdit(str(self._config.get("blender_path", "")))
        self._blender.setPlaceholderText("Auto-detect, or choose the studio engine")
        blender_browse = QtWidgets.QPushButton("Browse")
        blender_browse.clicked.connect(self._browse_blender)
        blender_row.addWidget(self._blender, 1)
        blender_row.addWidget(blender_browse)
        form.addRow("Studio engine (advanced)", blender_row)

        self._render_material = QtWidgets.QComboBox()
        self._render_material.addItem("Aluminum (brushed)", "aluminum")
        self._render_material.addItem("Plastic (satin orange)", "plastic")
        self._render_material.addItem("Rubber (matte black)", "rubber")
        current_material = str(self._config.get("render_material", "aluminum"))
        index = self._render_material.findData(current_material)
        if index >= 0:
            self._render_material.setCurrentIndex(index)
        form.addRow("Studio material", self._render_material)

        self._render_engine = QtWidgets.QComboBox()
        self._render_engine.addItem("Cycles (quality reflections)", "CYCLES")
        self._render_engine.addItem("EEVEE (faster)", "EEVEE")
        current_engine = str(self._config.get("render_engine", "CYCLES"))
        index = self._render_engine.findData(current_engine)
        if index >= 0:
            self._render_engine.setCurrentIndex(index)
        form.addRow("Render engine", self._render_engine)

        resolution = self._config.get("render_resolution", [1200, 800])
        try:
            render_width = int(resolution[0])
            render_height = int(resolution[1])
        except Exception:
            render_width, render_height = 1200, 800

        size_row = QtWidgets.QHBoxLayout()
        self._render_width = QtWidgets.QSpinBox()
        self._render_width.setRange(400, 4000)
        self._render_width.setSingleStep(100)
        self._render_width.setSuffix(" px")
        self._render_width.setValue(render_width)
        self._render_height = QtWidgets.QSpinBox()
        self._render_height.setRange(400, 4000)
        self._render_height.setSingleStep(100)
        self._render_height.setSuffix(" px")
        self._render_height.setValue(render_height)
        size_row.addWidget(self._render_width)
        size_row.addWidget(QtWidgets.QLabel("x"))
        size_row.addWidget(self._render_height)
        size_row.addStretch(1)
        form.addRow("Render size", size_row)

        self._render_samples = QtWidgets.QSpinBox()
        self._render_samples.setRange(8, 512)
        self._render_samples.setSingleStep(8)
        self._render_samples.setValue(int(self._config.get("render_samples", 64)))
        form.addRow("Render samples", self._render_samples)

        layout.addLayout(form)
        note = QtWidgets.QLabel("Cycles + 64 samples is a good default. Lower samples for speed; raise them for cleaner metal reflections.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(note)

        storage = QtWidgets.QLabel(f"Secret storage: {secret_store.storage_description()}")
        storage.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(storage)

        test_row = QtWidgets.QHBoxLayout()
        self._test = QtWidgets.QPushButton("Test AI connection")
        self._test.clicked.connect(self._test_connection)
        self._test_status = QtWidgets.QLabel("")
        self._test_status.setWordWrap(True)
        test_row.addWidget(self._test)
        test_row.addWidget(self._test_status, 1)
        layout.addLayout(test_row)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_ai_status()

    def _provider_changed(self, *_args) -> None:
        provider = self._provider.currentData() or "learncad"
        if provider != "learncad":
            default_base, default_model = settings.PROVIDER_DEFAULTS.get(provider, ("", ""))
            known_bases = {value[0] for value in settings.PROVIDER_DEFAULTS.values() if value[0]}
            known_models = {value[1] for value in settings.PROVIDER_DEFAULTS.values() if value[1]}
            base = self._direct_base.text().strip()
            if not base or base in known_bases:
                self._direct_base.setText(default_base)
            model = self._direct_model.text().strip()
            if not model or model in known_models:
                self._direct_model.setText(default_model)
            self._direct_key.setEnabled(provider != "ollama")
        self._direct_box.setVisible(provider != "learncad")
        self._sub_box.setVisible(provider == "learncad")
        self._update_ai_status()

    def _update_ai_status(self) -> None:
        provider = self._provider.currentData() or "learncad"
        if provider != "learncad":
            if settings.direct_ready(self._pending_config()):
                text = "Ready to use " + str(self._direct_model.text().strip()) + "."
                color = SEVERITY_COLOR["good"]
            else:
                text = "Add the base URL, model, and API key (Ollama needs no key)."
                color = SEVERITY_COLOR["warn"]
            self._ai_status.setText(text)
            self._ai_status.setStyleSheet(f"color: {color};")
            return
        token = settings.get_license_token(self._config)
        expires = settings.license_expires_at(self._config)
        if not token:
            text = "No subscription activated."
            color = SEVERITY_COLOR["warn"]
        elif expires is not None and expires <= datetime.now(timezone.utc):
            text = "Subscription expired."
            color = SEVERITY_COLOR["critical"]
        elif expires is not None:
            text = "Active until " + expires.astimezone().strftime("%Y-%m-%d %H:%M")
            color = SEVERITY_COLOR["good"]
        else:
            text = "Subscription active."
            color = SEVERITY_COLOR["good"]
        self._ai_status.setText(text)
        self._ai_status.setStyleSheet(f"color: {color};")

    def _activate_license(self) -> None:
        data = self._pending_config()
        code = self._license.text().strip() or settings.get_license_code(self._config)
        if not data.get("cloud_base_url"):
            self._test_status.setText("Set the AI server URL first.")
            self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['warn']};")
            return
        if not data.get("license_email"):
            self._test_status.setText("Enter the email used for the subscription.")
            self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['warn']};")
            return
        if not code:
            self._test_status.setText("Enter the license code from your confirmation email.")
            self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['warn']};")
            return
        device = settings.device_id(data)
        self._activate.setEnabled(False)
        self._test_status.setText("Activating...")
        self._test_status.setStyleSheet("color: #888;")
        worker = _ActivateWorker(
            data.get("cloud_base_url", ""),
            data.get("license_email", ""),
            code,
            device,
            self,
        )
        worker.done.connect(lambda result: self._on_activate_done(result, data, code, device))
        worker.failed.connect(self._on_activate_failed)
        worker.finished.connect(worker.deleteLater)
        self._activate_worker = worker
        worker.start()

    def _on_activate_done(self, result, data: dict[str, Any], code: str, device: str) -> None:
        self._activate.setEnabled(True)
        token = str(result.get("token", "") or "")
        if not token:
            self._on_activate_failed("The server did not return an access token.")
            return
        self._config = dict(data)
        self._config["device_id"] = device
        self._config["license_email"] = str(data.get("license_email", ""))
        settings.set_license_code(self._config, code)
        settings.set_license_token(self._config, token)
        self._config["license_expires"] = str(result.get("expires_at", "") or "")
        self._config["ai_provider"] = "learncad"
        self._license.clear()
        self._enabled.setChecked(True)
        index = self._provider.findData("learncad")
        if index >= 0:
            self._provider.setCurrentIndex(index)
        try:
            settings.save(self._config)
        except Exception:
            pass
        self._provider_changed()
        self._test_status.setText("Activated. Tick Privacy, then Save.")
        self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['good']};")

    def _on_activate_failed(self, message: str) -> None:
        self._activate.setEnabled(True)
        self._test_status.setText(message)
        self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['warn']};")

    def _open_subscribe(self) -> None:
        url = (self._subscribe_url.text().strip() or self._base.text().strip().rstrip("/") + "/subscribe")
        if not url or url == "/subscribe":
            self._test_status.setText("Set the Subscribe page URL first.")
            self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['warn']};")
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def _pending_config(self) -> dict[str, Any]:
        data = dict(self._config)
        data["ai_enabled"] = self._enabled.isChecked()
        data["consent_ai"] = self._consent.isChecked()
        data["ai_provider"] = self._provider.currentData() or "learncad"
        data["cloud_base_url"] = self._base.text().strip()
        data["subscribe_url"] = self._subscribe_url.text().strip()
        data["license_email"] = self._email.text().strip()
        data["direct_base_url"] = self._direct_base.text().strip()
        data["direct_model"] = self._direct_model.text().strip()
        if self._direct_key.text().strip():
            settings.set_direct_api_key(data, self._direct_key.text().strip())
        if self._license.text().strip():
            settings.set_license_code(data, self._license.text().strip())
        settings.device_id(data)
        for legacy in ("api_key_enc", "base_url", "model"):
            data.pop(legacy, None)
        data["poll_ms"] = int(self._poll.value())
        data["blender_path"] = self._blender.text().strip()
        data["render_material"] = self._render_material.currentData() or "aluminum"
        data["render_engine"] = self._render_engine.currentData() or "CYCLES"
        data["render_resolution"] = [int(self._render_width.value()), int(self._render_height.value())]
        data["render_samples"] = int(self._render_samples.value())
        data["simple_mode"] = self._simple.isChecked()
        data["navigation_style"] = self._navigation.currentData() or "Gui::OpenInventorNavigationStyle"
        return data

    def _browse_blender(self) -> None:
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Choose the studio engine",
            self._blender.text() or "C:\\Program Files",
            "Executables (*.exe)",
        )
        if path:
            self._blender.setText(path)

    def _test_connection(self) -> None:
        data = self._pending_config()
        provider = settings.provider(data)
        if provider == "learncad":
            if not data.get("cloud_base_url"):
                self._test_status.setText("Set the AI server URL first.")
                self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['warn']};")
                return
            if not settings.get_license_token(data):
                self._test_status.setText("Activate a subscription first.")
                self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['warn']};")
                return
        else:
            if not data.get("direct_base_url"):
                self._test_status.setText("Set the provider base URL first.")
                self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['warn']};")
                return
            if not data.get("direct_model"):
                self._test_status.setText("Set the provider model first.")
                self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['warn']};")
                return
            if provider in ("openai", "deepseek", "custom") and not settings.get_direct_api_key(data):
                self._test_status.setText("Add the provider API key first.")
                self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['warn']};")
                return
        self._test.setEnabled(False)
        self._test_status.setText("Testing connection...")
        self._test_status.setStyleSheet("color: #888;")
        worker = _TestWorker(data, self)
        worker.done.connect(self._on_test_done)
        worker.finished.connect(worker.deleteLater)
        self._test_worker = worker
        worker.start()

    def _on_test_done(self, ok: bool, message: str) -> None:
        self._test.setEnabled(True)
        self._test_status.setText(message)
        self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['good'] if ok else SEVERITY_COLOR['warn']};")

    def _save(self) -> None:
        data = self._pending_config()
        if data["ai_enabled"] and not data["consent_ai"]:
            QtWidgets.QMessageBox.warning(
                self,
                "Consent required",
                "Tick the privacy note before enabling AI explanations.",
            )
            return
        if data["ai_enabled"] and not settings.ai_ready(data):
            if settings.provider(data) == "learncad":
                message = (
                    "Activate a LearnCad subscription with your email and license code, "
                    "or choose another AI provider. The local coach stays free."
                )
            else:
                message = (
                    "Complete the API connection: base URL, model, and API key "
                    "(Ollama needs no key). The local coach stays free."
                )
            QtWidgets.QMessageBox.warning(self, "AI not ready", message)
            return
        self._config = data
        try:
            if data.get("simple_mode", True):
                simple_mode.apply()
            else:
                simple_mode.restore()
        except Exception:
            pass
        self.accept()

    def config(self) -> dict[str, Any]:
        return dict(self._config)


def _size_dock(main_window, dock, final: bool = False) -> None:
    """Keep the coach compact beside the viewport."""
    try:
        dock.setMinimumWidth(320)
        dock.setMaximumWidth(380)
    except Exception:
        pass
    try:
        main_window.resizeDocks([dock], [340], QtCore.Qt.Horizontal)
    except Exception:
        pass



_TASK_DOCK_ALLOWED = False


def allow_task_dock() -> None:
    """Allow the native task dock for an advanced tool the user asked for."""
    global _TASK_DOCK_ALLOWED
    _TASK_DOCK_ALLOWED = True


def _task_is_active() -> bool:
    """True only while a real engine task dialog is open."""
    try:
        import FreeCADGui as Gui

        return bool(Gui.Control.activeDialog())
    except Exception:
        return False


def force_ui_idle() -> bool:
    """False while the user is dragging, orbiting or a modal dialog is open."""
    try:
        if QtWidgets.QApplication.mouseButtons() != QtCore.Qt.NoButton:
            return False
        if blocking_modal() is not None:
            return False
    except Exception:
        pass
    return True


def _install_task_watch(main_window, task_dock, coach_dock) -> None:
    """Keep the engine task bar completely out of the way.

    LearnCad now owns sketch creation, dimensions, Pad, Pocket, Hole, Fillet
    and Shell, so the native dock is never needed. It is forced to the left
    and hidden on a fast timer in case the engine re-shows it.
    """

    def sync() -> None:
        global _TASK_DOCK_ALLOWED
        try:
            if not force_ui_idle():
                return
        except Exception:
            pass
        try:
            if not settings.simple_mode_enabled():
                return
        except Exception:
            pass
        active = _task_is_active()
        if not active:
            _TASK_DOCK_ALLOWED = False
        if _TASK_DOCK_ALLOWED and active:
            try:
                if main_window.dockWidgetArea(task_dock) == QtCore.Qt.NoDockWidgetArea:
                    main_window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, task_dock)
                task_dock.show()
                task_dock.raise_()
            except Exception:
                pass
            return
        # Hide only. Detaching and re-adding the dock on every tick makes it
        # jump between sides, which looked like the task bar "popping up".
        try:
            if task_dock.isVisible():
                task_dock.hide()
        except Exception:
            pass

    try:
        timer = QtCore.QTimer(task_dock)
        timer.setInterval(250)
        timer.timeout.connect(sync)
        timer.start()
        task_dock._learncad_watch = timer
    except Exception:
        pass
    QtCore.QTimer.singleShot(200, sync)


def show_panel() -> QtWidgets.QDockWidget:
    global _DOCK, _PANEL
    import FreeCADGui as Gui

    main_window = Gui.getMainWindow()
    created = _DOCK is None or _PANEL is None
    if created:
        _PANEL = MentorPanel(main_window)
        dock = QtWidgets.QDockWidget("Mentor", main_window)
        dock.setObjectName("CADetMentorDock")
        try:
            icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "icons", "learncad.svg")
            dock.setWindowIcon(QtGui.QIcon(icon))
        except Exception:
            pass
        empty_title = QtWidgets.QWidget()
        empty_title.setFixedHeight(0)
        dock.setTitleBarWidget(empty_title)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidget(_PANEL)
        dock.setWidget(scroll)
        dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        dock.visibilityChanged.connect(_on_visibility)
        main_window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
        dock.setMinimumWidth(320)
        dock.setMaximumWidth(380)
        _DOCK = dock

        # One left dock only. The engine's empty Task panel is kept hidden;
        # the real constraint panel appears only while a sketch or feature
        # task is active, tabbed with the coach.
        try:
            for other in main_window.findChildren(QtWidgets.QDockWidget):
                if other is dock:
                    continue
                if other.windowTitle().strip().lower() in ("tasks", "task", "inspector", "tool"):
                    other.setWindowTitle("Constraints")
                    other.setFloating(False)
                    empty = QtWidgets.QWidget()
                    empty.setFixedHeight(0)
                    other.setTitleBarWidget(empty)
                    main_window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, other)
                    other.hide()
                    _PANEL._task_dock = other
                    _install_task_watch(main_window, other, dock)
                    break
        except Exception:
            pass

        dock.show()
        dock.raise_()
        try:
            main_window.setTabPosition(
                QtCore.Qt.LeftDockWidgetArea, QtWidgets.QTabWidget.North
            )
        except Exception:
            pass

    _DOCK.show()
    _DOCK.raise_()
    try:
        for sub in main_window.findChildren(QtWidgets.QMdiSubWindow):
            sub.setMinimumSize(0, 0)
        central = main_window.centralWidget()
        if central is not None:
            central.setMinimumSize(0, 0)
            for child in central.findChildren(QtWidgets.QWidget):
                child.setMinimumSize(0, 0)
        for view in main_window.findChildren(QtWidgets.QWidget):
            if view.metaObject().className() in ("Gui::View3DInventor", "Gui::View3DInventorViewer"):
                view.setMinimumSize(0, 0)
                view.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        main_window.setMinimumSize(0, 0)
        main_window.showMaximized()
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            main_window.resize(area.width(), area.height())
        main_window.raise_()
    except Exception:
        pass
    if created:
        for delay in (0, 300, 1000, 2500, 5000):
            QtCore.QTimer.singleShot(
                delay,
                lambda m=main_window, d=_DOCK, last=(delay == 5000): _size_dock(m, d, last),
            )
    _PANEL._engine.start()
    return _DOCK


def _on_visibility(visible: bool) -> None:
    if _PANEL is None:
        return
    if visible:
        _PANEL._engine.start()
    else:
        _PANEL._engine.stop()


def toggle_panel() -> None:
    global _DOCK
    if _DOCK is not None and _DOCK.isVisible():
        _DOCK.hide()
        return
    show_panel()
