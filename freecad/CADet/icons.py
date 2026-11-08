# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the LearnCad addon.
"""Small self-contained toolbar icons for the LearnCad simple shell.

Drawing them here keeps the beginner toolbar independent of the engine's icon
theme and guarantees that it still looks right when a different workbench is
active. Each icon is a 32 px pixmap with a light stroke and an orange accent.
"""

from __future__ import annotations

import math

from .compat import QtCore, QtGui

INK = "#f2f2f2"
ACCENT = "#ff7a18"
_CACHE: dict[str, QtGui.QIcon] = {}


def _pen(color: str = INK, width: float = 2.0) -> QtGui.QPen:
    pen = QtGui.QPen(QtGui.QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(QtCore.Qt.RoundCap)
    pen.setJoinStyle(QtCore.Qt.RoundJoin)
    return pen


def _dot(painter: QtGui.QPainter, x: float, y: float, r: float = 2.0, color: str = ACCENT) -> None:
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(color))
    painter.drawEllipse(QtCore.QPointF(x, y), r, r)
    painter.setBrush(QtCore.Qt.NoBrush)


def _arrow(
    painter: QtGui.QPainter,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: str = ACCENT,
    width: float = 2.2,
    head: float = 5.0,
) -> None:
    painter.setPen(_pen(color, width))
    painter.drawLine(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2))
    angle = math.atan2(y2 - y1, x2 - x1)
    for offset in (0.55, -0.55):
        hx = x2 - head * math.cos(angle - offset)
        hy = y2 - head * math.sin(angle - offset)
        painter.drawLine(QtCore.QPointF(x2, y2), QtCore.QPointF(hx, hy))


def _draw_undo(painter: QtGui.QPainter) -> None:
    path = QtGui.QPainterPath()
    path.moveTo(8.0, 12.0)
    path.cubicTo(11.0, 5.5, 23.0, 5.5, 25.0, 14.0)
    path.cubicTo(26.0, 19.5, 22.0, 23.0, 17.0, 23.0)
    painter.setPen(_pen(INK, 2.2))
    painter.drawPath(path)
    _arrow(painter, 12.5, 7.0, 7.5, 12.5, INK, 2.2, 4.0)


def icon(kind: str) -> QtGui.QIcon:
    """Return a cached, theme-independent QIcon."""
    key = kind.lower()
    if key in _CACHE:
        return _CACHE[key]

    pm = QtGui.QPixmap(32, 32)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
    p.setPen(_pen())
    p.setBrush(QtCore.Qt.NoBrush)

    if key == "new":
        p.drawRoundedRect(QtCore.QRectF(8, 5, 16, 22), 2.5, 2.5)
        p.setPen(_pen(INK, 1.5))
        p.drawLine(QtCore.QPointF(19, 5), QtCore.QPointF(24, 10))
        p.drawLine(QtCore.QPointF(19, 5), QtCore.QPointF(19, 10))
        p.drawLine(QtCore.QPointF(19, 10), QtCore.QPointF(24, 10))
        p.setPen(_pen(ACCENT, 2.6))
        p.drawLine(QtCore.QPointF(20.5, 18), QtCore.QPointF(26.5, 18))
        p.drawLine(QtCore.QPointF(23.5, 15), QtCore.QPointF(23.5, 21))
    elif key == "open":
        path = QtGui.QPainterPath()
        path.moveTo(4, 11)
        path.lineTo(12, 11)
        path.lineTo(14, 8)
        path.lineTo(28, 8)
        path.lineTo(28, 25)
        path.lineTo(4, 25)
        path.closeSubpath()
        p.drawPath(path)
        p.setPen(_pen(ACCENT, 2.0))
        p.drawLine(QtCore.QPointF(4, 14), QtCore.QPointF(28, 14))
    elif key == "save":
        p.drawRoundedRect(QtCore.QRectF(5, 5, 22, 22), 2.0, 2.0)
        p.setPen(_pen(INK, 1.6))
        p.drawRect(QtCore.QRectF(11, 5, 10, 7))
        p.drawRoundedRect(QtCore.QRectF(9, 17, 14, 10), 1.2, 1.2)
        _dot(p, 24.0, 10.0, 2.2, ACCENT)
    elif key == "undo":
        _draw_undo(p)
    elif key == "redo":
        p.save()
        p.translate(32, 0)
        p.scale(-1, 1)
        _draw_undo(p)
        p.restore()
    elif key == "fit":
        for x1, y1, x2, y2 in (
            (6, 12, 6, 6), (6, 6, 12, 6),
            (20, 6, 26, 6), (26, 6, 26, 12),
            (6, 20, 6, 26), (6, 26, 12, 26),
            (20, 26, 26, 26), (26, 26, 26, 20),
        ):
            p.drawLine(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2))
        _dot(p, 16, 16, 2.4, ACCENT)
    elif key == "rect":
        p.setPen(_pen(INK, 2.2))
        p.drawRoundedRect(QtCore.QRectF(5, 9, 22, 15), 2.0, 2.0)
        _dot(p, 5, 9, 2.4, ACCENT)
        _dot(p, 27, 24, 2.4, ACCENT)
    elif key == "circle":
        p.setPen(_pen(INK, 2.2))
        p.drawEllipse(QtCore.QRectF(5, 5, 22, 22))
        _dot(p, 16, 16, 2.6, ACCENT)
    elif key == "line":
        p.setPen(_pen(INK, 2.2))
        p.drawLine(QtCore.QPointF(6, 26), QtCore.QPointF(26, 6))
        _dot(p, 6, 26, 2.6, ACCENT)
        _dot(p, 26, 6, 2.6, ACCENT)
    elif key == "coincident":
        p.setPen(_pen(INK, 2.0))
        p.drawLine(QtCore.QPointF(7, 25), QtCore.QPointF(16, 16))
        p.drawLine(QtCore.QPointF(16, 16), QtCore.QPointF(25, 25))
        _dot(p, 16, 16, 3.0, ACCENT)
    elif key == "horizontal":
        p.setPen(_pen(INK, 1.6))
        p.drawLine(QtCore.QPointF(8, 10), QtCore.QPointF(8, 22))
        p.drawLine(QtCore.QPointF(24, 10), QtCore.QPointF(24, 22))
        _arrow(p, 9, 16, 23, 16, ACCENT, 2.4)
    elif key == "vertical":
        p.setPen(_pen(INK, 1.6))
        p.drawLine(QtCore.QPointF(10, 8), QtCore.QPointF(22, 8))
        p.drawLine(QtCore.QPointF(10, 24), QtCore.QPointF(22, 24))
        _arrow(p, 16, 9, 16, 23, ACCENT, 2.4)
    elif key == "dimension":
        p.setPen(_pen(INK, 1.5))
        p.drawLine(QtCore.QPointF(7, 9), QtCore.QPointF(7, 23))
        p.drawLine(QtCore.QPointF(25, 9), QtCore.QPointF(25, 23))
        _arrow(p, 8, 16, 24, 16, ACCENT, 2.0)
        p.setPen(_pen(INK, 1.0))
        p.setFont(QtGui.QFont("Segoe UI", 7))
        p.drawText(QtCore.QRectF(10, 2, 12, 10), QtCore.Qt.AlignCenter, "10")
    elif key == "radius":
        p.drawArc(QtCore.QRectF(5, 5, 22, 22), 30 * 16, 280 * 16)
        _arrow(p, 16, 16, 25, 8, ACCENT, 2.2, 4.0)
        _dot(p, 16, 16, 2.4, ACCENT)
    elif key == "leave":
        p.drawRoundedRect(QtCore.QRectF(6, 4, 14, 24), 1.5, 1.5)
        _arrow(p, 14, 16, 28, 16, ACCENT, 2.4, 5.0)
    elif key == "sketch":
        p.drawRoundedRect(QtCore.QRectF(5, 10, 20, 15), 1.8, 1.8)
        p.setPen(_pen(ACCENT, 2.6))
        p.drawLine(QtCore.QPointF(9, 22), QtCore.QPointF(24, 7))
        p.setPen(_pen(INK, 1.5))
        p.drawLine(QtCore.QPointF(20, 6), QtCore.QPointF(27, 11))
    elif key == "pad":
        p.setPen(_pen(INK, 1.8))
        p.drawPolygon(
            QtGui.QPolygonF(
                [
                    QtCore.QPointF(5, 14),
                    QtCore.QPointF(16, 7),
                    QtCore.QPointF(27, 14),
                    QtCore.QPointF(16, 21),
                ]
            )
        )
        p.drawLine(QtCore.QPointF(5, 14), QtCore.QPointF(5, 23))
        p.drawLine(QtCore.QPointF(27, 14), QtCore.QPointF(27, 23))
        p.drawLine(QtCore.QPointF(16, 21), QtCore.QPointF(16, 28))
        p.drawLine(QtCore.QPointF(5, 23), QtCore.QPointF(16, 28))
        p.drawLine(QtCore.QPointF(27, 23), QtCore.QPointF(16, 28))
        _arrow(p, 16, 16, 16, 4, ACCENT, 2.2, 4.5)
    elif key == "pocket":
        p.setPen(_pen(INK, 1.8))
        p.drawPolygon(
            QtGui.QPolygonF(
                [
                    QtCore.QPointF(5, 14),
                    QtCore.QPointF(16, 7),
                    QtCore.QPointF(27, 14),
                    QtCore.QPointF(16, 21),
                ]
            )
        )
        p.drawLine(QtCore.QPointF(5, 14), QtCore.QPointF(5, 23))
        p.drawLine(QtCore.QPointF(27, 14), QtCore.QPointF(27, 23))
        p.drawLine(QtCore.QPointF(16, 21), QtCore.QPointF(16, 28))
        p.drawLine(QtCore.QPointF(5, 23), QtCore.QPointF(16, 28))
        p.drawLine(QtCore.QPointF(27, 23), QtCore.QPointF(16, 28))
        p.setPen(_pen(INK, 1.4))
        p.drawEllipse(QtCore.QRectF(12, 12, 8, 5))
        _arrow(p, 16, 8, 16, 19, ACCENT, 2.2, 4.0)
    elif key == "hole":
        p.setPen(_pen(INK, 2.0))
        p.drawEllipse(QtCore.QRectF(6, 6, 20, 20))
        p.drawEllipse(QtCore.QRectF(12, 12, 8, 8))
        _dot(p, 16, 16, 2.0, ACCENT)
    elif key == "fillet":
        path = QtGui.QPainterPath()
        path.moveTo(5, 27)
        path.lineTo(5, 15)
        path.quadTo(5, 6, 14, 6)
        path.lineTo(27, 6)
        p.setPen(_pen(INK, 2.2))
        p.drawPath(path)
        p.setPen(_pen(ACCENT, 2.2))
        p.drawArc(QtCore.QRectF(5, 6, 18, 18), 90 * 16, 90 * 16)
    elif key == "export":
        p.drawRoundedRect(QtCore.QRectF(4, 9, 16, 18), 1.5, 1.5)
        p.setPen(_pen(INK, 1.8))
        p.drawLine(QtCore.QPointF(20, 15), QtCore.QPointF(27, 15))
        p.drawLine(QtCore.QPointF(20, 21), QtCore.QPointF(27, 21))
        _arrow(p, 14, 17, 29, 17, ACCENT, 2.4, 4.5)
    elif key == "render":
        p.drawRoundedRect(QtCore.QRectF(4, 11, 24, 16), 3.0, 3.0)
        p.drawEllipse(QtCore.QRectF(11, 14, 10, 10))
        p.drawLine(QtCore.QPointF(8, 11), QtCore.QPointF(10, 7))
        p.drawLine(QtCore.QPointF(10, 7), QtCore.QPointF(16, 7))
        p.drawLine(QtCore.QPointF(16, 7), QtCore.QPointF(18, 11))
        _dot(p, 25, 15, 2.2, ACCENT)
    elif key == "studio":
        p.drawEllipse(QtCore.QRectF(11, 11, 10, 10))
        for i in range(8):
            angle = i * math.pi / 4
            x1 = 16 + 8 * math.cos(angle)
            y1 = 16 + 8 * math.sin(angle)
            x2 = 16 + 12 * math.cos(angle)
            y2 = 16 + 12 * math.sin(angle)
            p.setPen(_pen(ACCENT if i % 2 == 0 else INK, 1.8))
            p.drawLine(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2))
    elif key == "coach":
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(4, 6, 24, 17), 4.0, 4.0)
        p.drawPath(path)
        p.setPen(_pen(INK, 1.8))
        p.drawLine(QtCore.QPointF(10, 23), QtCore.QPointF(8, 28))
        p.drawLine(QtCore.QPointF(8, 28), QtCore.QPointF(16, 23))
        _dot(p, 11, 14.5, 1.8, ACCENT)
        _dot(p, 16, 14.5, 1.8, ACCENT)
        _dot(p, 21, 14.5, 1.8, ACCENT)
    elif key == "setup":
        for y, knob in ((9, 13), (16, 22), (23, 9)):
            p.setPen(_pen(INK, 1.8))
            p.drawLine(QtCore.QPointF(5, y), QtCore.QPointF(27, y))
            _dot(p, knob, y, 3.0, ACCENT)
    elif key == "find":
        p.setPen(_pen(INK, 2.2))
        p.drawEllipse(QtCore.QRectF(5, 5, 16, 16))
        p.drawLine(QtCore.QPointF(19, 19), QtCore.QPointF(27, 27))
        _dot(p, 13, 13, 2.2, ACCENT)
    elif key == "more":
        for x in (10, 16, 22):
            _dot(p, x, 16, 2.4, ACCENT if x == 16 else INK)
    elif key == "draw":
        p.setPen(_pen(INK, 2.0))
        p.drawLine(QtCore.QPointF(7, 25), QtCore.QPointF(23, 9))
        p.drawLine(QtCore.QPointF(23, 9), QtCore.QPointF(27, 5))
        p.drawLine(QtCore.QPointF(7, 25), QtCore.QPointF(6, 28))
        p.drawLine(QtCore.QPointF(6, 28), QtCore.QPointF(11, 26))
        p.setPen(_pen(ACCENT, 2.6))
        p.drawLine(QtCore.QPointF(20, 12), QtCore.QPointF(24, 16))
    elif key == "constrain":
        p.drawRoundedRect(QtCore.QRectF(8, 14, 16, 12), 2.0, 2.0)
        p.drawArc(QtCore.QRectF(11, 6, 10, 14), 0, 180 * 16)
        _dot(p, 16, 20, 2.4, ACCENT)
    elif key == "model":
        p.drawPolygon(
            QtGui.QPolygonF(
                [
                    QtCore.QPointF(5, 12),
                    QtCore.QPointF(16, 6),
                    QtCore.QPointF(27, 12),
                    QtCore.QPointF(16, 18),
                ]
            )
        )
        p.drawLine(QtCore.QPointF(5, 12), QtCore.QPointF(5, 21))
        p.drawLine(QtCore.QPointF(27, 12), QtCore.QPointF(27, 21))
        p.drawLine(QtCore.QPointF(16, 18), QtCore.QPointF(16, 27))
        p.drawLine(QtCore.QPointF(5, 21), QtCore.QPointF(16, 27))
        p.drawLine(QtCore.QPointF(27, 21), QtCore.QPointF(16, 27))
        _dot(p, 16, 12, 2.2, ACCENT)
    elif key == "tools":
        p.setPen(_pen(INK, 1.8))
        p.drawLine(QtCore.QPointF(5, 10), QtCore.QPointF(27, 10))
        p.drawLine(QtCore.QPointF(5, 16), QtCore.QPointF(27, 16))
        p.drawLine(QtCore.QPointF(5, 22), QtCore.QPointF(27, 22))
        _dot(p, 11, 10, 2.8, ACCENT)
        _dot(p, 21, 16, 2.8, ACCENT)
        _dot(p, 14, 22, 2.8, ACCENT)
    elif key == "arc":
        p.drawArc(QtCore.QRectF(5, 7, 22, 22), 10 * 16, 160 * 16)
        _dot(p, 6, 19, 2.6, ACCENT)
        _dot(p, 26, 19, 2.6, ACCENT)
    elif key == "slot":
        p.drawRoundedRect(QtCore.QRectF(5, 11, 22, 10), 5.0, 5.0)
        p.setPen(_pen(ACCENT, 2.0))
        p.drawLine(QtCore.QPointF(11, 16), QtCore.QPointF(21, 16))
        _dot(p, 11, 16, 2.0, ACCENT)
        _dot(p, 21, 16, 2.0, ACCENT)
    elif key == "trim":
        p.setPen(_pen(INK, 1.8))
        p.drawLine(QtCore.QPointF(6, 24), QtCore.QPointF(19, 11))
        p.drawLine(QtCore.QPointF(6, 8), QtCore.QPointF(19, 21))
        p.drawEllipse(QtCore.QRectF(17, 17, 8, 8))
        p.drawEllipse(QtCore.QRectF(17, 3, 8, 8))
    elif key == "construction":
        p.setPen(_pen(INK, 1.8))
        for start in (5, 12, 19, 26):
            p.drawLine(QtCore.QPointF(start, 20), QtCore.QPointF(start + 3, 10))
        _dot(p, 16, 16, 2.2, ACCENT)
    elif key == "parallel":
        p.setPen(_pen(INK, 2.0))
        p.drawLine(QtCore.QPointF(8, 24), QtCore.QPointF(14, 8))
        p.drawLine(QtCore.QPointF(18, 24), QtCore.QPointF(24, 8))
        _dot(p, 8, 24, 2.2, ACCENT)
        _dot(p, 18, 24, 2.2, ACCENT)
    elif key == "perp":
        p.setPen(_pen(INK, 2.0))
        p.drawLine(QtCore.QPointF(8, 25), QtCore.QPointF(8, 8))
        p.drawLine(QtCore.QPointF(8, 25), QtCore.QPointF(26, 25))
        p.drawRect(QtCore.QRectF(8, 20, 5, 5))
        _dot(p, 8, 8, 2.2, ACCENT)
        _dot(p, 26, 25, 2.2, ACCENT)
    elif key == "tangent":
        p.drawEllipse(QtCore.QRectF(5, 10, 14, 14))
        p.setPen(_pen(ACCENT, 2.2))
        p.drawLine(QtCore.QPointF(4, 6), QtCore.QPointF(28, 6))
        _dot(p, 12, 10, 2.4, INK)
    elif key == "equal":
        p.setPen(_pen(INK, 2.0))
        p.drawLine(QtCore.QPointF(5, 13), QtCore.QPointF(27, 13))
        p.drawLine(QtCore.QPointF(5, 19), QtCore.QPointF(27, 19))
        p.setPen(_pen(ACCENT, 2.0))
        p.drawLine(QtCore.QPointF(12, 7), QtCore.QPointF(12, 25))
        p.drawLine(QtCore.QPointF(20, 7), QtCore.QPointF(20, 25))
    elif key == "angle":
        p.setPen(_pen(INK, 2.0))
        p.drawLine(QtCore.QPointF(6, 25), QtCore.QPointF(26, 25))
        p.drawLine(QtCore.QPointF(6, 25), QtCore.QPointF(22, 9))
        p.drawArc(QtCore.QRectF(6, 15, 14, 14), 0, 45 * 16)
        _dot(p, 6, 25, 2.4, ACCENT)
    elif key == "measure":
        p.drawRoundedRect(QtCore.QRectF(4, 11, 24, 10), 1.5, 1.5)
        p.setPen(_pen(INK, 1.2))
        for x in (9, 14, 19, 24):
            p.drawLine(QtCore.QPointF(x, 11), QtCore.QPointF(x, 16))
        _arrow(p, 6, 24, 26, 24, ACCENT, 1.8, 3.5)
    else:
        p.drawEllipse(QtCore.QRectF(6, 6, 20, 20))
        _dot(p, 16, 16, 2.5, ACCENT)

    p.end()
    result = QtGui.QIcon(pm)
    _CACHE[key] = result
    return result
