# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""LearnCad branding: orange/black palette, title, icon, and theme files.

The underlying engine is still FreeCAD. This module changes the edition the
user sees: window title, application palette, stylesheet overrides, the custom
theme YAML, and the studio viewport.
"""

from __future__ import annotations

import os
import re
import shutil
from typing import Any

from .compat import QtCore, QtGui, QtWidgets, blocking_modal

from . import settings, studio


THEME_NAME = "LearnCad Dark"
STYLE_MARKER = "/* LearnCad theme marker */"
ORANGE = (255, 122, 24)
AMBER = (255, 179, 71)
DARK_ORANGE = (122, 52, 8)

_applied = False
_palette_applied = False
_params_saved = False
_title_connected = False
_retitling = False
_tidied = False


def _root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _qss_path() -> str:
    return os.path.join(_root(), "resources", "styles", "learncad.qss")


def _theme_source() -> str:
    return os.path.join(_root(), "resources", "styles", "parameters", THEME_NAME + ".yaml")


def _icon_path() -> str:
    return os.path.join(_root(), "resources", "icons", "learncad.svg")


def _user_theme_dir() -> str:
    import FreeCAD as App

    return os.path.join(App.getUserAppDataDir(), "Gui", "Stylesheets", "parameters")


def copy_theme() -> bool:
    try:
        source = _theme_source()
        if not os.path.isfile(source):
            return False
        target_dir = _user_theme_dir()
        os.makedirs(target_dir, exist_ok=True)
        target = os.path.join(target_dir, THEME_NAME + ".yaml")
        shutil.copyfile(source, target)
        return True
    except Exception:
        return False


def apply_preferences() -> None:
    import FreeCAD as App

    main = App.ParamGet("User parameter:BaseApp/Preferences/MainWindow")
    main.SetString("Theme", THEME_NAME)
    main.SetString("StyleSheet", "FreeCAD.qss")
    main.SetUnsigned("ThemeAccentColor1", studio.argb(*ORANGE))
    main.SetUnsigned("ThemeAccentColor2", studio.argb(*AMBER))
    main.SetUnsigned("ThemeAccentColor3", studio.argb(*DARK_ORANGE))

    general = App.ParamGet("User parameter:BaseApp/Preferences/General")
    general.SetInt("ToolbarIconSize", 24)
    general.SetBool("ShowSplasher", False)

    view = App.ParamGet("User parameter:BaseApp/Preferences/View")
    view.SetInt("AntiAliasing", 3)
    view.SetString("NavigationStyle", str(settings.load().get("navigation_style", "Gui::OpenInventorNavigationStyle")))
    view.SetBool("Gradient", True)
    view.SetBool("ShowAxisCross", False)
    view.SetBool("Perspective", False)


def _read_qss() -> str:
    try:
        with open(_qss_path(), "r", encoding="utf-8") as handle:
            return handle.read()
    except Exception:
        return ""


def apply_qss() -> None:
    qss = _read_qss()
    if not qss:
        return
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    current = app.styleSheet() or ""
    if STYLE_MARKER in current:
        return
    app.setStyleSheet(current + "\n" + STYLE_MARKER + "\n" + qss)


def apply_palette() -> None:
    global _palette_applied
    if _palette_applied:
        return
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#0a0a0a"))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#f5f5f5"))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor("#111111"))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor("#181818"))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor("#f5f5f5"))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor("#151515"))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor("#f5f5f5"))
    palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor("#ffffff"))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor("#ff7a18"))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#080808"))
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor("#ff9a3c"))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor("#111111"))
    palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor("#ffb347"))
    app.setPalette(palette)
    _palette_applied = True


def _main_window():
    import FreeCADGui as Gui

    try:
        return Gui.getMainWindow()
    except Exception:
        return None


def _retitle() -> None:
    global _retitling
    if _retitling:
        return
    window = _main_window()
    if window is None:
        return
    title = window.windowTitle()
    if not title:
        return
    if "FreeCAD" in title:
        _retitling = True
        try:
            cleaned = re.sub(r"FreeCAD(?:\s+\d+(?:\.\d+)*)?", "LearnCad", title)
            window.setWindowTitle(cleaned)
        finally:
            _retitling = False


def apply_title() -> None:
    global _title_connected
    window = _main_window()
    if window is None:
        return
    if not _title_connected:
        try:
            window.windowTitleChanged.connect(lambda _title: _retitle())
            _title_connected = True
        except Exception:
            pass
    _retitle()


def _scrub_windows() -> None:
    """Remove the engine name from any dialog or auxiliary window title."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    for widget in app.topLevelWidgets():
        try:
            title = widget.windowTitle() or ""
            lowered = title.strip().lower()
            if lowered in ("start page", "freecad start page") and widget.isVisible():
                widget.hide()
                continue
            if "freecad" in lowered:
                cleaned = re.sub(r"FreeCAD(?:\s+\d+(?:\.\d+)*)?", "LearnCad", title)
                widget.setWindowTitle(cleaned)
        except Exception:
            pass


def apply_icon() -> None:
    window = _main_window()
    if window is None:
        return
    try:
        icon = QtGui.QIcon(_icon_path())
        if not icon.isNull():
            window.setWindowIcon(icon)
    except Exception:
        pass


def _mouse_busy() -> bool:
    try:
        app = QtWidgets.QApplication.instance()
        if app is not None and app.mouseButtons() != QtCore.Qt.NoButton:
            return True
    except Exception:
        pass
    return False


def _ui_busy() -> bool:
    if _mouse_busy():
        return True
    try:
        app = QtWidgets.QApplication.instance()
        if blocking_modal() is not None:
            return True
    except Exception:
        pass
    return False


def apply(force: bool = True) -> tuple[bool, str]:
    global _applied
    if not force and _mouse_busy():
        return False, "Busy."
    try:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            try:
                app.setApplicationDisplayName("LearnCad")
            except Exception:
                pass
        copied = copy_theme()
        apply_preferences()
        apply_qss()
        apply_palette()
        apply_title()
        apply_icon()
        _scrub_windows()
        ok, message = studio.apply("learncad")
        global _params_saved
        if not _params_saved:
            try:
                import FreeCAD as App

                App.saveParameter()
                _params_saved = True
            except Exception:
                pass
        _applied = True
        theme_note = "Theme file installed." if copied else "Theme file could not be copied; runtime colors are still applied."
        return ok, theme_note + " " + message
    except Exception as exc:
        return False, f"Could not apply LearnCad branding: {exc}"


def restore_view() -> None:
    """Bring the 3D view back to the full central area.

    A previous dock experiment can leave the MDI child collapsed. This is a
    harmless no-op when the view is already healthy.
    """
    if _mouse_busy():
        return
    try:
        win = _main_window()
        if win is None:
            return
        for sub in win.findChildren(QtWidgets.QMdiSubWindow):
            try:
                sub.showMaximized()
            except Exception:
                pass
        for view in win.findChildren(QtWidgets.QWidget):
            if view.metaObject().className() == "Gui::View3DInventor":
                try:
                    view.show()
                except Exception:
                    pass
        try:
            import FreeCADGui as Gui

            doc = Gui.activeDocument()
            if doc is not None and doc.activeView() is None:
                Gui.runCommand("Std_ViewCreate")
                for sub in win.findChildren(QtWidgets.QMdiSubWindow):
                    try:
                        sub.showMaximized()
                    except Exception:
                        pass
        except Exception:
            pass
    except Exception:
        pass


def tidy_empty_documents() -> None:
    """Keep one blank document when the app opens.

    The engine can restore an empty session document and also create a fresh
    one. Two blank documents in the tree look like a bug to a beginner, so close
    only unsaved, empty, non-active documents during startup.
    """
    global _tidied
    if _tidied:
        return
    try:
        import FreeCAD as App

        docs = dict(App.listDocuments())
        if not docs:
            App.newDocument()
            _tidied = True
            return

        active = App.ActiveDocument
        if active is None:
            for name, doc in docs.items():
                try:
                    App.setActiveDocument(name)
                    active = doc
                    break
                except Exception:
                    pass
            if active is None:
                _tidied = True
                return

        for name, doc in docs.items():
            if doc is active:
                continue
            try:
                if doc.is_empty and not doc.FileName:
                    App.closeDocument(name)
            except Exception:
                pass
        _tidied = True
    except Exception:
        pass


def schedule() -> None:
    if not settings.load().get("learncad_branding", True):
        return
    for delay in (1200, 3000, 6000, 12000, 20000):
        QtCore.QTimer.singleShot(delay, lambda: apply(force=False))
    QtCore.QTimer.singleShot(6000, tidy_empty_documents)
    QtCore.QTimer.singleShot(8000, apply_title)
    for delay in (5000, 9000, 13000, 20000, 30000):
        QtCore.QTimer.singleShot(delay, restore_view)
    for delay in (2500, 7000, 15000, 25000):
        QtCore.QTimer.singleShot(delay, _scrub_windows)
    try:
        from . import simple_mode

        simple_mode.schedule()
    except Exception:
        pass
    try:
        from . import panel

        def _open_panel():
            if not settings.load().get("auto_open_panel", True):
                return
            try:
                panel.show_panel()
            except Exception:
                QtCore.QTimer.singleShot(1500, _open_panel)

        QtCore.QTimer.singleShot(5500, _open_panel)
        QtCore.QTimer.singleShot(10000, _open_panel)
    except Exception:
        pass
