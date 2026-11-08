# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Workbench registration.

Keep import-time work light: the panel and its polling engine are only created
when the user actually opens the mentor.
"""

from __future__ import annotations

import os

import FreeCAD
import FreeCADGui as Gui


def _icon_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "icons", "learncad.svg")


class _OpenMentorCommand:
    def GetResources(self):
        return {
            "MenuText": "Open LearnCad",
            "ToolTip": "Open the LearnCad coaching panel",
            "Pixmap": _icon_path(),
            "Accel": "Ctrl+Shift+M",
        }

    def IsActive(self):
        return True

    def Activated(self):
        from . import panel

        panel.show_panel()


class _ReviewCommand:
    def GetResources(self):
        return {
            "MenuText": "Review My Model",
            "ToolTip": "Refresh the full engineering review",
            "Pixmap": _icon_path(),
        }

    def IsActive(self):
        return True

    def Activated(self):
        from . import panel

        panel.show_panel()
        if panel._PANEL is not None:
            panel._PANEL._force_review()


class _RenderCommand:
    def GetResources(self):
        return {
            "MenuText": "Render Studio Preview",
            "ToolTip": "Render the active solid as a realistic studio image",
            "Pixmap": _icon_path(),
        }

    def IsActive(self):
        return True

    def Activated(self):
        from . import panel

        panel.show_panel()
        if panel._PANEL is not None:
            panel._PANEL._render_preview()


class _SettingsCommand:
    def GetResources(self):
        return {
            "MenuText": "LearnCad Settings",
            "ToolTip": "Configure the optional AI explanation layer",
            "Pixmap": _icon_path(),
        }

    def IsActive(self):
        return True

    def Activated(self):
        from . import panel

        panel.show_panel()
        if panel._PANEL is not None:
            panel._PANEL._open_settings()


class _TreeCommand:
    def GetResources(self):
        return {
            "MenuText": "Model tree",
            "ToolTip": "Show or hide the model tree",
            "Pixmap": _icon_path(),
        }

    def IsActive(self):
        return True

    def Activated(self):
        from . import simple_mode

        simple_mode.toggle_tree()


class _ActivateBodyCommand:
    def GetResources(self):
        return {
            "MenuText": "Set active body",
            "ToolTip": "Make the selected Body the active Body",
            "Pixmap": _icon_path(),
        }

    def IsActive(self):
        return True

    def Activated(self):
        from . import actions

        ok, message = actions.activate_body(None)
        FreeCAD.Console.PrintMessage("[LearnCad] " + message + "\n")


class _StudioCommand:
    def GetResources(self):
        return {
            "MenuText": "Studio Look",
            "ToolTip": "Apply a cleaner SolidWorks-like viewport to the active document",
            "Pixmap": _icon_path(),
        }

    def IsActive(self):
        return True

    def Activated(self):
        from . import studio

        ok, message = studio.apply("keep")
        FreeCAD.Console.PrintMessage("[LearnCad] " + message + "\n")


class _StudioLightCommand:
    def GetResources(self):
        return {
            "MenuText": "Studio Light Theme",
            "ToolTip": "Apply the studio viewport and switch to the light theme (restart required)",
            "Pixmap": _icon_path(),
        }

    def IsActive(self):
        return True

    def Activated(self):
        from . import studio

        ok, message = studio.apply("light")
        FreeCAD.Console.PrintMessage("[LearnCad] " + message + "\n")


Gui.addCommand("CADet_OpenMentor", _OpenMentorCommand())
Gui.addCommand("CADet_ReviewModel", _ReviewCommand())
Gui.addCommand("CADet_StudioLook", _StudioCommand())
Gui.addCommand("CADet_StudioLight", _StudioLightCommand())
Gui.addCommand("CADet_RenderPreview", _RenderCommand())
Gui.addCommand("CADet_Settings", _SettingsCommand())
Gui.addCommand("CADet_ToggleTree", _TreeCommand())
Gui.addCommand("CADet_ActivateBody", _ActivateBodyCommand())


class CADetWorkbench(Gui.Workbench):
    MenuText = "LearnCad"
    ToolTip = "LearnCad: a senior mechanical engineer watching your model"
    Icon = _icon_path()

    def Initialize(self):
        self.appendToolbar("LearnCad", ["CADet_OpenMentor", "CADet_ReviewModel", "CADet_StudioLook", "CADet_ToggleTree", "CADet_Settings"])
        self.appendMenu("LearnCad", ["CADet_OpenMentor", "CADet_ReviewModel", "CADet_StudioLook", "CADet_StudioLight", "CADet_RenderPreview", "CADet_ToggleTree", "CADet_ActivateBody", "CADet_Settings"])

    def Activated(self):
        from . import panel

        panel.show_panel()

    def Deactivated(self):
        pass

    def ContextMenu(self, recipient):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(CADetWorkbench())

try:
    from . import branding

    branding.schedule()
except Exception:
    pass
