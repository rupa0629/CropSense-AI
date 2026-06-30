"""
disease_model.py
----------------
Rice disease detection engine.

Priority order:
1) Custom trained model file: models/rice_disease_model.h5
2) MobileNetV2 ImageNet heuristic mapping
3) Pure color-statistics heuristic fallback
"""

from __future__ import annotations

import os
import threading
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_TF_AVAILABLE = False
_tf: Any = None
_MobileNetV2: Any = None
_preprocess_input: Any = None
_decode_predictions: Any = None
_eff_preprocess_input: Any = None
_img_to_array: Any = None

_model_lock = threading.Lock()
_backbone = None
_custom_model = None

DISEASE_CLASSES = ["Leaf Blast", "Brown Spot", "Bacterial Blight", "Healthy"]
_CONFIDENCE_THRESHOLD = 0.30


def _ensure_tf() -> bool:
    global _TF_AVAILABLE, _tf, _MobileNetV2, _preprocess_input, _decode_predictions, _eff_preprocess_input, _img_to_array

    if _TF_AVAILABLE:
        return True

    try:
        import tensorflow as tf
        from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input, decode_predictions
        from tensorflow.keras.applications.efficientnet import preprocess_input as eff_preprocess_input
        from tensorflow.keras.preprocessing.image import img_to_array

        _tf = tf
        _MobileNetV2 = MobileNetV2
        _preprocess_input = preprocess_input
        _decode_predictions = decode_predictions
        _eff_preprocess_input = eff_preprocess_input
        _img_to_array = img_to_array
        _TF_AVAILABLE = True
        return True
    except ImportError as exc:
        logger.warning("TensorFlow is unavailable: %s", exc)
    except Exception as exc:
        logger.warning("Failed to initialize TensorFlow runtime: %s", exc)

    _TF_AVAILABLE = False
    return False


def configure_tensorflow(
    use_gpu: bool = False,
    inter_threads: int = 1,
    intra_threads: int = 2,
    gpu_memory_limit_mb: Optional[int] = None,
) -> None:
    if not use_gpu:
        os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

    if not _ensure_tf():
        return

    try:
        _tf.get_logger().setLevel("ERROR")
        _tf.config.threading.set_inter_op_parallelism_threads(inter_threads)
        _tf.config.threading.set_intra_op_parallelism_threads(intra_threads)
    except Exception as exc:
        logger.warning("Unable to tune TensorFlow threading: %s", exc)

    if use_gpu:
        try:
            gpus = _tf.config.list_physical_devices("GPU")
            if not gpus:
                logger.warning("No GPU devices detected; falling back to CPU.")
                return

            for gpu in gpus:
                _tf.config.experimental.set_memory_growth(gpu, True)

            if gpu_memory_limit_mb and gpu_memory_limit_mb > 0:
                _tf.config.set_logical_device_configuration(
                    gpus[0],
                    [_tf.config.LogicalDeviceConfiguration(memory_limit=gpu_memory_limit_mb)],
                )
        except Exception as exc:
            logger.warning("GPU memory configuration failed: %s", exc)


def _custom_model_path() -> Path:
    configured = Path(settings.model_path)
    if configured.is_absolute():
        return configured
    return Path(__file__).resolve().parent.parent / configured


def has_custom_model() -> bool:
    return _custom_model is not None


def has_backbone() -> bool:
    return _backbone is not None


def initialize_models() -> None:
    if not _ensure_tf():
        return

    if _custom_model_path().exists():
        _get_custom_model()
    else:
        _get_backbone()


def _load_custom_model() -> Optional[Any]:
    if not _ensure_tf():
        return None

    try:
        return _tf.keras.models.load_model(_custom_model_path(), compile=False)
    except Exception as exc:
        logger.warning("Failed to load custom model: %s", exc)
        return None


def _get_custom_model() -> Optional[Any]:
    global _custom_model
    if _custom_model is not None:
        return _custom_model

    with _model_lock:
        if _custom_model is not None:
            return _custom_model

        if not _custom_model_path().exists():
            return None

        _custom_model = _load_custom_model()
        return _custom_model


def _get_backbone() -> Optional[Any]:
    global _backbone
    if _backbone is not None:
        return _backbone

    if not _ensure_tf():
        return None

    with _model_lock:
        if _backbone is not None:
            return _backbone

        try:
            _backbone = _MobileNetV2(weights="imagenet", include_top=True)
        except Exception as exc:
            logger.warning("Failed to load MobileNetV2 backbone: %s", exc)
            _backbone = None

    return _backbone


def _softmax_safe(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    x = x - np.max(x)
    e = np.exp(x)
    return e / (np.sum(e) + 1e-8)


def _prepare_rgb(image: Image.Image) -> Image.Image:
    return image.convert("RGB").resize((224, 224))


def _prepare_model_input(image_rgb: Image.Image) -> np.ndarray:
    arr = _img_to_array(image_rgb)
    return np.expand_dims(arr.astype("float32"), axis=0)


def _format_prediction(probs: np.ndarray, method: str) -> dict:
    probs = np.asarray(probs, dtype=float)
    probs = np.nan_to_num(probs, nan=0.0, posinf=1.0, neginf=0.0)
    if probs.sum() == 0.0:
        probs = np.ones_like(probs) / float(len(probs))
    else:
        probs = probs / probs.sum()
    idx = int(np.argmax(probs))
    sorted_probs = np.sort(probs)[::-1]
    top1 = float(sorted_probs[0])
    top2 = float(sorted_probs[1]) if len(sorted_probs) > 1 else 0.0
    margin = top1 - top2
    needs_retake = bool(top1 < 0.60 or margin < 0.12)
    reason = ""
    if top1 < 0.60 and margin < 0.12:
        reason = "Low confidence and very close class probabilities."
    elif top1 < 0.60:
        reason = "Low confidence prediction."
    elif margin < 0.12:
        reason = "Prediction is ambiguous between top classes."

    return {
        "disease": DISEASE_CLASSES[idx],
        "confidence": float(probs[idx]),
        "all_probs": {c: float(p) for c, p in zip(DISEASE_CLASSES, probs)},
        "method": method,
        "margin": margin,
        "needs_retake": needs_retake,
        "uncertainty_reason": reason,
    }


def _is_confident(probs: np.ndarray) -> bool:
    sorted_probs = np.sort(probs)[::-1]
    return float(sorted_probs[0]) >= 0.72 and float(sorted_probs[0] - sorted_probs[1]) >= 0.12


def _predict_with_custom_model(image_rgb: Image.Image) -> Optional[dict]:
    model = _get_custom_model()
    if model is None:
        return None

    try:
        input_array = _prepare_model_input(image_rgb)
        preds = model.predict(_eff_preprocess_input(input_array), verbose=0)
        preds = np.squeeze(preds)
        if preds.ndim != 1 or len(preds) != len(DISEASE_CLASSES):
            return None

        probs = _softmax_safe(preds)
        if _is_confident(probs):
            return _format_prediction(probs, "custom_model")

        variants = [
            image_rgb,
            image_rgb.transpose(Image.FLIP_LEFT_RIGHT),
            image_rgb.transpose(Image.FLIP_TOP_BOTTOM),
        ]

        tta_probs = [probs]
        for variant in variants[1:]:
            arr = _prepare_model_input(variant)
            preds = model.predict(_eff_preprocess_input(arr), verbose=0)
            preds = np.squeeze(preds)
            if preds.ndim != 1 or len(preds) != len(DISEASE_CLASSES):
                continue
            tta_probs.append(_softmax_safe(preds))

        probs = np.mean(np.stack(tta_probs, axis=0), axis=0)
        return _format_prediction(probs, "custom_model")
    except Exception as exc:
        logger.warning("Custom model prediction failed: %s", exc)
        return None


def _predict_with_backbone(image_rgb: Image.Image) -> Optional[np.ndarray]:
    backbone = _get_backbone()
    if backbone is None:
        return None

    try:
        arr = _prepare_model_input(image_rgb)
        arr = _preprocess_input(arr)
        preds = backbone.predict(arr, verbose=0)
        top5 = _decode_predictions(preds, top=5)[0]
        confidence = float(top5[0][2])

        # WARNING: This ImageNet class mapping is a heuristic fallback and is NOT scientifically grounded.
        # It maps unrelated ImageNet classes to rice diseases based on visual similarity assumptions.
        # This should only be used when the custom trained model is unavailable.
        # For production use, train a proper rice disease detection model on actual rice disease datasets.
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
            probs = np.full(len(DISEASE_CLASSES), (1 - confidence) / 3, dtype=np.float32)
            probs[idx] = confidence
            return probs
    except Exception as exc:
        logger.warning("Backbone prediction failed: %s", exc)

    return None


def _heuristic_predict(image: Image.Image) -> tuple[str, float, np.ndarray]:
    # WARNING: This heuristic uses fixed RGB color ratios that are NOT lighting-condition invariant.
    # Different lighting conditions (sunlight, shade, indoor lighting) will produce different RGB ratios,
    # leading to unreliable predictions. This is a last-resort fallback when no model is available.
    # For accurate results, always use the trained model or implement proper color normalization.
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
    denom = float(scores.sum())
    if denom <= 0.0:
        probs = np.ones_like(scores) / float(len(scores))
    else:
        probs = scores / denom
    probs = np.nan_to_num(probs, nan=1.0 / len(scores), posinf=1.0, neginf=0.0)
    if probs.sum() == 0.0:
        probs = np.ones_like(scores) / float(len(scores))
    idx = int(np.argmax(probs))
    return DISEASE_CLASSES[idx], float(probs[idx]), probs


def predict_disease(image: Image.Image) -> dict:
    image_rgb = _prepare_rgb(image)
    custom_result = _predict_with_custom_model(image_rgb)
    if custom_result is not None:
        return custom_result

    # Check if heuristic fallbacks are allowed
    if not settings.allow_heuristic_fallbacks:
        logger.error("Custom model not available and heuristic fallbacks are disabled. Cannot make prediction.")
        raise RuntimeError(
            "Trained model not available and heuristic fallbacks are disabled. "
            "Ensure the model file exists at the configured path or set ALLOW_HEURISTIC_FALLBACKS=true "
            "(not recommended for production)."
        )

    probs = _predict_with_backbone(image_rgb)
    if probs is None:
        _, _, probs = _heuristic_predict(image_rgb)
        method = "heuristic"
    else:
        method = "mobilenetv2"

    return {**_format_prediction(probs, method)}
