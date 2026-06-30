"""Advanced chatbot engine: OpenAI-first, context-aware, safety-hardened fallback."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

_OPENAI_URL = "https://api.openai.com/v1/responses"
_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
_TIMEOUT = 40

_SYSTEM_PROMPT = (
    "You are CropSense AI, a rice-farming assistant. "
    "Always respond with exactly 4 sections: Diagnosis, Why, Actions, Cautions. "
    "Use concise bullet points. "
    "Never provide dangerous, illegal, or unsafe instructions. "
    "Do not invent certainty: if unclear, state uncertainty and request one key clarification. "
    "If app context indicates low confidence/uncertain prediction, prioritize retake-image guidance. "
    "Keep advice practical for field use and mention label/local-extension compliance for chemical use."
)

_KB = {
    "leaf blast": {
        "why": "Often associated with fungal pressure, high humidity, and excess nitrogen.",
        "actions": [
            "Remove infected leaves and infected residue.",
            "Reduce nitrogen temporarily and rebalance nutrition.",
            "Improve spacing and airflow to reduce leaf wetness.",
            "Use locally approved fungicide schedule as per label guidance.",
        ],
        "caution": "Avoid spraying in strong heat, high wind, or just before rain.",
    },
    "brown spot": {
        "why": "Linked to nutrient stress and prolonged leaf wetness.",
        "actions": [
            "Correct potassium and phosphorus deficiencies.",
            "Keep irrigation stable and avoid moisture stress.",
            "Use recommended fungicide only if needed by local guidance.",
        ],
        "caution": "Avoid repeated non-target fungicide use without diagnosis confirmation.",
    },
    "bacterial blight": {
        "why": "Can spread via water splash, tools, and humid conditions.",
        "actions": [
            "Reduce nitrogen and avoid over-irrigation.",
            "Improve drainage and reduce standing water.",
            "Sanitize tools and avoid handling wet foliage.",
            "Follow approved bactericide schedule if recommended locally.",
        ],
        "caution": "Do not rely on random pesticide combinations.",
    },
}

_DEFAULT = (
    "Diagnosis:\n"
    "- Please share disease name or upload analysis result for precise support.\n"
    "Why:\n"
    "- Treatment varies by disease type, crop stage, and weather conditions.\n"
    "Actions:\n"
    "- Provide location, key symptoms, and severity for tailored guidance.\n"
    "Cautions:\n"
    "- Avoid unsupervised pesticide mixing; follow label and local extension advice."
)

_UNSAFE_HINTS = [
    "poison", "harm", "kill", "illegal", "bomb", "weapon", "suicide", "self harm",
]


def _tokenise(text: str) -> str:
    return re.sub(r"[^\w\s]", " ", text.lower())


def _is_unsafe_query(message: str) -> bool:
    t = _tokenise(message)
    return any(h in t for h in _UNSAFE_HINTS)


def _context_to_text(context: dict[str, Any] | None) -> str:
    if not context:
        return "No app context available."
    safe = {
        "latest_prediction": context.get("latest_prediction"),
        "latest_weather": context.get("latest_weather"),
        "recent_chat": context.get("recent_chat", [])[-4:],
    }
    return json.dumps(safe, ensure_ascii=True)


def _format_safe_refusal() -> str:
    return (
        "Diagnosis:\n- I cannot help with harmful or unsafe requests.\n"
        "Why:\n- This assistant supports safe agricultural guidance only.\n"
        "Actions:\n- Ask crop-disease, fertilizer, irrigation, or weather-risk questions.\n"
        "Cautions:\n- For emergencies, contact local emergency or health services immediately."
    )


def _rule_reply(message: str, context: dict[str, Any] | None = None) -> str:
    if _is_unsafe_query(message):
        return _format_safe_refusal()

    txt = _tokenise(message)
    picked = None

    for k in _KB:
        if k in txt:
            picked = k
            break

    if not picked and context:
        pred = (context.get("latest_prediction") or {}).get("disease", "").lower()
        for k in _KB:
            if k in pred:
                picked = k
                break

    if not picked:
        return _DEFAULT

    item = _KB[picked]
    action_lines = "\n".join([f"- {x}" for x in item["actions"]])

    weather_note = ""
    w = (context or {}).get("latest_weather")
    if isinstance(w, dict):
        hum = w.get("humidity")
        desc = w.get("description")
        if isinstance(hum, (int, float)):
            weather_note += (
                f"\n- Current humidity {hum}% may increase disease pressure."
                if hum >= 80
                else f"\n- Current humidity {hum}% is moderate."
            )
        if desc:
            weather_note += f"\n- Weather condition: {desc}."

    pred = (context or {}).get("latest_prediction") or {}
    if pred and (pred.get("confidence", 1) < 0.6 or pred.get("needs_retake")):
        retake_note = "\n- App prediction confidence is low. Retake a clear close-up leaf image before treatment decision."
    else:
        retake_note = ""

    return (
        f"Diagnosis:\n- Likely concern: {picked.title()}.{retake_note}\n"
        f"Why:\n- {item['why']}{weather_note}\n"
        f"Actions:\n{action_lines}\n"
        f"Cautions:\n- {item['caution']}"
    )


def _openai_reply(message: str, context: dict[str, Any] | None = None) -> str | None:
    if _is_unsafe_query(message):
        return _format_safe_refusal()

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    context_text = _context_to_text(context)
    user_prompt = (
        f"User question: {message}\n\n"
        f"App context: {context_text}\n\n"
        "Output strictly in 4 sections: Diagnosis, Why, Actions, Cautions. "
        "Use short bullets and practical steps."
    )

    payload = {
        "model": _DEFAULT_MODEL,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": _SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
        ],
    }

    try:
        resp = requests.post(
            _OPENAI_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        text = (data.get("output_text") or "").strip()
        if text:
            return text

        for item in data.get("output", []):
            for c in item.get("content", []):
                if c.get("type") == "output_text" and c.get("text"):
                    return str(c["text"]).strip()
    except Exception:
        return None

    return None


def get_response(user_message: str, context: dict[str, Any] | None = None) -> str:
    live = _openai_reply(user_message, context=context)
    if live:
        return live
    return _rule_reply(user_message, context=context)
