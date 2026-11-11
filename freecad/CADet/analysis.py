# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""The senior-engineer analysis engine.

Input: a Snapshot built from the live FreeCAD document.
Output: a plain Analysis object that the panel and the AI client can render.

Everything here is deterministic. The AI is an explanation layer, not the
source of truth about the model.
"""

from __future__ import annotations

from .intent import infer_intent
from .model import Analysis, BodyInfo, Issue, Praise, SketchInfo, Snapshot


SEVERITY_ORDER = {"critical": 0, "warn": 1, "info": 2, "good": 3}


def _fmt(value: float, digits: int = 1) -> str:
    text = f"{value:.{digits}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _obj_name(obj) -> str:
    return obj.label or obj.name


def _add(issues: list[Issue], code: str, severity: str, title: str, detail: str = "", fix: str = "", obj=None):
    issues.append(
        Issue(
            code=code,
            severity=severity,
            title=title,
            detail=detail,
            fix=fix,
            object_name=getattr(obj, "name", "") if obj else "",
            object_label=getattr(obj, "label", "") if obj else "",
        )
    )


def _praise(praises: list[Praise], code: str, text: str, obj=None):
    praises.append(
        Praise(
            code=code,
            text=text,
            object_name=getattr(obj, "name", "") if obj else "",
        )
    )


def _has_feature(body: BodyInfo, needle: str) -> bool:
    needle = needle.lower()
    return any(needle in f.type_id.lower() for f in body.features)


def _count_feature(body: BodyInfo, needle: str) -> int:
    needle = needle.lower()
    return sum(1 for f in body.features if needle in f.type_id.lower())


def _active_sketch(doc, sketch: SketchInfo) -> bool:
    if not doc.edit_mode:
        return False
    return doc.edit_mode in (sketch.name, sketch.label)


def _analyze_document(snapshot: Snapshot, issues: list[Issue], praises: list[Praise]) -> None:
    doc = snapshot.doc
    if doc is None:
        _add(
            issues,
            "no_document",
            "info",
            "No document is open",
            "LearnCad watches the active document. Until there is one, I have nothing to review.",
            "Create a new document (Ctrl+N), then add a Body. I'll pick it up automatically.",
        )
        return

    if doc.is_empty:
        _add(
            issues,
            "empty_document",
            "info",
            "Empty document",
            "A clean start. The first decision is the one that matters most: choose a principal plane and a body before drawing anything.",
            "Create a Body, then a sketch on the XY, XZ or YZ plane.",
        )
        return

    if doc.sketches and not doc.bodies:
        _add(
            issues,
            "sketch_outside_body",
            "warn",
            "Sketch is outside a Body",
            "Modeling features need a Body. A sketch drawn outside it can look finished but cannot become a Pad or Pocket until it belongs to a body.",
            "Create a Body, then move the sketch into it or create a new sketch on the body's origin plane.",
            doc.sketches[0] if doc.sketches else None,
        )

    if doc.bodies and doc.features:
        _add(
            issues,
            "mixed_workbenches",
            "info",
            "Loose Part geometry and Body geometry in the same document",
            "Mixing loose Part tools with a Body makes the feature tree hard to follow. Beginners often lose the active body and wonder why a tool is greyed out.",
            "Pick one workflow. For parts you plan to edit, use Body tools for the whole part and keep loose Part tools out of it.",
        )

    workbench = (doc.workbench or "").lower()
    non_modeling = (
        "draft", "techdraw", "mesh", "fem", "cam", "spreadsheet", "bim",
        "inspection", "points", "reverse", "robot", "material",
    )
    if doc.bodies and any(token in workbench for token in non_modeling):
        _add(
            issues,
            "workbench_mismatch",
            "info",
            "The modeling tools are hidden right now",
            "The model is fine. The active workspace only changes which tools are in front of you.",
            "Switch back to Model tools when you want to add features; switch to Sketch when you want to edit the profile.",
        )

    if not doc.bodies and doc.features:
        if doc.imported_objects:
            mesh_only = all(feature.type_id.startswith("Mesh::") for feature in doc.features)
            if mesh_only:
                _add(
                    issues,
                    "imported_mesh",
                    "info",
                    "This is an imported mesh",
                    "A mesh is made of triangles, not editable CAD faces. It can print, but it cannot be dimensioned, sketched on, or edited like a solid.",
                    "Use Shape from mesh, then Make solid, to convert it. If you only need to print it, check it in the slicer.",
                    doc.features[0] if doc.features else None,
                )
            else:
                _add(
                    issues,
                    "imported_solid",
                    "info",
                    "This is imported geometry, not a Body",
                    "It can be measured and exported, but it has no editable feature tree.",
                    "Use Base feature to bring it into a Body, or verify the dimensions and export it as-is.",
                    doc.features[0] if doc.features else None,
                )
        else:
            _add(
                issues,
                "no_body",
                "info",
                "Loose Part geometry, not a Body",
                "This kind of model is quick to make but harder to revise later because there is no single feature tree.",
                "If this part will change, rebuild it in a Body. If it is a one-off, keep going.",
            )


def _analyze_bodies(snapshot: Snapshot, issues: list[Issue], praises: list[Praise]) -> None:
    doc = snapshot.doc
    if doc is None:
        return

    if len(doc.bodies) > 1:
        _add(
            issues,
            "multiple_bodies",
            "info",
            f"{len(doc.bodies)} separate bodies",
            "Separate bodies are fine for separate parts, but mating features between them will not update together unless you use an assembly or a shape binder.",
            "Keep one part per body. If these parts must move relative to each other, use the assembly tools.",
        )

    for body in doc.bodies:
        label = body.label or body.name
        if body.feature_count == 0:
            has_sketch = any(sketch.geometry_count > 0 for sketch in body.sketches)
            if has_sketch:
                _add(
                    issues,
                    "body_sketch_only",
                    "info",
                    f"Body '{label}' has a sketch but no solid yet",
                    "The profile exists. It becomes a printable part only after Pad or Revolve.",
                    "Close the sketch, then pad or revolve it.",
                    body,
                )
            else:
                _add(
                    issues,
                    "empty_body",
                    "info",
                    f"Body '{label}' is empty",
                    "A body with no features cannot produce a solid yet.",
                    "Create a sketch on a principal plane and pad or revolve it.",
                    body,
                )
            continue

        if not body.tip:
            _add(
                issues,
                "no_tip",
                "warn",
                f"Body '{label}' has no tip feature",
                "Without a tip, downstream operations and exports do not know which result is the current shape.",
                "Right-click the last good feature in the tree and choose 'Set tip'.",
                body,
            )

        errored = [f for f in body.features if f.has_error]
        if errored:
            first = errored[0]
            _add(
                issues,
                "feature_error",
                "critical",
                f"Feature '{first.label or first.name}' is failing",
                f"{len(errored)} feature(s) in this body report an error. Everything after the first failure is built on bad geometry. If this appeared after changing an earlier dimension, it is often a broken generated-face reference (topological naming).",
                "Open the first red feature, read the solver message, and fix it before adding anything else. Do not keep stacking features on top. Prefer datum/principal planes over generated faces when you rebuild.",
                first,
            )

        if not body.shape_valid:
            _add(
                issues,
                "body_invalid",
                "critical",
                f"Body '{label}' is not a valid solid",
                "The result has broken topology. It may look fine on screen and still fail to slice or export.",
                "Use Part -> Check geometry, then fix the first failing feature. If it is a fillet or chamfer, reduce the radius.",
                body,
            )
        elif body.has_solid and not body.shape_closed:
            _add(
                issues,
                "body_open",
                "warn",
                f"Body '{label}' is not closed",
                "A printable part needs a watertight solid. Open shells will not slice cleanly.",
                "Look for an unclosed sketch profile or a thickness operation that opened the shell.",
                body,
            )

        if body.has_solid and body.volume <= 0:
            _add(
                issues,
                "zero_volume",
                "critical",
                f"Body '{label}' has no volume",
                "The feature tree produced a surface or an empty result instead of a solid.",
                "Check that the profile is closed and that the pad or revolve actually encloses material.",
                body,
            )

        center = body.bbox.center
        distance = (center[0] ** 2 + center[1] ** 2 + center[2] ** 2) ** 0.5
        if distance > 500.0:
            _add(
                issues,
                "far_from_origin",
                "warn",
                f"Body '{label}' sits {_fmt(distance, 0)} mm from the origin",
                "Geometry far from the origin makes booleans, exports and assemblies less reliable. It also makes the model hard to re-use.",
                "Move the body near the origin, or build it around the origin from the start.",
                body,
            )

        dims = body.bbox.dims
        max_dim = max(dims) if dims else 0.0
        positive_dims = [dim for dim in dims if dim > 0.001]
        min_dim = min(positive_dims) if positive_dims else 0.0
        if body.has_solid and min_dim and min_dim < 0.8:
            has_thin_feature = any(
                feature.length is not None and 0 < feature.length < 0.8
                for feature in body.features
            )
            if not has_thin_feature:
                _add(
                    issues,
                    "thin_body",
                    "warn",
                    f"'{label}' is only {_fmt(min_dim, 2)} mm thick",
                    "That is thinner than two typical 0.4 mm perimeters. Thin sections flex, warp, or print as a membrane.",
                    "Increase the thin dimension to at least 1.2 mm, or accept that it is a flexible part.",
                    body,
                )
        if body.has_solid and body.shape_valid and body.shape_closed:
            _praise(
                praises,
                "clean_solid",
                f"'{label}' is a clean, closed solid. That is the baseline for a part that will actually print.",
                body,
            )
            if not _has_feature(body, "fillet") and not _has_feature(body, "chamfer") and max_dim >= 40.0:
                _add(
                    issues,
                    "no_fillets",
                    "info",
                    f"'{label}' has no fillets or chamfers",
                    "Sharp external corners concentrate stress, chip in FDM, and look unfinished. Not every edge needs a radius, but load-bearing ones usually do.",
                    "Add a small fillet (0.5-2 mm) to the corners that see load or handling. Leave mating faces sharp.",
                    body,
                )

        if body.has_solid and body.shape_valid:
            box_volume = body.bbox.x * body.bbox.y * body.bbox.z
            if box_volume > 0:
                fill = body.volume / box_volume
                if fill < 0.05:
                    _add(
                        issues,
                        "low_fill",
                        "warn",
                        f"'{label}' uses only {fill * 100:.1f}% of its bounding box",
                        "The part is either very thin, mostly empty, or the sketch is much larger than the material. Thin walls are a common print failure.",
                        "Check wall thickness in the sketch. For FDM, keep walls at 1.2 mm or more unless you have a reason not to.",
                        body,
                    )


def _analyze_sketches(snapshot: Snapshot, issues: list[Issue], praises: list[Praise]) -> None:
    doc = snapshot.doc
    if doc is None:
        return

    for sketch in doc.sketches:
        if sketch.helper:
            continue
        label = sketch.label or sketch.name
        if sketch.is_empty:
            _add(
                issues,
                "empty_sketch",
                "info",
                f"Sketch '{label}' is empty",
                "There is no geometry to constrain or pad yet.",
                "Draw the profile with lines, arcs or circles. Start with the overall shape before adding holes.",
                sketch,
            )
            continue

        if sketch.conflicting > 0:
            _add(
                issues,
                "conflicting_constraints",
                "critical",
                f"Sketch '{label}' has {sketch.conflicting} conflicting constraint(s)",
                "The solver cannot satisfy all of them at once. The sketch may jump or refuse to update, and downstream features inherit the instability.",
                "Delete the highlighted conflicting constraints first. Then re-add one dimension at a time and watch the sketch.",
                sketch,
            )

        if sketch.redundant > 0 or sketch.partially_redundant > 0:
            _add(
                issues,
                "redundant_constraints",
                "warn",
                f"Sketch '{label}' has redundant constraints",
                "Redundant constraints fight each other. They often appear when a dimension repeats something the geometry already enforces.",
                "Remove the redundant constraint the solver highlights. Keep the one that expresses design intent, not the one that is easiest to delete.",
                sketch,
            )

        if sketch.malformed > 0:
            _add(
                issues,
                "malformed_constraints",
                "critical",
                f"Sketch '{label}' has malformed constraints",
                "A constraint references geometry that no longer exists or has the wrong type.",
                "Delete the malformed constraint and re-create it on the current geometry.",
                sketch,
            )

        if sketch.dof > 0:
            detail = "The solver can still move the geometry. If you pad it now, later edits will drift."
            fix = "Add the missing constraints. Work from the outside in: coincident, then horizontal/vertical, then dimensions."
            if sketch.missing_coincident > 0:
                detail += f" I can see {sketch.missing_coincident} endpoint pair(s) that look connected but are not constrained together."
                fix = "Use Coincident on the open endpoints first. That usually removes the largest chunk of freedom."
            elif sketch.missing_hv > 0:
                detail += f" {sketch.missing_hv} line(s) look almost horizontal or vertical."
                fix = "Add Horizontal or Vertical constraints to those lines, then dimension the overall size."
            elif sketch.missing_radius > 0:
                detail += f" {sketch.missing_radius} arc(s) or circle(s) still need a radius or diameter."
                fix = "Dimension the radii and the center positions. A circle without a radius is two degrees of freedom."
            elif sketch.missing_equality > 0:
                detail += " Some lines look equal in length."
                fix = "Use Equal constraints where the design intends equal lengths, then dimension only one of them."
            elif sketch.dof <= 3:
                detail += f" Only {sketch.dof} degree(s) of freedom remain, so this is close."
                fix = "Add one or two dimensions and you should be fully constrained."

            _add(
                issues,
                "underconstrained",
                "warn",
                f"Sketch '{label}' has {sketch.dof} degree(s) of freedom",
                detail,
                fix,
                sketch,
            )
        elif sketch.dof == 0 and not sketch.conflicting and not sketch.malformed:
            _praise(
                praises,
                "fully_constrained",
                f"'{label}' is fully constrained. This is the habit that separates a quick hack from a model that survives changes.",
                sketch,
            )

        if sketch.open_wires > 0:
            _add(
                issues,
                "open_profile",
                "critical",
                f"Sketch '{label}' has {sketch.open_wires} open profile(s)",
                "Pad, Pocket and Revolve need closed profiles. An open profile will fail or produce a thin shell instead of a solid. Even a 0.001 mm gap counts.",
                "Find the gap: zoom in on the endpoints, add Coincident constraints, and confirm the wire is closed before closing the sketch.",
                sketch,
            )

        if sketch.zero_length_edges > 0:
            _add(
                issues,
                "zero_length",
                "critical",
                f"Sketch '{label}' has {sketch.zero_length_edges} zero-length edge(s)",
                "Degenerate geometry breaks the solver and produces unpredictable results.",
                "Delete the duplicate or zero-length geometry and re-close the profile.",
                sketch,
            )

        if not sketch.attached:
            _add(
                issues,
                "unattached_sketch",
                "warn",
                f"Sketch '{label}' is not attached to a plane",
                "An unattached sketch is positioned in global space. If the body moves or the design changes, the sketch will not follow.",
                "Attach the sketch to a principal plane or a face of the body. The XY plane is a good default for a flat part.",
                sketch,
            )
        else:
            support = (sketch.support or "").lower()
            if ("face" in support or "edge" in support) and "plane" not in support:
                _add(
                    issues,
                    "face_attachment",
                    "warn",
                    f"Sketch '{label}' is attached to a generated face",
                    "That face can be renamed when an earlier feature changes. This is the classic topological-naming trap: the hole or sketch flies off after a dimension edit.",
                    "Attach the sketch to a datum plane or a principal plane. If it must follow a face, expect to re-attach it after major dimension changes.",
                    sketch,
                )

        if sketch.constraint_count == 0 and sketch.geometry_count > 0:
            _add(
                issues,
                "no_constraints",
                "warn",
                f"Sketch '{label}' has geometry but no constraints",
                "The geometry is only where you dropped it. Any later change will move points you did not intend to move.",
                "Add coincident, horizontal/vertical and dimensional constraints before padding.",
                sketch,
            )

        dims = sketch.bbox.dims
        max_dim = max(dims) if dims else 0.0
        min_dim = min([d for d in dims if d > 0.001], default=0.0)
        if max_dim > 5000.0:
            _add(
                issues,
                "huge_sketch",
                "warn",
                f"Sketch '{label}' is {_fmt(max_dim, 0)} mm across",
                "That is either a very large part or a unit mistake. LearnCad works in millimetres by default.",
                "Check the units and the coordinate values before building more features on top.",
                sketch,
            )
        if 0 < min_dim < 0.5:
            _add(
                issues,
                "tiny_sketch",
                "warn",
                f"Sketch '{label}' has a feature smaller than 0.5 mm",
                "A 0.4 mm nozzle cannot reproduce details that small. The feature may disappear or become a weak point.",
                "Scale the detail up, or accept that it will not print as drawn.",
                sketch,
            )

        for dim in sketch.dimensions:
            if dim.kind.lower() in ("radius", "diameter") and 0 < dim.value < 1.0:
                _add(
                    issues,
                    "tiny_radius",
                    "warn",
                    f"Sketch '{label}' has a {dim.kind.lower()} of {_fmt(dim.value, 2)} mm",
                    "Small radii and holes are fragile in FDM and hard to measure. They often print undersized.",
                    "Use 1 mm or more for printed radii, and 2 mm or more for holes that must accept a fastener.",
                    sketch,
                )
                break

        if _active_sketch(doc, sketch):
            if sketch.dof == 0 and sketch.open_wires == 0:
                _praise(
                    praises,
                    "active_sketch_ready",
                    f"You're editing '{label}', and it is ready to pad. Finish the sketch before adding the next feature.",
                    sketch,
                )


def _analyze_design(snapshot: Snapshot, intent) -> list[Issue]:
    issues: list[Issue] = []
    doc = snapshot.doc
    if doc is None:
        return issues

    for body in doc.bodies:
        for feature in body.features:
            type_id = feature.type_id.lower()
            if ("pad" in type_id or "pocket" in type_id) and feature.length is not None:
                if 0 < feature.length < 0.8:
                    _add(
                        issues,
                        "thin_pad",
                        "warn",
                        f"'{feature.label or feature.name}' is only {_fmt(feature.length, 2)} mm thick",
                        "That is thinner than two typical 0.4 mm perimeters. Thin walls warp, tear, or print as a membrane.",
                        "Increase the thickness to at least 0.8-1.2 mm, or redesign the feature so it is not load-bearing.",
                        feature,
                    )
            if "hole" in type_id and feature.diameter is not None:
                if 0 < feature.diameter < 2.0:
                    _add(
                        issues,
                        "small_hole",
                        "warn",
                        f"Hole '{feature.label or feature.name}' is {_fmt(feature.diameter, 2)} mm across",
                        "Printed holes below 2 mm close up or print undersized. A fastener will not fit reliably.",
                        "Use 2.5-3.2 mm for M3 clearance, or drill the hole after printing.",
                        feature,
                    )

    if intent.label == "bracket":
        for body in doc.bodies:
            if body.has_solid and body.shape_valid and body.bbox.x * body.bbox.y * body.bbox.z > 0:
                fill = body.volume / (body.bbox.x * body.bbox.y * body.bbox.z)
                if fill > 0.7 and not _has_feature(body, "pocket"):
                    _add(
                        issues,
                        "solid_bracket",
                        "info",
                        "This bracket is a solid block",
                        "A bracket usually carries load around its outside, not through its middle. Solid material adds weight, print time and warp.",
                        "Add a lightening pocket or ribs, and keep material where the bolt holes and load paths are.",
                        body,
                    )
                    break

    if intent.label == "enclosure":
        for body in doc.bodies:
            if body.has_solid and not _has_feature(body, "shell") and not _has_feature(body, "thickness"):
                _add(
                    issues,
                    "solid_enclosure",
                    "info",
                    "This enclosure is solid",
                    "An enclosure needs an internal cavity, wall thickness and a lid strategy. A solid block is not an enclosure yet.",
                    "Use Thickness or Shell to hollow it, then design the lid and the connector openings.",
                    body,
                )
                break

    if intent.label == "plate":
        for body in doc.bodies:
            dims = sorted(body.bbox.dims)
            if body.has_solid and dims and dims[0] > 10.0:
                _add(
                    issues,
                    "thick_plate",
                    "info",
                    "This plate is thick relative to its footprint",
                    "If it is a mounting plate, thick stock is wasteful. If it is a structural block, the name may be misleading.",
                    "Check the design intent: pocket it, or rename it so the next person understands what it is.",
                    body,
                )
                break

    if intent.label == "phone stand":
        for body in doc.bodies:
            if body.has_solid and body.bbox.z < 80.0:
                _add(
                    issues,
                    "unstable_stand",
                    "info",
                    "This phone stand may be top-heavy",
                    "A phone stand needs a wide base relative to the phone's center of mass, plus a lip so the phone cannot slide off.",
                    "Check the footprint against the phone size, and add a front lip and a cable opening before printing.",
                    body,
                )
                break

    return issues


def _analyze_goal(snapshot: Snapshot, intent) -> list[Issue]:
    """Check the model against the goal the user stated, not just its shape."""
    issues: list[Issue] = []
    goal = (snapshot.goal or "").strip()
    doc = snapshot.doc
    if not goal or doc is None:
        return issues
    if not any(body.has_solid for body in doc.bodies):
        return issues

    label = intent.label
    if label == "bracket":
        has_mounting = any(
            _has_feature(body, "hole") or _has_feature(body, "pocket")
            for body in doc.bodies
        )
        if not has_mounting:
            _add(
                issues,
                "goal_bracket_holes",
                "warn",
                "You said this is a bracket, but there are no mounting holes yet",
                "A bracket without holes cannot fasten to anything. The load path usually runs between the bolt holes and the supported member.",
                "Add the mounting holes and make sure there is at least one hole diameter of material around each one.",
            )
    elif label == "phone stand":
        _add(
            issues,
            "goal_phone_stand",
            "info",
            "Phone stand checklist",
            "Check the three things that decide whether a printed stand works: a footprint wide enough for the phone's center of mass, a front lip that stops the phone sliding off, and a cable opening if it charges while standing.",
            "Verify those three against the real phone before printing. A beautiful stand that tips over is still a failed part.",
        )
    elif label in ("enclosure", "box", "lid"):
        hollow = any(
            _has_feature(body, "shell") or _has_feature(body, "thickness") or _has_feature(body, "pocket")
            for body in doc.bodies
        )
        if not hollow:
            _add(
                issues,
                "goal_enclosure_hollow",
                "warn",
                "You said this is an enclosure, but it is still solid",
                "An enclosure needs an internal cavity, a wall thickness, and a lid strategy. A solid block is a shape, not a housing.",
                "Hollow it with Thickness or Shell, then design the lid, the wall thickness and the connector openings.",
            )
    elif label == "plate":
        holes = any(_has_feature(body, "hole") for body in doc.bodies)
        if not holes:
            _add(
                issues,
                "goal_plate_holes",
                "info",
                "You said this is a plate, but it has no holes yet",
                "A mounting or cover plate usually needs fastener holes, a clearance pattern, or a cable opening. If it is a blank, that is fine.",
                "Add the holes the real assembly needs, then check the edge distance around each hole.",
            )
    elif label == "gear":
        _add(
            issues,
            "goal_gear_profile",
            "info",
            "Gear geometry needs a real tooth profile",
            "A gear is not a disc with notches. The involute flank, pressure angle and backlash determine whether it meshes. LearnCad can review dimensions and printability, but it does not generate a validated involute yet.",
            "Use a dedicated gear tool for the tooth profile, then bring the result back for the printability review.",
        )
    return issues


def _has_any_solid(doc) -> bool:
    return any(b.has_solid for b in doc.bodies) or any(f.volume > 0 for f in doc.features)


def _score(snapshot: Snapshot, issues: list[Issue]) -> int:
    doc = snapshot.doc
    if doc is None:
        return 0
    if doc.is_empty:
        return 12

    score = 100
    for issue in issues:
        if issue.severity == "critical":
            score -= 38
        elif issue.severity == "warn":
            score -= 11
        elif issue.severity == "info":
            score -= 3

    user_sketches = [sketch for sketch in doc.sketches if not sketch.helper]
    if not _has_any_solid(doc):
        score -= 8
    if any(s.fully_constrained for s in user_sketches):
        score += 6
    if any(b.has_solid and b.shape_valid and b.shape_closed for b in doc.bodies):
        score += 8
    if any(issue.code.startswith("goal_") and issue.severity == "warn" for issue in issues):
        score = min(score, 84)

    if any(issue.severity == "critical" for issue in issues):
        score = min(score, 40)
    elif any(issue.severity == "warn" for issue in issues):
        score = min(score, 80)
    elif any(issue.severity == "info" for issue in issues):
        score = min(score, 95)

    if not _has_any_solid(doc):
        score = min(score, 70)
        if (
            not user_sketches
            and not any(body.feature_count for body in doc.bodies)
            and not doc.imported_objects
        ):
            score = min(score, 30)
    if doc.imported_objects and not doc.bodies:
        score = min(score, 60)

    return max(0, min(100, score))


def _headline(score: int, snapshot: Snapshot) -> str:
    doc = snapshot.doc
    if doc is None:
        return "Open a document and I'll start watching."
    if doc.is_empty:
        return "Empty canvas. Let's make the first body."
    if (
        doc.bodies
        and not any(body.feature_count for body in doc.bodies)
        and not doc.features
        and not any(
            sketch.geometry_count > 0 and not sketch.helper for sketch in doc.sketches
        )
    ):
        return "Body ready. Sketch the profile next."
    if score >= 60 and not _has_any_solid(doc) and any(
        sketch.fully_constrained and sketch.geometry_count > 0 and sketch.open_wires == 0
        for sketch in doc.sketches
    ):
        return "Sketch ready. Pad it next."
    if doc.imported_objects and not doc.bodies:
        if any(feature.type_id.startswith("Mesh::") for feature in doc.features):
            return "Imported mesh. Convert it to a solid or check it in the slicer."
        return "Imported geometry. Use Base feature to edit it, or export it as-is."
    if score >= 92:
        return "This is shaping up like production work."
    if score >= 78:
        return "Solid progress. A few things to tighten."
    if score >= 60:
        return "You're moving, but the model isn't trustworthy yet."
    if score >= 35:
        return "Stop and fix the fundamentals before adding more features."
    return "This won't survive a rebuild or a print yet."


def _next_step(snapshot: Snapshot, issues: list[Issue], intent) -> str:
    doc = snapshot.doc
    if doc is None:
        return "Create a new document (Ctrl+N), then add a Body."
    if doc.is_empty:
        return "Create a Body, then sketch on the XY plane."

    critical = [i for i in issues if i.severity == "critical"]
    if critical:
        first = critical[0]
        return f"Fix this first: {first.title}. {first.fix}".strip()

    under = [i for i in issues if i.code == "underconstrained"]
    if under:
        first = under[0]
        return f"Finish the constraints in '{first.object_label or first.object_name}'. {first.fix}".strip()

    warnings = [
        issue for issue in issues
        if issue.severity == "warn"
        and issue.code != "underconstrained"
        and not issue.code.startswith("goal_")
    ]
    if warnings and not snapshot.goal:
        first = warnings[0]
        return f"Fix this before adding more: {first.title}. {first.fix}".strip()

    for body in doc.bodies:
        label = body.label or body.name
        if body.feature_count == 0:
            return f"Sketch the profile for '{label}', then close it and constrain it."
        if not body.has_solid:
            return f"Turn the profile in '{label}' into a solid with Pad or Revolve."
        if snapshot.goal and intent.label == "bracket" and not (
            _has_feature(body, "pocket") or _has_feature(body, "hole")
        ):
            return f"Add the mounting holes or lightening pocket to '{label}', then check the hole spacing."
        if snapshot.goal and intent.label in ("enclosure", "box", "lid") and not (
            _has_feature(body, "shell")
            or _has_feature(body, "thickness")
            or _has_feature(body, "pocket")
        ):
            return f"Hollow '{label}' with Thickness or Shell, then design the lid and openings."
        if snapshot.goal and intent.label == "phone stand":
            return f"Check the base footprint, front lip and cable opening on '{label}' against the real phone."
        if snapshot.goal and intent.label == "plate" and not _has_feature(body, "hole"):
            return f"Add the mounting or clearance holes to '{label}', then verify edge distances."
        if warnings:
            first = warnings[0]
            return f"Fix this before adding more: {first.title}. {first.fix}".strip()
        if not _has_feature(body, "pocket") and not _has_feature(body, "hole"):
            return f"Add any holes, pockets or mounting features '{label}' needs. If the shape is final, verify dimensions and export."
        if not _has_feature(body, "fillet") and not _has_feature(body, "chamfer"):
            return f"Add fillets or chamfers to the load-bearing edges of '{label}', then verify dimensions and export."
        if body.shape_valid and body.shape_closed:
            return f"Check '{label}' against the real part dimensions, then export STL or STEP."

    if not doc.bodies and doc.features:
        if doc.imported_objects:
            mesh_only = all(feature.type_id.startswith("Mesh::") for feature in doc.features)
            if mesh_only:
                return "Convert the mesh to a solid: All tools > Shape from mesh, then Make solid. If you only need to print it, check it in the slicer."
            return "This is imported geometry. Use Base feature to bring it into a Body, or verify dimensions and export it as-is."
        return "If this part needs to change later, rebuild it inside a Body. Otherwise, verify the dimensions and export."

    return "Keep building the feature tree. I'll flag the first thing that will cause trouble."


def _build_plan(snapshot: Snapshot, intent, issues: list[Issue]) -> list[str]:
    doc = snapshot.doc
    if doc is None:
        return [
            "Create a new document (Ctrl+N).",
            "Add a Body.",
            "Sketch the overall profile on a principal plane before adding holes.",
        ]
    if doc.is_empty:
        return [
            "Add a Body.",
            "Sketch on the XY plane for a flat part, or XZ/YZ for a vertical one.",
            "Draw the overall profile, close it, and constrain it before padding.",
        ]

    steps: list[str] = []
    critical = [issue for issue in issues if issue.severity == "critical"]
    if critical:
        steps.append(f"Fix the first blocker: {critical[0].title}.")
    under = [issue for issue in issues if issue.code == "underconstrained"]
    if under:
        name = under[0].object_label or under[0].object_name
        steps.append(f"Finish the constraints in '{name}' before adding features.")

    body = doc.bodies[0] if doc.bodies else None
    if body is None:
        if doc.features:
            steps.append("Verify the geometry and the dimensions; this model has no editable feature tree.")
            steps.append("Export STL or STEP.")
        return _unique(steps)[:5]

    label = body.label or body.name
    if body.feature_count == 0:
        steps.append(f"Turn the profile in '{label}' into a solid with Pad or Revolve.")
    elif not body.has_solid:
        steps.append(f"Make '{label}' a valid, closed solid before adding more features.")
    else:
        if intent.label == "bracket" and not (_has_feature(body, "hole") or _has_feature(body, "pocket")):
            steps.append("Add the mounting holes and keep at least one hole diameter of material around each one.")
        elif intent.label in ("enclosure", "box", "lid") and not (
            _has_feature(body, "shell") or _has_feature(body, "thickness") or _has_feature(body, "pocket")
        ):
            steps.append("Hollow the body with Thickness or Shell, then design the lid and connector openings.")
        elif intent.label == "phone stand":
            steps.append("Check the base footprint, front lip and cable opening against the real phone.")
        elif not _has_feature(body, "hole") and not _has_feature(body, "pocket"):
            steps.append("Add the functional holes or pockets before cosmetic features.")

        if not _has_feature(body, "fillet") and not _has_feature(body, "chamfer"):
            steps.append("Fillet or chamfer the load-bearing edges.")
        steps.append("Verify the overall dimensions against the real part.")
        steps.append("Export STL or STEP.")

    if not steps:
        steps.append("Keep the feature tree simple and dimension the design intent.")
    return _unique(steps)[:5]


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _summary(snapshot: Snapshot, analysis: Analysis) -> str:
    doc = snapshot.doc
    if doc is None:
        return "No document is open."
    if doc.is_empty:
        return "Empty document. No geometry to review yet."
    parts = []
    if snapshot.goal:
        parts.append(f"Goal: {snapshot.goal}.")
    parts.extend([
        f"Intent: {analysis.intent.description}.",
        f"State: {len(doc.bodies)} body(ies), {len(doc.sketches)} sketch(es), {len(doc.features)} standalone feature(s).",
        f"Score: {analysis.score}/100.",
    ])
    if analysis.critical:
        parts.append(f"First risk: {analysis.critical[0].title}.")
    elif analysis.warnings:
        parts.append(f"Main concern: {analysis.warnings[0].title}.")
    else:
        parts.append("No structural problems detected.")
    parts.append(f"Next: {analysis.next_step}")
    return " ".join(parts)


def analyze(snapshot: Snapshot) -> Analysis:
    intent = infer_intent(snapshot)
    issues: list[Issue] = []
    praises: list[Praise] = []

    _analyze_document(snapshot, issues, praises)
    _analyze_bodies(snapshot, issues, praises)
    _analyze_sketches(snapshot, issues, praises)
    if snapshot.doc is not None and not snapshot.doc.is_empty:
        issues.extend(_analyze_design(snapshot, intent))
        issues.extend(_analyze_goal(snapshot, intent))

    issues.sort(key=lambda i: (SEVERITY_ORDER.get(i.severity, 9), i.code))
    score = _score(snapshot, issues)

    analysis = Analysis(
        score=score,
        headline=_headline(score, snapshot),
        intent=intent,
        issues=issues,
        praise=praises,
        next_step=_next_step(snapshot, issues, intent),
        plan=_build_plan(snapshot, intent, issues),
    )
    analysis.summary = _summary(snapshot, analysis)
    return analysis
