# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Windows DPAPI wrapper for the AI access token and license code.

No third-party dependency. On non-Windows systems they are stored with a
clear warning; paid AI is opt-in and never required for the free coach.
"""

from __future__ import annotations

import base64
import ctypes
import os
import sys
from ctypes import wintypes


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _dpapi_available() -> bool:
    return sys.platform == "win32" and hasattr(ctypes, "WinDLL")


if _dpapi_available():  # pragma: no cover - Windows only
    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptProtectData.restype = wintypes.BOOL

    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL

    _kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    _kernel32.LocalFree.restype = wintypes.HLOCAL
else:  # pragma: no cover - non-Windows
    _crypt32 = None
    _kernel32 = None


def _make_blob(data: bytes):
    buffer = ctypes.create_string_buffer(data, len(data))
    blob = _DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    return blob, buffer


def protect(text: str) -> str:
    if not text:
        return ""
    data = text.encode("utf-8")
    if not _dpapi_available():
        return "plain:" + base64.b64encode(data).decode("ascii")
    try:
        in_blob, _in_buffer = _make_blob(data)
        out_blob = _DATA_BLOB()
        result = _crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0x1,
            ctypes.byref(out_blob),
        )
        if not result:
            raise OSError(ctypes.get_last_error(), "CryptProtectData failed")
        try:
            protected = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            _kernel32.LocalFree(out_blob.pbData)
        return "dpapi:" + base64.b64encode(protected).decode("ascii")
    except Exception:
        return "plain:" + base64.b64encode(data).decode("ascii")


def unprotect(token: str) -> str:
    if not token:
        return ""
    if token.startswith("dpapi:"):
        if not _dpapi_available():
            return ""
        try:
            data = base64.b64decode(token[6:])
            in_blob, _in_buffer = _make_blob(data)
            out_blob = _DATA_BLOB()
            description = wintypes.LPWSTR()
            result = _crypt32.CryptUnprotectData(
                ctypes.byref(in_blob),
                ctypes.byref(description),
                None,
                None,
                None,
                0x1,
                ctypes.byref(out_blob),
            )
            if not result:
                raise OSError(ctypes.get_last_error(), "CryptUnprotectData failed")
            try:
                return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8", errors="replace")
            finally:
                if description:
                    _kernel32.LocalFree(description)
                _kernel32.LocalFree(out_blob.pbData)
        except Exception:
            return ""
    if token.startswith("plain:"):
        try:
            return base64.b64decode(token[6:]).decode("utf-8", errors="replace")
        except Exception:
            return ""
    return token


def storage_description() -> str:
    if _dpapi_available():
        return "Windows DPAPI"
    return "local file permissions (no OS keychain available)"


def harden_file(path: str) -> None:
    try:
        if os.name != "nt":
            os.chmod(path, 0o600)
    except Exception:
        pass
