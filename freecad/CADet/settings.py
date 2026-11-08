# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Local configuration. The deterministic mentor runs offline and needs no
account. Paid AI explanations are activated with an email and license code from
the LearnCad subscription server.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import FreeCAD as App

from . import secret_store


DEFAULTS: dict[str, Any] = {
    "ai_enabled": False,
    "consent_ai": False,
    "cloud_base_url": "",
    "subscribe_url": "",
    "license_email": "",
    "license_code_enc": "",
    "license_token_enc": "",
    "license_expires": "",
    "ai_model": "learncad-ai",
    "device_id": "",
    "poll_ms": 900,
    "max_history": 12,
    "goal": "",
    "blender_path": "",
    "render_engine": "CYCLES",
    "render_resolution": [1200, 800],
    "render_samples": 64,
    "render_material": "aluminum",
    "simple_mode": True,
    "auto_open_panel": True,
    "navigation_style": "Gui::OpenInventorNavigationStyle",
}


def config_dir() -> str:
    try:
        base = App.getUserConfigDir()
    except Exception:
        base = App.getUserAppDataDir()
    path = os.path.join(base, "LearnCad")
    os.makedirs(path, exist_ok=True)
    return path


def config_path() -> str:
    return os.path.join(config_dir(), "config.json")


def load() -> dict[str, Any]:
    path = config_path()
    data: dict[str, Any] = dict(DEFAULTS)
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                data.update(loaded)
    except Exception:
        pass
    for legacy in ("api_key_enc", "base_url", "model"):
        data.pop(legacy, None)
    if not get_license_token(data):
        data["ai_enabled"] = False
        data["consent_ai"] = False
    return data


def save(data: dict[str, Any]) -> None:
    path = config_path()
    payload = dict(DEFAULTS)
    payload.update(data or {})
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    os.replace(tmp, path)
    secret_store.harden_file(path)


def get_license_token(data: dict[str, Any]) -> str:
    return secret_store.unprotect(str(data.get("license_token_enc", "") or ""))


def set_license_token(data: dict[str, Any], token: str) -> None:
    data["license_token_enc"] = secret_store.protect(token or "")


def get_license_code(data: dict[str, Any]) -> str:
    return secret_store.unprotect(str(data.get("license_code_enc", "") or ""))


def set_license_code(data: dict[str, Any], code: str) -> None:
    data["license_code_enc"] = secret_store.protect(code or "")


def device_id(data: dict[str, Any]) -> str:
    value = str(data.get("device_id", "") or "").strip()
    if not value:
        value = uuid.uuid4().hex
        data["device_id"] = value
    return value


def license_expires_at(data: dict[str, Any]) -> datetime | None:
    raw = str(data.get("license_expires", "") or "").strip()
    if not raw:
        return None
    try:
        value = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def license_active(data: dict[str, Any]) -> bool:
    if not get_license_token(data):
        return False
    expires = license_expires_at(data)
    if expires is not None and expires <= datetime.now(timezone.utc):
        return False
    return True


def ai_ready(data: dict[str, Any]) -> bool:
    if not data.get("ai_enabled") or not data.get("consent_ai"):
        return False
    if not str(data.get("cloud_base_url", "") or "").strip():
        return False
    return license_active(data)
