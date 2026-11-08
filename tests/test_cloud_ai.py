# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Network-free tests for the paid AI client contract."""

from __future__ import annotations

import json

import pytest

from freecad.CADet import cloud_ai


class FakeResponse:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._raw


def test_base_url_requires_a_scheme():
    with pytest.raises(cloud_ai.CloudAIError):
        cloud_ai.chat("api.example.com", "token", {})
    with pytest.raises(cloud_ai.CloudAIError):
        cloud_ai.chat("", "token", {})


def test_activate_calls_the_expected_endpoint(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"token": "licence-token", "expires_at": "2027-01-01T00:00:00Z"})

    monkeypatch.setattr(cloud_ai.urllib.request, "urlopen", fake_urlopen)
    result = cloud_ai.activate("https://ai.example.com/", "a@b.com", "ABC-123", "device-1")
    assert result["token"] == "licence-token"
    assert captured["url"] == "https://ai.example.com/v1/license/activate"
    assert captured["body"] == {
        "email": "a@b.com",
        "license_code": "ABC-123",
        "device_id": "device-1",
    }


def test_chat_sends_the_bearer_token_and_payload(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(cloud_ai.urllib.request, "urlopen", fake_urlopen)
    result = cloud_ai.chat(
        "https://ai.example.com",
        "licence-token",
        {"model": "learncad-ai", "messages": []},
    )
    assert result["choices"][0]["message"]["content"] == "ok"
    assert captured["url"] == "https://ai.example.com/v1/chat/completions"
    assert captured["auth"] == "Bearer licence-token"
    assert captured["body"]["model"] == "learncad-ai"
