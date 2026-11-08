# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""The simple CADet panel.

Default view: what you are making, the one next step, a big Guide Me button,
and the top mentor notes. Context, plan, activity, review and AI live behind
"More details". The engine is unchanged.
"""

from __future__ import annotations

import html
import os
import shutil
import time
from datetime import datetime, timezone
from typing import Any, Optional

from .compat import QtCore, QtGui, QtWidgets

from . import actions, ai_client, branding, cloud_ai, coach, guide, render_bridge, secret_store, settings, simple_mode, studio, suggest
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


class MentorPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = settings.load()
        self._snapshot: Optional[Snapshot] = None
        self._analysis: Optional[Analysis] = None
        self._worker: Optional[_AskWorker] = None
        self._test_worker: Optional[_TestWorker] = None
        self._activate_worker: Optional[_ActivateWorker] = None
        self._suggestion = None
        self._walkthrough = None
        self._walkthrough_steps: list = []
        self._walkthrough_index = 0
        self._target_widget = None
        self._target_clicked = False
        self._highlighted = None
        self._highlight_timer = None
        self._pulse_on = False
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
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 10)
        outer.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("LearnCad")
        font = title.font()
        font.setPointSize(font.pointSize() + 5)
        font.setBold(True)
        title.setFont(font)
        header.addWidget(title)
        header.addStretch(1)

        self._score = QtWidgets.QLabel("Ready")
        self._score.setAlignment(QtCore.Qt.AlignCenter)
        self._score.setMinimumWidth(86)
        self._score.setStyleSheet(
            "QLabel { border-radius: 10px; padding: 6px 10px; font-weight: 700; color: white; background: #888; }"
        )
        header.addWidget(self._score)

        self._menu_btn = QtWidgets.QToolButton()
        self._menu_btn.setText("\u22ef")
        self._menu_btn.setToolTip("LearnCad options")
        self._menu_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(self._menu_btn)
        menu.addAction("Details", lambda: self._show_details(not self._advanced.isVisible()))
        menu.addAction("Tools panel", self._toggle_tools)
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
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: #888; font-size: 10px;")
        outer.addWidget(self._status)

        self._answer = QtWidgets.QTextBrowser()
        self._answer.setOpenExternalLinks(False)
        self._answer.setMinimumHeight(90)
        self._answer.setMaximumHeight(240)
        self._answer.setStyleSheet(
            "QTextBrowser { border: 1px solid palette(mid); border-radius: 8px; padding: 8px; }"
        )
        outer.addWidget(self._answer, 1)

        self._guided_frame = QtWidgets.QFrame()
        self._guided_frame.setObjectName("guidedStep")
        guided_layout = QtWidgets.QVBoxLayout(self._guided_frame)
        guided_layout.setContentsMargins(10, 8, 10, 9)
        guided_layout.setSpacing(4)
        guided_head = QtWidgets.QHBoxLayout()
        guided_label = QtWidgets.QLabel("GUIDED WALKTHROUGH")
        guided_label.setStyleSheet(
            "font-size: 9px; font-weight: 700; color: #ff9a3c; letter-spacing: 1px;"
        )
        self._guided_count = QtWidgets.QLabel("")
        self._guided_count.setStyleSheet("color: #ff9a3c; font-size: 10px; font-weight: 700;")
        guided_head.addWidget(guided_label)
        guided_head.addStretch(1)
        guided_head.addWidget(self._guided_count)
        self._guided_title = QtWidgets.QLabel("")
        self._guided_title.setStyleSheet("font-weight: 700; font-size: 11px;")
        self._guided_text = QtWidgets.QLabel("")
        self._guided_text.setWordWrap(True)
        self._guided_text.setMinimumWidth(0)
        self._guided_text.setMaximumWidth(600)
        self._guided_text.setStyleSheet("font-weight: 600;")
        guided_buttons = QtWidgets.QHBoxLayout()
        guided_buttons.addStretch(1)
        self._guided_stop = QtWidgets.QToolButton()
        self._guided_stop.setText("Stop")
        self._guided_stop.clicked.connect(self._stop_walkthrough)
        self._guided_next = QtWidgets.QPushButton("Next")
        self._guided_next.setCursor(QtCore.Qt.PointingHandCursor)
        self._guided_next.setStyleSheet(
            "QPushButton { background: #ff7a18; color: #080808; border: none; padding: 6px 14px; "
            "border-radius: 5px; font-weight: 700; } QPushButton:hover { background: #ff9a3c; }"
        )
        self._guided_next.clicked.connect(self._walkthrough_next)
        guided_buttons.addWidget(self._guided_stop)
        guided_buttons.addWidget(self._guided_next)
        guided_layout.addLayout(guided_head)
        guided_layout.addWidget(self._guided_title)
        guided_layout.addWidget(self._guided_text)
        guided_layout.addLayout(guided_buttons)
        self._guided_frame.setStyleSheet(
            "QFrame#guidedStep { border-left: 4px solid #ff7a18; background: #1a120a; "
            "border-radius: 6px; }"
        )
        self._guided_frame.setVisible(False)
        outer.addWidget(self._guided_frame)

        self._next_frame = QtWidgets.QFrame()
        next_frame = self._next_frame
        next_frame.setObjectName("nextStep")
        next_layout = QtWidgets.QVBoxLayout(next_frame)
        next_layout.setContentsMargins(10, 8, 10, 9)
        next_layout.setSpacing(4)
        next_label = QtWidgets.QLabel("DO THIS NEXT")
        next_label.setStyleSheet("font-size: 9px; font-weight: 700; color: #888; letter-spacing: 1px;")
        self._next = QtWidgets.QLabel("Open a document and I'll start watching.")
        self._next.setWordWrap(True)
        self._next.setStyleSheet("font-weight: 600;")
        self._guide_btn = QtWidgets.QPushButton("Guide me")
        self._guide_btn.setMinimumHeight(34)
        self._guide_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._guide_btn.setToolTip("Open the workbench and dialog required for the next step")
        self._guide_btn.clicked.connect(self._guide)
        self._guide_btn.setStyleSheet(
            "QPushButton { background: #ff7a18; color: #080808; border: none; padding: 7px 12px; "
            "border-radius: 5px; font-weight: 700; } "
            "QPushButton:hover { background: #ff9a3c; } "
            "QPushButton:disabled { background: #777; color: #ddd; }"
        )
        self._guide_btn.setEnabled(False)
        next_layout.addWidget(next_label)
        next_layout.addWidget(self._next)
        next_layout.addWidget(self._guide_btn)
        next_frame.setStyleSheet(
            "QFrame#nextStep { border-left: 3px solid #ff7a18; background: palette(alternate-base); border-radius: 5px; }"
        )
        outer.addWidget(next_frame)

        self._notes_label = QtWidgets.QLabel("HEADS-UP")
        self._notes_label.setStyleSheet("font-size: 9px; font-weight: 700; color: #888; letter-spacing: 1px;")
        outer.addWidget(self._notes_label)
        self._simple_notes = QtWidgets.QTextBrowser()
        self._simple_notes.setOpenExternalLinks(False)
        self._simple_notes.setMinimumHeight(60)
        self._simple_notes.setMaximumHeight(110)
        self._simple_notes.setStyleSheet(
            "QTextBrowser { border: 1px solid palette(mid); border-radius: 6px; padding: 7px; }"
        )
        outer.addWidget(self._simple_notes)

        input_row = QtWidgets.QHBoxLayout()
        self._goal_input = QtWidgets.QLineEdit(str(self._config.get("goal", "")))
        self._goal_input.setPlaceholderText("Ask anything, or tell me what you're making...")
        self._goal_input.setToolTip("LearnCad reads the live model and the current selection.")
        self._goal_input.setMinimumHeight(34)
        self._goal_input.returnPressed.connect(self._submit_input)
        self._ask_btn = QtWidgets.QPushButton("Send")
        self._ask_btn.setMinimumHeight(34)
        self._ask_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._ask_btn.setStyleSheet(
            "QPushButton { background: #ff7a18; color: #080808; border: none; padding: 6px 16px; "
            "border-radius: 6px; font-weight: 700; } QPushButton:hover { background: #ff9a3c; } "
            "QPushButton:disabled { background: #777; color: #ddd; }"
        )
        self._ask_btn.clicked.connect(self._ask)
        input_row.addWidget(self._goal_input, 1)
        input_row.addWidget(self._ask_btn)
        outer.addLayout(input_row)

        self._footer = QtWidgets.QLabel()
        self._footer.setWordWrap(True)
        self._footer.setStyleSheet("color: #888; font-size: 10px;")
        outer.addWidget(self._footer)

        self._advanced = QtWidgets.QWidget()
        advanced = QtWidgets.QVBoxLayout(self._advanced)
        advanced.setContentsMargins(0, 0, 0, 0)
        advanced.setSpacing(6)
        self._context = QtWidgets.QTextBrowser()
        self._context.setOpenExternalLinks(False)
        self._context.setMinimumHeight(86)
        self._context.setMaximumHeight(120)
        self._context.setStyleSheet(
            "QTextBrowser { border: 1px solid palette(mid); border-radius: 6px; padding: 6px; }"
        )
        advanced.addWidget(self._context)
        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setDocumentMode(True)
        self._plan = QtWidgets.QTextBrowser()
        self._plan.setOpenExternalLinks(False)
        self._activity = QtWidgets.QTextBrowser()
        self._activity.setOpenExternalLinks(False)
        self._activity.document().setMaximumBlockCount(400)
        self._review = QtWidgets.QTextBrowser()
        self._review.setOpenExternalLinks(False)
        self._review.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        self._tabs.addTab(self._plan, "Plan")
        self._tabs.addTab(self._activity, "Activity")
        self._tabs.addTab(self._review, "Review")
        advanced.addWidget(self._tabs, 1)
        self._advanced.setVisible(False)
        outer.addWidget(self._advanced)

        self._activity.append(
            '<div style="color: #888;">LearnCad is local-first. The deterministic mentor never needs the network. '
            "AI is included with LearnCad.</div>"
        )
        self._render_footer()
        self._render_empty()
        self._set_answer("LearnCad", "Hi. What are you making? Ask me anything as you build.")

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

    def _force_review(self) -> None:
        self._engine.force()
        if self._analysis is not None:
            self._show_details(True)
            self._tabs.setCurrentWidget(self._review)
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
        if self._suggestion is not None:
            self._guide_btn.setText(self._suggestion.label)
            self._guide_btn.setToolTip(self._suggestion.hint)
            self._guide_btn.setEnabled(True)
        else:
            self._guide_btn.setText("Guide me")
            self._guide_btn.setEnabled(False)

        word = _status_word(analysis.score, doc)
        self._score.setText(word)
        self._score.setToolTip(f"Model score: {analysis.score}/100")
        self._score.setStyleSheet(
            f"QLabel {{ border-radius: 10px; padding: 6px 10px; font-weight: 700; color: white; "
            f"background: {_score_color(analysis.score)}; }}"
        )

        if doc is None:
            self._status.setText("No document yet. Start a new part when you are ready.")
            self._next.setText("Press Start a new part, then draw the outer profile.")
            self._render_empty()
            return

        self._status.setText(self._status_line(snapshot))
        self._next.setText(analysis.next_step)
        self._next.setStyleSheet("font-weight: 600; color: #d64545;" if analysis.critical else "font-weight: 600;")

        color = SEVERITY_COLOR["critical"] if analysis.critical else "#ff7a18"
        frame = self.findChild(QtWidgets.QFrame, "nextStep")
        if frame is not None:
            frame.setStyleSheet(
                f"QFrame#nextStep {{ border-left: 3px solid {color}; background: palette(alternate-base); border-radius: 5px; }}"
            )

        has_notes = bool(analysis.critical or analysis.warnings)
        self._notes_label.setVisible(has_notes)
        self._simple_notes.setVisible(has_notes)
        self._simple_notes.setHtml(self._simple_notes_html(analysis) if has_notes else "")
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
        if doc.sketches:
            sketch = doc.sketches[-1]
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
        if doc.workbench:
            rows.append(f"<b>Workbench</b> | {_esc(doc.workbench)}")
        if doc.edit_mode:
            rows.append(f"<b>Editing</b> | {_esc(doc.edit_mode)}")
        for body in doc.bodies[:2]:
            status = "valid solid" if body.shape_valid and body.has_solid else "in progress"
            if body.shape_valid and body.has_solid and not body.shape_closed:
                status = "open shell"
            rows.append(f"<b>{_esc(body.label or body.name)}</b> | {body.feature_count} feature(s) | {status}")
        for sketch in doc.sketches[:2]:
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
            self._footer.setText("Local-first. Paid AI explanations are active. The geometry review stays local.")
        else:
            self._footer.setText("Local-first. The coach is free. AI needs an active subscription.")

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

        if self._snapshot is None or self._analysis is None:
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

        local_answer = coach.answer(question, snapshot, analysis)
        if guide.looks_like_howto(question):
            walkthrough = guide.walkthrough_for(question)
            if walkthrough is not None:
                self._start_walkthrough(walkthrough)
        if not settings.ai_ready(self._config):
            self._set_answer("LearnCad", local_answer)
            self._history.append({"role": "user", "content": question})
            self._history.append({"role": "assistant", "content": local_answer})
            self._history = self._history[-8:]
            self._append_activity(local_answer, "info", "mentor")
            return

        self._ask_btn.setEnabled(False)
        self._ask_btn.setText("...")
        self._set_answer("LearnCad", "Thinking about your model...")
        self._append_activity("Thinking with the built-in AI...", "info", "info")
        history = list(self._history[-8:])
        worker = _AskWorker(self._config, question, snapshot, analysis, self, history)
        worker.done.connect(lambda answer: self._on_ai_done(answer, local_answer, question))
        worker.failed.connect(lambda error: self._on_ai_failed(error, local_answer, question))
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_ai_done(self, answer: str, local_answer: str, question: str = "") -> None:
        self._ask_btn.setEnabled(True)
        self._ask_btn.setText("Send")
        self._set_answer("LearnCad", answer)
        self._append_activity(answer, "good", "ai")
        if question:
            self._history.append({"role": "user", "content": question})
            self._history.append({"role": "assistant", "content": answer})
            self._history = self._history[-8:]

    def _on_ai_failed(self, error: str, local_answer: str, question: str = "") -> None:
        self._ask_btn.setEnabled(True)
        self._ask_btn.setText("Send")
        self._set_answer("LearnCad", local_answer)
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
            self._highlight(widget)
            if not step.wait_for_sketch:
                self._wire_target(widget)
        elif step.target.startswith("dialog:"):
            self._retry_dialog(step.target, 0)

    def _find_target(self, target: str):
        if target.startswith("panel:"):
            mapping = {
                "primary": getattr(self, "_guide_btn", None),
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
        wanted = name.replace("&", "").strip().lower()
        for action in bar.actions():
            if action.isSeparator():
                continue
            if action.text().replace("&", "").strip().lower() == wanted:
                return bar.widgetForAction(action)
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
            ("Fix constraints", self._fix_constraints, False),
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


class _SettingsDialog(QtWidgets.QDialog):
    def __init__(self, config: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("LearnCad settings")
        self.setMinimumWidth(520)
        self._config = dict(config)
        self._test_worker: Optional[_TestWorker] = None

        layout = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "The mentor always runs locally and stays free. AI explanations are a paid add-on: "
            "only a compact model summary and your question are sent to the LearnCad AI server."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._simple = QtWidgets.QCheckBox("Simple mode: hide advanced toolbars, menus, and the workbench selector")
        self._simple.setChecked(bool(self._config.get("simple_mode", True)))
        layout.addWidget(self._simple)

        ai_box = QtWidgets.QGroupBox("LearnCad AI subscription")
        ai_form = QtWidgets.QFormLayout(ai_box)
        self._ai_status = QtWidgets.QLabel("")
        self._ai_status.setWordWrap(True)
        ai_form.addRow("Status", self._ai_status)

        self._enabled = QtWidgets.QCheckBox("Enable paid AI explanations")
        self._enabled.setChecked(bool(self._config.get("ai_enabled")))
        ai_form.addRow("AI", self._enabled)

        self._consent = QtWidgets.QCheckBox("I agree to send the model summary and question to the LearnCad AI server")
        self._consent.setChecked(bool(self._config.get("consent_ai")))
        ai_form.addRow("Privacy", self._consent)

        self._base = QtWidgets.QLineEdit(str(self._config.get("cloud_base_url", "")))
        self._base.setPlaceholderText("https://ai.your-server.example")
        ai_form.addRow("AI server", self._base)

        self._subscribe_url = QtWidgets.QLineEdit(str(self._config.get("subscribe_url", "")))
        self._subscribe_url.setPlaceholderText("https://your-server.example/subscribe")
        ai_form.addRow("Subscribe page", self._subscribe_url)

        self._email = QtWidgets.QLineEdit(str(self._config.get("license_email", "")))
        self._email.setPlaceholderText("you@example.com")
        ai_form.addRow("Email", self._email)

        self._license = QtWidgets.QLineEdit()
        self._license.setEchoMode(QtWidgets.QLineEdit.Password)
        self._license.setPlaceholderText("License code from your email")
        ai_form.addRow("License code", self._license)

        ai_buttons = QtWidgets.QHBoxLayout()
        self._activate = QtWidgets.QPushButton("Activate")
        self._activate.clicked.connect(self._activate_license)
        self._subscribe = QtWidgets.QPushButton("Subscribe")
        self._subscribe.clicked.connect(self._open_subscribe)
        ai_buttons.addWidget(self._activate)
        ai_buttons.addWidget(self._subscribe)
        ai_buttons.addStretch(1)
        ai_form.addRow("", ai_buttons)
        layout.addWidget(ai_box)

        ai_hint = QtWidgets.QLabel(
            "Subscribe on the web page, then enter the email and license code from the confirmation message. "
            "The token is stored locally; the language-model key stays on the server."
        )
        ai_hint.setWordWrap(True)
        ai_hint.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(ai_hint)

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

        storage = QtWidgets.QLabel(f"Access token storage: {secret_store.storage_description()}")
        storage.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(storage)

        test_row = QtWidgets.QHBoxLayout()
        self._test = QtWidgets.QPushButton("Check subscription")
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

    def _update_ai_status(self) -> None:
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
        self._license.clear()
        self._enabled.setChecked(True)
        try:
            settings.save(self._config)
        except Exception:
            pass
        self._update_ai_status()
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
        data["cloud_base_url"] = self._base.text().strip()
        data["subscribe_url"] = self._subscribe_url.text().strip()
        data["license_email"] = self._email.text().strip()
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
        if not data.get("cloud_base_url"):
            self._test_status.setText("Set the AI server URL first.")
            self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['warn']};")
            return
        if not settings.get_license_token(data):
            self._test_status.setText("Activate a subscription first.")
            self._test_status.setStyleSheet(f"color: {SEVERITY_COLOR['warn']};")
            return
        self._test.setEnabled(False)
        self._test_status.setText("Checking subscription...")
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
                "Tick the privacy note before enabling paid AI explanations.",
            )
            return
        if data["ai_enabled"] and not settings.license_active(data):
            QtWidgets.QMessageBox.warning(
                self,
                "Subscription required",
                "Activate a subscription with your email and license code, or turn AI off. "
                "The local mentor stays free.",
            )
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

        # The engine's parameters live in a hidden Task tab. The visible TOOL
        # tab is LearnCad's own page, so every button is under our control.
        try:
            for other in main_window.findChildren(QtWidgets.QDockWidget):
                if other is dock:
                    continue
                if other.windowTitle().strip().lower() in ("tasks", "task", "inspector", "tool"):
                    other.setWindowTitle("Task")
                    other.setFloating(False)
                    empty = QtWidgets.QWidget()
                    empty.setFixedHeight(0)
                    other.setTitleBarWidget(empty)
                    main_window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, other)
                    other.hide()
                    _PANEL._task_dock = other
                    break
        except Exception:
            pass

        try:
            tools_dock = QtWidgets.QDockWidget("TOOL", main_window)
            tools_dock.setObjectName("LearnCadToolsDock")
            empty = QtWidgets.QWidget()
            empty.setFixedHeight(0)
            tools_dock.setTitleBarWidget(empty)
            tools_dock.setWidget(_ToolsPage(_PANEL, tools_dock))
            main_window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, tools_dock)
            main_window.tabifyDockWidget(tools_dock, dock)
            tools_dock.show()
            dock.show()
            dock.raise_()
            try:
                main_window.setTabPosition(
                    QtCore.Qt.LeftDockWidgetArea, QtWidgets.QTabWidget.North
                )
            except Exception:
                pass
            _PANEL._inspector_dock = tools_dock
            main_window.resizeDocks([dock, tools_dock], [340, 340], QtCore.Qt.Horizontal)
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
