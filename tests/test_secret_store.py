# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Secret storage tests. They do not need FreeCAD or Qt."""

from __future__ import annotations

import base64
import sys

import pytest

from freecad.CADet import secret_store


def test_empty_values():
    assert secret_store.protect("") == ""
    assert secret_store.unprotect("") == ""


def test_plain_fallback_roundtrip():
    token = "plain:" + base64.b64encode(b"hello").decode("ascii")
    assert secret_store.unprotect(token) == "hello"


def test_invalid_token_is_safe():
    assert secret_store.unprotect("dpapi:not-base64") == ""
    assert secret_store.unprotect("garbage") == "garbage"


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
def test_dpapi_roundtrip():
    token = secret_store.protect("sk-test-123456789")
    assert token.startswith("dpapi:")
    assert secret_store.unprotect(token) == "sk-test-123456789"
    assert secret_store.storage_description() == "Windows DPAPI"
