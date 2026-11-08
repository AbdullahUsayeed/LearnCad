# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Paid AI client for the LearnCad subscription server.

The desktop app never holds the language-model API key. It activates a license
with the user's server, stores the returned access token, and sends AI requests
through that server.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class CloudAIError(RuntimeError):
    pass


def _base(base_url: str) -> str:
    value = str(base_url or "").strip().rstrip("/")
    if not value:
        raise CloudAIError("Set the LearnCad AI server URL first.")
    if not (value.startswith("https://") or value.startswith("http://")):
        raise CloudAIError("The LearnCad AI server URL must start with https:// or http://.")
    return value


def _request(
    base_url: str,
    path: str,
    payload: dict[str, Any] | None = None,
    token: str = "",
    method: str = "POST",
    timeout: int = 60,
) -> dict[str, Any]:
    url = _base(base_url) + path
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        if exc.code in (401, 402, 403):
            raise CloudAIError(
                "Your LearnCad AI subscription is inactive or expired. Activate it again in Setup."
            ) from exc
        message = f"The AI server returned HTTP {exc.code}."
        if detail:
            message += " " + detail
        raise CloudAIError(message) from exc
    except urllib.error.URLError as exc:
        raise CloudAIError(f"Could not reach the LearnCad AI server: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CloudAIError("The LearnCad AI server timed out.") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CloudAIError("The LearnCad AI server returned a response that was not JSON.") from exc
    if not isinstance(parsed, dict):
        raise CloudAIError("The LearnCad AI server returned an unexpected response.")
    return parsed


def activate(base_url: str, email: str, license_code: str, device: str) -> dict[str, Any]:
    result = _request(
        base_url,
        "/v1/license/activate",
        {
            "email": str(email or "").strip(),
            "license_code": str(license_code or "").strip(),
            "device_id": str(device or "").strip(),
        },
        timeout=30,
    )
    token = str(result.get("token", "") or "").strip()
    if not token:
        raise CloudAIError("The AI server did not return an access token.")
    return result


def status(base_url: str, token: str) -> dict[str, Any]:
    return _request(base_url, "/v1/license/me", token=token, method="GET", timeout=20)


def chat(base_url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request(base_url, "/v1/chat/completions", payload, token=token, timeout=90)
