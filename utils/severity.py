"""
severity.py
-----------
Estimates disease severity from model confidence and basic image analysis.

Logic
-----
  Confidence < 0.50  → Mild      (early stage, uncertain)
  Confidence < 0.75  → Moderate  (progressing)
  Confidence ≥ 0.75  → Severe    (advanced infection)

An additional pixel-analysis step checks the proportion of
"anomalous" (non-green) pixels in the image as a cross-check.
"""

import numpy as np
from PIL import Image

# ── Thresholds ────────────────────────────────────────────────────────────────
_MILD_MAX    = 0.50
_MODERATE_MAX= 0.75

# Severity metadata
SEVERITY_INFO = {
    "Mild": {
        "emoji": "🟡",
        "colour": "#FFC107",
        "advice": "Early detection – monitor closely every 3 days.",
    },
    "Moderate": {
        "emoji": "🟠",
        "colour": "#FF9800",
        "advice": "Visible lesions spreading – begin treatment this week.",
    },
    "Severe": {
        "emoji": "🔴",
        "colour": "#F44336",
        "advice": "Heavy infection – immediate treatment required to save yield.",
    },
}


def _anomalous_pixel_ratio(image: Image.Image) -> float:
    """
    Fraction of pixels that are NOT healthy green.
    Healthy green: G channel dominant AND G > 80.
    """
    arr = np.array(image.convert("RGB"))
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    green_mask  = (g > r) & (g > b) & (g > 80)
    total_px    = arr.shape[0] * arr.shape[1]
    anomalous   = total_px - int(green_mask.sum())
    return anomalous / total_px


def classify_severity(disease: str, confidence: float, image: Image.Image) -> dict:
    """
    Classify severity of the detected disease.

    Parameters
    ----------
    disease    : predicted disease label
    confidence : model confidence [0, 1]
    image      : original PIL Image for pixel analysis

    Returns
    -------
    dict with keys: level, emoji, colour, advice, pixel_ratio
    """
    # Healthy crops always reported as N/A
    if disease == "Healthy":
        return {
            "level":       "N/A",
            "emoji":       "✅",
            "colour":      "#4CAF50",
            "advice":      "Crop appears healthy. Continue routine care.",
            "pixel_ratio": 0.0,
        }

    # Image-based cross-check
    pixel_ratio = _anomalous_pixel_ratio(image.resize((128, 128)))

    # Weighted score: 60 % model confidence + 40 % pixel ratio
    combined_score = 0.6 * confidence + 0.4 * pixel_ratio

    if combined_score < _MILD_MAX:
        level = "Mild"
    elif combined_score < _MODERATE_MAX:
        level = "Moderate"
    else:
        level = "Severe"

    info = SEVERITY_INFO[level]
    return {
        "level":       level,
        "emoji":       info["emoji"],
        "colour":      info["colour"],
        "advice":      info["advice"],
        "pixel_ratio": round(pixel_ratio * 100, 1),  # as percentage
    }
