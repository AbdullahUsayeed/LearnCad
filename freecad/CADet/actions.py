# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Safe UI actions for the Guide Me button.

These actions set the user up for the next step. They do not silently change
geometry: they switch workbenches, enter sketch edit mode, preselect the
relevant geometry, and open the relevant task dialog. The user still does the
work and confirms the feature.
"""

from __future__ import annotations

from typing import Optional

import FreeCAD as App

try:
    import FreeCADGui as Gui  # type: ignore
except Exception:  # pragma: no cover - console mode
    Gui = None

from .model import Snapshot


MAX_SELECT = 8


def _fail(message: str) -> tuple[bool, str]:
    return False, message


def _ok(message: str) -> tuple[bool, str]:
    return True, message


def _gui_doc():
    if Gui is None:
        return None
    try:
        gdoc = Gui.activeDocument()
        if gdoc is not None:
            return gdoc
    except Exception:
        pass
    doc = App.ActiveDocument
    if doc is not None:
        try:
            return Gui.getDocument(doc.Name)
        except Exception:
            pass
    return None


def _body_obj(snapshot: Snapshot):
    doc = App.ActiveDocument
    if doc is None:
        return None
    if snapshot is not None and snapshot.doc is not None and snapshot.doc.bodies:
        body = doc.getObject(snapshot.doc.bodies[0].name)
        if body is not None:
            return body
    return _first_body(doc)


def _sketch_obj(snapshot: Snapshot):
    doc = App.ActiveDocument
    if doc is None:
        return None
    if snapshot is not None and snapshot.doc is not None:
        sketch_names = [sketch.name for sketch in snapshot.doc.sketches]
        if sketch_names:
            if snapshot.doc.edit_mode:
                for name in sketch_names:
                    obj = doc.getObject(name)
                    if obj is not None and (
                        obj.Name == snapshot.doc.edit_mode or obj.Label == snapshot.doc.edit_mode
                    ):
                        return obj
            if not snapshot.doc.selection.is_empty:
                selected = doc.getObject(snapshot.doc.selection.object_name)
                if selected is not None and selected.TypeId == "Sketcher::SketchObject":
                    return selected

    try:
        gdoc = _gui_doc()
        edit = gdoc.getInEdit() if gdoc is not None else None
        if isinstance(edit, (tuple, list)):
            edit = edit[0] if edit else None
        obj = getattr(edit, "Object", edit)
        if obj is not None and str(getattr(obj, "TypeId", "")) == "Sketcher::SketchObject":
            return obj
    except Exception:
        pass

    try:
        for obj in Gui.Selection.getSelection():
            if str(getattr(obj, "TypeId", "")) == "Sketcher::SketchObject":
                return obj
    except Exception:
        pass

    sketches = [
        obj for obj in doc.Objects
        if str(getattr(obj, "TypeId", "")) == "Sketcher::SketchObject"
    ]
    for sketch in reversed(sketches):
        try:
            if bool(getattr(sketch, "LearnCadHelper", False)):
                continue
            if int(getattr(sketch, "GeometryCount", 0) or 0) > 0:
                return sketch
        except Exception:
            pass
    for sketch in reversed(sketches):
        try:
            if not bool(getattr(sketch, "LearnCadHelper", False)):
                return sketch
        except Exception:
            pass
    return sketches[-1] if sketches else None


def _nearest_vertex(sketch, geo_id: int, pos_id: int) -> Optional[int]:
    try:
        geometry = sketch.Geometry[geo_id]
    except Exception:
        return None
    point = None
    try:
        if pos_id == 1:
            point = geometry.StartPoint
        elif pos_id == 2:
            point = geometry.EndPoint
    except Exception:
        return None
    if point is None:
        return None
    try:
        vertexes = list(sketch.Shape.Vertexes)
    except Exception:
        return None
    best_index = None
    best_distance = 1e9
    for index, vertex in enumerate(vertexes):
        try:
            distance = (vertex.Point - point).Length
        except Exception:
            continue
        if distance < best_distance:
            best_distance = distance
            best_index = index
    if best_index is None or best_distance > 0.5:
        return None
    return best_index + 1


def _select_missing(sketch) -> str:
    try:
        geometry_count = int(getattr(sketch, "GeometryCount", 0) or 0)
        if geometry_count > 0 and (
            bool(getattr(sketch, "FullyConstrained", False)) or int(getattr(sketch, "DoF", 0) or 0) == 0
        ):
            return "This sketch is fully constrained. Close the sketch and pad it, or add the next feature."
    except Exception:
        pass
    for method, args in (
        ("detectMissingPointOnPointConstraints", (0.3, False)),
        ("detectMissingVerticalHorizontalConstraints", (0.1,)),
        ("detectMissingEqualityConstraints", (0.1,)),
    ):
        try:
            getattr(sketch, method)(*args)
        except Exception:
            pass

    try:
        pairs = list(sketch.MissingPointOnPointConstraints)
    except Exception:
        pairs = []
    if pairs:
        geo1, pos1, geo2, pos2 = pairs[0][:4]
        vertex1 = _nearest_vertex(sketch, geo1, pos1)
        vertex2 = _nearest_vertex(sketch, geo2, pos2)
        if vertex1 and vertex2:
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(sketch, f"Vertex{vertex1}")
            Gui.Selection.addSelection(sketch, f"Vertex{vertex2}")
            return (
                "I selected the two endpoints that need a Coincident constraint. "
                "Click the Coincident tool (C), then check the solver."
            )

    try:
        hv_items = list(sketch.MissingVerticalHorizontalConstraints)
    except Exception:
        hv_items = []
    if hv_items:
        geo_id = int(hv_items[0][0])
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(sketch, f"Edge{geo_id + 1}")
        return (
            "I selected a line that is almost horizontal or vertical. "
            "Click Horizontal (H) or Vertical (V) to lock it."
        )

    try:
        equality = list(sketch.MissingLineEqualityConstraints)
    except Exception:
        equality = []
    if equality and len(equality[0]) >= 3:
        geo1 = int(equality[0][0])
        geo2 = int(equality[0][2])
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(sketch, f"Edge{geo1 + 1}")
        Gui.Selection.addSelection(sketch, f"Edge{geo2 + 1}")
        return (
            "I selected two lines that look equal. Click the Equal constraint if that matches the design intent."
        )

    return (
        "The sketch is open. Start with Coincident on the endpoints, then Horizontal/Vertical, "
        "then dimensions. I will keep watching the solver."
    )


def _parent_body(sketch):
    doc = App.ActiveDocument
    if doc is None:
        return None
    try:
        parent = sketch.getParentGeoFeatureGroup()
        if parent is not None and parent.TypeId == "PartDesign::Body":
            return parent
    except Exception:
        pass
    for obj in doc.Objects:
        if obj.TypeId != "PartDesign::Body":
            continue
        try:
            if sketch in obj.Group:
                return obj
        except Exception:
            continue
    return None


def _is_editing(sketch, gdoc) -> bool:
    try:
        edit = gdoc.getInEdit()
        if isinstance(edit, (tuple, list)):
            edit = edit[0] if edit else None
        if edit is not None and hasattr(edit, "Object"):
            edit = edit.Object
        return edit is not None and getattr(edit, "Name", "") == sketch.Name
    except Exception:
        return False


def _activate_body(body) -> None:
    if body is None or Gui is None:
        return
    try:
        Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    except Exception:
        try:
            Gui.activeDocument().ActiveView.setActiveObject("pdbody", body)
        except Exception:
            pass


def _enter_sketch(sketch) -> tuple[bool, str]:
    if Gui is None:
        return False, "The LearnCad interface is not available in this session."
    body = _parent_body(sketch)
    try:
        Gui.activateWorkbench("SketcherWorkbench")
    except Exception:
        pass
    _activate_body(body)
    gdoc = _gui_doc()
    if gdoc is None:
        return False, "No active GUI document."
    try:
        gdoc.setEdit(sketch.Name, 0)
    except Exception:
        pass
    if _is_editing(sketch, gdoc):
        return True, ""
    try:
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(sketch)
        Gui.runCommand("Sketcher_EditSketch")
    except Exception:
        pass
    if _is_editing(sketch, gdoc):
        return True, ""
    return False, "Could not enter sketch edit mode. Double-click the sketch in the tree."


def guide_sketch(snapshot: Snapshot) -> tuple[bool, str]:
    sketch = _sketch_obj(snapshot)
    if sketch is None:
        return _fail("No sketch found. Create a sketch first.")
    ok, message = _enter_sketch(sketch)
    if not ok:
        return _fail(message)
    message = _select_missing(sketch)
    return _ok(message)


def draw_rectangle(snapshot: Snapshot) -> tuple[bool, str]:
    sketch = _sketch_obj(snapshot)
    if sketch is None:
        return _fail("No sketch found. Create a sketch first.")
    ok, message = _enter_sketch(sketch)
    if not ok:
        return _fail(message)
    try:
        Gui.activateWorkbench("SketcherWorkbench")
        Gui.runCommand("Sketcher_CreateRectangle")
    except Exception:
        return _fail("Could not start the rectangle tool. Pick Rectangle in the sketch toolbar.")
    return _ok("Rectangle tool ready. Click the first corner, then the opposite corner.")


def close_sketch(snapshot: Snapshot) -> tuple[bool, str]:
    try:
        Gui.runCommand("Sketcher_LeaveSketch")
    except Exception:
        return _fail("Could not close the sketch. Use Leave in the sketch toolbar.")
    return _ok("Sketch closed. The profile is ready to pad.")


def _sketch_state(sketch) -> dict[str, int]:
    def _count(name: str) -> int:
        try:
            return len(getattr(sketch, name, []) or [])
        except Exception:
            return 0

    try:
        dof = int(getattr(sketch, "DoF", 0) or 0)
    except Exception:
        dof = 0
    return {
        "dof": dof,
        "conflicting": _count("ConflictingConstraints"),
        "redundant": _count("RedundantConstraints"),
        "malformed": _count("MalformedConstraints"),
    }


def _solve_quietly(sketch) -> None:
    try:
        sketch.solve()
    except Exception:
        pass


def _remove_redundant_constraints(sketch) -> int:
    """Delete constraints the solver reports as redundant.

    A redundant constraint adds no information (it is implied by the others),
    but it keeps the sketch in an error state and makes every later tool fail.
    FreeCAD's own solver routine removes exactly the flagged constraints and
    re-maps the remaining indexes, which is far safer than deleting by index.
    """
    try:
        before = len(list(sketch.RedundantConstraints or []))
    except Exception:
        before = 0
    try:
        remover = getattr(sketch, "autoRemoveRedundants", None)
        if remover is not None:
            remover(True)
    except Exception:
        pass
    _solve_quietly(sketch)
    try:
        after = len(list(sketch.RedundantConstraints or []))
    except Exception:
        after = 0
    return max(0, before - after)


def _try_constraint(sketch, constraint, label: str, added: list[str]) -> bool:
    """Add one constraint only if it removes freedom without breaking the solver."""
    before = _sketch_state(sketch)
    index = None
    try:
        index = sketch.addConstraint(constraint)
    except Exception:
        return False
    _solve_quietly(sketch)
    after = _sketch_state(sketch)
    helpful = (
        after["dof"] < before["dof"]
        and after["conflicting"] <= before["conflicting"]
        and after["redundant"] <= before["redundant"]
        and after["malformed"] <= before["malformed"]
    )
    if helpful:
        added.append(label)
        return True
    try:
        if index is not None:
            sketch.delConstraint(index)
    except Exception:
        pass
    _solve_quietly(sketch)
    return False


def _run_missing_detectors(sketch) -> None:
    for method, args in (
        ("detectMissingPointOnPointConstraints", (0.3, False)),
        ("detectMissingVerticalHorizontalConstraints", (0.1,)),
        ("detectMissingEqualityConstraints", (0.1,)),
    ):
        try:
            getattr(sketch, method)(*args)
        except Exception:
            pass


def stabilize_sketch(sketch) -> int:
    """Add only the obvious geometric constraints before a dimension.

    This keeps the current shape from shearing when a new dimension is
    applied. It never adds dimensions and it rolls back anything the solver
    rejects. Returns the number of constraints added.
    """
    try:
        import Sketcher
    except Exception:
        return 0
    # If the sketch is already in an error state, clean up what the solver
    # says is redundant and do not pile more constraints on top of real
    # conflicts. Otherwise every later tool reports errors everywhere.
    _remove_redundant_constraints(sketch)
    state = _sketch_state(sketch)
    if state["conflicting"] or state["malformed"] or state["redundant"]:
        return 0
    try:
        sketch.detectMissingPointOnPointConstraints(0.2, False)
        sketch.detectMissingVerticalHorizontalConstraints(0.02)
    except Exception:
        pass
    doc = App.ActiveDocument
    added: list[str] = []
    if doc is not None:
        try:
            doc.openTransaction("LearnCad stabilize")
        except Exception:
            pass
    try:
        try:
            pairs = list(getattr(sketch, "MissingPointOnPointConstraints", []) or [])
        except Exception:
            pairs = []
        for pair in pairs:
            try:
                geo1, pos1, geo2, pos2 = (int(v) for v in pair[:4])
                _try_constraint(
                    sketch,
                    Sketcher.Constraint("Coincident", geo1, pos1, geo2, pos2),
                    "Coincident",
                    added,
                )
            except Exception:
                pass

        try:
            hv_items = list(getattr(sketch, "MissingVerticalHorizontalConstraints", []) or [])
        except Exception:
            hv_items = []
        for item in hv_items:
            try:
                geo_id = int(item[0])
                geometry = sketch.Geometry[geo_id]
                start = geometry.StartPoint
                end = geometry.EndPoint
                horizontal = abs(end.x - start.x) >= abs(end.y - start.y)
                kind = "Horizontal" if horizontal else "Vertical"
                _try_constraint(sketch, Sketcher.Constraint(kind, geo_id), kind, added)
            except Exception:
                pass
        if added:
            _solve_quietly(sketch)
        if doc is not None:
            doc.commitTransaction()
    except Exception:
        if doc is not None:
            try:
                doc.abortTransaction()
            except Exception:
                pass
    return len(added)


def _lock_candidates(sketch):
    """Yield the dimensional constraints that pin geometry to its current spot."""
    try:
        geometry_items = list(sketch.Geometry)
    except Exception:
        return

    for geo_id, geometry in enumerate(geometry_items):
        start = getattr(geometry, "StartPoint", None)
        end = getattr(geometry, "EndPoint", None)
        center = getattr(geometry, "Center", None)
        radius = getattr(geometry, "Radius", None)

        for point, pos_id in ((start, 1), (end, 2), (center, 3)):
            if point is None:
                continue
            try:
                x = float(point.x)
                y = float(point.y)
            except Exception:
                continue
            yield ("DistanceX", geo_id, pos_id, x), "Horizontal distance"
            yield ("DistanceY", geo_id, pos_id, y), "Vertical distance"

        if radius is not None:
            try:
                value = float(radius)
            except Exception:
                value = 0.0
            if value > 0:
                yield ("Radius", geo_id, value), "Radius"


def solve_constraints(snapshot: Snapshot) -> tuple[bool, str]:
    """Make the active sketch fully constrained in one click.

    It first joins endpoints, straightens lines, and adds missing radii. Any
    freedom that remains is pinned with ordinary dimensions at the current shape,
    so the model does not move and the user can edit the values later. Every
    constraint is validated against the solver and rolled back if it would
    conflict or be redundant. It never deletes user geometry or constraints.
    """
    sketch = _sketch_obj(snapshot)
    if sketch is None:
        return _fail("No sketch found. Open the sketch you want fixed.")
    doc = App.ActiveDocument
    if doc is None:
        return _fail("No document is open.")
    try:
        import Sketcher
    except Exception:
        return _fail("The sketch editor is not available in this session.")

    try:
        if Gui is not None:
            Gui.runCommand("Sketcher_StopOperation")
    except Exception:
        pass

    cleaned = _remove_redundant_constraints(sketch)
    prefix = f"Removed {cleaned} redundant constraint(s). " if cleaned else ""
    _run_missing_detectors(sketch)
    state = _sketch_state(sketch)
    if state["conflicting"] or state["malformed"] or state["redundant"]:
        return _fail(
            prefix
            + "This sketch still has a real conflict. Delete the constraint the "
            "solver marks in red, then run Fix constraints again."
        )
    if state["dof"] == 0 or bool(getattr(sketch, "FullyConstrained", False)):
        return _ok(prefix + "This sketch is already fully constrained.")

    added: list[str] = []
    doc.openTransaction("LearnCad auto constraints")
    try:
        try:
            pairs = list(getattr(sketch, "MissingPointOnPointConstraints", []) or [])
        except Exception:
            pairs = []
        for pair in pairs:
            try:
                geo1, pos1, geo2, pos2 = (int(v) for v in pair[:4])
                _try_constraint(
                    sketch,
                    Sketcher.Constraint("Coincident", geo1, pos1, geo2, pos2),
                    "Coincident",
                    added,
                )
            except Exception:
                pass

        try:
            hv_items = list(getattr(sketch, "MissingVerticalHorizontalConstraints", []) or [])
        except Exception:
            hv_items = []
        for item in hv_items:
            try:
                geo_id = int(item[0])
                geometry = sketch.Geometry[geo_id]
                start = geometry.StartPoint
                end = geometry.EndPoint
                horizontal = abs(end.x - start.x) >= abs(end.y - start.y)
                kind = "Horizontal" if horizontal else "Vertical"
                _try_constraint(sketch, Sketcher.Constraint(kind, geo_id), kind, added)
            except Exception:
                pass

        try:
            radius_items = list(getattr(sketch, "MissingRadiusConstraints", []) or [])
        except Exception:
            radius_items = []
        for item in radius_items:
            try:
                geo_id = int(item[0] if isinstance(item, (tuple, list)) else item)
                radius = float(sketch.Geometry[geo_id].Radius)
                if radius > 0:
                    _try_constraint(
                        sketch,
                        Sketcher.Constraint("Radius", geo_id, radius),
                        "Radius",
                        added,
                    )
            except Exception:
                pass

        for args, label in _lock_candidates(sketch):
            if _sketch_state(sketch)["dof"] == 0:
                break
            _try_constraint(sketch, Sketcher.Constraint(*args), label, added)

        if _sketch_state(sketch)["dof"] > 0:
            try:
                geometry_count = int(getattr(sketch, "GeometryCount", 0) or 0)
            except Exception:
                geometry_count = 0
            for geo_id in range(geometry_count):
                if _sketch_state(sketch)["dof"] == 0:
                    break
                _try_constraint(
                    sketch, Sketcher.Constraint("Block", geo_id), "Block", added
                )

        _solve_quietly(sketch)
        doc.recompute()
        doc.commitTransaction()
    except Exception as exc:
        try:
            doc.abortTransaction()
        except Exception:
            pass
        return _fail("Could not apply constraints: " + str(exc))

    state = _sketch_state(sketch)
    fully = state["dof"] == 0 or bool(getattr(sketch, "FullyConstrained", False))
    if not added:
        if fully:
            return _ok(prefix + "This sketch is already fully constrained.")
        return _fail(
            prefix
            + "I could not find a safe constraint to add. Select the geometry that still "
            "moves and add one dimension, then try again."
        )

    summary = ", ".join(sorted(set(added))[:6])
    if fully:
        return _ok(
            prefix
            + f"Done. I added {len(added)} constraint(s) ({summary}) and locked the current "
            "shape. It is fully constrained now. Edit the dimensions to resize it."
        )
    return _ok(
        prefix
        + f"I added {len(added)} constraint(s) ({summary}). {state['dof']} degree(s) of "
        "freedom remain; select the geometry that still moves and add one dimension."
    )


def _first_body(doc):
    for obj in doc.Objects:
        if getattr(obj, "TypeId", "") == "PartDesign::Body":
            return obj
    return None


def _active_body():
    gdoc = _gui_doc()
    if gdoc is None:
        return None
    try:
        view = gdoc.ActiveView
        if view is None:
            return None
        return view.getActiveObject("pdbody")
    except Exception:
        return None


def _selected_body():
    if Gui is None:
        return None
    try:
        selection = Gui.Selection.getSelectionEx()
    except Exception:
        return None
    if not selection:
        return None
    obj = getattr(selection[0], "Object", None)
    if obj is None:
        return None
    if getattr(obj, "TypeId", "") == "PartDesign::Body":
        return obj
    return _parent_body(obj)


def _ensure_view() -> None:
    try:
        gdoc = _gui_doc()
        if gdoc is not None and gdoc.ActiveView is None:
            Gui.runCommand("Std_ViewCreate")
    except Exception:
        pass


def activate_body(snapshot: Snapshot) -> tuple[bool, str]:
    if Gui is None:
        return _fail("The LearnCad interface is not available in this session.")
    body = None
    try:
        for obj in Gui.Selection.getSelection():
            if str(getattr(obj, "TypeId", "")) == "PartDesign::Body":
                body = obj
                break
            parent = _parent_body(obj)
            if parent is not None:
                body = parent
                break
    except Exception:
        body = None
    if body is None:
        return _fail("Select a Body or one of its features in the Model tree first.")
    _activate_body(body)
    return _ok(f"'{getattr(body, 'Label', None) or getattr(body, 'Name', 'Body')}' is now the active Body.")


def _selected_face_ref():
    try:
        for selection in Gui.Selection.getSelectionEx():
            obj = getattr(selection, "Object", None)
            for name in (getattr(selection, "SubElementNames", None) or []):
                text = str(name)
                if text.startswith("Face"):
                    return obj, text
    except Exception:
        pass
    return None, ""


def _set_working_view(sketch, size_mm: float = 100.0) -> None:
    """Zoom a brand-new sketch to a comfortable working size.

    An empty sketch otherwise inherits whatever zoom level was active, which is
    how beginners end up drawing parts that are only a millimetre across.
    """
    if Gui is None:
        return
    try:
        if int(getattr(sketch, "GeometryCount", 0) or 0) != 0:
            return
        span = max(1.0, float(size_mm))
        gdoc = _gui_doc()
        view = gdoc.activeView() if gdoc is not None else None
        if view is None:
            return
        try:
            view.setCameraType("Orthographic")
        except Exception:
            pass
        try:
            camera = view.getCameraNode()
            if str(view.getCameraType()) == "Orthographic":
                camera.height.setValue(span * 2.0)
            else:
                camera.heightAngle.setValue(0.7)
        except Exception:
            pass
        try:
            Gui.updateGui()
        except Exception:
            pass
    except Exception:
        pass


def _schedule_working_view(sketch, size_mm: float = 100.0) -> None:
    """Apply the working zoom now and again once the editor view settles."""
    _set_working_view(sketch, size_mm)
    try:
        from .compat import QtCore

        for delay in (250, 800):
            QtCore.QTimer.singleShot(delay, lambda: _set_working_view(sketch, size_mm))
    except Exception:
        pass


def new_sketch(snapshot: Snapshot) -> tuple[bool, str]:
    """Create a sketch on the selected face or a chosen plane.

    The sketch is created directly and opened with setEdit, so FreeCAD's
    native plane-picker task bar never appears.
    """
    if Gui is None:
        return _fail("The LearnCad interface is not available in this session.")
    doc = App.ActiveDocument
    if doc is None:
        doc = App.newDocument()

    try:
        Gui.activateWorkbench("PartDesignWorkbench")
    except Exception:
        pass
    _ensure_view()

    body = _selected_body() or _active_body() or _first_body(doc)
    if body is None:
        try:
            Gui.runCommand("PartDesign_Body")
        except Exception:
            pass
        body = _active_body() or _first_body(doc)
    if body is None:
        body = doc.addObject("PartDesign::Body", "Body")
        doc.recompute()
        _ensure_view()
    _activate_body(body)

    try:
        gdoc = _gui_doc()
        if gdoc is not None and gdoc.getInEdit() is not None:
            return _fail("Finish the current sketch first (click Done), then create the next one.")
    except Exception:
        pass

    face_obj, face_name = _selected_face_ref()
    feature = None
    if face_obj is None or not face_name:
        from .compat import QtWidgets

        options = ["XY plane", "XZ plane", "YZ plane"]
        choice, accepted = QtWidgets.QInputDialog.getItem(
            Gui.getMainWindow(), "New sketch", "Sketch plane:", options, 0, False
        )
        if not accepted:
            return _fail("Sketch cancelled.")
        wanted = {
            "XY plane": "XY_Plane",
            "XZ plane": "XZ_Plane",
            "YZ plane": "YZ_Plane",
        }.get(choice, "XY_Plane")
        try:
            feature = next(
                (f for f in body.Origin.OriginFeatures if f.Name == wanted), None
            )
        except Exception:
            feature = None

    try:
        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        if face_obj is not None and face_name:
            sketch.AttachmentSupport = [(face_obj, face_name)]
        elif feature is not None:
            sketch.AttachmentSupport = [(feature, "")]
        sketch.MapMode = "FlatFace"
        doc.recompute()
    except Exception as exc:
        return _fail("Could not create the sketch: " + str(exc))

    ok, message = _enter_sketch(sketch)
    if not ok:
        return _fail("Created the sketch, but could not open the editor. " + message)
    _schedule_working_view(sketch)
    where = "the selected face" if face_obj is not None and face_name else "the chosen plane"
    return _ok("Sketch started on " + where + ". Draw the profile, then constrain it.")


def new_part(snapshot: Snapshot) -> tuple[bool, str]:
    doc = App.ActiveDocument
    if doc is None:
        doc = App.newDocument()
    body = _first_body(doc)
    if body is not None:
        return new_sketch(snapshot)
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    plane = None
    try:
        for feature in body.Origin.OriginFeatures:
            if feature.Name == "XY_Plane":
                plane = feature
                break
    except Exception:
        plane = None
    if plane is not None:
        sketch.AttachmentSupport = [(plane, "")]
        sketch.MapMode = "FlatFace"
    doc.recompute()
    ok, message = _enter_sketch(sketch)
    if not ok:
        return _fail("Created the body and sketch, but could not open the sketch editor. " + message)
    _schedule_working_view(sketch)
    return _ok("Created a Body and a sketch on the XY plane. Draw the outer profile, then constrain it.")


def open_pad(snapshot: Snapshot) -> tuple[bool, str]:
    from . import panel

    try:
        created = panel.show_pad_dialog()
    except Exception as exc:
        return _fail("Could not open the Pad dialog: " + str(exc))
    if created:
        return _ok("Pad created. Set the length when you create the next one.")
    return _fail("Pad was cancelled. Finish the sketch and click Pad again.")


def open_pocket(snapshot: Snapshot) -> tuple[bool, str]:
    from . import panel

    try:
        created = panel.show_pocket_dialog()
    except Exception as exc:
        return _fail("Could not open the Pocket dialog: " + str(exc))
    if created:
        return _ok("Pocket cut.")
    return _fail("Pocket was cancelled. Select a closed sketch first.")


def _select_top_face(body) -> Optional[int]:
    try:
        faces = list(body.Shape.Faces)
    except Exception:
        return None
    best_index = None
    best_score = (-2.0, -1e9)
    for index, face in enumerate(faces):
        try:
            normal = face.normalAt(0, 0)
            score = (normal.z, face.BoundBox.ZMax)
        except Exception:
            continue
        if score > best_score:
            best_score = score
            best_index = index
    if best_index is None:
        return None
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(body, f"Face{best_index + 1}")
    return best_index + 1


def open_hole(snapshot: Snapshot) -> tuple[bool, str]:
    from . import panel

    try:
        created = panel.show_hole_dialog()
    except Exception as exc:
        return _fail("Could not open the Hole dialog: " + str(exc))
    if created:
        return _ok("Hole added.")
    return _fail("Hole was cancelled. Create a solid first.")


def _select_vertical_edges(body) -> int:
    try:
        edges = list(body.Shape.Edges)
    except Exception:
        return 0
    selected = 0
    Gui.Selection.clearSelection()
    for index, edge in enumerate(edges):
        try:
            vertexes = list(edge.Vertexes)
            if len(vertexes) < 2:
                continue
            if abs(vertexes[0].Point.z - vertexes[-1].Point.z) < 0.1:
                continue
        except Exception:
            continue
        Gui.Selection.addSelection(body, f"Edge{index + 1}")
        selected += 1
        if selected >= MAX_SELECT:
            break
    return selected


def open_thickness(snapshot: Snapshot) -> tuple[bool, str]:
    from . import panel

    try:
        created = panel.show_thickness_dialog()
    except Exception as exc:
        return _fail("Could not open the Shell dialog: " + str(exc))
    if created:
        return _ok("Shell applied.")
    return _fail("Shell was cancelled. Select the face to open first.")


def open_fillet(snapshot: Snapshot) -> tuple[bool, str]:
    from . import panel

    try:
        created = panel.show_fillet_dialog()
    except Exception as exc:
        return _fail("Could not open the Fillet dialog: " + str(exc))
    if created:
        return _ok("Fillet applied.")
    return _fail("Fillet was cancelled. Select the edges to round first.")


def open_export(snapshot: Snapshot) -> tuple[bool, str]:
    body = _body_obj(snapshot)
    Gui.Selection.clearSelection()
    if body is not None:
        Gui.Selection.addSelection(body)
    Gui.runCommand("Std_Export")
    return _ok("Opened the Export dialog. Choose STL for printing or STEP for CAD interchange.")


def edit_feature(snapshot: Snapshot) -> tuple[bool, str]:
    doc = App.ActiveDocument
    if doc is None or snapshot.doc is None:
        return _fail("No document is open.")
    target_name = ""
    for body in snapshot.doc.bodies:
        for feature in body.features:
            if feature.has_error:
                target_name = feature.name
                break
        if target_name:
            break
    if not target_name:
        return _fail("No failing feature found.")
    obj = doc.getObject(target_name)
    if obj is None:
        return _fail("The failing feature could not be found in the document.")
    try:
        Gui.activateWorkbench("PartDesignWorkbench")
    except Exception:
        pass
    gdoc = _gui_doc()
    try:
        gdoc.setEdit(obj.Name)
        return _ok(f"Opened '{obj.Label or obj.Name}'. Read the solver message and fix the first error.")
    except Exception:
        pass
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(obj)
    return _ok(
        f"Selected '{obj.Label or obj.Name}'. Double-click it in the tree to edit it and read the error."
    )


ACTIONS = {
    "new_document": new_part,
    "new_part": new_part,
    "new_sketch": new_sketch,
    "activate_body": activate_body,
    "guide_sketch": guide_sketch,
    "fix_constraints": solve_constraints,
    "draw_rectangle": draw_rectangle,
    "close_sketch": close_sketch,
    "open_pad": open_pad,
    "open_pocket": open_pocket,
    "open_hole": open_hole,
    "open_thickness": open_thickness,
    "open_fillet": open_fillet,
    "open_export": open_export,
    "edit_feature": edit_feature,
}


def run_action(action_id: str, snapshot: Snapshot) -> tuple[bool, str]:
    if Gui is None:
        return _fail("The LearnCad interface is not available in this session.")
    action = ACTIONS.get(action_id)
    if action is None:
        return _fail(f"No action is registered for '{action_id}'.")
    try:
        return action(snapshot)
    except Exception as exc:
        return _fail(f"Could not complete the action: {exc}")
