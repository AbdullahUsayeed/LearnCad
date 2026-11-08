# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Pure tests for the senior-engineer rules. No FreeCAD required."""

from __future__ import annotations

from pathlib import Path

from freecad.CADet.analysis import analyze
from freecad.CADet import guide as app_guide
from freecad.CADet.coach import answer, review_report
from freecad.CADet.suggest import suggest_action
from freecad.CADet.model import (
    BBox,
    BodyInfo,
    Dimension,
    DocumentInfo,
    FeatureInfo,
    SelectionInfo,
    SketchInfo,
    Snapshot,
)


def make_sketch(**overrides) -> SketchInfo:
    data = dict(
        name="Sketch",
        label="Sketch",
        dof=0,
        fully_constrained=True,
        geometry_count=4,
        constraint_count=10,
        total_wires=1,
        closed_wires=1,
        open_wires=0,
        attached=True,
        support="XY_Plane",
        map_mode="FlatFace",
        bbox=BBox(x=40, y=20, z=0, xmax=40, ymax=20),
    )
    data.update(overrides)
    return SketchInfo(**data)


def make_pad(**overrides) -> FeatureInfo:
    data = dict(
        name="Pad",
        label="Pad",
        type_id="PartDesign::Pad",
        state=["Up-to-date"],
        valid=True,
        closed=True,
        volume=8000.0,
        bbox=BBox(x=40, y=20, z=10, xmax=40, ymax=20, zmax=10),
        is_tip=True,
        length=10.0,
    )
    data.update(overrides)
    return FeatureInfo(**data)


def make_body(**overrides) -> BodyInfo:
    data = dict(
        name="Body",
        label="Body",
        tip="Pad",
        features=[make_pad()],
        sketches=[make_sketch()],
        shape_valid=True,
        shape_closed=True,
        volume=8000.0,
        bbox=BBox(x=40, y=20, z=10, xmax=40, ymax=20, zmax=10),
        state=["Up-to-date"],
    )
    data.update(overrides)
    return BodyInfo(**data)


def make_doc(**overrides) -> DocumentInfo:
    data = dict(
        name="Unnamed",
        label="Unnamed",
        object_count=11,
        bodies=[make_body()],
        sketches=[make_sketch()],
        workbench="PartDesignWorkbench",
        units="mm",
    )
    data.update(overrides)
    return DocumentInfo(**data)


def review(doc, goal: str = "") -> tuple[Snapshot, object]:
    snapshot = Snapshot(doc=doc, goal=goal)
    return snapshot, analyze(snapshot)


def codes(analysis) -> set[str]:
    return {issue.code for issue in analysis.issues}


def test_no_document():
    snapshot, analysis = review(None)
    assert analysis.score == 0
    assert "no_document" in codes(analysis)
    assert "Create a new document" in analysis.next_step


def test_empty_document():
    doc = DocumentInfo(name="Unnamed", label="Unnamed", object_count=0)
    snapshot, analysis = review(doc)
    assert analysis.score == 12
    assert "empty_document" in codes(analysis)
    assert "Body" in analysis.next_step


def test_underconstrained_sketch_is_a_warning_with_specific_next_step():
    sketch = make_sketch(dof=4, fully_constrained=False, constraint_count=2, missing_coincident=2)
    doc = make_doc(sketches=[sketch], bodies=[make_body(sketches=[sketch])])
    snapshot, analysis = review(doc)
    assert "underconstrained" in codes(analysis)
    issue = next(i for i in analysis.issues if i.code == "underconstrained")
    assert issue.severity == "warn"
    assert "Coincident" in issue.fix
    assert "constraints" in analysis.next_step.lower() or "Finish" in analysis.next_step
    assert analysis.score < 100


def test_fully_constrained_clean_solid_gets_praise_and_high_score():
    snapshot, analysis = review(make_doc())
    assert analysis.score >= 90
    assert any(praise.code == "fully_constrained" for praise in analysis.praise)
    assert any(praise.code == "clean_solid" for praise in analysis.praise)
    assert "export" in analysis.next_step.lower()


def test_empty_body_is_not_reported_as_on_track():
    body = make_body(features=[], sketches=[], volume=0.0, shape_closed=False)
    doc = make_doc(bodies=[body], sketches=[])
    snapshot, analysis = review(doc)
    assert "empty_body" in codes(analysis)
    assert analysis.score <= 30
    assert analysis.headline == "Body ready. Sketch the profile next."


def test_body_with_only_a_sketch_is_not_called_empty():
    sketch = make_sketch()
    body = make_body(features=[], sketches=[sketch], volume=0.0, shape_closed=False)
    doc = make_doc(bodies=[body], sketches=[sketch])
    snapshot, analysis = review(doc)
    assert "body_sketch_only" in codes(analysis)
    assert "empty_body" not in codes(analysis)
    assert analysis.headline == "Sketch ready. Pad it next."


def test_imported_mesh_gets_repair_guidance():
    mesh = FeatureInfo(
        name="ImportedMesh",
        label="ImportedMesh",
        type_id="Mesh::Feature",
        valid=True,
        volume=0.0,
    )
    doc = make_doc(bodies=[], sketches=[], features=[mesh], imported_objects=["ImportedMesh"])
    snapshot, analysis = review(doc)
    assert "imported_mesh" in codes(analysis)
    assert "no_body" not in codes(analysis)
    assert analysis.score <= 60
    assert "Imported mesh" in analysis.headline
    assert "Shape from mesh" in analysis.next_step


def test_imported_solid_gets_body_guidance():
    solid = FeatureInfo(
        name="ImportedSolid",
        label="ImportedSolid",
        type_id="Part::Feature",
        valid=True,
        closed=True,
        volume=1000.0,
        bbox=BBox(x=10, y=10, z=10, xmax=10, ymax=10, zmax=10),
    )
    doc = make_doc(bodies=[], sketches=[], features=[solid], imported_objects=["ImportedSolid"])
    snapshot, analysis = review(doc)
    assert "imported_solid" in codes(analysis)
    assert "Imported geometry" in analysis.headline
    assert "Base feature" in analysis.next_step


def test_thin_pad_warning_drives_the_next_step_and_caps_the_score():
    pad = make_pad(length=0.5, volume=400.0)
    body = make_body(features=[pad], volume=400.0)
    doc = make_doc(bodies=[body], sketches=[make_sketch()])
    snapshot, analysis = review(doc)
    assert "thin_pad" in codes(analysis)
    assert analysis.score <= 80
    assert "thick" in analysis.next_step.lower()


def test_phone_stand_next_step_checks_the_stand_not_holes():
    snapshot, analysis = review(make_doc(), goal="a phone stand")
    assert analysis.intent.label == "phone stand"
    assert "front lip" in analysis.next_step.lower()
    assert "mounting holes" not in analysis.next_step.lower()


def test_bracket_next_step_asks_for_mounting_holes():
    snapshot, analysis = review(make_doc(), goal="a bracket for a 40x40 extrusion")
    assert analysis.intent.label == "bracket"
    assert "mounting holes" in analysis.next_step.lower()


def test_conflicting_constraints_are_critical():
    sketch = make_sketch(dof=3, fully_constrained=False, conflicting=2)
    doc = make_doc(sketches=[sketch], bodies=[make_body(sketches=[sketch])])
    snapshot, analysis = review(doc)
    assert "conflicting_constraints" in codes(analysis)
    issue = next(i for i in analysis.issues if i.code == "conflicting_constraints")
    assert issue.severity == "critical"
    assert analysis.score < 60
    assert analysis.next_step.startswith("Fix this first")


def test_open_profile_is_critical():
    sketch = make_sketch(total_wires=1, closed_wires=0, open_wires=1)
    doc = make_doc(sketches=[sketch], bodies=[make_body(sketches=[sketch])])
    snapshot, analysis = review(doc)
    assert "open_profile" in codes(analysis)
    assert next(i for i in analysis.issues if i.code == "open_profile").severity == "critical"


def test_thin_pad_is_warned():
    pad = make_pad(length=0.5)
    body = make_body(features=[pad])
    snapshot, analysis = review(make_doc(bodies=[body], features=[]))
    assert "thin_pad" in codes(analysis)
    assert next(i for i in analysis.issues if i.code == "thin_pad").severity == "warn"


def test_small_hole_is_warned():
    hole = FeatureInfo(
        name="Hole",
        label="Hole",
        type_id="PartDesign::Hole",
        valid=True,
        closed=True,
        volume=10.0,
        diameter=1.5,
    )
    body = make_body(features=[hole])
    snapshot, analysis = review(make_doc(bodies=[body], sketches=[]))
    assert "small_hole" in codes(analysis)


def test_intent_reads_the_object_label():
    body = make_body(label="Bracket")
    snapshot, analysis = review(make_doc(bodies=[body], sketches=[]))
    assert analysis.intent.label == "bracket"
    assert analysis.intent.confidence >= 0.7


def test_intent_reads_flat_geometry():
    body = make_body(label="Body", features=[], sketches=[], bbox=BBox(x=100, y=80, z=3, xmax=100, ymax=80, zmax=3), volume=24000.0)
    snapshot, analysis = review(make_doc(bodies=[body], sketches=[]))
    assert analysis.intent.label == "plate"


def test_body_far_from_origin_is_warned():
    body = make_body(
        bbox=BBox(x=40, y=20, z=10, xmin=900, ymin=900, zmin=0, xmax=940, ymax=920, zmax=10)
    )
    snapshot, analysis = review(make_doc(bodies=[body], sketches=[]))
    assert "far_from_origin" in codes(analysis)


def test_missing_tip_is_warned():
    body = make_body(tip="")
    snapshot, analysis = review(make_doc(bodies=[body], sketches=[]))
    assert "no_tip" in codes(analysis)


def test_review_report_contains_the_sections():
    snapshot, analysis = review(make_doc())
    report = review_report(snapshot, analysis)
    assert "MODEL REVIEW" in report
    assert "Score:" in report
    assert "NEXT STEP" in report
    assert "DIMENSIONS" in report


def test_local_answer_explains_constraints():
    sketch = make_sketch(dof=3, fully_constrained=False, missing_hv=1)
    doc = make_doc(sketches=[sketch], bodies=[make_body(sketches=[sketch])])
    snapshot, analysis = review(doc)
    response = answer("why is my sketch not constrained?", snapshot, analysis)
    assert "DoF" in response or "Horizontal" in response
    assert "Coincident" in response or "constraint" in response.lower()


def test_local_answer_next_step():
    snapshot, analysis = review(make_doc())
    response = answer("what should I do next?", snapshot, analysis)
    assert analysis.next_step in response


def test_local_answer_printability():
    snapshot, analysis = review(make_doc())
    response = answer("is this printable?", snapshot, analysis)
    assert "solid" in response.lower()
    assert "orientation" in response.lower() or "print" in response.lower()


def test_local_answer_dimensions():
    snapshot, analysis = review(make_doc())
    response = answer("what are the dimensions?", snapshot, analysis)
    assert "40" in response and "20" in response and "10" in response


def test_tiny_sketch_and_radius_are_flagged():
    sketch = make_sketch(
        bbox=BBox(x=0.3, y=0.2, z=0, xmax=0.3, ymax=0.2),
        dimensions=[Dimension(kind="Radius", value=0.4)],
    )
    doc = make_doc(sketches=[sketch], bodies=[make_body(sketches=[sketch])])
    snapshot, analysis = review(doc)
    assert "tiny_sketch" in codes(analysis) or "tiny_radius" in codes(analysis)

def test_goal_sets_intent_and_reviews_against_it():
    snapshot, analysis = review(make_doc(), goal="a phone stand")
    assert analysis.intent.label == "phone stand"
    assert analysis.intent.confidence >= 0.8
    assert "goal_phone_stand" in codes(analysis)
    report = review_report(snapshot, analysis)
    assert "Goal: a phone stand" in report


def test_goal_bracket_reminds_about_holes():
    snapshot, analysis = review(make_doc(), goal="a bracket")
    assert analysis.intent.label == "bracket"
    assert "goal_bracket_holes" in codes(analysis)


def test_goal_enclosure_reminds_about_hollowing():
    snapshot, analysis = review(make_doc(), goal="a case for a PCB")
    assert analysis.intent.label == "enclosure"
    assert "goal_enclosure_hollow" in codes(analysis)


def test_local_answer_mentions_the_goal():
    snapshot, analysis = review(make_doc(), goal="a bracket")
    response = answer("what am I building?", snapshot, analysis)
    assert "a bracket" in response

def test_plan_is_actionable():
    snapshot, analysis = review(make_doc())
    assert analysis.plan
    assert any("export" in step.lower() for step in analysis.plan)
    report = review_report(snapshot, analysis)
    assert "SUGGESTED SEQUENCE" in report


def test_plan_for_bracket_mentions_mounting_holes():
    snapshot, analysis = review(make_doc(), goal="a bracket")
    assert any("mounting holes" in step.lower() for step in analysis.plan)


def test_plan_for_underconstrained_sketch_mentions_constraints():
    sketch = make_sketch(dof=4, fully_constrained=False, constraint_count=2)
    doc = make_doc(sketches=[sketch], bodies=[make_body(sketches=[sketch])])
    snapshot, analysis = review(doc)
    assert any("constraint" in step.lower() for step in analysis.plan)

def test_suggest_no_document():
    snapshot, analysis = review(None)
    assert suggest_action(snapshot, analysis).id == "new_document"


def test_suggest_empty_document():
    doc = DocumentInfo(name="Unnamed", label="Unnamed", object_count=0)
    snapshot, analysis = review(doc)
    assert suggest_action(snapshot, analysis).id == "new_part"


def test_suggest_underconstrained_sketch():
    sketch = make_sketch(dof=4, fully_constrained=False, constraint_count=2)
    doc = make_doc(sketches=[sketch], bodies=[make_body(sketches=[sketch])])
    snapshot, analysis = review(doc)
    assert suggest_action(snapshot, analysis).id == "guide_sketch"


def test_suggest_enclosure_uses_shell_not_hole():
    snapshot, analysis = review(make_doc(), goal="an enclosure for an Arduino")
    assert analysis.intent.label == "enclosure"
    assert suggest_action(snapshot, analysis).id == "open_thickness"


def test_suggest_phone_stand_points_to_export_when_solid():
    snapshot, analysis = review(make_doc(), goal="a phone stand")
    assert analysis.intent.label == "phone stand"
    assert suggest_action(snapshot, analysis).id == "open_export"


def test_suggest_pad_for_empty_body():
    body = make_body(features=[], tip="")
    doc = make_doc(bodies=[body], sketches=[make_sketch()])
    snapshot, analysis = review(doc)
    assert suggest_action(snapshot, analysis).id == "open_pad"


def test_suggest_hole_after_solid():
    snapshot, analysis = review(make_doc())
    assert suggest_action(snapshot, analysis).id == "open_hole"


def test_suggest_fillet_after_hole():
    hole = FeatureInfo(
        name="Hole", label="Hole", type_id="PartDesign::Hole",
        valid=True, closed=True, volume=10.0, diameter=3.2,
    )
    body = make_body(features=[make_pad(), hole])
    snapshot, analysis = review(make_doc(bodies=[body], sketches=[]))
    assert suggest_action(snapshot, analysis).id == "open_fillet"


def test_suggest_export_when_complete():
    hole = FeatureInfo(
        name="Hole", label="Hole", type_id="PartDesign::Hole",
        valid=True, closed=True, volume=10.0, diameter=3.2,
    )
    fillet = FeatureInfo(
        name="Fillet", label="Fillet", type_id="PartDesign::Fillet",
        valid=True, closed=True, volume=7900.0, radius=1.0,
    )
    body = make_body(features=[make_pad(), hole, fillet])
    snapshot, analysis = review(make_doc(bodies=[body], sketches=[]))
    assert suggest_action(snapshot, analysis).id == "open_export"


def test_suggest_edit_feature_for_failure():
    body = make_body(features=[make_pad(valid=False, state=["Error"])])
    snapshot, analysis = review(make_doc(bodies=[body], sketches=[]))
    assert suggest_action(snapshot, analysis).id == "edit_feature"


def test_suggest_part_workbench_exports():
    doc = make_doc(bodies=[], sketches=[], features=[make_pad()])
    snapshot, analysis = review(doc)
    assert suggest_action(snapshot, analysis).id == "open_export"

def test_python_mentor_uses_the_selected_face():
    selection = SelectionInfo(
        object_name="Body",
        object_label="Body",
        object_type="PartDesign::Body",
        subelements=["Face3"],
    )
    snapshot, analysis = review(make_doc(selection=selection))
    response = answer("how do I script a fillet on this edge?", snapshot, analysis)
    assert "App.ActiveDocument" in response
    assert 'doc.getObject("Body")' in response
    assert "Faces[2]" in response


def test_python_mentor_asks_for_a_selection_when_missing():
    snapshot, analysis = review(make_doc())
    response = answer("how do I write a macro?", snapshot, analysis)
    assert "select a face or edge" in response.lower()

def test_sketch_on_generated_face_warns_about_topological_naming():
    sketch = make_sketch(support="Pad:Face3", attached=True)
    doc = make_doc(sketches=[sketch], bodies=[make_body(sketches=[sketch])])
    snapshot, analysis = review(doc)
    assert "face_attachment" in codes(analysis)
    issue = next(i for i in analysis.issues if i.code == "face_attachment")
    assert "topological" in issue.detail.lower()


def test_sketch_outside_a_body_is_explained():
    sketch = make_sketch()
    doc = make_doc(bodies=[], sketches=[sketch], features=[])
    snapshot, analysis = review(doc)
    assert "sketch_outside_body" in codes(analysis)


def test_mixed_part_and_partdesign_is_flagged():
    doc = make_doc(bodies=[make_body()], features=[make_pad()])
    snapshot, analysis = review(doc)
    assert "mixed_workbenches" in codes(analysis)


def test_feature_error_mentions_topological_naming():
    body = make_body(features=[make_pad(valid=False, state=["Error"])])
    snapshot, analysis = review(make_doc(bodies=[body], sketches=[]))
    issue = next(i for i in analysis.issues if i.code == "feature_error")
    assert "topological" in issue.detail.lower()

def test_local_mentor_teaches_the_rectangle_tool():
    snapshot, analysis = review(None)
    text = answer("How do I draw a rectangle?", snapshot, analysis)
    assert "Rect" in text
    assert "Create Body + Sketch" in text


def test_local_mentor_teaches_the_pad_workflow():
    snapshot, analysis = review(None)
    text = answer("How do I pad this sketch?", snapshot, analysis)
    assert "Done" in text
    assert "Pad" in text


def test_local_mentor_teaches_view_navigation():
    snapshot, analysis = review(None)
    text = answer("Where do I rotate the view?", snapshot, analysis)
    assert "middle-drag" in text


def test_ai_prompt_carries_the_learncad_app_guide():
    source = Path(__file__).resolve().parents[1] / "freecad" / "CADet" / "ai_client.py"
    prompt_source = source.read_text(encoding="utf-8")
    assert "APP_GUIDE" in prompt_source
    assert "LEARNCAD APP GUIDE" in prompt_source
    assert "Create Body + Sketch" in app_guide.APP_GUIDE
    assert "Rect" in app_guide.APP_GUIDE
    assert "FreeCAD" not in app_guide.APP_GUIDE
    assert "Blender" not in app_guide.APP_GUIDE

def test_walkthrough_for_circle_targets_the_toolbar_buttons():
    walkthrough = app_guide.walkthrough_for("How do I draw a circle?")
    assert walkthrough is not None
    assert walkthrough.id == "circle"
    targets = {step.target for step in walkthrough.steps}
    assert "sketch:Circle" in targets
    assert "sketch:Radius" in targets
    assert "main:Pad" in targets


def test_walkthrough_for_extrude_highlights_pad():
    walkthrough = app_guide.walkthrough_for("How do I extrude this sketch?")
    assert walkthrough is not None
    assert any(step.target == "main:Pad" for step in walkthrough.steps)


def test_app_guide_teaches_the_guided_walkthrough():
    assert "interactive walkthrough" in app_guide.APP_GUIDE
    source = Path(__file__).resolve().parents[1] / "freecad" / "CADet" / "ai_client.py"
    assert "APP_GUIDE" in source.read_text(encoding="utf-8")


def test_app_guide_teaches_sketching_on_a_face():
    assert "SKETCHING ON AN EXISTING PART" in app_guide.APP_GUIDE
    text = app_guide.answer("how do i create a sketch on a face")
    assert "Sketch" in text
    assert "face" in text.lower()
    assert "plane" in text.lower()


def test_app_guide_teaches_the_full_tool_set():
    assert "ALL TOOLS" in app_guide.APP_GUIDE
    assert "Constrain menu" in app_guide.APP_GUIDE
    assert "Draw menu" in app_guide.APP_GUIDE
    assert "Model tree" in app_guide.APP_GUIDE
    text = app_guide.answer("where is the tangent tool")
    assert "Ctrl+K" in text
    assert "All tools" in text
