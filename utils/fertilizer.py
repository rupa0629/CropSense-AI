"""
fertilizer.py
-------------
Rule-based fertiliser and treatment recommendation engine.

For each disease class a structured recommendation is returned covering:
  • immediate_action  – what to do right now
  • fertiliser        – nutrient management advice
  • pesticide         – chemical treatment guidance
  • cultural          – field management practices
  • prevention        – long-term prevention tips
"""

# ── Knowledge base ────────────────────────────────────────────────────────────
_RECOMMENDATIONS: dict[str, dict] = {
    "Leaf Blast": {
        "emoji": "🍃",
        "colour": "#FF7043",
        "immediate_action": "Remove and destroy infected leaves immediately to reduce spore spread.",
        "fertiliser": [
            "⚠️  Reduce nitrogen (N) fertiliser — excess N promotes blast.",
            "✅  Increase silicon (Si) fertiliser (e.g., calcium silicate) to strengthen cell walls.",
            "✅  Maintain balanced K (potassium) to improve plant immunity.",
        ],
        "pesticide": [
            "🧪  Apply Tricyclazole 75 WP @ 0.6 g/L water as foliar spray.",
            "🧪  Alternatively: Carbendazim 50 WP @ 1 g/L water.",
            "🕐  Spray in early morning or evening; repeat after 10–14 days if needed.",
        ],
        "cultural": [
            "🌊  Maintain 5 cm flood water in fields to suppress blast.",
            "🌱  Use blast-resistant rice varieties in future planting.",
            "🚫  Avoid planting in low-lying, mist-prone areas.",
        ],
        "prevention": [
            "🌾  Treat seeds with Carbendazim before sowing.",
            "📅  Avoid late planting — synchronise planting with neighbours.",
        ],
    },

    "Brown Spot": {
        "emoji": "🟤",
        "colour": "#795548",
        "immediate_action": "Scout field for nutrient deficiency signs; brown spot is often linked to poor soil nutrition.",
        "fertiliser": [
            "✅  Apply potassium (K) fertiliser — brown spot is aggravated by K deficiency.",
            "✅  Correct manganese (Mn) and iron (Fe) levels through soil testing.",
            "⚠️  Avoid excess nitrogen which may worsen lesion spread.",
        ],
        "pesticide": [
            "🧪  Apply Mancozeb 75 WP @ 2.5 g/L water as foliar spray.",
            "🧪  Alternatively: Iprodione 50 WP @ 1.5 g/L water.",
            "🕐  Spray at booting stage; repeat every 14 days.",
        ],
        "cultural": [
            "💧  Maintain adequate irrigation — water stress worsens brown spot.",
            "🌱  Use certified, treated seeds from disease-free sources.",
            "🌿  Remove crop debris after harvest to reduce inoculum.",
        ],
        "prevention": [
            "🧪  Seed treatment with Captan 50 WP @ 2 g/kg seed.",
            "📊  Conduct soil health tests at the start of each season.",
        ],
    },

    "Bacterial Blight": {
        "emoji": "🦠",
        "colour": "#F57F17",
        "immediate_action": "Do NOT enter the field after heavy rain — you will spread bacteria. Drain flood water if possible.",
        "fertiliser": [
            "⚠️  Drastically reduce nitrogen fertiliser — N accelerates BB spread.",
            "✅  Apply phosphorus (P) and potassium (K) to boost plant defence.",
            "🚫  Stop applying any fertiliser until disease is under control.",
        ],
        "pesticide": [
            "🧪  Apply Copper Oxychloride 50 WP @ 3 g/L water as foliar spray.",
            "🧪  Alternatively: Streptomycin sulphate + Tetracycline @ 1 g/10 L water.",
            "🕐  Apply 3–4 times at 10-day intervals; do not spray during flowering.",
        ],
        "cultural": [
            "💧  Improve drainage — standing water spreads the bacteria rapidly.",
            "✂️  Avoid deep cuts / wounds during weeding to prevent entry points.",
            "🌱  Plant resistant varieties (e.g., IR20, Swarna Sub1).",
        ],
        "prevention": [
            "🧪  Seed treatment: soak in Streptomycin @ 0.025% for 8 hours.",
            "🚜  Disinfect farm tools with bleach solution between uses.",
        ],
    },

    "Healthy": {
        "emoji": "✅",
        "colour": "#4CAF50",
        "immediate_action": "Crop looks healthy — maintain current practices.",
        "fertiliser": [
            "✅  Continue balanced NPK schedule as per crop growth stage.",
            "🌾  At tillering: 60 kg N/ha, 30 kg P/ha, 30 kg K/ha.",
            "🌾  At panicle initiation: top-dress with 30 kg N/ha.",
        ],
        "pesticide": [
            "🚫  No pesticide needed currently.",
            "👀  Monitor weekly for early pest/disease signs.",
        ],
        "cultural": [
            "💧  Maintain intermittent irrigation (alternate wetting and drying).",
            "🌿  Keep field weed-free especially in the first 30 days.",
        ],
        "prevention": [
            "📅  Schedule next scouting in 5–7 days.",
            "📊  Keep field records for better season planning.",
        ],
    },
}


# ── Public API ────────────────────────────────────────────────────────────────
def get_recommendation(disease: str, severity: str = "") -> dict:
    """
    Return fertiliser and treatment recommendations for a given disease.

    Parameters
    ----------
    disease  : one of DISEASE_CLASSES
    severity : "Mild" | "Moderate" | "Severe" | "" (optional context)

    Returns
    -------
    Full recommendation dict including urgency note
    """
    rec = _RECOMMENDATIONS.get(disease, _RECOMMENDATIONS["Healthy"]).copy()

    # Add severity-based urgency note
    urgency_map = {
        "Mild":     "🟡 Urgency: LOW — monitor and apply preventive measures.",
        "Moderate": "🟠 Urgency: MEDIUM — begin treatment within 48 hours.",
        "Severe":   "🔴 Urgency: HIGH — apply treatment immediately to prevent yield loss.",
        "N/A":      "✅ No disease detected — routine management is sufficient.",
    }
    rec["urgency"] = urgency_map.get(severity, "")
    rec["disease"] = disease
    return rec
