# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the LearnCad addon.
"""Curated tool catalog for the LearnCad shell.

Commands are plain FreeCAD command ids so the toolbar menus and the searchable
palette stay independent of any Qt or geometry code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    label: str
    command: str
    hint: str = ""


@dataclass(frozen=True)
class Group:
    label: str
    tools: tuple[Tool, ...]


SKETCH_DRAW = Group("Draw", (
    Tool("Line", "Sketcher_CreatePolyline", "Connected line segments"),
    Tool("Line by angle", "Sketcher_CreateLineAngleLength", "Line from an angle and a length"),
    Tool("Arc", "Sketcher_CreateArc", "Arc from centre, start and end"),
    Tool("Arc (3 point)", "Sketcher_Create3PointArc", "Arc through three points"),
    Tool("Circle", "Sketcher_CreateCircle", "Circle from centre and radius"),
    Tool("Circle (3 point)", "Sketcher_Create3PointCircle", "Circle through three points"),
    Tool("Rectangle", "Sketcher_CreateRectangle", "Rectangle from two corners"),
    Tool("Rectangle (centre)", "Sketcher_CreateRectangle_Center", "Rectangle from its centre"),
    Tool("Rectangle (3 point)", "Sketcher_CreateRectangle3Points", "Angled rectangle"),
    Tool("Slot", "Sketcher_CreateSlot", "Straight slot"),
    Tool("Arc slot", "Sketcher_CreateArcSlot", "Curved slot"),
    Tool("Ellipse", "Sketcher_CreateEllipseByCenter", "Ellipse from centre"),
    Tool("Ellipse (3 point)", "Sketcher_CreateEllipseBy3Points", "Ellipse through points"),
    Tool("Elliptical arc", "Sketcher_CreateElliptical_Arc", "Arc of an ellipse"),
    Tool("Polygon", "Sketcher_CreateRegularPolygon", "Regular polygon with a chosen side count"),
    Tool("Triangle", "Sketcher_CreateTriangle", "Equilateral triangle"),
    Tool("Square", "Sketcher_CreateSquare", "Square"),
    Tool("Pentagon", "Sketcher_CreatePentagon", "Regular pentagon"),
    Tool("Hexagon", "Sketcher_CreateHexagon", "Regular hexagon"),
    Tool("Heptagon", "Sketcher_CreateHeptagon", "Regular heptagon"),
    Tool("Octagon", "Sketcher_CreateOctagon", "Regular octagon"),
    Tool("B-spline", "Sketcher_CreateBSpline", "Freeform curve"),
    Tool("B-spline by interpolation", "Sketcher_CreateBSplineByInterpolation", "Freeform curve through points"),
    Tool("Periodic B-spline", "Sketcher_CreatePeriodicBSpline", "Closed freeform curve"),
    Tool("Periodic B-spline by interpolation", "Sketcher_CreatePeriodicBSplineByInterpolation", "Closed freeform curve through points"),
    Tool("Arc of hyperbola", "Sketcher_CreateArcOfHyperbola", "Hyperbolic arc"),
    Tool("Arc of parabola", "Sketcher_CreateArcOfParabola", "Parabolic arc"),
    Tool("Point", "Sketcher_CreatePoint", "Single point"),
    Tool("Sketch fillet", "Sketcher_CreateFillet", "Round two sketch edges"),
    Tool("Sketch chamfer", "Sketcher_CreateChamfer", "Bevel two sketch edges"),
))

SKETCH_GEOMETRIC = Group("Geometric constraints", (
    Tool("Coincident", "Sketcher_ConstrainCoincident", "Join two points"),
    Tool("Point on object", "Sketcher_ConstrainPointOnObject", "Keep a point on an edge"),
    Tool("Horizontal", "Sketcher_ConstrainHorizontal", "Make a line horizontal"),
    Tool("Vertical", "Sketcher_ConstrainVertical", "Make a line vertical"),
    Tool("Horizontal/Vertical", "Sketcher_ConstrainHorVer", "Choose horizontal or vertical automatically"),
    Tool("Parallel", "Sketcher_ConstrainParallel", "Make two lines parallel"),
    Tool("Perpendicular", "Sketcher_ConstrainPerpendicular", "Make two lines perpendicular"),
    Tool("Tangent", "Sketcher_ConstrainTangent", "Make an edge tangent to a curve"),
    Tool("Equal", "Sketcher_ConstrainEqual", "Make two lengths or radii equal"),
    Tool("Symmetric", "Sketcher_ConstrainSymmetric", "Mirror two points about a line"),
    Tool("Block", "Sketcher_ConstrainBlock", "Freeze geometry in place"),
    Tool("Lock", "Sketcher_ConstrainLock", "Lock a point to its current position"),
))

SKETCH_DIMENSIONAL = Group("Dimensional constraints", (
    Tool("Distance", "Sketcher_ConstrainDistance", "Distance between two points"),
    Tool("Horizontal distance", "Sketcher_ConstrainDistanceX", "Horizontal distance"),
    Tool("Vertical distance", "Sketcher_ConstrainDistanceY", "Vertical distance"),
    Tool("Radius", "Sketcher_ConstrainRadius", "Radius of a circle or arc"),
    Tool("Diameter", "Sketcher_ConstrainDiameter", "Diameter of a circle or arc"),
    Tool("Radius/Diameter", "Sketcher_ConstrainRadiam", "Choose radius or diameter"),
    Tool("Angle", "Sketcher_ConstrainAngle", "Angle between two lines"),
    Tool("Snell's law", "Sketcher_ConstrainSnellsLaw", "Refraction constraint"),
))

SKETCH_CONSTRAINT_TOOLS = Group("Constraint tools", (
    Tool("Toggle driving/reference", "Sketcher_ToggleDrivingConstraint", "Switch a dimension between driving and reference"),
    Tool("Select degrees of freedom", "Sketcher_SelectElementsWithDoFs", "Highlight geometry that can still move"),
    Tool("Select redundant", "Sketcher_SelectRedundantConstraints", "Highlight redundant constraints"),
    Tool("Select conflicting", "Sketcher_SelectConflictingConstraints", "Highlight conflicting constraints"),
    Tool("Select malformed", "Sketcher_SelectMalformedConstraints", "Highlight malformed constraints"),
    Tool("Select partially redundant", "Sketcher_SelectPartiallyRedundantConstraints", "Highlight partially redundant constraints"),
    Tool("Select constraints", "Sketcher_SelectConstraints", "Highlight selected constraints"),
    Tool("Select associated geometry", "Sketcher_SelectElementsAssociatedWithConstraints", "Show geometry linked to constraints"),
    Tool("Toggle active constraint", "Sketcher_ToggleActiveConstraint", "Activate or deactivate a constraint"),
    Tool("Validate sketch", "Sketcher_ValidateSketch", "Find open vertices, missing coincidences and invalid geometry"),
))

SKETCH_MODIFY = Group("Modify", (
    Tool("Trim", "Sketcher_Trimming", "Trim an edge to the nearest intersection"),
    Tool("Extend", "Sketcher_Extend", "Extend an edge to the next boundary"),
    Tool("Split", "Sketcher_Split", "Split an edge at a point"),
    Tool("Offset", "Sketcher_Offset", "Offset selected edges"),
    Tool("Copy", "Sketcher_Copy", "Copy sketch geometry"),
    Tool("Move", "Sketcher_Move", "Move sketch geometry"),
    Tool("Rotate", "Sketcher_Rotate", "Rotate sketch geometry"),
    Tool("Scale", "Sketcher_Scale", "Scale sketch geometry"),
    Tool("Symmetry", "Sketcher_Symmetry", "Mirror sketch geometry"),
    Tool("Rectangular array", "Sketcher_RectangularArray", "Repeat geometry in a grid"),
    Tool("Construction geometry", "Sketcher_ToggleConstruction", "Toggle construction mode"),
    Tool("Mirror sketch", "Sketcher_MirrorSketch", "Mirror the whole sketch"),
))

SKETCH_DELETE = Group("Delete", (
    Tool("Delete geometry", "Sketcher_DeleteGeometry", "Delete selected geometry"),
    Tool("Delete constraints", "Sketcher_DeleteConstraints", "Delete selected constraints"),
    Tool("Delete all geometry", "Sketcher_DeleteAllGeometry", "Clear the sketch geometry"),
    Tool("Delete all constraints", "Sketcher_DeleteAllConstraints", "Clear all sketch constraints"),
))

SKETCH_UTILITIES = Group("Sketch utilities", (
    Tool("View sketch", "Sketcher_ViewSketch", "Look straight at the sketch plane"),
    Tool("Section view", "Sketcher_ViewSection", "Section the view at the sketch plane"),
    Tool("Map sketch", "Sketcher_MapSketch", "Attach a sketch to a face or plane"),
    Tool("Reorient sketch", "Sketcher_ReorientSketch", "Move the sketch to another plane"),
    Tool("Merge sketches", "Sketcher_MergeSketches", "Combine two sketches"),
    Tool("Switch virtual space", "Sketcher_SwitchVirtualSpace", "Show hidden construction geometry"),
    Tool("Restore internal geometry", "Sketcher_RestoreInternalAlignmentGeometry", "Restore ellipse and B-spline internals"),
    Tool("B-spline to NURBS", "Sketcher_BSplineConvertToNURBS", "Convert a B-spline to NURBS"),
    Tool("B-spline polygon", "Sketcher_BSplinePolygon", "Show the control polygon"),
    Tool("B-spline comb", "Sketcher_BSplineComb", "Show the curvature comb"),
    Tool("Join curves", "Sketcher_JoinCurves", "Join selected curves"),
    Tool("Carbon copy", "Sketcher_CarbonCopy", "Copy geometry from another sketch"),
    Tool("Grid", "Sketcher_Grid", "Toggle the sketch grid"),
    Tool("Snap", "Sketcher_Snap", "Toggle grid snapping"),
    Tool("Crosshair", "Sketcher_Crosshair", "Toggle the crosshair"),
    Tool("Stop operation", "Sketcher_StopOperation", "Stop the current sketch tool"),
))

SKETCH_GROUPS = (
    SKETCH_DRAW,
    SKETCH_GEOMETRIC,
    SKETCH_DIMENSIONAL,
    SKETCH_CONSTRAINT_TOOLS,
    SKETCH_MODIFY,
    SKETCH_DELETE,
    SKETCH_UTILITIES,
)

MODEL_CREATE = Group("Create", (
    Tool("New body", "PartDesign_Body", "Create a PartDesign Body"),
    Tool("New sketch", "PartDesign_NewSketch", "Create a sketch on a plane or face"),
    Tool("Text shape", "Draft_ShapeString", "Create printable geometry from a text string"),
    Tool("Part container", "Std_Part", "Create a Part container for assemblies"),
    Tool("Datum plane", "PartDesign_Plane", "Create a reference plane"),
    Tool("Datum line", "PartDesign_Line", "Create a reference axis"),
    Tool("Datum point", "PartDesign_Point", "Create a reference point"),
    Tool("Shape binder", "PartDesign_ShapeBinder", "Reference geometry from another body"),
    Tool("Sub-shape binder", "PartDesign_SubShapeBinder", "Reference faces or edges"),
    Tool("Clone", "PartDesign_Clone", "Clone a body or feature"),
    Tool("Boolean", "PartDesign_Boolean", "Combine bodies"),
    Tool("Base feature", "PartDesign_BaseFeature", "Start from imported geometry"),
    Tool("Move tip", "PartDesign_MoveTip", "Choose the current result feature"),
))

MODEL_EDIT = Group("Edit", (
    Tool("Undo", "Std_Undo", "Undo the last change"),
    Tool("Redo", "Std_Redo", "Redo the last undone change"),
    Tool("Copy", "Std_Copy", "Copy the selection"),
    Tool("Paste", "Std_Paste", "Paste the clipboard"),
    Tool("Duplicate", "Std_DuplicateSelection", "Duplicate the selection"),
    Tool("Delete", "Std_Delete", "Delete the selection"),
    Tool("Recompute", "Std_Recompute", "Recompute the document"),
))

MODEL_ADD = Group("Add material", (
    Tool("Pad", "PartDesign_Pad", "Extrude a sketch"),
    Tool("Revolution", "PartDesign_Revolution", "Revolve a sketch"),
    Tool("Additive pipe", "PartDesign_AdditivePipe", "Sweep a profile along a path"),
    Tool("Additive loft", "PartDesign_AdditiveLoft", "Loft between profiles"),
    Tool("Additive helix", "PartDesign_AdditiveHelix", "Add a helical feature"),
    Tool("Additive box", "PartDesign_AdditiveBox", "Add a box"),
    Tool("Additive cylinder", "PartDesign_AdditiveCylinder", "Add a cylinder"),
    Tool("Additive sphere", "PartDesign_AdditiveSphere", "Add a sphere"),
    Tool("Additive cone", "PartDesign_AdditiveCone", "Add a cone"),
    Tool("Additive torus", "PartDesign_AdditiveTorus", "Add a torus"),
    Tool("Additive prism", "PartDesign_AdditivePrism", "Add a prism"),
    Tool("Additive wedge", "PartDesign_AdditiveWedge", "Add a wedge"),
    Tool("Additive ellipsoid", "PartDesign_AdditiveEllipsoid", "Add an ellipsoid"),
))

MODEL_REMOVE = Group("Remove material", (
    Tool("Pocket", "PartDesign_Pocket", "Cut a sketch into the solid"),
    Tool("Hole", "PartDesign_Hole", "Add a hole feature"),
    Tool("Groove", "PartDesign_Groove", "Revolve a cut"),
    Tool("Subtractive pipe", "PartDesign_SubtractivePipe", "Sweep a cut along a path"),
    Tool("Subtractive loft", "PartDesign_SubtractiveLoft", "Loft a cut between profiles"),
    Tool("Subtractive helix", "PartDesign_SubtractiveHelix", "Cut a helical feature"),
    Tool("Subtractive box", "PartDesign_SubtractiveBox", "Cut a box"),
    Tool("Subtractive cylinder", "PartDesign_SubtractiveCylinder", "Cut a cylinder"),
    Tool("Subtractive sphere", "PartDesign_SubtractiveSphere", "Cut a sphere"),
    Tool("Subtractive cone", "PartDesign_SubtractiveCone", "Cut a cone"),
    Tool("Subtractive torus", "PartDesign_SubtractiveTorus", "Cut a torus"),
    Tool("Subtractive prism", "PartDesign_SubtractivePrism", "Cut a prism"),
    Tool("Subtractive wedge", "PartDesign_SubtractiveWedge", "Cut a wedge"),
    Tool("Subtractive ellipsoid", "PartDesign_SubtractiveEllipsoid", "Cut an ellipsoid"),
))

MODEL_DRESS = Group("Dress-up and repeat", (
    Tool("Fillet", "PartDesign_Fillet", "Round selected edges"),
    Tool("Chamfer", "PartDesign_Chamfer", "Bevel selected edges"),
    Tool("Draft", "PartDesign_Draft", "Draft selected faces"),
    Tool("Thickness / Shell", "PartDesign_Thickness", "Hollow a solid"),
    Tool("Mirror", "PartDesign_Mirrored", "Mirror a feature about a plane"),
    Tool("Linear pattern", "PartDesign_LinearPattern", "Repeat a feature in a line"),
    Tool("Polar pattern", "PartDesign_PolarPattern", "Repeat a feature around an axis"),
    Tool("Multi-transform", "PartDesign_MultiTransform", "Combine patterns and mirrors"),
    Tool("Scaled", "PartDesign_Scaled", "Scale a feature"),
))

MODEL_TREE = Group("Feature tree", (
    Tool("Move feature", "PartDesign_MoveFeature", "Move a feature to another body"),
    Tool("Move feature in tree", "PartDesign_MoveFeatureInTree", "Reorder a feature"),
    Tool("Coordinate system", "PartDesign_CoordinateSystem", "Add a local coordinate system"),
    Tool("Migrate", "PartDesign_Migrate", "Migrate legacy Part Design features"),
    Tool("Involute gear", "PartDesign_InvoluteGear", "Create an involute gear"),
    Tool("Sprocket", "PartDesign_Sprocket", "Create a sprocket"),
))

MODEL_PART = Group("Part and inspection", (
    Tool("Check geometry", "Part_CheckGeometry", "Check a shape for invalid topology"),
    Tool("Measure", "Std_Measure", "Measure a distance, angle or area"),
    Tool("Extrude", "Part_Extrude", "Extrude a shape, including text"),
    Tool("Revolve", "Part_Revolve", "Revolve a shape"),
    Tool("Loft", "Part_Loft", "Loft between shapes"),
    Tool("Sweep", "Part_Sweep", "Sweep a shape along a path"),
    Tool("Mirror", "Part_Mirror", "Mirror a shape"),
    Tool("Offset 2D", "Part_Offset2D", "Offset a 2D outline"),
    Tool("Thickness", "Part_Thickness", "Hollow a shape"),
    Tool("Chamfer", "Part_Chamfer", "Bevel edges"),
    Tool("Fillet", "Part_Fillet", "Round edges"),
    Tool("Shape from mesh", "Part_ShapeFromMesh", "Turn an imported mesh into a shape"),
    Tool("Section", "Part_Section", "Section a shape with a plane"),
    Tool("Cross sections", "Part_CrossSections", "Create cross-section curves"),
    Tool("Offset", "Part_Offset", "Offset a shape"),
    Tool("Boolean", "Part_Boolean", "Fuse, cut or intersect shapes"),
    Tool("Defeaturing", "Part_Defeaturing", "Remove selected faces"),
    Tool("Refine shape", "Part_RefineShape", "Remove redundant edges"),
    Tool("Shape info", "Part_ShapeInfo", "Inspect a shape"),
    Tool("Make face", "Part_MakeFace", "Build a face from edges"),
    Tool("Make solid", "Part_MakeSolid", "Turn a shell into a solid"),
    Tool("Reverse shape", "Part_ReverseShape", "Reverse face orientation"),
))

MODEL_GROUPS = (
    MODEL_CREATE,
    MODEL_EDIT,
    MODEL_ADD,
    MODEL_REMOVE,
    MODEL_DRESS,
    MODEL_TREE,
    MODEL_PART,
)

VIEW_GROUPS = (
    Group("View", (
        Tool("Fit all", "Std_ViewFitAll", "Frame the whole model"),
        Tool("Fit selection", "Std_ViewFitSelection", "Frame the selection"),
        Tool("Isometric", "Std_ViewIsometric", "Isometric view"),
        Tool("Front", "Std_ViewFront", "Front view"),
        Tool("Top", "Std_ViewTop", "Top view"),
        Tool("Right", "Std_ViewRight", "Right view"),
        Tool("Left", "Std_ViewLeft", "Left view"),
        Tool("Rear", "Std_ViewRear", "Rear view"),
        Tool("Bottom", "Std_ViewBottom", "Bottom view"),
        Tool("Dimetric", "Std_ViewDimetric", "Dimetric view"),
        Tool("Trimetric", "Std_ViewTrimetric", "Trimetric view"),
        Tool("Home", "Std_ViewHome", "Home view"),
        Tool("Orthographic", "Std_OrthographicCamera", "Orthographic camera"),
        Tool("Perspective", "Std_PerspectiveCamera", "Perspective camera"),
        Tool("Rotate left", "Std_ViewRotateLeft", "Rotate the view left"),
        Tool("Rotate right", "Std_ViewRotateRight", "Rotate the view right"),
        Tool("Zoom in", "Std_ViewZoomIn", "Zoom in"),
        Tool("Zoom out", "Std_ViewZoomOut", "Zoom out"),
        Tool("Clip plane", "Std_ToggleClipPlane", "Toggle a clipping plane"),
        Tool("Screenshot", "Std_ViewScreenShot", "Save a screenshot"),
        Tool("Toggle visibility", "Std_ToggleVisibility", "Show or hide the selection"),
        Tool("Hide selection", "Std_HideSelection", "Hide the selection"),
        Tool("Show selection", "Std_ShowSelection", "Show the selection"),
        Tool("Select all", "Std_SelectAll", "Select all objects"),
        Tool("Delete", "Std_Delete", "Delete the selection"),
        Tool("Transform", "Std_Transform", "Move or rotate the selection"),
        Tool("Placement", "Std_Placement", "Edit placement numerically"),
        Tool("Properties", "Std_Properties", "Open the property editor"),
        Tool("Recompute", "Std_Recompute", "Recompute the document"),
        Tool("Model tree", "CADet_ToggleTree", "Show or hide the model tree"),
    )),
)

FILE_GROUPS = (
    Group("File", (
        Tool("New", "Std_New", "New document"),
        Tool("Open", "Std_Open", "Open a model"),
        Tool("Save", "Std_Save", "Save the document"),
        Tool("Save as", "Std_SaveAs", "Save under a new name"),
        Tool("Save a copy", "Std_SaveCopy", "Write a copy without changing the open file"),
        Tool("Import", "Std_Import", "Import STEP, IGES, STL or other formats"),
        Tool("Export", "Std_Export", "Export the selection"),
        Tool("Print", "Std_Print", "Print the current view"),
        Tool("Print PDF", "Std_PrintPdf", "Write a PDF"),
    )),
)

LEARNCAD_GROUPS = (
    Group("LearnCad", (
        Tool("Open coach", "CADet_OpenMentor", "Open the LearnCad coach panel"),
        Tool("Review model", "CADet_ReviewModel", "Run a fresh engineering review"),
        Tool("Studio look", "CADet_StudioLook", "Apply the clean viewport style"),
        Tool("Render studio", "CADet_RenderPreview", "Render a still with the studio engine"),
        Tool("Set active body", "CADet_ActivateBody", "Make the selected Body active"),
        Tool("Model tree", "CADet_ToggleTree", "Show or hide the model tree"),
        Tool("Setup", "CADet_Settings", "Open LearnCad settings"),
    )),
)

ALL_GROUPS = SKETCH_GROUPS + MODEL_GROUPS + VIEW_GROUPS + FILE_GROUPS + LEARNCAD_GROUPS


def tool_by_command(command: str) -> Tool | None:
    for group in ALL_GROUPS:
        for tool in group.tools:
            if tool.command == command:
                return tool
    return None
