# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Local mentor responses.

The deterministic mentor must be useful with the network unplugged. The AI
client is optional; this module is the floor, not a fallback stub.
"""

from __future__ import annotations

from . import guide as app_guide
from .model import Analysis, Snapshot


def _fmt(value: float, digits: int = 1) -> str:
    text = f"{value:.{digits}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _label(obj) -> str:
    return obj.label or obj.name


def _dims_text(snapshot: Snapshot) -> str:
    doc = snapshot.doc
    if not doc:
        return "No model yet."
    lines: list[str] = []
    for body in doc.bodies:
        dims = body.bbox.dims
        if body.has_solid:
            lines.append(
                f"{_label(body)}: {_fmt(dims[0])} x {_fmt(dims[1])} x {_fmt(dims[2])} mm, "
                f"volume {_fmt(body.volume, 0)} mm3"
            )
    for feature in doc.features:
        if feature.volume > 0:
            dims = feature.bbox.dims
            lines.append(
                f"{_label(feature)}: {_fmt(dims[0])} x {_fmt(dims[1])} x {_fmt(dims[2])} mm"
            )
    if not lines:
        for sketch in doc.sketches:
            dims = sketch.bbox.dims
            if max(dims) > 0:
                lines.append(f"{_label(sketch)} (sketch): {_fmt(dims[0])} x {_fmt(dims[1])} x {_fmt(dims[2])} mm")
    return "\n".join(lines) if lines else "Nothing measured yet."


def _sketch_lines(snapshot: Snapshot) -> list[str]:
    doc = snapshot.doc
    if not doc:
        return []
    lines = []
    for sketch in doc.sketches:
        status = "fully constrained" if sketch.fully_constrained else f"{sketch.dof} DoF left"
        profile = "closed" if sketch.is_closed else f"{sketch.open_wires} open wire(s)"
        lines.append(f"{_label(sketch)}: {sketch.geometry_count} geometry, {sketch.constraint_count} constraints, {status}, {profile}.")
    return lines


def _critical_lines(analysis: Analysis) -> list[str]:
    return [f"- {i.title}. {i.fix}".strip() for i in analysis.critical[:5]]


def _warning_lines(analysis: Analysis) -> list[str]:
    return [f"- {i.title}. {i.fix}".strip() for i in analysis.warnings[:5]]


def _printability(snapshot: Snapshot, analysis: Analysis) -> str:
    doc = snapshot.doc
    if not doc:
        return "There is nothing to print yet."
    solids = [b for b in doc.bodies if b.has_solid]
    if not solids:
        return "No solid yet. Finish the profile and turn it into a solid before thinking about printing."
    lines = []
    for body in solids:
        issues = []
        if not body.shape_valid:
            issues.append("invalid topology")
        if not body.shape_closed:
            issues.append("not watertight")
        fill = body.volume / (body.bbox.x * body.bbox.y * body.bbox.z) if body.bbox.x * body.bbox.y * body.bbox.z > 0 else 0
        if 0 < fill < 0.05:
            issues.append("very little material in the bounding box, so check wall thickness")
        if not issues:
            lines.append(f"{_label(body)} is a closed, valid solid. It should slice cleanly.")
        else:
            lines.append(f"{_label(body)}: " + ", ".join(issues) + ".")
    thin = [i for i in analysis.issues if i.code in ("thin_pad", "tiny_radius", "small_hole", "low_fill")]
    if thin:
        lines.append("Thin features to check: " + "; ".join(i.title for i in thin[:3]) + ".")
    lines.append("Print orientation is a design decision: put the largest flat face on the bed unless it creates supports on a critical surface.")
    return "\n".join(lines)


def _constraints_help(snapshot: Snapshot) -> str:
    doc = snapshot.doc
    if not doc:
        return "Open a sketch first, then I can read its constraints."
    if not doc.sketches:
        return "There is no sketch in this document yet. Create one on a principal plane."
    lines = []
    for sketch in doc.sketches:
        name = _label(sketch)
        if sketch.conflicting:
            lines.append(f"{name}: delete the {sketch.conflicting} conflicting constraint(s) first. Do not add more until the solver is calm.")
        elif sketch.fully_constrained:
            lines.append(f"{name}: fully constrained. Leave it alone and pad it.")
        else:
            hint = []
            if sketch.missing_coincident:
                hint.append(f"join {sketch.missing_coincident} endpoint pair(s) with Coincident")
            if sketch.missing_hv:
                hint.append(f"make {sketch.missing_hv} line(s) Horizontal/Vertical")
            if sketch.missing_radius:
                hint.append(f"dimension {sketch.missing_radius} radius/diameter")
            if sketch.missing_equality:
                hint.append("use Equal where lengths are meant to match")
            if not hint:
                hint.append("add coincident, horizontal/vertical, then dimensional constraints")
            lines.append(f"{name}: {sketch.dof} DoF left. Add constraints: " + "; ".join(hint) + ".")
    return "\n".join(lines)


def _python_help(snapshot: Snapshot) -> str:
    doc = snapshot.doc
    if doc is None:
        return "Open a document first, then select the object or subelement you want to script."
    lines = [
        "Python access path for what you are looking at:",
        "",
        "    import FreeCAD as App",
        "    doc = App.ActiveDocument",
    ]
    if not doc.selection.is_empty:
        selection = doc.selection
        name = selection.object_name
        type_name = selection.object_type
        lines.append(f'    obj = doc.getObject("{name}")  # {type_name}')
        if selection.subelements:
            lines.append(f"    # selected: {', '.join(selection.subelements)}")
            sub = selection.subelements[0]
            try:
                if sub.startswith("Face"):
                    lines.append(f"    face = obj.Shape.Faces[{int(sub[4:]) - 1}]")
                elif sub.startswith("Edge"):
                    lines.append(f"    edge = obj.Shape.Edges[{int(sub[4:]) - 1}]")
                elif sub.startswith("Vertex"):
                    lines.append(f"    vertex = obj.Shape.Vertexes[{int(sub[6:]) - 1}]")
            except Exception:
                pass
        if "Sketch" in type_name:
            lines.extend([
                "    sketch = obj",
                "    # sketch.Geometry, sketch.Constraints, sketch.addConstraint(...)",
            ])
        elif "Body" in type_name:
            lines.extend([
                "    body = obj",
                "    tip = body.Tip",
                "    shape = body.Shape",
            ])
        else:
            lines.extend([
                "    shape = obj.Shape",
                "    # shape.Edges, shape.Faces, shape.Vertexes",
            ])
    else:
        lines.extend([
            '    body = doc.getObject("Body")  # use your body name',
            "    shape = body.Shape",
            "    # select a face or edge in the 3D view for an exact path",
        ])
    lines.extend([
        "",
        "Rules that save time:",
        "- Python indices are 0-based; the UI is 1-based (Face3 becomes Faces[2]).",
        "- call doc.recompute() after changing a feature.",
        "- look up objects by Name, not Label.",
        "- if you script a multi-step edit, wrap it in a transaction.",
    ])
    return "\n".join(lines)


def _errors(snapshot: Snapshot, analysis: Analysis) -> str:
    if not analysis.critical:
        return "I don't see a structural error right now. The warnings are the things that will bite later."
    lines = ["Fix these in order. Downstream features inherit the first failure:"]
    for issue in analysis.critical[:6]:
        lines.append(f"- {issue.title} - {issue.fix}")
    return "\n".join(lines)


def _help_text() -> str:
    return (
        "I watch the live document and review it like a senior mechanical engineer.\n"
        "Ask me things like:\n"
        "- What am I building?\n"
        "- Why is my sketch not constrained?\n"
        "- Is this printable?\n"
        "- What should I do next?\n"
        "- Review this model.\n"
        "- What are the dimensions?\n"
        "I can also explain a failing feature, a thin wall, a hole size, or a missing fillet.\n"
        "Ask me how to use LearnCad too:\n"
        "- How do I draw a rectangle?\n"
        "- How do I pad a sketch?\n"
        "- Where is the Hole tool?\n"
        "- How do I constrain this sketch?\n"
        "- How do I export or render?\n"
        "- How do I move the 3D view?"
    )


_MODEL_QUESTION_MARKERS = (
    "what model are you",
    "which model are you",
    "what ai model",
    "which ai model",
    "what model do you use",
    "what model is this",
    "are you an ai",
    "are you chatgpt",
    "are you deepseek",
    "are you gpt",
    "what llm",
    "which llm",
    "who made you",
    "what provider",
    "what ai are you",
    "what version are you",
    "deepseek",
    "openai",
    "chatgpt",
    "gpt-4",
    "claude",
    "llama",
)


def _is_model_question(question: str) -> bool:
    q = (question or "").strip().lower()
    return any(marker in q for marker in _MODEL_QUESTION_MARKERS)


def answer(question: str, snapshot: Snapshot, analysis: Analysis) -> str:
    q = (question or "").strip().lower()
    doc = snapshot.doc

    if not q:
        return "I'm watching. Tell me what you're trying to make, or ask me to review what is on screen."

    if _is_model_question(q):
        return (
            "I'm LearnCad's built-in CAD coach. I can't discuss the model behind me, "
            "but I can help with your sketch, constraints, or next feature."
        )

    if any(word in q for word in ("hello", "hi ", "hey", "good morning", "good evening")) and len(q) < 20:
        return "I'm here. I can see the active document. Tell me what the part is for and I'll review it against that."

    if any(phrase in q for phrase in ("what can you do", "help me", "how do you work", "commands", "what is learncad", "how does learncad work")):
        return _help_text()

    if any(word in q for word in ("python", "script", "macro", "api", "code")):
        return _python_help(snapshot)

    if app_guide.looks_like_howto(q):
        return app_guide.answer(q)

    if doc is None:
        return "No document is open. Create one (Ctrl+N), add a Body, and I'll start reading the model."

    if doc.is_empty:
        return (
            "The document is empty. Start with a Body and a sketch on a principal plane. "
            "Tell me what the part is for, and I'll keep the review focused on that."
        )

    if any(phrase in q for phrase in ("what am i building", "what is this", "what does this look like", "intent", "recognize", "recognise", "my goal", "trying to build")):
        intent = analysis.intent
        evidence = "; ".join(intent.evidence[:3]) if intent.evidence else "the current geometry"
        if snapshot.goal:
            return f"You told me your goal is: {snapshot.goal}. The model reads as {intent.description} (confidence {intent.confidence:.0%}). I'm reading that from {evidence}."
        return f"This looks like {intent.description} (confidence {intent.confidence:.0%}). I'm reading that from {evidence}."

    if ("why" in q or "how" in q) and any(word in q for word in ("constrain", "dof", "degree", "fully", "lock")):
        return _constraints_help(snapshot)

    if any(phrase in q for phrase in ("next", "what should i do", "where do i go", "what now", "proceed")):
        return f"Next: {analysis.next_step}\n\nWhy: {analysis.headline}"

    if any(phrase in q for phrase in ("review", "rate", "how am i", "how is it", "good", "grade", "score", "audit")):
        return review_report(snapshot, analysis)

    if any(word in q for word in ("print", "printable", "slice", "slicer", "fdm", "3d print")):
        return _printability(snapshot, analysis)

    if any(phrase in q for phrase in ("dimension", "size", "measure", "how big", "how tall", "how wide", "bounding")):
        return _dims_text(snapshot)

    if any(word in q for word in ("hole", "bolt", "screw", "clearance", "fastener")):
        holes = [f for b in doc.bodies for f in b.features if "hole" in f.type_id.lower()]
        if not holes:
            return "No Hole feature yet. For M3 screws, use 3.2-3.4 mm clearance, or 2.5 mm for a self-tapping screw in plastic. Keep at least one diameter of material around the hole."
        lines = ["Hole features I can see:"]
        for hole in holes:
            diameter = f"{_fmt(hole.diameter, 2)} mm" if hole.diameter else "diameter not exposed"
            lines.append(f"- {_label(hole)}: {diameter}")
        lines.append("For printed holes, expect the slicer to undersize them by 0.1-0.3 mm. Drill or ream critical fits.")
        return "\n".join(lines)

    if any(word in q for word in ("python", "script", "macro", "api", "code")):
        return _python_help(snapshot)

    if any(word in q for word in ("error", "wrong", "broken", "fix", "fail", "red", "invalid")):
        return _errors(snapshot, analysis)

    if any(word in q for word in ("fillet", "chamfer", "round", "edge")):
        return (
            "Fillets and chamfers are finishing features. Add them after the functional geometry: holes, pockets, mating faces. "
            "For FDM, 0.5-2 mm on external corners is usually enough. Do not fillet faces that must sit flush. "
            "If a fillet fails, the radius is usually larger than the local edge can support."
        )

    if any(word in q for word in ("wall", "thickness", "thin", "strong", "strength")):
        return (
            "For FDM in PLA/PETG, 1.2-2.0 mm walls are a safe starting point (3-5 perimeters). "
            "Thin walls fail by tearing or warping; thick walls add print time and internal stress. "
            "Put material along load paths and keep pockets away from bolt holes."
        )

    if "why" in q or "explain" in q:
        if analysis.critical:
            issue = analysis.critical[0]
            return f"{issue.title}. {issue.detail} Fix: {issue.fix}"
        if analysis.warnings:
            issue = analysis.warnings[0]
            return f"{issue.title}. {issue.detail} Fix: {issue.fix}"
        return analysis.headline + " " + analysis.summary

    if any(word in q for word in ("sketch", "constraint", "profile", "dof")):
        lines = _sketch_lines(snapshot)
        return "\n".join(lines) if lines else "No sketch to inspect yet."

    if any(word in q for word in ("body", "tree", "feature", "model")):
        bodies = doc.bodies
        if not bodies:
            return "There is no Body. This is either an empty document or loose Part geometry."
        lines = []
        for body in bodies:
            lines.append(
                f"{_label(body)}: {body.feature_count} feature(s), tip {body.tip or 'not set'}, "
                f"{'valid' if body.shape_valid else 'invalid'}, {'closed' if body.shape_closed else 'open'}."
            )
        return "\n".join(lines)

    return (
        f"{analysis.headline} The most useful thing right now: {analysis.next_step}\n"
        "Ask me about constraints, dimensions, printability, holes, walls, or the next feature."
    )


def review_report(snapshot: Snapshot, analysis: Analysis) -> str:
    doc = snapshot.doc
    if doc is None:
        return "No document is open, so there is nothing to review."
    if doc.is_empty:
        return "The document is empty. Create a body and a sketch, then ask me for a review."

    lines = [
        "MODEL REVIEW",
        f"Score: {analysis.score}/100 - {analysis.headline}",
    ]
    if snapshot.goal:
        lines.append(f"Goal: {snapshot.goal}")
    lines.extend([
        f"Intent: {analysis.intent.description} (confidence {analysis.intent.confidence:.0%})",
        "",
        "DIMENSIONS",
        _dims_text(snapshot),
        "",
        "SKETCHES",
    ])
    sketch_lines = _sketch_lines(snapshot)
    lines.extend(sketch_lines or ["No sketches."])
    lines.extend(["", "BODIES"])
    if doc.bodies:
        for body in doc.bodies:
            lines.append(
                f"- {_label(body)}: {body.feature_count} feature(s), tip {body.tip or 'not set'}, "
                f"{'valid' if body.shape_valid else 'invalid'} {'closed' if body.shape_closed else 'open'} solid, "
                f"volume {_fmt(body.volume, 0)} mm3."
            )
    else:
        lines.append("No bodies.")

    if analysis.critical:
        lines.extend(["", "CRITICAL"])
        lines.extend(_critical_lines(analysis))
    if analysis.warnings:
        lines.extend(["", "WARNINGS"])
        lines.extend(_warning_lines(analysis))
    if analysis.praise:
        lines.extend(["", "WHAT IS WORKING"])
        lines.extend(f"- {p.text}" for p in analysis.praise[:6])
    lines.extend(["", "NEXT STEP", analysis.next_step])
    if analysis.plan:
        lines.extend(["", "SUGGESTED SEQUENCE"])
        lines.extend(f"{index}. {step}" for index, step in enumerate(analysis.plan, 1))
    return "\n".join(lines)
