"""Advanced chatbot engine: OpenAI-first, context-aware, safety-hardened fallback."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import requests

_OPENAI_URL = "https://api.openai.com/v1/responses"
_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
_TIMEOUT = 40
logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are CropSense AI, an evidence-informed rice-crop decision-support assistant. "
    "Always respond with exactly 5 sections: Assessment, Evidence, Actions, Safety, Sources. "
    "Use concise bullet points. "
    "Treat image predictions as screening evidence, not a confirmed diagnosis. "
    "Consider crop stage, symptoms, recent weather, irrigation, nitrogen use, variety, "
    "field distribution, and location. If critical facts are missing, ask up to 3 focused questions. "
    "Prioritize integrated pest management: confirmation, resistant varieties, sanitation, "
    "balanced nutrition, water/canopy management, monitoring, then chemical control only when justified. "
    "Never invent a pesticide, dose, interval, registration, or legal approval. "
    "Only discuss chemical treatment conditionally and tell the user to verify the current local label, "
    "pre-harvest interval, re-entry interval, PPE, and local extension guidance. "
    "Never provide dangerous, illegal, or unsafe instructions. "
    "Do not invent certainty: if unclear, state uncertainty and request one key clarification. "
    "If app context indicates low confidence/uncertain prediction, prioritize retake-image guidance. "
    "Keep advice practical for field use. Cite IRRI or FAO links in Sources. "
    "Reply in the user's language when it can be identified, including Telugu. "
    "State that the answer is decision support and not a substitute for an on-site agronomist."
)

_IRRI_DISEASES = "https://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases"
_FAO_IPM = "https://www.fao.org/4/Y4544E/y4544e02.htm"

_KB = {
    "leaf blast": {
        "symptoms": "Diamond- or spindle-shaped leaf lesions with gray centers and brown margins; neck infection can prevent grain filling.",
        "why": "Often associated with fungal pressure, high humidity, and excess nitrogen.",
        "actions": [
            "Confirm lesion shape and check whether infection is on leaves, nodes, or the panicle neck.",
            "Avoid additional nitrogen until crop need is verified; maintain balanced potassium and overall nutrition.",
            "Reduce prolonged leaf wetness where irrigation management allows and remove heavily infected residue after harvest.",
            "Use resistant varieties and clean seed in the next crop where locally available.",
        ],
        "caution": "If a fungicide is justified, use only a product currently registered for rice blast locally and follow its label; avoid spraying before rain or in high wind.",
        "source": "https://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/blast-leaf-collar",
    },
    "brown spot": {
        "symptoms": "Numerous oval brown lesions, often with a gray center; severe infection can kill large portions of the leaf.",
        "why": "Linked to nutrient stress and prolonged leaf wetness.",
        "actions": [
            "Confirm oval brown lesions and rule out blast or nutrient injury.",
            "Use a soil or leaf test before correcting potassium, phosphorus, or micronutrient deficiencies.",
            "Keep irrigation stable and avoid moisture stress.",
            "Use clean seed, balanced fertility, and remove infected residue after harvest.",
        ],
        "caution": "Do not repeatedly apply a non-target fungicide; confirm diagnosis and verify any product against the current local rice label.",
        "source": "https://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/brown-spot",
    },
    "bacterial blight": {
        "symptoms": "Water-soaked yellow-orange stripes starting near leaf tips or margins, later becoming straw-colored; seedlings may wilt.",
        "why": "Can spread via water splash, tools, and humid conditions.",
        "actions": [
            "Check for wavy, water-soaked lesions and seek local confirmation because symptoms can resemble other blights.",
            "Avoid excess nitrogen and apply only the crop's balanced nutrient requirement.",
            "Improve drainage and reduce standing water.",
            "Sanitize tools, avoid handling wet foliage, remove weed hosts, and manage infected stubble after harvest.",
            "Prefer locally resistant varieties; this is the most reliable control option.",
        ],
        "caution": "Do not use random antibiotic or pesticide mixtures; bacterial blight management is primarily preventive and label/legal restrictions vary.",
        "source": "https://www.knowledgebank.irri.org/decision-tools/rice-doctor/rice-doctor-fact-sheets/item/bacterial-blight",
    },
    "sheath blight": {
        "symptoms": "Oval green-gray lesions on lower leaf sheaths near the waterline that expand upward, often with gray-white centers and brown margins.",
        "why": "Favored by dense canopies, high nitrogen, warm humid weather, and close spacing.",
        "actions": [
            "Inspect lower sheaths and look for characteristic lesions or sclerotia before acting.",
            "Avoid excess nitrogen and overly dense crop establishment.",
            "Improve canopy airflow, manage weeds on levees, and use drainage appropriate to the crop stage.",
            "Monitor spread toward upper leaves and the flag leaf, where yield risk becomes more serious.",
        ],
        "caution": "Confirm against stem rot and stem-borer injury; use a fungicide only when locally registered and economically justified.",
        "source": "https://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/sheath-blight",
    },
    "tungro": {
        "symptoms": "Yellow-orange discoloration, stunting, reduced tillering, and delayed flowering; plants may occur in patches.",
        "why": "A viral disease transmitted by green leafhoppers; infected plants cannot be cured.",
        "actions": [
            "Confirm symptoms and check for green leafhopper activity with local extension support.",
            "Remove severely infected plants early when practical and control volunteer rice and weed hosts.",
            "Use resistant varieties, synchronized planting, and avoid overlapping rice crops.",
            "Manage the vector using local thresholds and IPM rather than routine calendar spraying.",
        ],
        "caution": "Fungicides do not cure viral disease; unnecessary insecticide can disrupt natural enemies.",
        "source": _IRRI_DISEASES,
    },
}

_DEFAULT = (
    "Assessment:\n"
    "- There is not enough information for a reliable field assessment.\n"
    "Evidence:\n"
    "- Please provide the rice growth stage, affected plant part, lesion color/shape, field distribution, and recent weather.\n"
    "Actions:\n"
    "- Upload a sharp close-up plus one whole-plant or field-pattern photo and state your location.\n"
    "Safety:\n"
    "- Do not mix or apply pesticides from an uncertain diagnosis; follow current local labels and extension advice.\n"
    "Sources:\n"
    f"- IRRI Rice Disease Fact Sheets: {_IRRI_DISEASES}\n"
    f"- FAO Integrated Pest Management principles: {_FAO_IPM}"
)

_UNSAFE_HINTS = [
    "poison", "harm", "kill", "illegal", "bomb", "weapon", "suicide", "self harm",
]
_REQUIRED_SECTIONS = ("Assessment:", "Evidence:", "Actions:", "Safety:", "Sources:")


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


def _is_well_formed_answer(text: str) -> bool:
    """Reject incomplete model output so the UI always receives a safe structure."""
    positions = [text.find(section) for section in _REQUIRED_SECTIONS]
    return all(position >= 0 for position in positions) and positions == sorted(positions)


def _format_safe_refusal() -> str:
    return (
        "Assessment:\n- I cannot help with harmful or unsafe requests.\n"
        "Evidence:\n- This assistant supports safe agricultural decision-making only.\n"
        "Actions:\n- Ask crop-disease, fertilizer, irrigation, or weather-risk questions.\n"
        "Safety:\n- For emergencies, contact local emergency or health services immediately.\n"
        f"Sources:\n- FAO pesticide and IPM safety principles: {_FAO_IPM}"
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
        f"Assessment:\n- Screening concern: {picked.title()}; confirm from symptoms and field pattern before treatment.{retake_note}\n"
        f"Evidence:\n- Typical signs: {item['symptoms']}\n- Risk factors: {item['why']}{weather_note}\n"
        f"Actions:\n{action_lines}\n"
        f"Safety:\n- {item['caution']}\n"
        "- This is decision support, not a substitute for an on-site agronomist or local extension officer.\n"
        f"Sources:\n- IRRI disease guidance: {item['source']}\n- FAO IPM principles: {_FAO_IPM}"
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
        "Output strictly in 5 sections: Assessment, Evidence, Actions, Safety, Sources. "
        "Use short bullets, practical steps, and direct IRRI/FAO source URLs."
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
        if text and _is_well_formed_answer(text):
            return text

        for item in data.get("output", []):
            for c in item.get("content", []):
                if c.get("type") == "output_text" and c.get("text"):
                    candidate = str(c["text"]).strip()
                    if _is_well_formed_answer(candidate):
                        return candidate
    except Exception as exc:
        logger.warning("OpenAI chatbot request failed; using rule fallback: %s", type(exc).__name__)
        return None

    return None


def get_response(user_message: str, context: dict[str, Any] | None = None) -> str:
    live = _openai_reply(user_message, context=context)
    if live:
        return live
    return _rule_reply(user_message, context=context)
