# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Infer what the user is trying to build from names, features and proportions.

The goal is not to be certain. The goal is to make the mentor feel like it is
paying attention: "this looks like a thin mounting plate with four holes" is
useful even when the label is missing.
"""

from __future__ import annotations

from .model import Intent, Snapshot


KEYWORDS = (
    ("phone stand", "phone stand", "a stand that holds a phone"),
    ("headphone", "headphone stand", "a stand that holds headphones"),
    ("bracket", "bracket", "a bracket that connects or supports something"),
    ("enclosure", "enclosure", "an enclosure that houses hardware"),
    ("housing", "enclosure", "an enclosure that houses hardware"),
    ("case", "enclosure", "an enclosure that houses hardware"),
    ("box", "box", "a box or container"),
    ("lid", "lid", "a lid or cover"),
    ("cover", "cover", "a cover or lid"),
    ("plate", "plate", "a flat plate"),
    ("panel", "panel", "a flat panel"),
    ("flange", "flange", "a flange for a pipe or joint"),
    ("gear", "gear", "a gear or toothed wheel"),
    ("sprocket", "sprocket", "a sprocket or toothed wheel"),
    ("shaft", "shaft", "a shaft or axle"),
    ("axle", "shaft", "a shaft or axle"),
    ("pin", "pin", "a pin or shaft"),
    ("mount", "mount", "a mount or holder"),
    ("holder", "mount", "a mount or holder"),
    ("adapter", "adapter", "an adapter"),
    ("fixture", "fixture", "a fixture or jig"),
    ("jig", "fixture", "a fixture or jig"),
    ("knob", "knob", "a knob or handle"),
    ("handle", "handle", "a handle"),
    ("wheel", "wheel", "a wheel"),
    ("pulley", "pulley", "a pulley"),
    ("hinge", "hinge", "a hinge"),
    ("clip", "clip", "a clip"),
    ("clamp", "clamp", "a clamp"),
    ("stand", "stand", "a stand"),
)


def _collect_text(snapshot: Snapshot) -> str:
    doc = snapshot.doc
    if not doc:
        return ""
    parts: list[str] = [doc.label, doc.name]
    for body in doc.bodies:
        parts.extend([body.label, body.name, body.tip])
        for feature in body.features:
            parts.extend([feature.label, feature.name, feature.type_id])
        for sketch in body.sketches:
            parts.extend([sketch.label, sketch.name])
    for sketch in doc.sketches:
        parts.extend([sketch.label, sketch.name])
    for feature in doc.features:
        parts.extend([feature.label, feature.name, feature.type_id])
    return " ".join(parts).lower()


def _keyword_match(text: str) -> tuple[str, str, list[str]]:
    matches: list[tuple[str, str]] = []
    for keyword, label, description in KEYWORDS:
        if keyword in text:
            matches.append((label, description))
    if not matches:
        return "", "", []
    # Prefer the longest keyword (more specific).
    matches.sort(key=lambda item: len(item[0]), reverse=True)
    labels = [m[0] for m in matches]
    unique = list(dict.fromkeys(labels))
    return unique[0], matches[0][1], unique[:3]


def _all_bboxes(snapshot: Snapshot):
    doc = snapshot.doc
    if not doc:
        return []
    boxes = []
    for body in doc.bodies:
        if body.volume > 0:
            boxes.append(body.bbox)
    for feature in doc.features:
        if feature.volume > 0:
            boxes.append(feature.bbox)
    return boxes


def _shape_hint(snapshot: Snapshot) -> tuple[str, str, float, list[str]]:
    boxes = _all_bboxes(snapshot)
    if not boxes:
        return "", "", 0.0, []

    box = max(boxes, key=lambda b: b.x * b.y * b.z)
    dims = sorted([d for d in box.dims if d > 0.01])
    if not dims:
        return "", "", 0.0, []
    small, mid, large = dims[0], dims[len(dims) // 2], dims[-1]
    evidence = [f"bounding box {box.x:.1f} x {box.y:.1f} x {box.z:.1f} mm"]

    if large <= 0:
        return "", "", 0.0, evidence

    ratio = small / large
    if ratio < 0.12:
        return "plate", "a flat plate or panel", 0.65, evidence
    if ratio < 0.35 and mid / large > 0.55:
        return "plate", "a flat plate or panel", 0.5, evidence
    if max(dims) / max(small, 0.001) < 1.45:
        return "block", "a compact block", 0.55, evidence
    if abs(box.x - box.y) / max(box.x, box.y, 0.001) < 0.08 and box.z > 1.8 * box.x:
        return "shaft", "a round or cylindrical part", 0.55, evidence

    doc = snapshot.doc
    if doc:
        volume = sum(b.volume for b in doc.bodies)
        box_volume = box.x * box.y * box.z
        if box_volume > 0 and 0 < volume / box_volume < 0.32:
            return "enclosure", "a hollow enclosure or shell", 0.6, evidence + ["low material fill in the bounding box"]

    return "", "", 0.0, evidence


def _feature_hint(snapshot: Snapshot) -> tuple[str, str, float, list[str]]:
    doc = snapshot.doc
    if not doc:
        return "", "", 0.0, []
    types = [f.type_id for f in doc.features]
    for body in doc.bodies:
        types.extend(f.type_id for f in body.features)
    lowered = " ".join(types).lower()
    if "revolution" in lowered or "groove" in lowered:
        return "shaft", "a turned or cylindrical part", 0.55, ["revolution feature in the tree"]
    if "hole" in lowered:
        return "bracket", "a drilled or bolted part", 0.35, ["hole feature in the tree"]
    if "shell" in lowered:
        return "enclosure", "a hollow enclosure or shell", 0.55, ["shell feature in the tree"]
    return "", "", 0.0, []


def infer_intent(snapshot: Snapshot) -> Intent:
    doc = snapshot.doc
    if not doc:
        return Intent(
            label="nothing yet",
            description="no open document",
            confidence=0.0,
            evidence=[],
        )

    text = _collect_text(snapshot)
    goal = (snapshot.goal or "").strip()
    goal_label, goal_description, goal_matches = _keyword_match(goal.lower()) if goal else ("", "", [])
    key_label, key_description, key_matches = _keyword_match(text)
    shape_label, shape_description, shape_confidence, shape_evidence = _shape_hint(snapshot)
    feature_label, feature_description, feature_confidence, feature_evidence = _feature_hint(snapshot)

    evidence: list[str] = []
    if key_matches:
        evidence.append("name or label mentions " + ", ".join(key_matches))
    evidence.extend(shape_evidence)
    evidence.extend(feature_evidence)

    # The user's stated goal is the strongest signal of intent.
    if goal:
        evidence.insert(0, "your stated goal: " + goal)
        if goal_label:
            confidence = 0.88
            if shape_label and shape_label == goal_label:
                confidence = 0.97
                evidence.append("shape agrees with the goal")
            elif shape_label and shape_label != goal_label:
                confidence = 0.8
                evidence.append(f"shape also looks like a {shape_label}")
            return Intent(
                label=goal_label,
                description=goal_description,
                confidence=confidence,
                evidence=evidence,
            )
        return Intent(
            label="custom",
            description=goal,
            confidence=0.55,
            evidence=evidence,
        )

    # A name is strong evidence. Geometry is a useful tie-breaker.
    if key_label:
        confidence = 0.8
        if shape_label and shape_label == key_label:
            confidence = 0.95
            evidence.append("shape agrees with the name")
        elif shape_label and shape_label != key_label:
            confidence = 0.7
            evidence.append(f"shape also looks like a {shape_label}")
        return Intent(
            label=key_label,
            description=key_description,
            confidence=confidence,
            evidence=evidence,
        )

    if shape_label and feature_label and shape_label == feature_label:
        return Intent(
            label=shape_label,
            description=feature_description or shape_description,
            confidence=min(0.85, shape_confidence + feature_confidence),
            evidence=evidence,
        )

    if shape_label:
        return Intent(
            label=shape_label,
            description=shape_description,
            confidence=shape_confidence,
            evidence=evidence,
        )

    if feature_label:
        return Intent(
            label=feature_label,
            description=feature_description,
            confidence=feature_confidence,
            evidence=evidence,
        )

    if doc.sketches or doc.bodies:
        return Intent(
            label="part",
            description="an in-progress mechanical part",
            confidence=0.3,
            evidence=evidence,
        )

    return Intent(
        label="empty document",
        description="nothing modeled yet",
        confidence=0.1,
        evidence=[],
    )
