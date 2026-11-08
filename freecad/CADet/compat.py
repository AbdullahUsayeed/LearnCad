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


__all__ = ["QtCore", "QtGui", "QtWidgets"]
