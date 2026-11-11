# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""The LearnCad product guide.

This is the single source of truth for both the local mentor and the optional
AI layer. It describes the beginner-facing workspace only, using the labels the
user can actually see. It never reveals the underlying CAD engine or renderer.
"""

from __future__ import annotations

from dataclasses import dataclass

APP_GUIDE = """LearnCad is a guided mechanical CAD workspace for learning by building.
Units are millimetres. Simple Mode is on by default.

THE WORKSPACE
- The left panel titled "LearnCad" is the coach and the only toolbox. It shows the model state, "DO THIS NEXT" with one big button, and a single "MENTOR" note. A slim "Ask LearnCad..." bar sits at the bottom; type a goal there or ask a question. The three-dot menu holds Courses, All tools, Studio look, Render studio, Setup and Collapse. The footer says whether AI is on.
- The Course button under the status opens two courses: Start here (Sketch a sized profile, Constrain it, Pad and export) and Design a phone stand (side profile, width, cable opening, fillet and export). Each lesson highlights the next control and saves progress. Use it whenever the user asks where to learn or wants a guided lesson.
- Main toolbar, left to right: File | Undo, Redo, Fit | Sketch, Pad | Model, Export | Find, Coach, More. Sketch opens a small LearnCad plane chooser (XY, XZ, YZ); with a face selected it sketches on that face. File holds New, Open, Save, Import and Print. Model holds the modeling features. More holds views, render, studio, setup, model tree and active body. Find opens the searchable list of every tool.
- The 3D viewport has a navigation cube in the top-right. Middle-drag to orbit, Shift+middle-drag to pan, and scroll to zoom. Fit frames the model.
- LearnCad owns every dialog: Sketch plane, Dim/Radius value, Pad, Pocket, Hole, Fillet and Shell. The engine task bar is never shown, and there is no document tab bar. In a sketch, use the top sketch toolbar for constraints and Done to finish.
- Simple Mode hides the advanced menus, default toolbars, status bar, and Model tree. Setup has a Simple Mode checkbox that restores the advanced workspace.
- The coach is not a modal window. If it is closed, click Coach on the main toolbar.

THE ONE WORKFLOW
1. Type the part in the Ask LearnCad bar (for example: a phone stand, a bracket, an enclosure). Press Enter.
2. Click Create Body + Sketch. LearnCad creates a Body and opens a sketch on the XY plane.
3. Pick Rect, Circle, Arc, Slot or Line in the sketch toolbar. Click to place geometry. Right-click or Escape stops the tool. The Draw menu has ellipses, polygons, B-splines, points and more.
4. Constrain: select geometry, then use Coincident, Horizontal, Vertical, Parallel, Perpendicular, Tangent, Equal, Dimension or Radius. The Constrain menu has every constraint, including Symmetric, Block, Lock, Angle and horizontal/vertical distances. The coach button changes with the state: Draw a rectangle, Guide me through constraints, or Close the sketch. Fully constrained means 0 degrees of freedom.
5. Click Done to close the sketch.
6. Click Pad on the main toolbar. Set the distance and direction, then confirm. The sketch becomes the first solid.
7. Open the Model menu and choose Pocket, Hole, Chamfer or Fillet. Select the sketch, face, or edges first, or use the Guide me button in the coach.
8. Click Export to write STL (printing) or STEP (CAD exchange). Click Render for a studio image.

SKETCHING ON AN EXISTING PART
- Select the face where the next sketch should live, then click Sketch on the main toolbar.
- The LearnCad plane chooser opens with that face preselected. Choose XY, XZ, or YZ instead if needed.
- The new sketch belongs to the active Body. Finish the current sketch with Done before starting another.

SKETCH TOOLBAR
Undo, Redo, Fit | Rect, Circle, Arc, Slot, Line | Coincident, Horizontal, Vertical, Parallel, Perpendicular, Tangent, Equal, Dimension, Radius | Trim, Construction | Draw, Constrain, Edit | Coach, Done.
- Rect: click two opposite corners.
- Circle: click the centre, then a point on the circumference.
- Arc: click the centre, start and end. Slot: click the two end centres, then the width.
- Line: click points; right-click or Escape finishes; use Coincident to close the loop.
- Coincident joins two points. Horizontal and Vertical straighten a selected line. Parallel, Perpendicular, Tangent and Equal lock relationships. Dimension sets a distance. Radius sizes an arc or circle.
- Trim cuts an edge back to an intersection. Construction toggles reference geometry that does not become part of the profile.
- The Draw menu adds ellipse, elliptical arc, polygon, square, hexagon, triangle, B-spline, point and sketch fillet/chamfer.
- The Constrain menu adds Point on object, Symmetric, Block, Lock, Angle, Diameter, horizontal/vertical distance, Snell's law, reference dimensions, select degrees of freedom, redundant/conflicting/malformed constraints, and Validate sketch.
- The Edit menu adds Extend, Split, Offset, Copy, Move, Rotate, Scale, Symmetry, Rectangular array, Mirror sketch, Delete, View sketch, Map sketch, Reorient sketch, Merge sketches and B-spline tools.
- Done closes the sketch. Coach reopens the floating panel.

ALL TOOLS
- Click the search icon (All tools) on the main toolbar, or press Ctrl+K.
- Type a tool name such as arc, tangent, loft, measure or export, then double-click the result to run it.
- Inside a sketch, All tools shows sketch, view, file and LearnCad tools. Outside a sketch it shows model, view, file and LearnCad tools.
- The Model menu groups Create, Add material, Remove material, Dress-up and repeat, Feature tree, and Part and inspection tools.
- The More menu groups View (fits, standard views, camera, clipping, visibility, selection, placement) and LearnCad (render, studio, setup, model tree, active body).
- If a tool is not in these menus, turn Simple Mode off in Setup to reach the advanced workspace.
- To select a sketch, datum or body, click Model tree in the LearnCad TOOL tab or choose More > LearnCad > Model tree. Click it again to hide it.
- With several bodies, select the Body in the model tree, then click Active body in the LearnCad TOOL tab before adding features.

IMPORTANT TOOLS YOU MAY NEED
- Model: Revolution, Loft, Pipe, Helix, Thickness/Shell, Chamfer, Draft, Mirror, Linear/Polar pattern, Multi-transform, Boolean, Datum plane/line/point, Shape binder, Clone.
- Inspect: Check geometry, Measure, Section, Cross sections, Shape info.
- File: Save as, Save a copy, Import, Export, Print and Print PDF.
- View: Fit selection, standard views, clipping plane, screenshot and visibility controls.
- Text and imported meshes: Text shape in the Create group makes printable lettering; extrude it with Part Extrude. Shape from mesh and Make solid help clean up an imported STL.

COACH BUTTONS
- Create Body + Sketch: start a part on the XY plane.
- Draw a rectangle: arms Rect for an empty sketch.
- Guide me through constraints: enters the sketch and selects geometry with missing constraints.
- Open the Pad dialog: available after the sketch is closed and constrained.
- Studio: applies the clean LearnCad viewport look.
- Render: renders a still from the current solid.
- Setup: opens settings.
- Coach: reopens the panel from the main toolbar.
- Ask LearnCad bar: type a goal or a question. Without AI, the local mentor answers.

SETUP
- Simple Mode on/off. Off restores the advanced workspace.
- AI explanations are a paid add-on and off by default. The local mentor always works for free. Subscribe on the web page, then enter your email and license code in Setup and press Activate. AI sends a compact model summary and the question to the LearnCad AI server; geometry files are never uploaded.
- Render material (Aluminum, Plastic, Rubber), resolution, and samples are set here. Render uses the studio setup automatically.
- New, Open, and Save use the normal LearnCad file dialog. Undo and Redo cover model edits.
- The Render dialog has Advanced scene for inspecting the full studio scene.

TROUBLESHOOTING
- A tool is unavailable: finish the current sketch with Done, or select the sketch, face, or edges it needs.
- Pad does nothing: the profile is empty or open. Find the gap with Coincident and make one closed wire.
- The panel is gone: click Coach on the main toolbar.
- The canvas looks empty: click Fit. The model may be off-screen.
- The sketch is not constrained: the coach shows N DoF left. Add Coincident first, then Horizontal/Vertical, then dimensions.
- A sketch attached to a generated face broke after an edit: reattach it to a principal plane. Generated faces can be renamed.
- Export choices: STL for printing, STEP for CAD exchange.

AI BEHAVIOUR
- The coach can run an interactive walkthrough: one step at a time, with the target control glowing orange. When that happens, keep the answer short and tell the user to follow the highlighted control.
- For how-to questions, use only the control names in this guide, in a short numbered sequence.
- Never mention the underlying CAD engine, its menus, workbenches, or version. Never send the user to a menu that is not in this guide.
- For model questions, use the live document facts and the deterministic review.
- Keep UI answers under 200 words unless the user asks for a full walkthrough.
- If the guide does not cover a control, say that Simple Mode exposes the listed tools and that Setup can restore the advanced workspace.
"""


_HOWTO_MARKERS = (
    "how do i",
    "how to",
    "how can i",
    "where is",
    "where do i",
    "where can i",
    "which button",
    "what button",
    "find the",
    "show me the",
    "teach me",
    "walk me",
    "toolbar",
    "button",
    "panel",
    "menu",
    "shortcut",
    "use learncad",
    "learncad work",
    "what is the workflow",
    "get started",
    "start a part",
    "press",
    "click",
    "what next",
    "what now",
    "what do i do",
    "guide me",
    "help me",
    "stuck",
    "highlight",
    "which control",
    "show me where",
    "course",
    "lesson",
    "curriculum",
)


def looks_like_howto(question: str) -> bool:
    q = (question or "").strip().lower()
    return any(marker in q for marker in _HOWTO_MARKERS)


def answer(question: str) -> str:
    q = (question or "").strip().lower()

    if "course" in q or "lesson" in q or "curriculum" in q:
        return (
            "The LearnCad course has three lessons:\n"
            "1. Sketch a sized profile.\n"
            "2. Constrain it.\n"
            "3. Pad and export.\n"
            "Click the Courses button under the status in the LearnCad panel, then Start lesson. "
            "Each step glows the next control, and progress is saved between sessions."
        )
    if "rectangle" in q or "rect" in q:
        return (
            "To draw a rectangle:\n"
            "1. In the sketch toolbar, click Rect.\n"
            "2. Click the first corner, then the opposite corner on the XY plane.\n"
            "3. Right-click or press Escape to stop the tool.\n"
            "4. Select an edge, then use Dimension to set its size.\n"
            "If no sketch is open yet, first click Create Body + Sketch in the LearnCad panel."
        )
    if "circle" in q:
        return (
            "To draw a circle:\n"
            "1. In the sketch toolbar, click Circle.\n"
            "2. Click the centre, then a point on the circumference.\n"
            "3. Select the circle and use Radius or Dimension to set its size.\n"
            "Right-click or Escape stops the tool."
        )
    if "line" in q or "polyline" in q:
        return (
            "To draw lines:\n"
            "1. In the sketch toolbar, click Line.\n"
            "2. Click each point of the profile.\n"
            "3. Right-click or press Escape to finish.\n"
            "4. Select the endpoints and use Coincident to close the loop.\n"
            "A closed profile is required before Pad will work."
        )
    if "leave" in q or "close the sketch" in q or "close sketch" in q or "finish the sketch" in q:
        return (
            "Click Done in the sketch toolbar to close the sketch. "
            "If the profile is closed and fully constrained, the coach changes to Open the Pad dialog. "
            "If it is still open or under-constrained, the coach tells you what is missing first."
        )
    if "sketch" in q and any(
        word in q
        for word in ("new", "add", "create", "face", "plane", "on top", "another")
    ):
        return (
            "To create a new sketch:\n"
            "1. Select the face or principal plane you want, or select nothing to choose XY, XZ, or YZ.\n"
            "2. Click Sketch on the main toolbar.\n"
            "3. The LearnCad plane chooser preselects that face; choose it, then draw and constrain the profile.\n"
            "If a sketch is already open, click Done first."
        )
    if any(word in q for word in ("pad", "extrude", "make it solid", "make a solid")):
        return (
            "To pad a sketch:\n"
            "1. Click Done to close the sketch.\n"
            "2. Click Pad on the main toolbar.\n"
            "3. Enter the distance and direction in the LearnCad Pad dialog.\n"
            "4. Confirm. Pad needs one closed profile.\n"
            "If Pad is unavailable, select the sketch or finish the current edit first."
        )
    if "pocket" in q:
        return (
            "To cut a pocket:\n"
            "1. Create and constrain a sketch on the face where the pocket belongs.\n"
            "2. Click Done to close it.\n"
            "3. Open the Model menu and choose Pocket.\n"
            "4. Set the depth and confirm.\n"
            "Select the sketch first if Pocket is unavailable."
        )
    if "hole" in q:
        return (
            "To add a hole:\n"
            "1. Select the face where the hole should start.\n"
            "2. Open the Model menu and choose Hole.\n"
            "3. Set the diameter and depth in the LearnCad Hole dialog, then confirm.\n"
            "For an M3 clearance hole, 3.2-3.4 mm is a good starting point. Printed holes often come out undersized."
        )
    if any(word in q for word in ("fillet", "chamfer", "round the edge", "round edges")):
        return (
            "To round edges:\n"
            "1. Select the edges you want to change in the 3D viewport.\n"
            "2. Open the Model menu and choose Fillet.\n"
            "3. Set the radius and confirm.\n"
            "Add fillets after the functional holes and pockets. For printed parts, 0.5-2 mm is usually enough."
        )
    if "export" in q or "stl" in q or "step" in q:
        return (
            "To export:\n"
            "1. Select the body or the final feature.\n"
            "2. Click Export on the main toolbar.\n"
            "3. Choose STL for printing or STEP for CAD exchange.\n"
            "STL stores the mesh; STEP keeps precise surfaces."
        )
    if any(word in q for word in ("render", "studio image", "picture", "photo")):
        return (
            "To make a studio image:\n"
            "1. Open the LearnCad menu (three dots) and choose Render studio.\n"
            "2. Choose the material and size in Setup if you want a different look.\n"
            "3. Render. The Render dialog can open Advanced scene to inspect the full studio setup.\n"
            "Studio applies the clean viewport look; Render produces the still image."
        )
    if any(word in q for word in ("setup", "settings", "simple mode", "ai", "api key", "provider")):
        return (
            "Click Setup on the main toolbar or in the LearnCad panel.\n"
            "- Simple Mode switches between the beginner workspace and the advanced workspace.\n"
            "- AI explanations are a paid add-on and off by default. The local mentor works for free.\n"
            "- To activate AI: subscribe on the web page, then enter your email and license code in Setup and press Activate.\n"
            "- When AI is on, Ask LearnCad sends a compact model summary and your question to the LearnCad AI server; geometry files are not uploaded."
        )
    if any(word in q for word in ("panel", "coach", "more details", "ask learncad", "mentor")):
        return (
            "The floating LearnCad panel is the coach. If it is closed, click Coach on the main toolbar.\n"
            "- The Ask LearnCad bar stores the goal when you type a part name.\n"
            "- DO THIS NEXT is the next action and its button.\n"
            "- The slim Ask LearnCad bar types a goal or a question; the three-dot menu opens All tools, Studio, Render, Setup.\n"
            "- The coach works without AI. Setup turns AI explanations on if you want them."
        )
    if any(word in q for word in ("constrain", "constraint", "dimension", "radius", "coincident", "horizontal", "vertical", "dof", "degrees of freedom")):
        return (
            "Constrain in this order:\n"
            "1. Coincident: join endpoints that should touch.\n"
            "2. Horizontal or Vertical: straighten a selected line.\n"
            "3. Dimension: set distances and positions.\n"
            "4. Radius: size circles and arcs.\n"
            "The coach shows N DoF left. When it reaches 0, the sketch is fully constrained and ready to pad."
        )
    if any(word in q for word in ("rotate", "orbit", "zoom", "pan", "navigate", "fit", "view")):
        return (
            "To move around the 3D viewport:\n"
            "- Middle-drag to orbit.\n"
            "- Shift+middle-drag to pan.\n"
            "- Scroll to zoom.\n"
            "- Click Fit on the main toolbar to frame the model.\n"
            "- Use the navigation cube in the top-right for standard views."
        )
    if any(word in q for word in ("new", "open", "save", "undo", "redo", "file")):
        return (
            "The left side of the main toolbar has New, Open, and Save. Undo and Redo follow.\n"
            "- New starts a blank document.\n"
            "- Open loads a .FCStd model.\n"
            "- Save writes the current model.\n"
            "- Undo and Redo cover model edits."
        )
    if any(word in q for word in ("sketch", "start", "begin", "first", "get started", "workflow", "use learncad")):
        return (
            "Quick start:\n"
            "1. Type what you are making in the Ask LearnCad bar.\n"
            "2. Click Create Body + Sketch.\n"
            "3. Use Rect, Circle, or Line to draw the profile.\n"
            "4. Add Coincident, Horizontal/Vertical, then Dimension or Radius until the coach says 0 DoF left.\n"
            "5. Click Done, then Pad.\n"
            "6. Add Pocket, Hole, or Fillet, then Export or Render."
        )
    if any(phrase in q for phrase in ("all tools", "search", "where is", "where can i find", "find the")):
        return (
            "Click the search icon (All tools) on the main toolbar, or press Ctrl+K.\n"
            "Type the tool name, then double-click the result.\n"
            "The Model menu and the More > View section also group the most-used tools.\n"
            "Inside a sketch, use the Draw, Constrain and Edit menus."
        )
    return (
        "I can teach the full LearnCad workflow. Try: how do I draw a rectangle, how do I constrain a sketch, "
        "how do I pad it, where is the Hole tool, how do I export, or how do I render?"
    )

@dataclass(frozen=True)
class WalkthroughStep:
    """One guided step.

    target is a stable UI id such as main:Pad, sketch:Circle,
    panel:setup, or dialog:OK. An empty target is a canvas/reading step and
    uses the Next button.
    """
    text: str
    target: str = ""
    when: str = ""  # "", "not_sketch", or "sketch"
    wait_for_sketch: bool = False


@dataclass(frozen=True)
class Walkthrough:
    id: str
    title: str
    steps: tuple[WalkthroughStep, ...]


def _start_step() -> WalkthroughStep:
    return WalkthroughStep(
        "Let's start a sketch. Click Sketch on the main toolbar at the top, then choose the XY plane. "
        "I've highlighted Sketch in orange.",
        target="main:Sketch",
        when="not_sketch",
        wait_for_sketch=True,
    )


WALKTHROUGHS: dict[str, Walkthrough] = {
    "circle": Walkthrough(
        "circle",
        "Draw a circle",
        (
            _start_step(),
            WalkthroughStep(
                "Good. Now find Circle - the round symbol - in the sketch toolbar. "
                "It is glowing orange. Click it.",
                target="sketch:Circle",
            ),
            WalkthroughStep(
                "Click the centre of the sketch in the 3D view, then click a point on the circumference. "
                "When the circle is drawn, click Next.",
            ),
            WalkthroughStep(
                "Good. Select the circle edge, then click Radius in the sketch toolbar to set its size. "
                "It is highlighted.",
                target="sketch:Radius",
            ),
            WalkthroughStep(
                "Enter the radius in the LearnCad value dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "Good. Click Done in the sketch toolbar to close the sketch.",
                target="sketch:Done",
            ),
            WalkthroughStep(
                "Good. Now click Pad - the extrude command - on the main toolbar. "
                "It is glowing orange.",
                target="main:Pad",
            ),
            WalkthroughStep(
                "Set the distance in the LearnCad Pad dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "Nice work. The circle is now a solid. Add a hole, fillet, or export it."
            ),
        ),
    ),
    "rectangle": Walkthrough(
        "rectangle",
        "Draw a rectangle and pad it",
        (
            _start_step(),
            WalkthroughStep(
                "Good. Find Rect - the rectangle symbol - in the sketch toolbar. "
                "It is glowing orange. Click it.",
                target="sketch:Rect",
            ),
            WalkthroughStep(
                "Click one corner in the 3D view, then the opposite corner. "
                "When the rectangle is drawn, click Next.",
            ),
            WalkthroughStep(
                "Good. Select one edge, then click Dimension in the sketch toolbar and set the size. "
                "It is highlighted.",
                target="sketch:Dimension",
            ),
            WalkthroughStep(
                "Enter the size in the LearnCad value dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "Good. Click Done to close the sketch.",
                target="sketch:Done",
            ),
            WalkthroughStep(
                "Good. Now click Pad - the extrude command - on the main toolbar. "
                "It is glowing orange.",
                target="main:Pad",
            ),
            WalkthroughStep(
                "Set the distance in the LearnCad Pad dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "Nice work. The rectangle is now a solid. Add a hole, fillet, or export it."
            ),
        ),
    ),
    "line": Walkthrough(
        "line",
        "Draw lines and close a profile",
        (
            _start_step(),
            WalkthroughStep(
                "Good. Click Line in the sketch toolbar. It is glowing orange.",
                target="sketch:Line",
            ),
            WalkthroughStep(
                "Click each point of the profile. Right-click or Escape to finish. "
                "Then click Next.",
            ),
            WalkthroughStep(
                "Select two endpoints that should touch, then click Coincident in the sketch toolbar. "
                "It is highlighted.",
                target="sketch:Coincident",
            ),
            WalkthroughStep(
                "Good. Click Done when the profile is closed.",
                target="sketch:Done",
            ),
            WalkthroughStep(
                "Now click Pad on the main toolbar. It is glowing orange.",
                target="main:Pad",
            ),
            WalkthroughStep(
                "Set the distance and click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "The profile is now a solid. Add a hole, fillet, or export it."
            ),
        ),
    ),
    "constrain": Walkthrough(
        "constrain",
        "Constrain a sketch",
        (
            _start_step(),
            WalkthroughStep(
                "Select two endpoints that should touch, then click Coincident in the sketch toolbar. "
                "It is highlighted.",
                target="sketch:Coincident",
            ),
            WalkthroughStep(
                "Good. Select a line that should be level, then click Horiz.",
                target="sketch:Horizontal",
            ),
            WalkthroughStep(
                "Good. Select a line that should be upright, then click Vert.",
                target="sketch:Vertical",
            ),
            WalkthroughStep(
                "Select an edge, then click Dimension and enter the real size.",
                target="sketch:Dimension",
            ),
            WalkthroughStep(
                "For circles and arcs, select the curve and click Radius.",
                target="sketch:Radius",
            ),
            WalkthroughStep(
                "The coach shows N DoF left. When it reaches 0, the sketch is fully constrained and ready to pad."
            ),
        ),
    ),
    "pad": Walkthrough(
        "pad",
        "Pad a sketch into a solid",
        (
            WalkthroughStep(
                "If the sketch is still open, click Done in the sketch toolbar.",
                target="sketch:Done",
                when="sketch",
            ),
            WalkthroughStep(
                "Select the closed sketch, then click Pad - the extrude command - on the main toolbar. "
                "It is glowing orange.",
                target="main:Pad",
            ),
            WalkthroughStep(
                "Set the distance and direction in the LearnCad Pad dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "The sketch is now a solid. Add a pocket, hole, or fillet next."
            ),
        ),
    ),
    "pocket": Walkthrough(
        "pocket",
        "Cut a pocket",
        (
            WalkthroughStep(
                "Select the face where the pocket belongs in the 3D view, then click Next."
            ),
            WalkthroughStep(
                "Click Sketch on the main toolbar and choose that face.",
                target="main:Sketch",
            ),
            WalkthroughStep(
                "Draw the pocket profile with Rect or Circle in the sketch toolbar.",
                target="sketch:Rect",
            ),
            WalkthroughStep(
                "Click Done to close the profile.",
                target="sketch:Done",
            ),
            WalkthroughStep(
                "Open the Model menu and choose Pocket. The menu button is glowing orange.",
                target="main:Pocket",
            ),
            WalkthroughStep(
                "Set the depth in the LearnCad Pocket dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "The pocket is cut. Check the wall thickness around it in the coach notes."
            ),
        ),
    ),
    "hole": Walkthrough(
        "hole",
        "Add a hole",
        (
            WalkthroughStep(
                "Select the face where the hole should start in the 3D view, then click Next."
            ),
            WalkthroughStep(
                "Open the Model menu and choose Hole. The menu button is glowing orange.",
                target="main:Hole",
            ),
            WalkthroughStep(
                "Set the diameter and depth in the LearnCad Hole dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "The hole is done. For an M3 clearance hole, 3.2-3.4 mm is a good starting point."
            ),
        ),
    ),
    "fillet": Walkthrough(
        "fillet",
        "Round the edges",
        (
            WalkthroughStep(
                "Select the edges you want to round in the 3D view, then click Next."
            ),
            WalkthroughStep(
                "Open the Model menu and choose Fillet. The menu button is glowing orange.",
                target="main:Fillet",
            ),
            WalkthroughStep(
                "Set the radius in the LearnCad Fillet dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "The edges are rounded. For printed parts, 0.5-2 mm is usually enough."
            ),
        ),
    ),
    "export": Walkthrough(
        "export",
        "Export the model",
        (
            WalkthroughStep(
                "Select the body in the 3D view, then click Next."
            ),
            WalkthroughStep(
                "Click Export on the main toolbar. It is glowing orange.",
                target="main:Export",
            ),
            WalkthroughStep(
                "Choose STL for printing or STEP for CAD exchange."
            ),
        ),
    ),
    "render": Walkthrough(
        "render",
        "Render a studio image",
        (
            WalkthroughStep(
                "Open the LearnCad menu (three dots) and choose Render studio. "
                "The menu button is highlighted.",
                target="main:Render",
            ),
            WalkthroughStep(
                "Wait for the still image. Advanced scene opens the full studio setup."
            ),
        ),
    ),
}


def walkthrough_for(question: str) -> Walkthrough | None:
    q = (question or "").strip().lower()
    if "circle" in q:
        return WALKTHROUGHS["circle"]
    if any(word in q for word in ("rectangle", "rect", "box")):
        return WALKTHROUGHS["rectangle"]
    if "line" in q or "polyline" in q:
        return WALKTHROUGHS["line"]
    if "pocket" in q:
        return WALKTHROUGHS["pocket"]
    if "hole" in q:
        return WALKTHROUGHS["hole"]
    if any(word in q for word in ("fillet", "chamfer", "round the edge", "round edges")):
        return WALKTHROUGHS["fillet"]
    if "export" in q or "stl" in q or "step" in q:
        return WALKTHROUGHS["export"]
    if any(word in q for word in ("render", "studio image")):
        return WALKTHROUGHS["render"]
    if any(word in q for word in ("pad", "extrude", "make it solid", "make a solid")):
        return WALKTHROUGHS["pad"]
    if any(word in q for word in ("constrain", "coincident", "dimension", "radius", "horizontal", "vertical", "dof")):
        return WALKTHROUGHS["constrain"]
    if any(word in q for word in ("start", "begin", "first", "workflow", "use learncad", "draw")):
        return WALKTHROUGHS["rectangle"]
    return None
