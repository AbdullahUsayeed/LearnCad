# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Paid AI explanation layer.

The deterministic mentor in analysis.py is the source of truth. This module
sends a compact, explicit summary of the model to the LearnCad AI server, which
verifies the subscription and proxies the request to the language model.
"""

from __future__ import annotations

import json
from typing import Any

from . import cloud_ai, settings
from .guide import APP_GUIDE
from .model import Analysis, Snapshot


class AIClientError(RuntimeError):
    pass


SYSTEM_PROMPT = """You are LearnCad, a senior mechanical engineer and CAD coach mentoring a beginner inside the LearnCad application.

You can see the live document state and a deterministic engineering review. Use those facts for model questions. Use the LearnCad app guide for how-to questions.

=== LEARNCAD APP GUIDE (the complete beginner-facing UI) ===
""" + APP_GUIDE + """

=== RULES ===
- The user's stated goal is in the context. Review the model against that goal, not just against generic best practice.
- The goal is persistent. If the current question is clearly about a different project than the saved goal, name the saved goal and ask whether to change it before giving project-specific advice.
- Never invent dimensions, constraints, or object names. If a number is not in the context, say so.
- When a sketch is under-constrained, explain the exact missing constraint and the order to add it.
- Praise only when the model has earned it.
- Warn about consequences: printability, rebuildability, stress concentration, tolerance.
- The user is learning. Explain the why, not just the click.
- For "how do I...", "where is...", or "which button..." questions, use the exact LearnCad labels from the app guide and give a short numbered sequence. Do not mention the underlying CAD engine, its menus, workbenches, version, or the renderer. Never send the user to a menu that is not in the guide.
- If the guide does not cover a control, say that Simple Mode exposes the listed tools and that Setup can restore the advanced workspace.
- Do not write code unless the user asks. If asked, keep it short and use the standard Python console API.
- If the intent is ambiguous, ask one clarifying question instead of guessing.
- Keep UI answers under 200 words unless the user asks for a full walkthrough.
- Never reveal, confirm, deny, or discuss the model, provider, vendor, version, parameter count, or underlying technology. If asked, say only that you are LearnCad's built-in coach and redirect to the user's CAD question. Never output a model ID, provider name, or vendor name.
- No fluff, no "as an AI", no long introductions.
"""


def _compact_snapshot(snapshot: Snapshot) -> dict[str, Any]:
    if snapshot.doc is None:
        return {"document": None}
    doc = snapshot.doc
    bodies = []
    for body in doc.bodies[:3]:
        bodies.append({
            "label": body.label,
            "tip": body.tip,
            "feature_count": body.feature_count,
            "error_count": body.error_count,
            "valid": body.shape_valid,
            "closed": body.shape_closed,
            "volume": round(body.volume, 1),
            "bbox": [round(v, 1) for v in body.bbox.dims],
            "features": [
                {
                    "label": f.label,
                    "type": f.type_id,
                    "state": f.state,
                    "valid": f.valid,
                    "length": f.length,
                    "radius": f.radius,
                    "diameter": f.diameter,
                }
                for f in body.features[:12]
            ],
        })
    sketches = []
    for sketch in doc.sketches[:6]:
        sketches.append({
            "label": sketch.label,
            "dof": sketch.dof,
            "fully_constrained": sketch.fully_constrained,
            "geometry_count": sketch.geometry_count,
            "constraint_count": sketch.constraint_count,
            "wires": [sketch.total_wires, sketch.open_wires],
            "conflicts": [sketch.conflicting, sketch.redundant, sketch.malformed],
            "missing": {
                "coincident": sketch.missing_coincident,
                "horizontal_vertical": sketch.missing_hv,
                "radius": sketch.missing_radius,
                "equality": sketch.missing_equality,
            },
            "attached": sketch.attached,
            "support": sketch.support,
            "bbox": [round(v, 1) for v in sketch.bbox.dims],
            "dimensions": [
                {"kind": d.kind, "value": round(d.value, 2)}
                for d in sketch.dimensions[:20]
            ],
        })
    return {
        "goal": snapshot.goal,
        "document": {
            "label": doc.label,
            "workbench": doc.workbench,
            "edit_mode": doc.edit_mode,
            "active_object": doc.active_object,
            "selection": {
                "object": doc.selection.object_label or doc.selection.object_name,
                "type": doc.selection.object_type,
                "subelements": doc.selection.subelements[:6],
            },
            "object_count": doc.object_count,
            "units": doc.units,
            "bodies": bodies,
            "sketches": sketches,
            "standalone_features": [
                {"label": f.label, "type": f.type_id, "valid": f.valid}
                for f in doc.features[:8]
            ],
        }
    }


def build_payload(
    question: str,
    snapshot: Snapshot,
    analysis: Analysis,
    model: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    context = {
        "project": _compact_snapshot(snapshot),
        "review": analysis.to_dict(),
        "question": question,
    }
    user_text = (
        "Here is the live project context and the deterministic review. "
        "For model-specific questions, answer from these facts. "
        "For how-to or UI questions, answer from the LEARNCAD APP GUIDE in the system prompt. "
        "Do not use any other menu names.\n\n"
        + json.dumps(context, ensure_ascii=False, default=str)
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history or []:
        role = str(item.get("role", ""))
        content = str(item.get("content", "") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})
    return {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 650,
        "messages": messages,
    }


def _extract_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("choices"), list) and payload["choices"]:
        message = payload["choices"][0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            return "\n".join(parts).strip()
    if isinstance(payload.get("content"), list):
        parts = [str(block.get("text", "")) for block in payload["content"] if isinstance(block, dict)]
        return "\n".join(parts).strip()
    if isinstance(payload.get("response"), str):
        return payload["response"].strip()
    return ""


def ask(
    data: dict[str, Any],
    question: str,
    snapshot: Snapshot,
    analysis: Analysis,
    history: list[dict[str, str]] | None = None,
) -> str:
    if not settings.ai_ready(data):
        raise AIClientError(
            "AI needs an active LearnCad subscription. The local mentor still works for free."
        )

    base_url = str(data.get("cloud_base_url", "") or "").strip()
    token = settings.get_license_token(data)
    if not base_url or not token:
        raise AIClientError(
            "Activate your LearnCad AI subscription in Setup. The local mentor still works for free."
        )

    model = str(data.get("ai_model", "learncad-ai") or "learncad-ai")
    payload = build_payload(question, snapshot, analysis, model, history)
    try:
        parsed = cloud_ai.chat(base_url, token, payload)
    except cloud_ai.CloudAIError as exc:
        raise AIClientError(str(exc)) from exc

    text = _extract_text(parsed)
    if not text:
        raise AIClientError("The AI server returned an empty answer.")
    return text


def test_connection(data: dict[str, Any]) -> tuple[bool, str]:
    if not data.get("cloud_base_url"):
        return False, "Set the LearnCad AI server URL first."
    token = settings.get_license_token(data)
    if not token:
        return False, "Activate a subscription with your email and license code first."
    try:
        result = cloud_ai.status(str(data.get("cloud_base_url", "")), token)
    except cloud_ai.CloudAIError as exc:
        return False, str(exc)
    state = str(result.get("status", "") or "active").lower()
    if state not in ("active", "trialing", "paid"):
        return False, f"Subscription status: {state}."
    expires = str(result.get("expires_at", "") or "").strip()
    if expires:
        return True, f"Subscription active. Expires {expires}."
    return True, "Subscription active. Paid AI is ready."
