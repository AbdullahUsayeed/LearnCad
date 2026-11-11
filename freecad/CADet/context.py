# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Read the live FreeCAD document into a plain Snapshot.

The rest of CADet never talks to FreeCAD directly. Keeping the translation in
one place makes the mentor testable and keeps the UI thread out of geometry
code.
"""

from __future__ import annotations

from typing import Any, Optional

import FreeCAD as App

try:  # FreeCADCmd has no GUI
    import FreeCADGui as Gui  # type: ignore
except Exception:  # pragma: no cover - depends on the host
    Gui = None


from .model import (
    BBox,
    BodyInfo,
    Dimension,
    DocumentInfo,
    FeatureInfo,
    SelectionInfo,
    SketchInfo,
    Snapshot,
)


MAX_OBJECTS = 400
MAX_GEOMETRY = 200
MAX_CONSTRAINTS = 200
DIMENSION_TYPES = {"Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle", "AngleViaPoint"}


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _bbox(shape) -> BBox:
    if shape is None:
        return BBox()
    try:
        if shape.isNull():
            return BBox()
    except Exception:
        return BBox()
    try:
        bb = shape.BoundBox
        return BBox(
            x=float(bb.XLength),
            y=float(bb.YLength),
            z=float(bb.ZLength),
            xmin=float(bb.XMin),
            ymin=float(bb.YMin),
            zmin=float(bb.ZMin),
            xmax=float(bb.XMax),
            ymax=float(bb.YMax),
            zmax=float(bb.ZMax),
        )
    except Exception:
        return BBox()


def _shape_facts(obj) -> dict[str, Any]:
    shape = _safe(lambda: obj.Shape, None)
    if shape is None:
        return {"valid": True, "closed": False, "volume": 0.0, "area": 0.0, "bbox": BBox()}
    return {
        "valid": bool(_safe(lambda: shape.isValid(), True)),
        "closed": bool(_safe(lambda: shape.isClosed(), False)),
        "volume": float(_safe(lambda: shape.Volume, 0.0) or 0.0),
        "area": float(_safe(lambda: shape.Area, 0.0) or 0.0),
        "bbox": _bbox(shape),
    }


def _fmt_support(support) -> str:
    if not support:
        return ""
    pieces: list[str] = []
    try:
        for item in support:
            if isinstance(item, (tuple, list)) and item:
                ref = item[0]
                sub = item[1] if len(item) > 1 else ""
                name = getattr(ref, "Label", None) or getattr(ref, "Name", None) or str(ref)
                pieces.append(f"{name}{(':' + str(sub)) if sub else ''}")
            else:
                pieces.append(str(item))
    except Exception:
        return str(support)
    return ", ".join(pieces)


def _sketch_info(obj) -> SketchInfo:
    # FreeCAD only fills the Missing* lists when these detectors are called.
    # Run them on the full snapshot, never on the fast polling path.
    _safe(lambda: obj.detectMissingPointOnPointConstraints(0.3, False))
    _safe(lambda: obj.detectMissingVerticalHorizontalConstraints(0.1))
    _safe(lambda: obj.detectMissingEqualityConstraints(0.1))
    shape = _safe(lambda: obj.Shape, None)
    wires = list(_safe(lambda: list(shape.Wires), []) or [])
    edges = list(_safe(lambda: list(shape.Edges), []) or [])
    dimensions: list[Dimension] = []
    constraints = list(_safe(lambda: list(obj.Constraints), []) or [])
    for constraint in constraints[:MAX_CONSTRAINTS]:
        kind = str(_safe(lambda: constraint.Type, "") or "")
        if kind in DIMENSION_TYPES:
            value = _safe(lambda: float(constraint.Value), None)
            if value is not None:
                dimensions.append(Dimension(kind=kind, value=value, name=str(_safe(lambda: constraint.Name, "") or "")))

    support = _safe(lambda: getattr(obj, "AttachmentSupport", None), None)
    if support is None:
        support = _safe(lambda: getattr(obj, "Support", None), None)

    return SketchInfo(
        name=str(_safe(lambda: obj.Name, "") or ""),
        label=str(_safe(lambda: obj.Label, "") or ""),
        dof=int(_safe(lambda: obj.DoF, 0) or 0),
        fully_constrained=bool(_safe(lambda: obj.FullyConstrained, False)),
        geometry_count=int(_safe(lambda: obj.GeometryCount, 0) or 0),
        constraint_count=int(_safe(lambda: obj.ConstraintCount, 0) or 0),
        total_wires=len(wires),
        closed_wires=sum(1 for w in wires if _safe(lambda: w.isClosed(), False)),
        open_wires=sum(1 for w in wires if not _safe(lambda: w.isClosed(), False)),
        zero_length_edges=sum(1 for e in edges if float(_safe(lambda: e.Length, 0.0) or 0.0) < 1e-6),
        redundant=len(_safe(lambda: list(obj.RedundantConstraints), []) or []),
        conflicting=len(_safe(lambda: list(obj.ConflictingConstraints), []) or []),
        malformed=len(_safe(lambda: list(obj.MalformedConstraints), []) or []),
        partially_redundant=len(_safe(lambda: list(obj.PartiallyRedundantConstraints), []) or []),
        missing_coincident=len(_safe(lambda: list(obj.MissingPointOnPointConstraints), []) or []),
        missing_hv=len(_safe(lambda: list(obj.MissingVerticalHorizontalConstraints), []) or []),
        missing_radius=len(_safe(lambda: list(obj.MissingRadiusConstraints), []) or []),
        missing_equality=len(_safe(lambda: list(obj.MissingLineEqualityConstraints), []) or []),
        attached=bool(support),
        support=_fmt_support(support),
        map_mode=str(_safe(lambda: obj.MapMode, "") or ""),
        bbox=_bbox(shape),
        dimensions=dimensions,
        geometry_types=[str(_safe(lambda: g.TypeId, "") or "") for g in list(_safe(lambda: obj.Geometry, []) or [])[:MAX_GEOMETRY]],
        state=[str(s) for s in (_safe(lambda: list(obj.State), []) or [])],
        visible=bool(_safe(lambda: obj.ViewObject.Visibility, True)),
        helper=bool(_safe(lambda: getattr(obj, "LearnCadHelper", False), False)),
    )


def _feature_info(obj, is_tip: bool = False) -> FeatureInfo:
    facts = _shape_facts(obj)
    type_id = str(_safe(lambda: obj.TypeId, "") or "")
    lowered = type_id.lower()
    length = None
    if "pad" in lowered or "pocket" in lowered:
        length = _safe(lambda: float(obj.Length), None)
    radius = None
    if "fillet" in lowered or "chamfer" in lowered or "revolution" in lowered:
        radius = _safe(lambda: float(obj.Radius), None)
    diameter = None
    if "hole" in lowered:
        diameter = _safe(lambda: float(obj.Diameter), None)

    return FeatureInfo(
        name=str(_safe(lambda: obj.Name, "") or ""),
        label=str(_safe(lambda: obj.Label, "") or ""),
        type_id=type_id,
        state=[str(s) for s in (_safe(lambda: list(obj.State), []) or [])],
        valid=bool(facts["valid"]),
        closed=bool(facts["closed"]),
        volume=float(facts["volume"]),
        area=float(facts["area"]),
        bbox=facts["bbox"],
        is_tip=is_tip,
        length=float(length) if length is not None else None,
        radius=float(radius) if radius is not None else None,
        diameter=float(diameter) if diameter is not None else None,
    )


def _body_info(obj) -> BodyInfo:
    facts = _shape_facts(obj)
    tip = _safe(lambda: obj.Tip, None)
    tip_name = str(_safe(lambda: tip.Name, "") or "") if tip else ""
    group = list(_safe(lambda: list(obj.Group), []) or [])
    features: list[FeatureInfo] = []
    sketches: list[SketchInfo] = []
    for child in group:
        type_id = str(_safe(lambda: child.TypeId, "") or "")
        if type_id == "Sketcher::SketchObject":
            sketches.append(_sketch_info(child))
        else:
            features.append(_feature_info(child, is_tip=(child.Name == tip_name)))

    return BodyInfo(
        name=str(_safe(lambda: obj.Name, "") or ""),
        label=str(_safe(lambda: obj.Label, "") or ""),
        tip=tip_name,
        features=features,
        sketches=sketches,
        shape_valid=bool(facts["valid"]),
        shape_closed=bool(facts["closed"]),
        volume=float(facts["volume"]),
        bbox=facts["bbox"],
        state=[str(s) for s in (_safe(lambda: list(obj.State), []) or [])],
    )


def _selection() -> SelectionInfo:
    if Gui is None:
        return SelectionInfo()
    try:
        selection = Gui.Selection.getSelectionEx()
    except Exception:
        return SelectionInfo()
    if not selection:
        return SelectionInfo()
    first = selection[0]
    obj = getattr(first, "Object", None)
    if obj is None:
        return SelectionInfo()
    return SelectionInfo(
        object_name=str(getattr(obj, "Name", "") or ""),
        object_label=str(getattr(obj, "Label", "") or ""),
        object_type=str(getattr(obj, "TypeId", "") or ""),
        subelements=[str(s) for s in (getattr(first, "SubElementNames", []) or [])],
    )


def _edit_object() -> Optional[Any]:
    if Gui is None:
        return None
    try:
        gdoc = Gui.activeDocument()
        if gdoc is None:
            return None
        edit = gdoc.getInEdit()
        if edit is None:
            return None
        if isinstance(edit, (tuple, list)):
            edit = edit[0] if edit else None
        return getattr(edit, "Object", edit)
    except Exception:
        return None


def _workbench_name() -> str:
    if Gui is None:
        return ""
    try:
        wb = Gui.activeWorkbench()
        return str(getattr(wb, "MenuText", None) or type(wb).__name__)
    except Exception:
        return ""


def _units() -> str:
    try:
        return str(App.Units.getUserPreferred() or "mm")
    except Exception:
        return "mm"


def build_snapshot(goal: str = "") -> Snapshot:
    doc = App.ActiveDocument
    if doc is None:
        return Snapshot(doc=None, goal=goal)

    warnings: list[str] = []
    try:
        objects = list(doc.Objects)[:MAX_OBJECTS]
    except Exception as exc:
        return Snapshot(doc=None, warnings=[f"Could not read the document: {exc}"], goal=goal)

    if len(list(doc.Objects)) > MAX_OBJECTS:
        warnings.append(f"Only the first {MAX_OBJECTS} objects are being watched.")

    bodies: list[BodyInfo] = []
    sketches: list[SketchInfo] = []
    features: list[FeatureInfo] = []
    imported: list[str] = []
    body_feature_names: set[str] = set()

    for obj in objects:
        try:
            type_id = str(getattr(obj, "TypeId", "") or "")
            if type_id == "PartDesign::Body":
                bodies.append(_body_info(obj))
                group = _safe(lambda: list(obj.Group), []) or []
                body_feature_names.update(str(getattr(c, "Name", "")) for c in group)
            elif type_id == "Sketcher::SketchObject":
                sketches.append(_sketch_info(obj))
        except Exception as exc:
            warnings.append(f"Could not inspect {getattr(obj, 'Name', 'an object')}: {exc}")

    for obj in objects:
        try:
            type_id = str(getattr(obj, "TypeId", "") or "")
            name = str(getattr(obj, "Name", "") or "")
            if type_id in ("PartDesign::Body", "Sketcher::SketchObject"):
                continue
            if name in body_feature_names:
                continue
            if type_id.startswith("PartDesign::") or type_id.startswith("Part::") or type_id.startswith("Mesh::"):
                features.append(_feature_info(obj))
                if type_id.startswith("Mesh::") or type_id in ("Part::Feature", "Part::FeaturePython"):
                    imported.append(str(getattr(obj, "Label", "") or name))
        except Exception as exc:
            warnings.append(f"Could not inspect {getattr(obj, 'Name', 'an object')}: {exc}")

    edit = _edit_object()
    selection = _selection()
    active_name = ""
    if edit is not None:
        active_name = str(getattr(edit, "Label", "") or getattr(edit, "Name", "") or "")
    elif not selection.is_empty:
        active_name = selection.object_label or selection.object_name

    doc_info = DocumentInfo(
        name=str(getattr(doc, "Name", "") or ""),
        label=str(getattr(doc, "Label", "") or ""),
        file_name=str(getattr(doc, "FileName", "") or ""),
        modified=bool(getattr(doc, "Modified", False)),
        object_count=len(list(doc.Objects)),
        bodies=bodies,
        sketches=sketches,
        features=features,
        imported_objects=imported,
        workbench=_workbench_name(),
        edit_mode=str(getattr(edit, "Label", "") or getattr(edit, "Name", "") or "") if edit else "",
        active_object=active_name,
        selection=selection,
        units=_units(),
    )
    return Snapshot(doc=doc_info, warnings=warnings[:10], goal=goal)


def _dimension_signature(sketch) -> tuple:
    values: list[float] = []
    try:
        for constraint in list(sketch.Constraints)[:MAX_CONSTRAINTS]:
            kind = str(getattr(constraint, "Type", "") or "")
            if kind in DIMENSION_TYPES:
                try:
                    values.append(round(float(constraint.Value), 6))
                except Exception:
                    values.append(0.0)
    except Exception:
        pass
    return tuple(values)


def _feature_signature(feature) -> tuple:
    lowered = str(getattr(feature, "TypeId", "") or "").lower()
    values: list[float] = []
    for prop in ("Length", "Radius", "Diameter", "Angle", "Size", "Offset"):
        if prop.lower() in lowered or prop in ("Length", "Radius", "Diameter"):
            try:
                values.append(round(float(getattr(feature, prop)), 6))
            except Exception:
                pass
    return tuple(values)


def build_light_signature() -> tuple:
    """A cheap fingerprint used to decide whether a full review is needed."""
    doc = App.ActiveDocument
    if doc is None:
        return ("no_document",)

    try:
        objects = list(doc.Objects)[:MAX_OBJECTS]
    except Exception:
        return ("unreadable_document",)

    items: list[Any] = [doc.Name, bool(getattr(doc, "Modified", False)), len(objects)]
    edit = _edit_object()
    items.extend([
        _workbench_name(),
        getattr(edit, "Name", "") if edit else "",
    ])

    for obj in objects:
        try:
            type_id = str(getattr(obj, "TypeId", "") or "")
            state = tuple(str(s) for s in (getattr(obj, "State", []) or []))
            items.extend([getattr(obj, "Name", ""), getattr(obj, "Label", ""), type_id, state])
            if type_id == "Sketcher::SketchObject":
                items.extend([
                    int(getattr(obj, "DoF", 0) or 0),
                    int(getattr(obj, "ConstraintCount", 0) or 0),
                    int(getattr(obj, "GeometryCount", 0) or 0),
                    bool(getattr(obj, "FullyConstrained", False)),
                    _dimension_signature(obj),
                ])
            elif type_id == "PartDesign::Body":
                tip = getattr(obj, "Tip", None)
                items.extend([getattr(tip, "Name", "") if tip else "", len(getattr(obj, "Group", []) or [])])
            else:
                items.append(_feature_signature(obj))
        except Exception:
            items.append(("unreadable", getattr(obj, "Name", "")))

    return tuple(items)
