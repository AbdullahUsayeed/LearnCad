# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the LearnCad addon.
"""A deliberately small FreeCAD shell for beginners.

Hides the workbench selector, advanced toolbars, and workbench menus, and adds
two context-aware toolbars: one for modeling and one for sketching. Advanced UI
is one checkbox away in Setup.
"""

from __future__ import annotations

from typing import Any, Optional

from .compat import QtCore, QtGui, QtWidgets

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
_MENUBAR_VISIBLE = True
_STATUSBAR_VISIBLE = True
_TREE_PINNED = False


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
    """Bring the task/value panel forward when a command opens a dialog."""
    try:
        import FreeCADGui as Gui

        for dock in Gui.getMainWindow().findChildren(QtWidgets.QDockWidget):
            title = dock.windowTitle().strip().lower()
            if title in ("task", "tasks", "tool", "tools", "inspector"):
                dock.show()
                dock.raise_()
                break
    except Exception:
        pass


def _run(command: str) -> None:
    if command == "PartDesign_NewSketch":
        _new_sketch()
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
        Gui.runCommand(command)
        if command.startswith(("PartDesign_", "Sketcher_Constrain")):
            QtCore.QTimer.singleShot(250, _raise_tools)
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
    add("Dim", "Dimension: add a distance dimension", lambda: _run("Sketcher_ConstrainDistance"), "dimension")
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


def _simplify_docks(mw) -> None:
    for tabs in mw.findChildren(QtWidgets.QTabWidget):
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        if "Report view" not in labels:
            continue
        index = labels.index("Report view")
        try:
            if not tabs.tabBar().isTabVisible(index):
                continue
        except Exception:
            pass
        if "Model" in labels:
            try:
                tabs.setCurrentIndex(labels.index("Model"))
            except Exception:
                pass
        try:
            tabs.tabBar().setTabVisible(index, False)
            _HIDDEN_TABS.append((tabs, index))
        except Exception:
            pass
    for dock in mw.findChildren(QtWidgets.QDockWidget):
        title = dock.windowTitle().strip().lower()
        if "report" in title and dock.isVisible():
            _HIDDEN_DOCKS.append(dock)
            dock.setVisible(False)
        elif title == "model" and dock.isVisible() and not _TREE_PINNED:
            _HIDDEN_DOCKS.append(dock)
            dock.setVisible(False)


def _restore_docks() -> None:
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


def apply() -> None:
    global _APPLIED, _WORKBENCH_CONNECTED
    if not settings.load().get("simple_mode", True):
        return
    mw = _main_window()
    if mw is None:
        return
    _ensure_bars(mw)
    _hide_default_toolbars(mw)
    _hide_menus(mw)
    _simplify_docks(mw)
    _sync_bars()
    if not _WORKBENCH_CONNECTED:
        try:
            mw.workbenchActivated.connect(_on_workbench)
            _WORKBENCH_CONNECTED = True
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
    global _APPLIED, _COMBO_VISIBLE, _TREE_PINNED
    _TREE_PINNED = False
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
    for delay in (1500, 4500, 7500):
        QtCore.QTimer.singleShot(delay, apply)
