"""
disease_model.py
----------------
Rice disease detection engine.

Priority order:
1) Custom trained model file: models/rice_disease_model.h5
2) MobileNetV2 ImageNet heuristic mapping
3) Pure color-statistics heuristic fallback
"""

import numpy as np
from pathlib import Path
from PIL import Image

try:
    import tensorflow as tf
    from tensorflow.keras.applications.mobilenet_v2 import (
        MobileNetV2,
        preprocess_input,
        decode_predictions,
    )
    from tensorflow.keras.preprocessing.image import img_to_array

    _TF_AVAILABLE = True
except ImportError:
    _TF_AVAILABLE = False

DISEASE_CLASSES = ["Leaf Blast", "Brown Spot", "Bacterial Blight", "Healthy"]
_CONFIDENCE_THRESHOLD = 0.30

_backbone = None
_custom_model = None


def _custom_model_path() -> Path:
    return Path(__file__).resolve().parent / "rice_disease_model.h5"


def _get_custom_model():
    global _custom_model
    if not _TF_AVAILABLE:
        return None

    if _custom_model is None:
        model_path = _custom_model_path()
        if model_path.exists():
            try:
                _custom_model = tf.keras.models.load_model(model_path)
            except Exception:
                _custom_model = None
    return _custom_model


def _get_backbone():
    global _backbone
    if _backbone is None and _TF_AVAILABLE:
        _backbone = MobileNetV2(weights="imagenet", include_top=True)
    return _backbone


def _heuristic_predict(image: Image.Image) -> tuple[str, float, np.ndarray]:
    img_arr = np.array(image.convert("RGB")).astype(float)
    r, g, b = img_arr[:, :, 0].mean(), img_arr[:, :, 1].mean(), img_arr[:, :, 2].mean()
    total = r + g + b + 1e-6
    rn, gn, bn = r / total, g / total, b / total

    scores = np.array(
        [
            1.0 - abs(rn - 0.35) - abs(gn - 0.32) - abs(bn - 0.33),
            1.0 - abs(rn - 0.45) - abs(gn - 0.35) - abs(bn - 0.20),
            1.0 - abs(rn - 0.42) - abs(gn - 0.42) - abs(bn - 0.16),
            1.0 - abs(rn - 0.28) - abs(gn - 0.48) - abs(bn - 0.24),
        ]
    )

    scores = np.clip(scores, 0, 1)
    probs = scores / scores.sum()
    idx = int(np.argmax(probs))
    return DISEASE_CLASSES[idx], float(probs[idx]), probs


def _predict_with_custom_model(image_rgb: Image.Image):
    model = _get_custom_model()
    if model is None:
        return None

    try:
        arr = img_to_array(image_rgb)
        arr = np.expand_dims(arr, axis=0).astype("float32") / 255.0
        preds = model.predict(arr, verbose=0)
        preds = np.squeeze(preds)

        if preds.ndim != 1 or len(preds) != len(DISEASE_CLASSES):
            return None

        probs = preds / (preds.sum() + 1e-8)
        idx = int(np.argmax(probs))
        return {
            "disease": DISEASE_CLASSES[idx],
            "confidence": float(probs[idx]),
            "all_probs": {c: float(p) for c, p in zip(DISEASE_CLASSES, probs)},
            "method": "custom_model",
        }
    except Exception:
        return None


def predict_disease(image: Image.Image) -> dict:
    image_rgb = image.convert("RGB").resize((224, 224))

    custom_result = _predict_with_custom_model(image_rgb)
    if custom_result is not None:
        return custom_result

    backbone = _get_backbone()
    probs = None
    method = "heuristic"

    if backbone is not None:
        try:
            arr = img_to_array(image_rgb)
            arr = preprocess_input(np.expand_dims(arr, axis=0))
            preds = backbone.predict(arr, verbose=0)
            top5 = decode_predictions(preds, top=5)[0]
            confidence = float(top5[0][2])

            class_map = {
                "corn": "Leaf Blast",
                "ear": "Leaf Blast",
                "broom": "Leaf Blast",
                "mushroom": "Brown Spot",
                "porcini": "Brown Spot",
                "earthstar": "Brown Spot",
                "banana": "Bacterial Blight",
                "lemon": "Bacterial Blight",
                "green_mamba": "Healthy",
                "grass": "Healthy",
                "hay": "Healthy",
            }

            best_label = top5[0][1].lower()
            mapped = class_map.get(best_label)

            if mapped and confidence >= _CONFIDENCE_THRESHOLD:
                idx = DISEASE_CLASSES.index(mapped)
                probs = np.full(len(DISEASE_CLASSES), (1 - confidence) / 3)
                probs[idx] = confidence
                method = "mobilenetv2"
        except Exception:
            pass

    if probs is None:
        _, _, probs = _heuristic_predict(image_rgb)
        method = "heuristic"

    idx = int(np.argmax(probs))
    return {
        "disease": DISEASE_CLASSES[idx],
        "confidence": float(probs[idx]),
        "all_probs": {c: float(p) for c, p in zip(DISEASE_CLASSES, probs)},
        "method": method,
    }
