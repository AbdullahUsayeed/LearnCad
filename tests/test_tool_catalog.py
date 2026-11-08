# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the LearnCad addon.
"""Tests for the curated tool catalog and its user-facing groupings."""

from __future__ import annotations

from freecad.CADet import tool_catalog as catalog


def commands(groups):
    return {tool.command for group in groups for tool in group.tools}


def test_catalog_entries_are_complete():
    for group in catalog.ALL_GROUPS:
        assert group.label.strip()
        assert group.tools
        for tool in group.tools:
            assert tool.label.strip()
            assert tool.command.strip()
            assert " " not in tool.command


def test_sketch_drawing_and_constraint_tools_are_present():
    available = commands(catalog.SKETCH_GROUPS)
    for command in (
        "Sketcher_CreateArc",
        "Sketcher_CreateSlot",
        "Sketcher_CreateEllipseByCenter",
        "Sketcher_CreateRegularPolygon",
        "Sketcher_CreateBSpline",
        "Sketcher_CreatePoint",
        "Sketcher_ConstrainParallel",
        "Sketcher_ConstrainPerpendicular",
        "Sketcher_ConstrainTangent",
        "Sketcher_ConstrainEqual",
        "Sketcher_ConstrainSymmetric",
        "Sketcher_ConstrainBlock",
        "Sketcher_ConstrainLock",
        "Sketcher_ConstrainDistanceX",
        "Sketcher_ConstrainDistanceY",
        "Sketcher_ConstrainAngle",
        "Sketcher_ConstrainDiameter",
        "Sketcher_ToggleConstruction",
        "Sketcher_Trimming",
        "Sketcher_Extend",
        "Sketcher_ValidateSketch",
    ):
        assert command in available


def test_model_and_inspection_tools_are_present():
    available = commands(catalog.MODEL_GROUPS)
    for command in (
        "PartDesign_Revolution",
        "PartDesign_AdditiveLoft",
        "PartDesign_AdditivePipe",
        "PartDesign_AdditiveHelix",
        "PartDesign_Thickness",
        "PartDesign_Chamfer",
        "PartDesign_LinearPattern",
        "PartDesign_PolarPattern",
        "PartDesign_MultiTransform",
        "PartDesign_Mirrored",
        "PartDesign_Boolean",
        "PartDesign_Plane",
        "PartDesign_ShapeBinder",
        "Part_CheckGeometry",
        "Std_Measure",
        "Part_Section",
        "Part_CrossSections",
    ):
        assert command in available


def test_view_and_file_tools_are_present():
    available = commands(catalog.VIEW_GROUPS + catalog.FILE_GROUPS)
    for command in (
        "Std_ViewFitSelection",
        "Std_ViewIsometric",
        "Std_ViewFront",
        "Std_ViewTop",
        "Std_ToggleClipPlane",
        "Std_SaveAs",
        "Std_SaveCopy",
        "Std_Import",
        "Std_Export",
        "Std_PrintPdf",
    ):
        assert command in available


def test_tool_lookup_returns_matching_entry():
    tool = catalog.tool_by_command("Sketcher_ConstrainTangent")
    assert tool is not None
    assert tool.label == "Tangent"
    assert catalog.tool_by_command("Not_A_Tool") is None
