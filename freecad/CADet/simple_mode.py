# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the LearnCad addon.
"""A deliberately small FreeCAD shell for beginners.

Hides the workbench selector, advanced toolbars, and workbench menus, and adds
two context-aware toolbars: one for modeling and one for sketching. Advanced UI
is one checkbox away in Setup.
"""

from __future__ import annotations

from typing import Any, Optional

from .compat import QtCore, QtGui, QtWidgets, blocking_modal

from . import icons as toolbar_icons
from . import settings
from . import tool_catalog as catalog


FEATURES_BAR = "LearnCadSimpleBar"
SKETCH_BAR = "LearnCadSketchBar"
CUSTOM_BARS = {FEATURES_BAR, SKETCH_BAR}

_APPLIED = False
_TOOLBAR_STATE: dict[str, bool] = {}
_MENU_STATE: dict[str, bool] = {}
_COMBO_VISIBLE = True
_BARS: dict[str, Any] = {}
_WORKBENCH_CONNECTED = False
_WORKBENCH_HANDLER = None
_HIDDEN_TABS = []
_HIDDEN_DOCKS = []
_RENAMED_TABS = []
_RENAMED_DOCKS = []
_MENUBAR_VISIBLE = True
_STATUSBAR_VISIBLE = True
_TREE_PINNED = False
_WATCHER = None
_GUARD = None
_CONTEXT_FILTER = None

try:  # Qt6 moved QAction to QtGui
    _QAction = QtGui.QAction
except Exception:  # pragma: no cover - Qt5
    _QAction = QtWidgets.QAction


def _gui():
    import FreeCADGui as Gui

    return Gui


def _main_window():
    try:
        return _gui().getMainWindow()
    except Exception:
        return None


def _action(parent, text: str, tooltip: str, callback) -> QtGui.QAction:
    action = QtGui.QAction(text, parent)
    action.setToolTip(tooltip)
    action.setStatusTip(tooltip)
    action.triggered.connect(lambda checked=False: callback())
    return action


def _raise_tools() -> None:
    """Kept for compatibility. The engine task bar is never auto-revealed."""
    return


_PANEL_ACTIONS = {
    "PartDesign_Pad": "open_pad",
    "PartDesign_Pocket": "open_pocket",
    "PartDesign_Hole": "open_hole",
    "PartDesign_Fillet": "open_fillet",
    "PartDesign_Thickness": "open_thickness",
}

_DIMENSION_COMMANDS = {
    "Sketcher_ConstrainDistance": ("Distance", "Distance", "mm", False),
    "Sketcher_ConstrainDistanceX": ("DistanceX", "Horizontal distance", "mm", False),
    "Sketcher_ConstrainDistanceY": ("DistanceY", "Vertical distance", "mm", False),
    "Sketcher_ConstrainRadius": ("Radius", "Radius", "mm", False),
    "Sketcher_ConstrainDiameter": ("Diameter", "Diameter", "mm", False),
    "Sketcher_ConstrainAngle": ("Angle", "Angle", "deg", True),
}


def _editing_sketch():
    try:
        import FreeCADGui as Gui

        gdoc = Gui.activeDocument()
        if gdoc is None or gdoc.getInEdit() is None:
            return None
        edit = gdoc.getInEdit()
        if isinstance(edit, (tuple, list)):
            edit = edit[0] if edit else None
        obj = getattr(edit, "Object", edit)
        if obj is not None and str(getattr(obj, "TypeId", "")) == "Sketcher::SketchObject":
            return obj
    except Exception:
        pass
    return None


def _selected_sketch_items(sketch):
    edges = set()
    vertices = set()
    try:
        import FreeCADGui as Gui

        for selection in Gui.Selection.getSelectionEx():
            obj = getattr(selection, "Object", None)
            if obj is not None and obj is not sketch:
                continue
            for name in (getattr(selection, "SubElementNames", None) or []):
                text = str(name)
                if text.startswith("Edge"):
                    try:
                        edges.add(int(text[4:]) - 1)
                    except Exception:
                        pass
                elif text.startswith("Vertex"):
                    try:
                        vertices.add(int(text[6:]) - 1)
                    except Exception:
                        pass
    except Exception:
        pass
    return (
        sorted(index for index in edges if index >= 0),
        sorted(index for index in vertices if index >= 0),
    )


def _selected_axes(sketch) -> list[str]:
    """Which sketch axes/origin are selected alongside geometry.

    FreeCAD reports these as H_Axis, V_Axis and RootPoint sub-elements rather
    than edges, so the normal edge/vertex parser never sees them.
    """
    axes: list[str] = []
    try:
        import FreeCADGui as Gui

        for selection in Gui.Selection.getSelectionEx():
            obj = getattr(selection, "Object", None)
            if obj is not None and obj is not sketch:
                continue
            for name in (getattr(selection, "SubElementNames", None) or []):
                text = str(name)
                if text in ("H_Axis", "X_Axis"):
                    axes.append("H_Axis")
                elif text in ("V_Axis", "Y_Axis"):
                    axes.append("V_Axis")
                elif text == "RootPoint":
                    axes.append("RootPoint")
    except Exception:
        pass
    return sorted(set(axes))


def _axis_point_default(sketch, ref, axis: str, kind: str) -> float:
    point = _point_of(sketch, int(ref[0]), int(ref[1]))
    if point is None:
        return 10.0
    try:
        x = float(point.x)
        y = float(point.y)
    except Exception:
        return 10.0
    if axis == "H_Axis":
        return abs(y) or 10.0
    if axis == "V_Axis":
        return abs(x) or 10.0
    if kind == "DistanceX":
        return abs(x) or 10.0
    if kind == "DistanceY":
        return abs(y) or 10.0
    return max((x * x + y * y) ** 0.5, 0.001)


def _selected_sketch_edges(sketch):
    return _selected_sketch_items(sketch)[0]


def _default_dimension(sketch, geo_id: int, kind: str) -> float:
    try:
        geometry = sketch.Geometry[geo_id]
    except Exception:
        return 10.0
    try:
        if kind == "Diameter" and hasattr(geometry, "Radius"):
            return float(geometry.Radius) * 2.0
        if kind == "Radius" and hasattr(geometry, "Radius"):
            return float(geometry.Radius)
        if hasattr(geometry, "length"):
            return float(geometry.length())
        if hasattr(geometry, "Radius"):
            return float(geometry.Radius)
    except Exception:
        pass
    return 10.0


def _vertex_ref(sketch, vertex_index: int):
    try:
        geo, pos = sketch.getGeoVertexIndex(vertex_index)
        return int(geo), int(pos)
    except Exception:
        return None


def _default_two_point(sketch, v1: int, v2: int, kind: str) -> float:
    try:
        p1 = sketch.Shape.Vertexes[v1].Point
        p2 = sketch.Shape.Vertexes[v2].Point
        dx = abs(p2.x - p1.x)
        dy = abs(p2.y - p1.y)
        if kind == "DistanceX":
            return dx or 1.0
        if kind == "DistanceY":
            return dy or 1.0
        return max((dx * dx + dy * dy) ** 0.5, 0.001)
    except Exception:
        return 10.0


def _conflict_score(sketch) -> int:
    try:
        return len(list(getattr(sketch, "ConflictingConstraints", []) or [])) + len(
            list(getattr(sketch, "RedundantConstraints", []) or [])
        )
    except Exception:
        return 0


def _constraint_refs(constraint) -> tuple:
    return (
        str(getattr(constraint, "Type", "")),
        int(getattr(constraint, "First", -1)),
        int(getattr(constraint, "FirstPos", 0)),
        int(getattr(constraint, "Second", -2000)),
        int(getattr(constraint, "SecondPos", 0)),
    )


def _same_type_dimensions(sketch, kind: str) -> list[int]:
    """Indexes of existing driving dimensions of the same kind."""
    found: list[int] = []
    try:
        constraints = list(sketch.Constraints)
    except Exception:
        return found
    for index, constraint in enumerate(constraints):
        if str(getattr(constraint, "Type", "")) != kind:
            continue
        try:
            if int(getattr(constraint, "First", -1)) < 0:
                continue
        except Exception:
            continue
        found.append(index)
    return found


def _equivalent_dimension(sketch, constraint) -> Optional[int]:
    """Find an existing dimension that already sizes the exact same geometry."""
    refs = _constraint_refs(constraint)
    try:
        constraints = list(sketch.Constraints)
    except Exception:
        return None
    for index, existing in enumerate(constraints):
        if _constraint_refs(existing) == refs:
            return index
    return None


def _datum_text(sketch, index: int) -> str:
    try:
        return str(sketch.getDatum(index))
    except Exception:
        try:
            value = float(sketch.Constraints[index].Value)
            return f"{value:.2f}"
        except Exception:
            return "?"


_DIMENSION_TYPES = {"Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle"}


def _all_dimension_indexes(sketch) -> list[int]:
    indexes: list[int] = []
    try:
        constraints = list(sketch.Constraints)
    except Exception:
        return indexes
    for index, constraint in enumerate(constraints):
        if str(getattr(constraint, "Type", "")) in _DIMENSION_TYPES:
            indexes.append(index)
    return indexes


def _existing_dimension_hint(sketch, kind: str) -> str:
    indexes = _same_type_dimensions(sketch, kind) or _all_dimension_indexes(sketch)
    if not indexes:
        return ""
    shown = ", ".join(_datum_text(sketch, index) for index in indexes[:3])
    return f" Existing: {shown}."


def _over_constrained_message(sketch, label: str, kind: str) -> str:
    try:
        fully = bool(getattr(sketch, "FullyConstrained", False))
    except Exception:
        fully = False
    hint = _existing_dimension_hint(sketch, kind)
    if fully:
        return (
            "This sketch is already fully constrained, so a new "
            + label.lower()
            + " would over-constrain it. Edit an existing dimension instead."
            + hint
        )
    return (
        "That dimension conflicts with an existing constraint, so I left the "
        "sketch unchanged. Remove the conflicting constraint or try a different "
        "dimension." + hint
    )


def _measure_dimension(sketch, kind: str, target) -> Optional[float]:
    """Current value of the dimension the user is trying to apply."""
    try:
        import math

        if target[0] == "angle":
            g1, g2 = target[1]
            a = sketch.Geometry[int(g1)]
            b = sketch.Geometry[int(g2)]
            ax, ay = a.EndPoint.x - a.StartPoint.x, a.EndPoint.y - a.StartPoint.y
            bx, by = b.EndPoint.x - b.StartPoint.x, b.EndPoint.y - b.StartPoint.y
            angle = abs(math.degrees(math.atan2(ax * by - ay * bx, ax * bx + ay * by)))
            return 360.0 - angle if angle > 180.0 else angle
        if target[0] == "points":
            (g1, p1), (g2, p2) = target[1]
            p1 = _point_of(sketch, int(g1), int(p1))
            p2 = _point_of(sketch, int(g2), int(p2))
            if p1 is None or p2 is None:
                return None
            dx = abs(float(p2.x) - float(p1.x))
            dy = abs(float(p2.y) - float(p1.y))
            if kind == "DistanceX":
                return dx
            if kind == "DistanceY":
                return dy
            return (dx * dx + dy * dy) ** 0.5
        if target[0] == "axis_point":
            (g1, p1), axis = target[1]
            point = _point_of(sketch, int(g1), int(p1))
            if point is None:
                return None
            x = abs(float(point.x))
            y = abs(float(point.y))
            if axis == "H_Axis" or kind == "DistanceY":
                return y
            if axis == "V_Axis" or kind == "DistanceX":
                return x
            return (x * x + y * y) ** 0.5
        geometry = sketch.Geometry[int(target[1])]
        if kind in ("Radius", "Diameter"):
            radius = float(geometry.Radius)
            return radius * 2.0 if kind == "Diameter" else radius
        start = geometry.StartPoint
        end = geometry.EndPoint
        dx = abs(float(end.x) - float(start.x))
        dy = abs(float(end.y) - float(start.y))
        if kind == "DistanceX":
            return dx
        if kind == "DistanceY":
            return dy
        if hasattr(geometry, "length"):
            return float(geometry.length())
        return (dx * dx + dy * dy) ** 0.5
    except Exception:
        return None


def _matches_requested(measured: Optional[float], value: float, kind: str) -> bool:
    if measured is None:
        return False
    tolerance = 0.05 if kind == "Angle" else max(0.01, abs(value) * 1e-4)
    return abs(measured - value) <= tolerance


def _edge_is_horizontal(sketch, geo_id: int) -> bool:
    try:
        geometry = sketch.Geometry[geo_id]
        return abs(float(geometry.EndPoint.x) - float(geometry.StartPoint.x)) >= abs(
            float(geometry.EndPoint.y) - float(geometry.StartPoint.y)
        )
    except Exception:
        return False


def _candidate_dimensions(sketch, kind: str, target, constraint) -> list[int]:
    """Existing dimensions that could be re-used for this request, best first."""
    candidates: list[int] = []

    def add(index) -> None:
        if index is not None and index not in candidates:
            candidates.append(index)

    exact = _equivalent_dimension(sketch, constraint)
    if exact is not None:
        return [exact]

    same = _same_type_dimensions(sketch, kind)
    if len(same) == 1:
        add(same[0])

    if target[0] == "single":
        try:
            geo_id = int(target[1])
        except Exception:
            geo_id = -1
        related = ""
        if kind == "Distance":
            related = "DistanceX" if _edge_is_horizontal(sketch, geo_id) else "DistanceY"
        elif kind in ("DistanceX", "DistanceY"):
            related = "Distance"
        elif kind in ("Radius", "Diameter"):
            related = "Diameter" if kind == "Radius" else "Radius"
        if related:
            alternatives = _same_type_dimensions(sketch, related)
            if len(alternatives) == 1:
                add(alternatives[0])
        try:
            constraints = list(sketch.Constraints)
        except Exception:
            constraints = []
        for index, existing in enumerate(constraints):
            try:
                if (
                    int(getattr(existing, "First", -1)) == geo_id
                    and int(getattr(existing, "FirstPos", 0)) == 0
                    and str(getattr(existing, "Type", "")) in _DIMENSION_TYPES
                ):
                    add(index)
            except Exception:
                continue
    return candidates


def _point_of(sketch, geo_id: int, pos_id: int):
    try:
        geometry = sketch.Geometry[geo_id]
    except Exception:
        return None
    if pos_id == 1:
        return getattr(geometry, "StartPoint", None)
    if pos_id == 2:
        return getattr(geometry, "EndPoint", None)
    return getattr(geometry, "Center", None)


def _pin_point(sketch, geo_id: int, pos_id: int) -> list[int]:
    """Temporarily pin a sketch point where it is, so a new dimension only
    resizes the geometry instead of dragging the whole profile around."""
    import Sketcher

    point = _point_of(sketch, geo_id, pos_id)
    if point is None:
        return []
    try:
        coords = ((float(point.x), "DistanceX"), (float(point.y), "DistanceY"))
    except Exception:
        return []
    added: list[int] = []
    for value, kind in coords:
        before = _conflict_score(sketch)
        try:
            index = sketch.ConstraintCount
            sketch.addConstraint(Sketcher.Constraint(kind, geo_id, pos_id, value))
            sketch.solve()
        except Exception:
            continue
        if _conflict_score(sketch) > before:
            try:
                sketch.delConstraint(index)
                sketch.solve()
            except Exception:
                pass
            continue
        added.append(index)
    return added


def _release_points(sketch, indices: list[int]) -> None:
    """Remove the temporary pins, newest first so earlier indexes stay valid."""
    for index in sorted(set(indices), reverse=True):
        try:
            sketch.delConstraint(index)
        except Exception:
            pass
    try:
        sketch.solve()
    except Exception:
        pass


def _anchor_refs(sketch, target, kind: str) -> list[tuple[int, int]]:
    """Pick the point(s) that should stay fixed while the dimension changes."""
    try:
        if target[0] == "axis_point":
            # The axis itself is the anchor; pinning the point would fight
            # the distance we are about to apply.
            return []
        if target[0] == "points":
            (g1, p1), _ = target[1]
            return [(int(g1), int(p1))]
        if target[0] == "angle":
            refs = []
            for geo_id in target[1]:
                refs.append((int(geo_id), 1))
            return refs
        geo_id = int(target[1])
        if kind in ("Radius", "Diameter"):
            return [(geo_id, 3)]
        return [(geo_id, 1)]
    except Exception:
        return []


def _dimension_constraint(command: str) -> None:
    """Ask for one value and add the sketch constraint directly, no task bar."""
    import FreeCAD as App
    import Sketcher

    kind, label, unit, needs_two = _DIMENSION_COMMANDS[command]
    sketch = _editing_sketch()
    if sketch is None:
        QtWidgets.QMessageBox.information(
            _main_window(), "Dimension", "Open a sketch before adding a dimension."
        )
        return

    # Read the selection before touching the sketch. Cleaning up redundant
    # constraints can trigger a re-solve that clears the GUI selection.
    edges, vertices = _selected_sketch_items(sketch)
    axes = _selected_axes(sketch)
    try:
        from . import actions

        actions.stabilize_sketch(sketch)
    except Exception:
        pass

    target = None
    default = 45.0

    if kind == "Angle":
        if len(edges) < 2:
            QtWidgets.QMessageBox.information(
                _main_window(), label, "Select two edges first, then click " + label + "."
            )
            return
        target = ("angle", (edges[0], edges[1]))
    elif kind in ("Radius", "Diameter"):
        if len(edges) != 1:
            QtWidgets.QMessageBox.information(
                _main_window(),
                label,
                "Select one circle or arc first, then click " + label + ".",
            )
            return
        target = ("single", edges[0])
        default = _default_dimension(sketch, edges[0], kind)
    else:
        if len(vertices) == 1 and not edges and axes:
            ref = _vertex_ref(sketch, vertices[0])
            if ref is None:
                QtWidgets.QMessageBox.information(
                    _main_window(), label, "Could not read the selected point. Try again."
                )
                return
            axis = axes[0]
            if axis == "H_Axis":
                kind, label = "DistanceY", "Vertical distance"
            elif axis == "V_Axis":
                kind, label = "DistanceX", "Horizontal distance"
            elif kind not in ("DistanceX", "DistanceY"):
                QtWidgets.QMessageBox.information(
                    _main_window(),
                    label,
                    "Pick the horizontal or vertical axis (or use a horizontal/vertical "
                    "distance), then try again.",
                )
                return
            target = ("axis_point", (ref, axis))
            default = _axis_point_default(sketch, ref, axis, kind)
        elif len(edges) == 1:
            # Dim on a circle or arc should size it, not add a distance.
            try:
                geometry = sketch.Geometry[edges[0]]
            except Exception:
                geometry = None
            if geometry is not None and hasattr(geometry, "Radius"):
                kind = "Radius"
                label = "Radius"
            target = ("single", edges[0])
            default = _default_dimension(sketch, edges[0], kind)
        elif len(vertices) >= 2:
            refs = [_vertex_ref(sketch, vertices[0]), _vertex_ref(sketch, vertices[1])]
            if any(ref is None for ref in refs):
                QtWidgets.QMessageBox.information(
                    _main_window(), label, "Could not read the selected points. Try again."
                )
                return
            target = ("points", (refs[0], refs[1]))
            default = _default_two_point(sketch, vertices[0], vertices[1], kind)
        else:
            QtWidgets.QMessageBox.information(
                _main_window(),
                label,
                "Select one edge, or two points, then click " + label + ".",
            )
            return

    current = _measure_dimension(sketch, kind, target)
    prompt = label + " (" + unit + "):"
    if current is not None:
        prompt = f"{label} ({unit}) — current {current:.2f}:"
    value, accepted = QtWidgets.QInputDialog.getDouble(
        _main_window(),
        label,
        prompt,
        default,
        0.001,
        1000000.0,
        2,
    )
    if not accepted:
        return

    # A dimension that changes the size by a huge factor usually means the
    # sketch was drawn tiny (or a wrong unit was typed). Warn before turning a
    # 1 mm profile into a 50 mm sliver.
    if current is not None and current > 1e-6:
        ratio = float(value) / float(current)
        if ratio > 8.0 or ratio < 0.125:
            direction = "larger" if ratio > 1 else "smaller"
            answer = QtWidgets.QMessageBox.question(
                _main_window(),
                label,
                f"The current size is {current:.2f} {unit}. You entered "
                f"{value:g} {unit}, which is about {abs(ratio):.0f}× {direction}.\n\n"
                "That will stretch this part of the sketch. Apply it anyway?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if answer != QtWidgets.QMessageBox.Yes:
                return
    try:
        import FreeCADGui as Gui

        quantity = App.Units.Quantity(f"{value:.4f} {unit}")
        if target[0] == "angle":
            g1, g2 = target[1]
            constraint = Sketcher.Constraint("Angle", g1, g2, quantity)
        elif target[0] == "points":
            (g1, p1), (g2, p2) = target[1]
            constraint = Sketcher.Constraint(kind, g1, p1, g2, p2, quantity)
        elif target[0] == "axis_point":
            (g1, p1), axis = target[1]
            # Keep the point on the side of the axis it is currently on. The
            # dialog asks for a positive magnitude.
            point = _point_of(sketch, int(g1), int(p1))
            signed = float(value)
            if point is not None:
                if axis == "H_Axis" and float(point.y) < 0:
                    signed = -signed
                elif axis == "V_Axis" and float(point.x) < 0:
                    signed = -signed
                elif axis == "RootPoint" and kind == "DistanceY" and float(point.y) < 0:
                    signed = -signed
                elif axis == "RootPoint" and kind == "DistanceX" and float(point.x) < 0:
                    signed = -signed
            quantity = App.Units.Quantity(f"{signed:.4f} {unit}")
            if axis == "H_Axis":
                constraint = Sketcher.Constraint("DistanceY", g1, p1, quantity)
            elif axis == "V_Axis":
                constraint = Sketcher.Constraint("DistanceX", g1, p1, quantity)
            else:
                constraint = Sketcher.Constraint(kind, g1, p1, quantity)
        else:
            constraint = Sketcher.Constraint(kind, target[1], quantity)

        # Pin the reference point(s) first. Without this the solver is free to
        # slide the whole profile sideways while it satisfies the new value,
        # which is what made the sketch look like it "broke" for a moment.
        pins: list[int] = []
        try:
            for geo_id, pos_id in _anchor_refs(sketch, target, kind):
                pins.extend(_pin_point(sketch, geo_id, pos_id))
            App.ActiveDocument.recompute()
        except Exception:
            pins = []

        def _try_add() -> bool:
            """Add the dimension, returning True if it did not break the solver."""
            before = _conflict_score(sketch)
            index = sketch.ConstraintCount
            try:
                sketch.addConstraint(constraint)
                sketch.solve()
            except Exception:
                return False
            if _conflict_score(sketch) > before:
                try:
                    sketch.delConstraint(index)
                    sketch.solve()
                except Exception:
                    pass
                return False
            return True

        try:
            # Anchoring keeps the profile in place, but on sketches that are
            # already coupled by symmetry it can itself over-constrain. Try
            # with the pins, then fall back to a plain add.
            added = _try_add()
            if not added and pins:
                _release_points(sketch, pins)
                pins = []
                added = _try_add()
            if not added:
                # See whether the user was really just re-sizing a dimension
                # that already exists (same edge, opposite side, or equal arc).
                for match in _candidate_dimensions(sketch, kind, target, constraint):
                    try:
                        previous = sketch.getDatum(match)
                    except Exception:
                        previous = None
                    try:
                        sketch.setDatum(match, quantity)
                        sketch.solve()
                        if _conflict_score(sketch) == 0 and _matches_requested(
                            _measure_dimension(sketch, kind, target), value, kind
                        ):
                            App.ActiveDocument.recompute()
                            try:
                                Gui.updateGui()
                            except Exception:
                                pass
                            try:
                                view = Gui.activeDocument().activeView() if Gui.activeDocument() else None
                                if view is not None:
                                    view.fitAll()
                            except Exception:
                                pass
                            QtWidgets.QMessageBox.information(
                                _main_window(),
                                label,
                                f"Updated the existing {label.lower()} to {value:g} {unit}.",
                            )
                            return
                    except Exception:
                        pass
                    if previous is not None:
                        try:
                            sketch.setDatum(match, previous)
                            sketch.solve()
                        except Exception:
                            pass
                App.ActiveDocument.recompute()
                try:
                    Gui.updateGui()
                except Exception:
                    pass
                QtWidgets.QMessageBox.information(
                    _main_window(),
                    label,
                    _over_constrained_message(sketch, label, kind),
                )
                return
        finally:
            _release_points(sketch, pins)

        App.ActiveDocument.recompute()
        try:
            Gui.updateGui()
        except Exception:
            pass
        try:
            view = Gui.activeDocument().activeView() if Gui.activeDocument() else None
            if view is not None:
                view.fitAll()
        except Exception:
            pass
        try:
            QtCore.QTimer.singleShot(0, Gui.updateGui)
            QtCore.QTimer.singleShot(120, Gui.updateGui)
        except Exception:
            pass
    except Exception as exc:
        QtWidgets.QMessageBox.warning(
            _main_window(), label + " failed", str(exc)
        )


def _smart_dimension() -> None:
    """The right-click "Dimension" entry: infer the dimension from selection."""
    sketch = _editing_sketch()
    if sketch is None:
        QtWidgets.QMessageBox.information(
            _main_window(), "Dimension", "Open a sketch before adding a dimension."
        )
        return
    edges, vertices = _selected_sketch_items(sketch)
    if len(edges) >= 2:
        _dimension_constraint("Sketcher_ConstrainAngle")
    elif len(edges) == 1:
        _dimension_constraint("Sketcher_ConstrainDistance")
    elif len(vertices) >= 2:
        _dimension_constraint("Sketcher_ConstrainDistance")
    else:
        QtWidgets.QMessageBox.information(
            _main_window(),
            "Dimension",
            "Select an edge, or two points, first — then choose Dimension.",
        )


def _replace_menu_action(menu, action, handler) -> None:
    """Swap a native menu entry for a LearnCad one, in place."""
    try:
        replacement = _QAction(action.icon(), action.text(), menu)
        replacement.setEnabled(action.isEnabled())
        # Defer so the menu closes before we open LearnCad's dialog.
        replacement.triggered.connect(
            lambda checked=False: QtCore.QTimer.singleShot(0, handler)
        )
        menu.insertAction(action, replacement)
        action.setVisible(False)
    except Exception:
        pass


def _rewire_dimension_menu(menu) -> None:
    """Make native right-click dimension entries use LearnCad's dialog."""
    for action in list(menu.actions()):
        try:
            if not action.isVisible():
                continue
            command = str(action.data() or "")
        except Exception:
            command = ""
        if command == "Sketcher_Dimension":
            _replace_menu_action(menu, action, _smart_dimension)
        elif command in _DIMENSION_COMMANDS:
            _replace_menu_action(
                menu, action, lambda checked=False, c=command: _run(c)
            )


class _DimensionContextFilter(QtCore.QObject):
    def eventFilter(self, obj, event):
        try:
            if event.type() == QtCore.QEvent.Type.Show:
                is_menu = isinstance(obj, QtWidgets.QMenu)
                if not is_menu:
                    try:
                        is_menu = obj.inherits("QMenu")
                    except Exception:
                        is_menu = False
                if is_menu:
                    _rewire_dimension_menu(obj)
        except Exception:
            pass
        return False


def _install_context_filter() -> None:
    global _CONTEXT_FILTER
    if _CONTEXT_FILTER is not None:
        return
    try:
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        filt = _DimensionContextFilter(app)
        app.installEventFilter(filt)
        _CONTEXT_FILTER = filt
    except Exception:
        pass


def _run(command: str) -> None:
    if command == "PartDesign_NewSketch":
        _new_sketch()
        return
    if command in _PANEL_ACTIONS:
        _run_action(_PANEL_ACTIONS[command])
        return
    if command in _DIMENSION_COMMANDS:
        _dimension_constraint(command)
        return
    Gui = _gui()
    try:
        if command.startswith("PartDesign_"):
            Gui.activateWorkbench("PartDesignWorkbench")
        elif command.startswith("Sketcher_"):
            Gui.activateWorkbench("SketcherWorkbench")
        elif command.startswith("Part_"):
            Gui.activateWorkbench("PartWorkbench")
        elif command.startswith("Draft_"):
            Gui.activateWorkbench("DraftWorkbench")
        needs_task = (
            command.startswith(("PartDesign_", "Part_", "Draft_"))
            or command in ("Sketcher_ValidateSketch", "Sketcher_Dimension")
        )
        if needs_task:
            try:
                from . import panel

                panel.allow_task_dock()
            except Exception:
                pass
        Gui.runCommand(command)
    except Exception:
        pass


def _pad_dialog() -> None:
    try:
        from . import panel

        panel.show_pad_dialog()
    except Exception:
        pass


def _new_sketch() -> None:
    """Let FreeCAD choose the sketch plane, including a selected face."""
    try:
        from . import actions

        ok, message = actions.new_sketch(None)
        if not ok:
            QtWidgets.QMessageBox.information(_main_window(), "Sketch", message)
            return
        # Bring the task tab forward so the plane picker and solver are visible.
        QtCore.QTimer.singleShot(250, _raise_tools)
    except Exception as exc:
        QtWidgets.QMessageBox.warning(
            _main_window(), "Sketch", "Could not start a sketch: " + str(exc)
        )


def _run_action(action_id: str) -> None:
    try:
        from . import actions, panel

        snapshot = panel._PANEL._snapshot if panel._PANEL is not None else None
        ok, message = actions.run_action(action_id, snapshot)
        if not ok:
            QtWidgets.QMessageBox.information(_main_window(), "LearnCad", message)
    except Exception as exc:
        QtWidgets.QMessageBox.warning(
            _main_window(), "LearnCad", "Could not run that action: " + str(exc)
        )


def _panel_call(method: str) -> None:
    try:
        from . import panel

        panel.show_panel()
        if panel._PANEL is not None:
            getattr(panel._PANEL, method)()
    except Exception:
        pass


def _add_catalog_action(menu, tool) -> None:
    action = menu.addAction(tool.label)
    action.setToolTip(tool.hint)
    action.setStatusTip(tool.hint)
    action.triggered.connect(lambda checked=False, command=tool.command: _run(command))


def _catalog_menu(parent, groups):
    menu = QtWidgets.QMenu(parent)
    if len(groups) == 1:
        for tool in groups[0].tools:
            _add_catalog_action(menu, tool)
    else:
        for group in groups:
            submenu = menu.addMenu(group.label)
            for tool in group.tools:
                _add_catalog_action(submenu, tool)
    menu.addSeparator()
    search = menu.addAction("Search all tools...")
    search.triggered.connect(lambda checked=False: _open_all_tools(parent))
    return menu


def _menu_button(bar, text: str, icon_name: str, groups, tooltip: str = ""):
    button = QtWidgets.QToolButton(bar)
    button.setText(text)
    button.setIcon(toolbar_icons.icon(icon_name))
    button.setToolTip(tooltip or text)
    button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
    button.setMenu(_catalog_menu(button, groups))
    bar.addWidget(button)
    return button


def _visible_catalog_groups():
    in_sketch = _in_sketch()
    groups = list(catalog.SKETCH_GROUPS if in_sketch else catalog.MODEL_GROUPS)
    if in_sketch:
        groups.insert(0, catalog.MODEL_EDIT)
    groups.extend(catalog.VIEW_GROUPS)
    groups.extend(catalog.FILE_GROUPS)
    groups.extend(catalog.LEARNCAD_GROUPS)
    return groups


class _AllToolsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._command = ""
        self.setWindowTitle("LearnCad tools")
        self.setMinimumSize(520, 600)

        layout = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "Search every LearnCad tool. Type a name such as arc, tangent, loft, "
            "measure or export, then double-click the result."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._search = QtWidgets.QLineEdit()
        self._search.setPlaceholderText("Search tools...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filter)
        self._search.returnPressed.connect(self._run_selected)
        layout.addWidget(self._search)

        self._tree = QtWidgets.QTreeWidget()
        self._tree.setHeaderLabels(["Tool", "What it does"])
        self._tree.setColumnWidth(0, 220)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.itemDoubleClicked.connect(lambda item, column: self._run_selected())
        self._tree.currentItemChanged.connect(lambda current, previous: self._sync_run())
        layout.addWidget(self._tree, 1)

        buttons = QtWidgets.QHBoxLayout()
        self._run_btn = QtWidgets.QPushButton("Run")
        self._run_btn.clicked.connect(self._run_selected)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(self._run_btn)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        for group in _visible_catalog_groups():
            top = QtWidgets.QTreeWidgetItem([group.label, ""])
            top.setFlags(QtCore.Qt.ItemIsEnabled)
            font = top.font(0)
            font.setBold(True)
            top.setFont(0, font)
            self._tree.addTopLevelItem(top)
            for tool in group.tools:
                child = QtWidgets.QTreeWidgetItem([tool.label, tool.hint])
                child.setData(0, QtCore.Qt.UserRole, tool.command)
                child.setToolTip(0, tool.hint)
                child.setToolTip(1, tool.hint)
                top.addChild(child)
            top.setExpanded(True)

        self._sync_run()
        self._search.setFocus()

    def _filter(self, text: str) -> None:
        query = text.strip().lower()
        visible_total = 0
        for index in range(self._tree.topLevelItemCount()):
            group_item = self._tree.topLevelItem(index)
            visible = 0
            for child_index in range(group_item.childCount()):
                child = group_item.child(child_index)
                command = str(child.data(0, QtCore.Qt.UserRole) or "")
                haystack = " ".join(
                    [child.text(0), child.text(1), command, group_item.text(0)]
                ).lower()
                match = not query or query in haystack
                child.setHidden(not match)
                if match:
                    visible += 1
            group_item.setHidden(visible == 0)
            if query and visible:
                group_item.setExpanded(True)
            visible_total += visible
        self._run_btn.setEnabled(visible_total > 0 and bool(self._selected_command()))

    def _selected_command(self) -> str:
        item = self._tree.currentItem()
        if item is None:
            return ""
        return str(item.data(0, QtCore.Qt.UserRole) or "")

    def _sync_run(self) -> None:
        self._run_btn.setEnabled(bool(self._selected_command()))

    def _run_selected(self) -> None:
        command = self._selected_command()
        if not command:
            return
        self._command = command
        self.accept()

    def command(self) -> str:
        return self._command


def show_all_tools(parent=None) -> None:
    dialog = _AllToolsDialog(parent)
    if dialog.exec() == QtWidgets.QDialog.Accepted and dialog.command():
        _run(dialog.command())


def _open_all_tools(parent=None) -> None:
    show_all_tools(parent.window() if hasattr(parent, "window") else parent)


def _build_features_bar(mw) -> None:
    bar = QtWidgets.QToolBar("LearnCad", mw)
    bar.setObjectName(FEATURES_BAR)
    bar.setMovable(False)
    bar.setFloatable(False)
    bar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
    bar.setIconSize(QtCore.QSize(20, 20))

    def add(text, tip, callback, icon_name=None):
        action = _action(bar, text, tip, callback)
        if icon_name:
            action.setIcon(toolbar_icons.icon(icon_name))
        bar.addAction(action)

    _menu_button(bar, "File", "open", catalog.FILE_GROUPS, "New, open, save, import and print")
    bar.addSeparator()
    add("Undo", "Undo", lambda: _run("Std_Undo"), "undo")
    add("Redo", "Redo", lambda: _run("Std_Redo"), "redo")
    add("Fit", "Fit the model in the view", lambda: _run("Std_ViewFitAll"), "fit")
    bar.addSeparator()
    add("Sketch", "Create a new sketch on a selected face or a chosen plane", _new_sketch, "sketch")
    add("Pad", "Pad the sketch and set its length", _pad_dialog, "pad")
    bar.addSeparator()
    _menu_button(
        bar,
        "Model",
        "model",
        catalog.MODEL_GROUPS,
        "Add, remove, dress up, pattern, inspect and edit features",
    )
    add("Export", "Export the body as STL or STEP", lambda: _run_action("open_export"), "export")
    find = QtWidgets.QToolButton(bar)
    find.setIcon(toolbar_icons.icon("find"))
    find.setToolTip("Find a tool (Ctrl+K)")
    find.setShortcut(QtGui.QKeySequence("Ctrl+K"))
    find.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
    find.clicked.connect(lambda: _open_all_tools(find))
    bar.addWidget(find)
    add("Coach", "Open the LearnCad coach", lambda: _run("CADet_OpenMentor"), "coach")
    _menu_button(
        bar,
        "More",
        "more",
        catalog.VIEW_GROUPS + catalog.LEARNCAD_GROUPS,
        "Views, render, studio, setup, model tree and active body",
    )
    mw.addToolBar(QtCore.Qt.TopToolBarArea, bar)
    _BARS[FEATURES_BAR] = bar


def _build_sketch_bar(mw) -> None:
    bar = QtWidgets.QToolBar("LearnCad Sketch", mw)
    bar.setObjectName(SKETCH_BAR)
    bar.setMovable(False)
    bar.setFloatable(False)
    bar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
    bar.setIconSize(QtCore.QSize(20, 20))

    def add(text, tip, callback, icon_name=None):
        action = _action(bar, text, tip, callback)
        if icon_name:
            action.setIcon(toolbar_icons.icon(icon_name))
        bar.addAction(action)

    add("Rect", "Draw a rectangle", lambda: _run("Sketcher_CreateRectangle"), "rect")
    add("Circle", "Draw a circle", lambda: _run("Sketcher_CreateCircle"), "circle")
    add("Arc", "Draw an arc", lambda: _run("Sketcher_CreateArc"), "arc")
    add("Line", "Draw connected lines", lambda: _run("Sketcher_CreatePolyline"), "line")
    bar.addSeparator()
    add("Coincident", "Join two points", lambda: _run("Sketcher_ConstrainCoincident"), "coincident")
    add("Horiz", "Horizontal: make a line horizontal", lambda: _run("Sketcher_ConstrainHorizontal"), "horizontal")
    add("Vert", "Vertical: make a line vertical", lambda: _run("Sketcher_ConstrainVertical"), "vertical")
    add("Dim", "Smart dimension: pick geometry, then set the value", lambda: _run("Sketcher_Dimension"), "dimension")
    add("Radius", "Radius: size a circle or arc", lambda: _run("Sketcher_ConstrainRadius"), "radius")
    add(
        "Auto",
        "Add the missing constraints automatically and keep the current shape",
        lambda: _run_action("fix_constraints"),
        "constrain",
    )
    bar.addSeparator()
    _menu_button(bar, "Draw", "draw", (catalog.SKETCH_DRAW,), "All drawing tools")
    _menu_button(
        bar,
        "Constrain",
        "constrain",
        (catalog.SKETCH_GEOMETRIC, catalog.SKETCH_DIMENSIONAL, catalog.SKETCH_CONSTRAINT_TOOLS),
        "All geometric, dimensional and diagnostic constraints",
    )
    _menu_button(
        bar,
        "Edit",
        "more",
        (catalog.SKETCH_MODIFY, catalog.SKETCH_DELETE, catalog.SKETCH_UTILITIES),
        "Trim, offset, transform, delete and sketch utilities",
    )
    bar.addSeparator()
    add("Done", "Finish the sketch and return to the model", lambda: _run("Sketcher_LeaveSketch"), "leave")
    mw.addToolBarBreak(QtCore.Qt.TopToolBarArea)
    mw.addToolBar(QtCore.Qt.TopToolBarArea, bar)
    _BARS[SKETCH_BAR] = bar


def _ensure_bars(mw) -> None:
    for name, builder in ((FEATURES_BAR, _build_features_bar), (SKETCH_BAR, _build_sketch_bar)):
        bar = mw.findChild(QtWidgets.QToolBar, name)
        if bar is None:
            builder(mw)
        else:
            _BARS[name] = bar


def _in_sketch() -> bool:
    Gui = _gui()
    try:
        wb = Gui.activeWorkbench()
        if "sketcher" in str(getattr(wb, "MenuText", "")).lower():
            return True
    except Exception:
        pass
    try:
        gdoc = Gui.activeDocument()
        return gdoc is not None and gdoc.getInEdit() is not None
    except Exception:
        return False


def _sync_bars() -> None:
    sketch = _in_sketch()
    features = _BARS.get(FEATURES_BAR)
    sketch_bar = _BARS.get(SKETCH_BAR)
    if features is not None:
        features.setVisible(True)
    if sketch_bar is not None:
        sketch_bar.setVisible(sketch)


def _hide_default_toolbars(mw) -> None:
    global _COMBO_VISIBLE
    for bar in mw.findChildren(QtWidgets.QToolBar):
        name = bar.objectName()
        if name in CUSTOM_BARS:
            # Keep the main toolbar visible even while a sketch is open, so
            # Pad, Hole, Export and the rest never disappear.
            bar.setVisible(True if name == FEATURES_BAR else _in_sketch())
            continue
        if bar.isVisible():
            _TOOLBAR_STATE[name] = True
        bar.setVisible(False)
    # The workbench selector is a combo box inside the Workbench toolbar.
    for combo in mw.findChildren(QtWidgets.QComboBox):
        if "workbench" in (combo.toolTip() or "").lower():
            _COMBO_VISIBLE = combo.isVisible()
            combo.setVisible(False)


def _hide_menus(mw) -> None:
    global _MENUBAR_VISIBLE, _STATUSBAR_VISIBLE
    try:
        _MENUBAR_VISIBLE = mw.menuBar().isVisible()
        mw.menuBar().setVisible(False)
    except Exception:
        pass
    try:
        _STATUSBAR_VISIBLE = mw.statusBar().isVisible()
        mw.statusBar().setVisible(False)
    except Exception:
        pass


HIDDEN_TAB_NAMES = (
    "report view",
    "python console",
    "start page",
    "freecad",
)


def _simplify_docks(mw) -> None:
    for tabs in mw.findChildren(QtWidgets.QTabWidget):
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        lower = [label.strip().lower() for label in labels]
        if "model" in lower:
            try:
                tabs.setCurrentIndex(lower.index("model"))
            except Exception:
                pass
        for index, label in enumerate(lower):
            if label not in HIDDEN_TAB_NAMES:
                continue
            try:
                if not tabs.tabBar().isTabVisible(index):
                    continue
                tabs.tabBar().setTabVisible(index, False)
                _HIDDEN_TABS.append((tabs, index))
            except Exception:
                pass
    for dock in mw.findChildren(QtWidgets.QDockWidget):
        title = dock.windowTitle().strip().lower()
        if any(name in title for name in ("report", "python console", "start page", "freecad")):
            if dock.isVisible():
                _HIDDEN_DOCKS.append(dock)
                dock.setVisible(False)
        elif title == "model" and dock.isVisible() and not _TREE_PINNED:
            _HIDDEN_DOCKS.append(dock)
            dock.setVisible(False)
    for child in mw.findChildren(QtWidgets.QWidget):
        try:
            title = (child.windowTitle() or "").strip().lower()
        except Exception:
            continue
        if title in ("start page", "freecad start page") and child.isVisible():
            child.hide()


def _rebrand_tasks(mw) -> None:
    """Rename FreeCAD's Tasks tab/panel to a neutral LearnCad label."""
    for tabs in mw.findChildren(QtWidgets.QTabWidget):
        for index in range(tabs.count()):
            label = tabs.tabText(index).strip()
            low = label.lower()
            if low in ("task", "tasks"):
                _RENAMED_TABS.append((tabs, index, tabs.tabText(index)))
                try:
                    tabs.setTabText(index, "Step" if low == "task" else "Steps")
                except Exception:
                    pass
    for dock in mw.findChildren(QtWidgets.QDockWidget):
        title = dock.windowTitle().strip()
        if title.lower() in ("task", "tasks"):
            _RENAMED_DOCKS.append((dock, title))
            try:
                dock.setWindowTitle("Steps")
            except Exception:
                pass


def _hide_mdi_tabs(mw) -> None:
    """Hide the bottom document tab bar so it cannot pop back in."""
    try:
        bar = mw.findChild(QtWidgets.QTabBar, "mdiAreaTabBar")
        if bar is not None and bar.isVisible():
            bar.hide()
    except Exception:
        pass


def _task_active() -> bool:
    try:
        import FreeCADGui as Gui

        return bool(Gui.Control.activeDialog())
    except Exception:
        return False


def _mouse_idle() -> bool:
    try:
        return QtWidgets.QApplication.mouseButtons() == QtCore.Qt.NoButton
    except Exception:
        return True


def _ui_idle() -> bool:
    if not _mouse_idle():
        return False
    return blocking_modal() is None


def _guard_tick(mw) -> None:
    if not _ui_idle():
        return
    _hide_idle_tasks(mw)
    _hide_mdi_tabs(mw)


def _apply_if_idle() -> None:
    # Startup setup must still run behind FreeCAD's document-recovery modal.
    if not _mouse_idle():
        QtCore.QTimer.singleShot(1500, _apply_if_idle)
        return
    apply()


def _hide_idle_tasks(mw) -> None:
    """Keep the engine task bar hidden unless an advanced dialog is open."""
    try:
        if QtWidgets.QApplication.mouseButtons() != QtCore.Qt.NoButton:
            return
        if blocking_modal() is not None:
            return
    except Exception:
        pass
    allowed = False
    try:
        from . import panel

        allowed = bool(getattr(panel, "_TASK_DOCK_ALLOWED", False))
    except Exception:
        allowed = False
    if _task_active() and allowed:
        return
    for dock in mw.findChildren(QtWidgets.QDockWidget):
        if dock.windowTitle().strip().lower() not in (
            "task", "tasks", "step", "steps", "constraints"
        ):
            continue
        try:
            if mw.dockWidgetArea(dock) != QtCore.Qt.LeftDockWidgetArea:
                mw.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
        except Exception:
            pass
        if dock.isVisible():
            dock.hide()


def _restore_docks() -> None:
    for tabs, index, label in _RENAMED_TABS:
        try:
            tabs.setTabText(index, label)
        except Exception:
            pass
    _RENAMED_TABS.clear()
    for dock, title in _RENAMED_DOCKS:
        try:
            dock.setWindowTitle(title)
        except Exception:
            pass
    _RENAMED_DOCKS.clear()
    for tabs, index in _HIDDEN_TABS:
        try:
            tabs.tabBar().setTabVisible(index, True)
        except Exception:
            pass
    _HIDDEN_TABS.clear()
    for dock in _HIDDEN_DOCKS:
        try:
            dock.setVisible(True)
        except Exception:
            pass
    _HIDDEN_DOCKS.clear()


def _on_workbench(_name=None) -> None:
    if not settings.load().get("simple_mode", True):
        return
    QtCore.QTimer.singleShot(200, apply)


def _watch() -> None:
    """Keep the beginner shell clean if a panel pops back in."""
    if not settings.load().get("simple_mode", True):
        if _WATCHER is not None:
            _WATCHER.stop()
        return
    mw = _main_window()
    if mw is None:
        return
    if not _ui_idle():
        return
    _hide_default_toolbars(mw)
    _hide_menus(mw)
    _simplify_docks(mw)
    _rebrand_tasks(mw)
    _hide_idle_tasks(mw)
    _hide_mdi_tabs(mw)
    _sync_bars()


def apply() -> None:
    global _APPLIED, _WORKBENCH_CONNECTED, _GUARD
    if not settings.load().get("simple_mode", True):
        return
    mw = _main_window()
    if mw is None:
        return
    _ensure_bars(mw)
    _hide_default_toolbars(mw)
    _hide_menus(mw)
    _simplify_docks(mw)
    _rebrand_tasks(mw)
    _hide_idle_tasks(mw)
    _hide_mdi_tabs(mw)
    _sync_bars()
    # Native Sketcher context menus are intentionally left untouched so the
    # smart dimension command keeps FreeCAD's built-in behavior.
    if not _WORKBENCH_CONNECTED:
        try:
            mw.workbenchActivated.connect(_on_workbench)
            _WORKBENCH_CONNECTED = True
        except Exception:
            pass
    if _WATCHER is None:
        try:
            watcher = QtCore.QTimer(mw)
            watcher.setInterval(4000)
            watcher.timeout.connect(_watch)
            watcher.start()
            globals()["_WATCHER"] = watcher
        except Exception:
            pass
    if _GUARD is None:
        try:
            guard = QtCore.QTimer(mw)
            guard.setInterval(400)
            guard.timeout.connect(lambda: _guard_tick(mw))
            guard.start()
            globals()["_GUARD"] = guard
        except Exception:
            pass
    _APPLIED = True


def toggle_tree() -> None:
    global _TREE_PINNED
    mw = _main_window()
    if mw is None:
        return
    dock = None
    for candidate in mw.findChildren(QtWidgets.QDockWidget):
        if candidate.windowTitle().strip().lower() in ("model", "tree"):
            dock = candidate
            break
    if dock is None:
        try:
            _gui().runCommand("Std_TreeView")
        except Exception:
            pass
        return
    if _TREE_PINNED and dock.isVisible():
        dock.hide()
        _TREE_PINNED = False
        return
    dock.show()
    dock.raise_()
    _TREE_PINNED = True
    while dock in _HIDDEN_DOCKS:
        _HIDDEN_DOCKS.remove(dock)


def restore() -> None:
    global _APPLIED, _COMBO_VISIBLE, _TREE_PINNED, _WATCHER, _GUARD
    _TREE_PINNED = False
    for timer_name in ("_WATCHER", "_GUARD"):
        timer = globals().get(timer_name)
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except Exception:
                pass
            globals()[timer_name] = None
    mw = _main_window()
    if mw is None:
        return
    for name, visible in _TOOLBAR_STATE.items():
        bar = mw.findChild(QtWidgets.QToolBar, name)
        if bar is not None:
            bar.setVisible(visible)
    try:
        mw.menuBar().setVisible(True)
    except Exception:
        pass
    try:
        mw.statusBar().setVisible(True)
    except Exception:
        pass
    for combo in mw.findChildren(QtWidgets.QComboBox):
        if "workbench" in (combo.toolTip() or "").lower():
            combo.setVisible(_COMBO_VISIBLE)
    for name in CUSTOM_BARS:
        bar = mw.findChild(QtWidgets.QToolBar, name)
        if bar is not None:
            bar.setVisible(False)
    try:
        mdi_bar = mw.findChild(QtWidgets.QTabBar, "mdiAreaTabBar")
        if mdi_bar is not None:
            mdi_bar.show()
    except Exception:
        pass
    for dock in mw.findChildren(QtWidgets.QDockWidget):
        if dock.windowTitle().strip().lower() in ("task", "tasks", "step", "steps", "constraints"):
            try:
                dock.setTitleBarWidget(None)
                mw.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
                dock.show()
            except Exception:
                pass
    _restore_docks()
    _APPLIED = False


def toggle() -> None:
    current = bool(settings.load().get("simple_mode", True))
    config = settings.load()
    config["simple_mode"] = not current
    settings.save(config)
    if config["simple_mode"]:
        apply()
    else:
        restore()


def schedule() -> None:
    if not settings.load().get("simple_mode", True):
        return
    for delay in (1200, 3000, 6000, 10000, 16000, 24000):
        QtCore.QTimer.singleShot(delay, _apply_if_idle)
