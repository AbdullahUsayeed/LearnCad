# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Pure tests for the studio color encoding."""

from __future__ import annotations

from freecad.CADet.studio import LIGHT_BODY, LIGHT_LINE, argb


def test_argb_encoding():
    assert argb(0, 0, 0, 0) == 0x00000000
    assert argb(255, 255, 255, 255) == 0xFFFFFFFF
    assert argb(1, 2, 3, 4) == 0x01020304


def test_studio_body_and_line_colors_are_opaque():
    assert (LIGHT_BODY & 0xFF) == 0xFF
    assert (LIGHT_LINE & 0xFF) == 0xFF
    assert LIGHT_BODY != LIGHT_LINE
