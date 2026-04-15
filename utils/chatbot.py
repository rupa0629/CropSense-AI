"""
chatbot.py
----------
Rule-based farmer chatbot for common rice cultivation questions.

The bot uses keyword matching to find the best answer.
Responses are written in simple, farmer-friendly English.
"""

from __future__ import annotations
import re

# ── Knowledge base: (keywords, answer) pairs ─────────────────────────────────
# Each entry is (list_of_trigger_keywords, response_text)
_KB: list[tuple[list[str], str]] = [

    # ── Disease identification ────────────────────────────────────────────────
    (
        ["leaf blast", "blast", "grey spot", "gray spot", "diamond spot"],
        "🍃 **Leaf Blast** causes diamond-shaped grey lesions with brown borders on leaves. "
        "It is caused by the fungus *Magnaporthe oryzae*. It spreads fast in cool, humid weather. "
        "Reduce nitrogen fertiliser and spray Tricyclazole to control it.",
    ),
    (
        ["brown spot", "brown lesion", "brown patch"],
        "🟤 **Brown Spot** appears as oval/circular brown lesions with yellow halos. "
        "It is linked to nutrient deficiency — especially low potassium. "
        "Apply potassium fertiliser and spray Mancozeb to manage it.",
    ),
    (
        ["bacterial blight", "blight", "kresek", "yellow leaf", "wilting"],
        "🦠 **Bacterial Blight** causes water-soaked streaks that turn yellow, then white. "
        "It spreads through water and wounds. Avoid excess nitrogen; spray copper oxychloride.",
    ),
    (
        ["healthy", "no disease", "normal", "good crop"],
        "✅ Great news! A **healthy crop** needs balanced NPK fertiliser, "
        "good water management (alternate wetting and drying), and weekly scouting.",
    ),

    # ── Symptoms & diagnosis ──────────────────────────────────────────────────
    (
        ["yellow", "yellowing", "pale leaves"],
        "💛 Yellowing leaves can indicate:\n"
        "• Nitrogen deficiency (uniform yellow from older leaves)\n"
        "• Bacterial blight (yellow streaks from leaf tips)\n"
        "• Waterlogging (roots suffocating)\n"
        "Upload an image for accurate diagnosis!",
    ),
    (
        ["white tip", "dead tip", "tip burn"],
        "White / burnt leaf tips are often early signs of **Bacterial Blight** or severe **heat stress**. "
        "Check if tips have watery streaks — that confirms blight. "
        "Drain excess water and apply copper-based spray.",
    ),
    (
        ["spots", "lesion", "marks"],
        "Spots on rice leaves could be Leaf Blast (grey, diamond-shaped) or Brown Spot (brown, oval). "
        "Upload your field photo so I can give you the exact diagnosis! 📸",
    ),

    # ── Fertiliser ────────────────────────────────────────────────────────────
    (
        ["fertiliser", "fertilizer", "npk", "urea", "nutrient", "manure"],
        "🌾 **Fertiliser guide for rice:**\n"
        "• **Basal (before transplanting):** 30 kg N + 30 kg P + 30 kg K per hectare\n"
        "• **Tillering (25–30 days):** Top-dress 30 kg N/ha\n"
        "• **Panicle initiation (55–60 days):** Top-dress 30 kg N/ha\n"
        "• Use less N if disease is present!",
    ),
    (
        ["nitrogen", "urea"],
        "⚠️ Excess **nitrogen** promotes lush growth but increases Leaf Blast and Bacterial Blight risk. "
        "Apply N in splits — never all at once. If disease is detected, skip the next N dose.",
    ),
    (
        ["potassium", "potash"],
        "✅ **Potassium (K)** strengthens cell walls and reduces Brown Spot risk. "
        "Apply Muriate of Potash (MOP) @ 60 kg/ha as basal dose.",
    ),

    # ── Pesticide / treatment ─────────────────────────────────────────────────
    (
        ["pesticide", "spray", "fungicide", "chemical", "tricyclazole", "mancozeb", "copper"],
        "🧪 **Common sprays for rice diseases:**\n"
        "• Leaf Blast → Tricyclazole 75 WP @ 0.6 g/L\n"
        "• Brown Spot → Mancozeb 75 WP @ 2.5 g/L\n"
        "• Bacterial Blight → Copper Oxychloride 50 WP @ 3 g/L\n"
        "Always spray in early morning or evening. Wear protective gear!",
    ),

    # ── Irrigation / water ────────────────────────────────────────────────────
    (
        ["water", "irrigation", "flood", "drain", "waterlog"],
        "💧 **Water management tips:**\n"
        "• Transplanting to tillering: maintain 5 cm standing water\n"
        "• Mid-tillering: drain for 7 days (weed control)\n"
        "• Panicle initiation to flowering: 5 cm water critical\n"
        "• After flowering: Alternate Wetting & Drying (AWD) saves 30% water!",
    ),

    # ── Weather ───────────────────────────────────────────────────────────────
    (
        ["weather", "rain", "temperature", "humidity", "climate"],
        "🌤️ Weather greatly affects rice diseases:\n"
        "• High humidity (>80%) + cool nights → Blast risk ↑\n"
        "• Heavy rains → Bacterial Blight spreads via water\n"
        "• High temp (>35°C) → Heat stress, increase irrigation\n"
        "Check the Weather Advisory section for today's conditions!",
    ),

    # ── General farming ───────────────────────────────────────────────────────
    (
        ["planting", "transplant", "seedling", "sowing", "nursery"],
        "🌱 **Planting tips:**\n"
        "• Nursery: sow 25–30 kg seed/ha; treat seeds before sowing\n"
        "• Transplant at 25–30 days old seedlings\n"
        "• Spacing: 20×15 cm (2–3 seedlings per hill)\n"
        "• Avoid late planting — synchronise with your region's kharif calendar.",
    ),
    (
        ["harvest", "yield", "cutting", "maturity"],
        "🌾 **Harvest tips:**\n"
        "• Harvest when 80–85% of grains turn golden yellow\n"
        "• Grain moisture should be 20–25% at harvest\n"
        "• Avoid cutting in morning dew — grain shattering increases\n"
        "• Yield: 4–6 tonnes/ha for irrigated rice under good management.",
    ),
    (
        ["variety", "seed", "resistant"],
        "🌾 **Recommended resistant varieties:**\n"
        "• Blast-resistant: IR64, Samba Mahsuri, MTU 1010\n"
        "• Blight-resistant: Swarna Sub1, IR20, BPT 5204\n"
        "• High-yield: IR36, ADT 43, DRR Dhan 42\n"
        "Ask your local KVK (Krishi Vigyan Kendra) for region-specific advice.",
    ),
    (
        ["weed", "grass", "weed control"],
        "🌿 **Weed management:**\n"
        "• Apply pre-emergence herbicide (Butachlor) within 3 days of transplanting\n"
        "• Manual weeding at 20 and 40 days after transplanting\n"
        "• A clean field in the first 40 days prevents 30–40% yield loss.",
    ),

    # ── Help / greeting ───────────────────────────────────────────────────────
    (
        ["hello", "hi", "hey", "namaste", "good morning", "good evening"],
        "👋 Hello, Farmer! I'm your Rice Crop Assistant.\n\n"
        "I can help you with:\n"
        "🍃 Disease identification\n"
        "🌾 Fertiliser advice\n"
        "🧪 Pesticide guidance\n"
        "💧 Irrigation tips\n"
        "🌤️ Weather impact\n"
        "🌱 Planting & harvesting\n\n"
        "Just type your question in simple words!",
    ),
    (
        ["thank", "thanks", "dhanyawad", "shukriya"],
        "😊 You're welcome! Happy farming! 🌾\n"
        "Feel free to ask anything else about your rice crop.",
    ),
    (
        ["help", "what can you do", "capabilities"],
        "🤖 I can answer questions about:\n"
        "• Rice diseases (Blast, Brown Spot, Bacterial Blight)\n"
        "• Fertiliser and nutrient management\n"
        "• Pesticide application\n"
        "• Irrigation and water management\n"
        "• Seed varieties and planting\n"
        "• Weather impact on crops\n\n"
        "Type a question in simple English and I'll help!",
    ),
]

_DEFAULT_RESPONSE = (
    "🤔 I'm not sure about that. Try asking about:\n"
    "• Rice diseases (blast, brown spot, blight)\n"
    "• Fertiliser or nutrients\n"
    "• Irrigation or water management\n"
    "• Pesticide sprays\n"
    "• Planting or harvesting tips\n\n"
    "Or upload a crop photo for instant disease analysis! 📸"
)


# ── Matching engine ───────────────────────────────────────────────────────────
def _tokenise(text: str) -> str:
    """Lower-case and strip punctuation."""
    return re.sub(r"[^\w\s]", " ", text.lower())


def get_response(user_message: str) -> str:
    """
    Return the best matching chatbot response for a user message.

    Parameters
    ----------
    user_message : raw user input string

    Returns
    -------
    Markdown-formatted response string
    """
    clean = _tokenise(user_message)

    best_answer   = _DEFAULT_RESPONSE
    best_matches  = 0

    for keywords, answer in _KB:
        matches = sum(1 for kw in keywords if kw in clean)
        if matches > best_matches:
            best_matches = matches
            best_answer  = answer

    return best_answer
