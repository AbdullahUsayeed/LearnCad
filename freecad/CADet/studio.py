# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Optional visual polish for FreeCAD.

FreeCAD can look much closer to a commercial CAD package with a few deliberate
defaults: anti-aliasing, a gradient viewport, SolidWorks-style navigation, an
orthographic camera, a navigation cube, smooth tessellation, light gray bodies,
and dark edges. This module applies those settings and the live view changes.
"""

from __future__ import annotations

from typing import Optional



def _navigation_style() -> str:
    try:
        from . import settings

        return str(settings.load().get("navigation_style", "Gui::OpenInventorNavigationStyle"))
    except Exception:
        return "Gui::OpenInventorNavigationStyle"


def argb(red: int, green: int, blue: int, alpha: int = 255) -> int:
    """Encode a color the way FreeCAD stores FCUInt view preferences."""
    return ((int(red) & 0xFF) << 24) | ((int(green) & 0xFF) << 16) | ((int(blue) & 0xFF) << 8) | (int(alpha) & 0xFF)


LIGHT_BODY = argb(190, 197, 207)
LIGHT_LINE = argb(28, 34, 42)
SELECTION = argb(53, 140, 255)
HIGHLIGHT = argb(247, 201, 106)

LEARNCAD_BODY = argb(214, 205, 194)
LEARNCAD_LINE = argb(255, 122, 24)
LEARNCAD_ACCENT = argb(255, 122, 24)
LEARNCAD_ACCENT_2 = argb(255, 179, 71)
# Selection must contrast with both the orange brand accent and the white
# sketch edges. Cyan for a click, yellow for hover.
LEARNCAD_SELECTION = argb(0, 220, 255)
LEARNCAD_HIGHLIGHT = argb(255, 214, 64)
LEARNCAD_EDGE = argb(235, 235, 235)
LEARNCAD_CONSTRUCTION = argb(64, 156, 255)
LEARNCAD_FULLY_CONSTRAINED = argb(120, 220, 90)
LEARNCAD_EXTERNAL = argb(255, 120, 220)

DARK_BG_TOP = (0.03, 0.06, 0.11)
DARK_BG_MID = (0.06, 0.11, 0.19)
DARK_BG_BOTTOM = (0.10, 0.18, 0.30)

LIGHT_BG_TOP = (0.88, 0.90, 0.93)
LIGHT_BG_MID = (0.82, 0.85, 0.89)
LIGHT_BG_BOTTOM = (0.72, 0.76, 0.82)

LEARNCAD_BG_TOP = (0.01, 0.01, 0.01)
LEARNCAD_BG_MID = (0.08, 0.03, 0.00)
LEARNCAD_BG_BOTTOM = (0.20, 0.08, 0.01)


def _params():
    import FreeCAD as App

    return App.ParamGet("User parameter:BaseApp/Preferences/View")


def _general():
    import FreeCAD as App

    return App.ParamGet("User parameter:BaseApp/Preferences/General")


def _main_window():
    import FreeCAD as App

    return App.ParamGet("User parameter:BaseApp/Preferences/MainWindow")


def _part():
    import FreeCAD as App

    return App.ParamGet("User parameter:BaseApp/Preferences/Mod/Part")


def _sketcher():
    import FreeCAD as App

    return App.ParamGet("User parameter:BaseApp/Preferences/Mod/Sketcher/View")


def _set_uint(group, name: str, value: int) -> None:
    try:
        group.SetUnsigned(name, int(value))
    except Exception:
        try:
            group.SetInt(name, int(value))
        except Exception:
            pass


def apply_preferences(theme: str = "keep") -> None:
    """Write the preferences that need a restart (anti-aliasing, icons, theme)."""
    view = _params()
    # 3 = MSAA 4x in FreeCAD 1.1 (0 none, 1 line smoothing, 2 MSAA2x, 3 MSAA4x,
    # 4 MSAA8x, 5 MSAA6x). 4x is the safe quality/performance default.
    view.SetInt("AntiAliasing", 3)
    view.SetInt("RenderCache", 0)
    view.SetBool("Gradient", True)
    view.SetBool("RadialGradient", False)
    view.SetBool("UseBackgroundColorMid", False)
    view.SetBool("ShowAxisCross", False)
    view.SetBool("Perspective", False)
    view.SetString("NavigationStyle", _navigation_style())
    view.SetInt("MarkerSize", 7)
    if theme == "learncad":
        _set_uint(view, "DefaultShapeColor", LEARNCAD_BODY)
        _set_uint(view, "DefaultLineColor", LEARNCAD_LINE)
        _set_uint(view, "SelectionColor", LEARNCAD_SELECTION)
        _set_uint(view, "HighlightColor", LEARNCAD_HIGHLIGHT)
        _set_uint(view, "BackgroundColor", argb(5, 5, 5))
        _set_uint(view, "BackgroundColor2", argb(46, 18, 3))
        _set_uint(view, "BackgroundColor3", argb(18, 8, 2))
        sketcher = _sketcher()

        def sketch_color(name: str, value: int) -> None:
            # FreeCAD reads these from BaseApp/Preferences/View (this is where
            # the Sketcher colour page saves them). Mirror them into the
            # Sketcher group as well so older/newer builds pick them up.
            _set_uint(view, name, value)
            _set_uint(sketcher, name, value)

        sketch_color("SketchEdgeColor", LEARNCAD_EDGE)
        sketch_color("SketchVertexColor", LEARNCAD_EDGE)
        sketch_color("ConstructionColor", LEARNCAD_CONSTRUCTION)
        sketch_color("FullyConstrainedColor", LEARNCAD_FULLY_CONSTRAINED)
        sketch_color("ExternalColor", LEARNCAD_EXTERNAL)
        sketch_color("CreateLineColor", LEARNCAD_HIGHLIGHT)
        # Red is reserved for real conflicts. Driving dimensions are amber,
        # reference dimensions blue, geometry neutral.
        sketch_color("ConstrainedDimColor", argb(255, 209, 102))
        sketch_color("NonDrivingConstrDimColor", argb(120, 200, 255))
        sketch_color("DatumColor", argb(120, 200, 255))
        sketch_color("ConstrainedColor", argb(205, 218, 230))
        sketch_color("DeactivatedConstrDimColor", argb(150, 150, 150))
        sketch_color("ExprBasedConstrDimColor", argb(196, 156, 255))
        main = _main_window()
        main.SetUnsigned("ThemeAccentColor1", LEARNCAD_ACCENT)
        main.SetUnsigned("ThemeAccentColor2", LEARNCAD_ACCENT_2)
        main.SetUnsigned("ThemeAccentColor3", argb(122, 52, 8))
    elif theme == "light":
        _set_uint(view, "DefaultShapeColor", LIGHT_BODY)
        _set_uint(view, "DefaultLineColor", LIGHT_LINE)
        _set_uint(view, "SelectionColor", SELECTION)
        _set_uint(view, "HighlightColor", HIGHLIGHT)
        _set_uint(view, "BackgroundColor", argb(224, 229, 235))
        _set_uint(view, "BackgroundColor2", argb(184, 191, 201))
        _set_uint(view, "BackgroundColor3", argb(204, 210, 218))
    else:
        _set_uint(view, "DefaultShapeColor", LIGHT_BODY)
        _set_uint(view, "DefaultLineColor", LIGHT_LINE)
        _set_uint(view, "SelectionColor", SELECTION)
        _set_uint(view, "HighlightColor", HIGHLIGHT)
        _set_uint(view, "BackgroundColor", argb(8, 15, 28))
        _set_uint(view, "BackgroundColor2", argb(26, 46, 77))
        _set_uint(view, "BackgroundColor3", argb(15, 28, 48))

    _general().SetInt("ToolbarIconSize", 24)
    _part().SetFloat("MeshDeviation", 0.1)
    _part().SetFloat("MeshAngularDeflection", 10.0)

    if theme == "learncad":
        _main_window().SetString("Theme", "LearnCad Dark")
        _main_window().SetString("StyleSheet", "FreeCAD.qss")
    elif theme in ("light", "dark"):
        _main_window().SetString("Theme", "FreeCAD Light" if theme == "light" else "FreeCAD Dark")


def apply_view(theme: str = "keep") -> bool:
    """Apply the live view changes. Returns True if a 3D view was updated."""
    import FreeCADGui as Gui

    try:
        gdoc = Gui.activeDocument()
        if gdoc is None:
            return False
        view = gdoc.ActiveView
        if view is None:
            return False
    except Exception:
        return False

    try:
        view.setAxisCross(False)
    except Exception:
        pass
    try:
        view.setCameraType("Orthographic")
    except Exception:
        pass
    try:
        view.setNavigationType(_navigation_style())
    except Exception:
        pass

    try:
        viewer = view.getViewer()
    except Exception:
        viewer = None

    if viewer is not None:
        try:
            viewer.setEnabledNaviCube(True)
        except Exception:
            pass
        if theme == "learncad":
            top, mid, bottom = LEARNCAD_BG_TOP, LEARNCAD_BG_MID, LEARNCAD_BG_BOTTOM
        elif theme == "light":
            top, mid, bottom = LIGHT_BG_TOP, LIGHT_BG_MID, LIGHT_BG_BOTTOM
        else:
            top, mid, bottom = DARK_BG_TOP, DARK_BG_MID, DARK_BG_BOTTOM
        try:
            viewer.setGradientBackground("Linear")
            viewer.setGradientBackgroundColor(top, bottom, mid)
        except Exception:
            try:
                viewer.setBackgroundColor(*top)
            except Exception:
                pass

    try:
        Gui.updateGui()
    except Exception:
        pass
    return True


def apply_object_style(theme: str = "keep") -> int:
    """Give existing Part and PartDesign objects a clean studio appearance."""
    import FreeCAD as App

    if theme == "learncad":
        body_color = (214 / 255.0, 205 / 255.0, 194 / 255.0)
        line_color = (255 / 255.0, 122 / 255.0, 24 / 255.0)
    else:
        body_color = (190 / 255.0, 197 / 255.0, 207 / 255.0)
        line_color = (28 / 255.0, 34 / 255.0, 42 / 255.0)

    doc = App.ActiveDocument
    if doc is None:
        return 0
    changed = 0
    for obj in doc.Objects:
        type_id = str(getattr(obj, "TypeId", "") or "")
        if type_id in ("Sketcher::SketchObject", "App::Origin", "App::Line", "App::Plane", "App::Point"):
            continue
        if not (type_id.startswith("PartDesign::") or type_id.startswith("Part::")):
            continue
        vobj = getattr(obj, "ViewObject", None)
        if vobj is None:
            continue
        try:
            vobj.ShapeColor = body_color
        except Exception:
            pass
        try:
            vobj.LineColor = line_color
        except Exception:
            pass
        try:
            vobj.LineWidth = 2.0
        except Exception:
            pass
        try:
            vobj.Transparency = 0
        except Exception:
            pass
        try:
            vobj.DisplayMode = "Flat Lines"
        except Exception:
            pass
        changed += 1
    return changed


def apply(theme: str = "keep") -> tuple[bool, str]:
    """Apply the studio look. `theme` is keep, light, or dark."""
    try:
        import FreeCAD as App

        apply_preferences(theme)
        view_ok = apply_view(theme)
        objects = apply_object_style(theme)
        try:
            App.saveParameter()
        except Exception:
            pass
        if not view_ok:
            return False, "Studio preferences saved. Open a 3D view, then try again for the live view changes."
        suffix = " Restart LearnCad for anti-aliasing, icon size, and theme changes." if theme in ("light", "dark", "learncad") else " Restart LearnCad for anti-aliasing and icon size."
        return True, f"Studio look applied to {objects} object(s).{suffix}"
    except Exception as exc:
        return False, f"Could not apply the studio look: {exc}"
