# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Live monitoring loop.

The engine polls a cheap fingerprint, and only runs the full geometry review
when the document actually changes. That keeps FreeCAD responsive with large
models while still feeling live.
"""

from __future__ import annotations

from typing import Any, Optional

from .compat import QtCore, QtWidgets, blocking_modal

from .analysis import analyze
from .context import build_light_signature, build_snapshot
from .model import Analysis, Issue, Snapshot


class MentorEngine(QtCore.QObject):
    updated = QtCore.Signal(object, object, list)
    failed = QtCore.Signal(str)

    def __init__(self, interval_ms: int = 900, parent=None, goal: str = ""):
        super().__init__(parent)
        self._interval = max(250, int(interval_ms or 900))
        self._goal = str(goal or "")
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self._interval)
        self._timer.timeout.connect(self._tick)
        self._last_sig: Optional[tuple] = None
        self._last_snapshot: Optional[Snapshot] = None
        self._last_analysis: Optional[Analysis] = None
        self._last_error = ""
        self._paused = False

    def start(self) -> None:
        was_active = self._timer.isActive()
        self._timer.start()
        if not was_active:
            self._tick(force=True)

    def stop(self) -> None:
        self._timer.stop()

    def set_goal(self, goal: str) -> None:
        goal = str(goal or "")
        if goal != self._goal:
            self._goal = goal
            self._last_sig = None
            self.force()

    def set_interval(self, interval_ms: int) -> None:
        self._interval = max(250, int(interval_ms or 900))
        self._timer.setInterval(self._interval)

    def pause(self) -> None:
        self._paused = True
        self._timer.stop()

    def resume(self) -> None:
        self._paused = False
        self.start()

    def force(self) -> None:
        self._tick(force=True)

    def _tick(self, force: bool = False) -> None:
        if self._paused and not force:
            return
        # Do not run the review while the user is dragging, orbiting or
        # dimensioning. A concurrent solve makes the Sketcher view flicker.
        try:
            if not force and QtWidgets.QApplication.mouseButtons() != QtCore.Qt.NoButton:
                return
            if not force and blocking_modal() is not None:
                return
        except Exception:
            pass
        try:
            signature = build_light_signature()
        except Exception as exc:
            self._report_error(f"Could not read the model state: {exc}")
            return

        if not force and signature == self._last_sig:
            return
        self._last_sig = signature
        self._review()

    def _review(self) -> None:
        try:
            snapshot = build_snapshot(goal=self._goal)
            analysis = analyze(snapshot)
        except Exception as exc:
            self._report_error(f"Review failed: {exc}")
            return

        previous_snapshot = self._last_snapshot
        previous_analysis = self._last_analysis
        if (
            previous_snapshot is not None
            and snapshot.doc is not None
            and previous_snapshot.doc is not None
            and previous_snapshot.doc.name != snapshot.doc.name
        ):
            previous_analysis = None

        events = self._events(previous_snapshot, previous_analysis, snapshot, analysis)
        self._last_snapshot = snapshot
        self._last_analysis = analysis
        self._last_error = ""
        self.updated.emit(snapshot, analysis, events)

    def _events(
        self,
        old_snapshot: Optional[Snapshot],
        old_analysis: Optional[Analysis],
        snapshot: Snapshot,
        analysis: Analysis,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        old_doc = old_snapshot.doc if old_snapshot else None
        new_doc = snapshot.doc
        if old_doc is None and new_doc is not None:
            events.append({"kind": "info", "severity": "info", "text": f"Document '{new_doc.label or new_doc.name}' is open. I'm watching."})
        if old_doc is not None and new_doc is None:
            events.append({"kind": "info", "severity": "info", "text": "Document closed. Open another one when you're ready."})
        if old_doc is not None and new_doc is not None and old_doc.is_empty and not new_doc.is_empty:
            events.append({"kind": "good", "severity": "good", "text": "First geometry detected. Now we have something to work with."})

        old_issues: dict[tuple[str, str], Issue] = {}
        if old_analysis:
            for issue in old_analysis.issues:
                old_issues[(issue.code, issue.object_name)] = issue
        new_issues = {(i.code, i.object_name): i for i in analysis.issues}

        new_notable = [
            issue for key, issue in new_issues.items()
            if key not in old_issues and issue.severity in ("critical", "warn")
        ]
        new_notable.sort(key=lambda i: 0 if i.severity == "critical" else 1)
        for issue in new_notable[:3]:
            events.append({
                "kind": "issue",
                "severity": issue.severity,
                "text": f"{issue.title}. {issue.fix}".strip(),
            })

        resolved = [
            issue for key, issue in old_issues.items()
            if key not in new_issues and issue.severity in ("critical", "warn")
        ]
        for issue in resolved[:3]:
            events.append({
                "kind": "resolved",
                "severity": "good",
                "text": f"Resolved: {issue.title}.",
            })

        if old_doc is not None and new_doc is not None:
            old_fc = {s.name for s in old_doc.sketches if s.fully_constrained}
            new_fc = {s.name for s in new_doc.sketches if s.fully_constrained}
            for name in sorted(new_fc - old_fc):
                sketch = next((s for s in new_doc.sketches if s.name == name), None)
                events.append({
                    "kind": "good",
                    "severity": "good",
                    "text": f"'{sketch.label if sketch else name}' is fully constrained. That is the standard to hold.",
                })

            old_solids = {b.name for b in old_doc.bodies if b.has_solid and b.shape_valid and b.shape_closed}
            new_solids = {b.name for b in new_doc.bodies if b.has_solid and b.shape_valid and b.shape_closed}
            for name in sorted(new_solids - old_solids):
                body = next((b for b in new_doc.bodies if b.name == name), None)
                events.append({
                    "kind": "good",
                    "severity": "good",
                    "text": f"'{body.label if body else name}' is now a closed, valid solid. That will slice.",
                })

        if not events and old_analysis is None and new_doc is not None and not new_doc.is_empty:
            if analysis.critical:
                events.append({"kind": "issue", "severity": "critical", "text": analysis.critical[0].title})
            elif analysis.warnings:
                events.append({"kind": "issue", "severity": "warn", "text": analysis.warnings[0].title})

        return events[:6]

    def _report_error(self, message: str) -> None:
        if message == self._last_error:
            return
        self._last_error = message
        self.failed.emit(message)
