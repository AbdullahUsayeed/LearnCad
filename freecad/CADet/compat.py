# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Qt imports across FreeCAD's supported PySide generations."""

from __future__ import annotations

try:  # FreeCAD 1.1+
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore
except Exception:  # pragma: no cover - older FreeCAD
    try:
        from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore
    except Exception:
        from PySide import QtCore, QtGui, QtWidgets  # type: ignore


def blocking_modal():
    """Return the active modal dialog, ignoring the startup recovery dialog.

    FreeCAD creates the DocumentRecovery dialog at startup even when there is
    nothing to recover. It must not freeze the live coach or UI guards.
    """
    try:
        modal = QtWidgets.QApplication.activeModalWidget()
    except Exception:
        return None
    if modal is None or not modal.isVisible():
        return None
    try:
        name = modal.objectName() or ""
        cls = type(modal).__name__
        if "DocumentRecovery" in name or "DocumentRecovery" in cls:
            return None
    except Exception:
        pass
    return modal


__all__ = ["QtCore", "QtGui", "QtWidgets", "blocking_modal"]
