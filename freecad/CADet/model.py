# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Plain data model shared by the live context builder, the analysis engine,
and the mentor panel.

This module deliberately has no FreeCAD or Qt imports so it can be unit-tested
with a normal Python interpreter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


SEVERITY_ORDER = {"critical": 0, "warn": 1, "info": 2, "good": 3}


@dataclass
class Issue:
    code: str
    severity: str
    title: str
    detail: str = ""
    fix: str = ""
    object_name: str = ""
    object_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "fix": self.fix,
            "object": self.object_label or self.object_name,
        }


@dataclass
class Praise:
    code: str
    text: str
    object_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "text": self.text, "object": self.object_name}


@dataclass
class Dimension:
    kind: str
    value: float
    name: str = ""


@dataclass
class BBox:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    xmin: float = 0.0
    ymin: float = 0.0
    zmin: float = 0.0
    xmax: float = 0.0
    ymax: float = 0.0
    zmax: float = 0.0

    @property
    def dims(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    @property
    def center(self) -> tuple[float, float, float]:
        return (
            (self.xmin + self.xmax) / 2.0,
            (self.ymin + self.ymax) / 2.0,
            (self.zmin + self.zmax) / 2.0,
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "z": round(self.z, 3),
            "center": [round(v, 3) for v in self.center],
        }


@dataclass
class SketchInfo:
    name: str
    label: str
    dof: int = 0
    fully_constrained: bool = False
    geometry_count: int = 0
    constraint_count: int = 0
    total_wires: int = 0
    closed_wires: int = 0
    open_wires: int = 0
    zero_length_edges: int = 0
    redundant: int = 0
    conflicting: int = 0
    malformed: int = 0
    partially_redundant: int = 0
    missing_coincident: int = 0
    missing_hv: int = 0
    missing_radius: int = 0
    missing_equality: int = 0
    attached: bool = False
    support: str = ""
    map_mode: str = ""
    bbox: BBox = field(default_factory=BBox)
    dimensions: list[Dimension] = field(default_factory=list)
    geometry_types: list[str] = field(default_factory=list)
    state: list[str] = field(default_factory=list)
    visible: bool = True
    helper: bool = False

    @property
    def is_empty(self) -> bool:
        return self.geometry_count == 0

    @property
    def is_closed(self) -> bool:
        return self.total_wires > 0 and self.open_wires == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "dof": self.dof,
            "fully_constrained": self.fully_constrained,
            "geometry_count": self.geometry_count,
            "constraint_count": self.constraint_count,
            "wires": {"total": self.total_wires, "closed": self.closed_wires, "open": self.open_wires},
            "conflicts": {
                "redundant": self.redundant,
                "conflicting": self.conflicting,
                "malformed": self.malformed,
                "partially_redundant": self.partially_redundant,
            },
            "missing": {
                "coincident": self.missing_coincident,
                "horizontal_vertical": self.missing_hv,
                "radius": self.missing_radius,
                "equality": self.missing_equality,
            },
            "attached": self.attached,
            "support": self.support,
            "map_mode": self.map_mode,
            "bbox": self.bbox.to_dict(),
            "dimensions": [{"kind": d.kind, "value": round(d.value, 3), "name": d.name} for d in self.dimensions],
            "geometry_types": self.geometry_types,
            "state": self.state,
            "helper": self.helper,
        }


@dataclass
class FeatureInfo:
    name: str
    label: str
    type_id: str
    state: list[str] = field(default_factory=list)
    valid: bool = True
    closed: bool = False
    volume: float = 0.0
    area: float = 0.0
    bbox: BBox = field(default_factory=BBox)
    is_tip: bool = False
    length: Optional[float] = None
    radius: Optional[float] = None
    diameter: Optional[float] = None

    @property
    def has_error(self) -> bool:
        lowered = [s.lower() for s in self.state]
        return any("error" in s or "invalid" in s for s in lowered) or not self.valid

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "label": self.label,
            "type": self.type_id,
            "state": self.state,
            "valid": self.valid,
            "closed": self.closed,
            "volume": round(self.volume, 3),
            "bbox": self.bbox.to_dict(),
            "is_tip": self.is_tip,
        }
        if self.length is not None:
            result["length"] = round(self.length, 3)
        if self.radius is not None:
            result["radius"] = round(self.radius, 3)
        if self.diameter is not None:
            result["diameter"] = round(self.diameter, 3)
        return result


@dataclass
class BodyInfo:
    name: str
    label: str
    tip: str = ""
    features: list[FeatureInfo] = field(default_factory=list)
    sketches: list[SketchInfo] = field(default_factory=list)
    shape_valid: bool = True
    shape_closed: bool = False
    volume: float = 0.0
    bbox: BBox = field(default_factory=BBox)
    state: list[str] = field(default_factory=list)

    @property
    def feature_count(self) -> int:
        return len(self.features)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.features if f.has_error)

    @property
    def has_solid(self) -> bool:
        return self.feature_count > 0 and self.volume > 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "tip": self.tip,
            "feature_count": self.feature_count,
            "error_count": self.error_count,
            "shape_valid": self.shape_valid,
            "shape_closed": self.shape_closed,
            "volume": round(self.volume, 3),
            "bbox": self.bbox.to_dict(),
            "state": self.state,
            "features": [f.to_dict() for f in self.features],
            "sketches": [s.to_dict() for s in self.sketches],
        }


@dataclass
class SelectionInfo:
    object_name: str = ""
    object_label: str = ""
    object_type: str = ""
    subelements: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.object_name

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object_label or self.object_name,
            "type": self.object_type,
            "subelements": self.subelements,
        }


@dataclass
class DocumentInfo:
    name: str
    label: str
    file_name: str = ""
    modified: bool = False
    object_count: int = 0
    bodies: list[BodyInfo] = field(default_factory=list)
    sketches: list[SketchInfo] = field(default_factory=list)
    features: list[FeatureInfo] = field(default_factory=list)
    imported_objects: list[str] = field(default_factory=list)
    workbench: str = ""
    edit_mode: str = ""
    active_object: str = ""
    selection: SelectionInfo = field(default_factory=SelectionInfo)
    units: str = "mm"

    @property
    def is_empty(self) -> bool:
        return self.object_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "file_name": self.file_name,
            "modified": self.modified,
            "object_count": self.object_count,
            "workbench": self.workbench,
            "edit_mode": self.edit_mode,
            "active_object": self.active_object,
            "selection": self.selection.to_dict(),
            "units": self.units,
            "imported_objects": self.imported_objects,
            "bodies": [b.to_dict() for b in self.bodies],
            "sketches": [s.to_dict() for s in self.sketches],
            "features": [f.to_dict() for f in self.features],
        }


@dataclass
class Snapshot:
    doc: Optional[DocumentInfo] = None
    warnings: list[str] = field(default_factory=list)
    goal: str = ""

    @property
    def has_doc(self) -> bool:
        return self.doc is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "document": self.doc.to_dict() if self.doc else None,
            "warnings": self.warnings,
            "goal": self.goal,
        }


@dataclass
class Intent:
    label: str = "part"
    description: str = "an unspecified mechanical part"
    confidence: float = 0.3
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "description": self.description,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
        }


@dataclass
class Analysis:
    score: int = 0
    headline: str = ""
    intent: Intent = field(default_factory=Intent)
    issues: list[Issue] = field(default_factory=list)
    praise: list[Praise] = field(default_factory=list)
    next_step: str = ""
    plan: list[str] = field(default_factory=list)
    summary: str = ""

    @property
    def critical(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "critical"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warn"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "headline": self.headline,
            "intent": self.intent.to_dict(),
            "issues": [i.to_dict() for i in self.issues],
            "praise": [p.to_dict() for p in self.praise],
            "next_step": self.next_step,
            "plan": self.plan,
            "summary": self.summary,
        }
