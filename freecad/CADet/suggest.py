# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Choose the next UI action to set up for the user.

Pure logic: no FreeCAD, no Qt. The panel renders the label, and actions.py
executes the matching FreeCAD command.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Analysis, BodyInfo, Snapshot


@dataclass
class Suggestion:
    id: str
    label: str
    hint: str = ""


def _has_feature(body: BodyInfo, needle: str) -> bool:
    needle = needle.lower()
    return any(needle in feature.type_id.lower() for feature in body.features)


def _first_body(snapshot: Snapshot) -> BodyInfo | None:
    doc = snapshot.doc
    if doc is None or not doc.bodies:
        return None
    return doc.bodies[0]


def _has_sketch_issue(analysis: Analysis) -> bool:
    sketch_codes = {
        "conflicting_constraints", "malformed_constraints", "open_profile", "zero_length",
        "underconstrained", "no_constraints", "unattached_sketch", "empty_sketch",
    }
    return any(issue.code in sketch_codes for issue in analysis.issues)


def suggest_action(snapshot: Snapshot, analysis: Analysis) -> Suggestion:
    doc = snapshot.doc
    if doc is None:
        return Suggestion(
            "new_document",
            "Create a new document",
            "Start a document, a Body and a sketch on the XY plane.",
        )
    if doc.is_empty:
        return Suggestion(
            "new_part",
            "Create Body + Sketch",
            "Create the Body and enter the sketch on the XY plane.",
        )

    critical = analysis.critical
    if critical:
        first = critical[0]
        if first.code in ("feature_error", "body_invalid", "zero_volume"):
            return Suggestion(
                "edit_feature",
                "Open the failing feature",
                "Open the first red feature and read the solver message.",
            )
        if _has_sketch_issue(analysis):
            return Suggestion(
                "guide_sketch",
                "Open sketch and show me",
                "Enter Sketcher and preselect the geometry that needs the next constraint.",
            )
        return Suggestion(
            "edit_feature",
            "Open the failing feature",
            "Open the first feature that reports an error.",
        )

    if any(issue.code == "underconstrained" for issue in analysis.warnings):
        return Suggestion(
            "guide_sketch",
            "Guide me through constraints",
            "Enter Sketcher and preselect the missing endpoints or lines.",
        )

    if not doc.bodies and doc.features:
        return Suggestion(
            "open_export",
            "Open the Export dialog",
            "This is a Part-workbench model; select the result and export it.",
        )

    body = _first_body(snapshot)
    if body is None:
        return Suggestion(
            "new_part",
            "Create Body + Sketch",
            "Create a Body and start the profile.",
        )

    active_sketch = None
    if doc.edit_mode:
        for sketch in doc.sketches:
            if doc.edit_mode in (sketch.name, sketch.label):
                active_sketch = sketch
                break
    if active_sketch is not None:
        if active_sketch.geometry_count == 0:
            return Suggestion(
                "draw_rectangle",
                "Draw a rectangle",
                "Click two corners for the outer profile, then dimension it.",
            )
        if active_sketch.fully_constrained and active_sketch.open_wires == 0:
            return Suggestion(
                "close_sketch",
                "Finish the sketch",
                "The profile is ready. Leave Sketcher, then pad it.",
            )

    if body.feature_count == 0 or not body.has_solid:
        return Suggestion(
            "open_pad",
            "Open the Pad dialog",
            "Select the profile and start a Pad or Revolve.",
        )

    if snapshot.goal:
        if analysis.intent.label in ("enclosure", "box", "lid") and not (
            _has_feature(body, "shell")
            or _has_feature(body, "thickness")
            or _has_feature(body, "pocket")
        ):
            return Suggestion(
                "open_thickness",
                "Hollow it with Shell",
                "Select the top face and open the Thickness dialog.",
            )
        if analysis.intent.label == "phone stand":
            return Suggestion(
                "open_export",
                "Export when the stand is ready",
                "Check the base, front lip and cable opening, then export STL or STEP.",
            )
        if analysis.intent.label == "plate" and not _has_feature(body, "hole"):
            return Suggestion(
                "open_hole",
                "Open the Hole dialog",
                "Select the top face and add the mounting holes.",
            )

    if not _has_feature(body, "pocket") and not _has_feature(body, "hole"):
        return Suggestion(
            "open_hole",
            "Open the Hole dialog",
            "Select the top face and start the first functional hole.",
        )

    if not _has_feature(body, "fillet") and not _has_feature(body, "chamfer"):
        return Suggestion(
            "open_fillet",
            "Select edges and open Fillet",
            "Preselect the vertical edges and start a Fillet.",
        )

    return Suggestion(
        "open_export",
        "Open the Export dialog",
        "Select the body and export STL or STEP.",
    )
