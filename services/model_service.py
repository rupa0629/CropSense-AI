"""Model service: centralize model lifecycle, inference, and runtime tuning.

This service loads TensorFlow models once, exposes async prediction, and
centralizes GPU/CPU runtime configuration for production deployment.
"""
from __future__ import annotations

import logging
import hashlib
import threading
from pathlib import Path
from PIL import Image
import time
from starlette.concurrency import run_in_threadpool

from config.settings import get_settings
from models import disease_model

logger = logging.getLogger(__name__)
settings = get_settings()

_model_init_lock = threading.Lock()
_initialized = False


def initialize_model() -> None:
    global _initialized
    with _model_init_lock:
        if _initialized:
            return

        disease_model.configure_tensorflow(
            use_gpu=settings.model_use_gpu,
            inter_threads=settings.model_cpu_inter_threads,
            intra_threads=settings.model_cpu_intra_threads,
            gpu_memory_limit_mb=settings.model_gpu_memory_limit_mb,
        )
        disease_model.initialize_models()
        if not settings.allow_heuristic_fallbacks and not disease_model.has_custom_model():
            raise RuntimeError(f"Trained model could not be loaded from {settings.model_path}")
        _initialized = True
        model_path = Path(settings.model_path)
        if not model_path.is_absolute():
            model_path = Path(__file__).resolve().parent.parent / model_path
        model_sha256 = "unavailable"
        if model_path.is_file():
            digest = hashlib.sha256()
            with model_path.open("rb") as model_file:
                for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
                    digest.update(chunk)
            model_sha256 = digest.hexdigest()
        try:
            from observability import monitoring

            monitoring.MODEL_INFO.info(
                {
                    "sha256": model_sha256,
                    "filename": model_path.name,
                    "custom_model": str(disease_model.has_custom_model()).lower(),
                }
            )
        except Exception:
            logger.debug("Unable to publish model identity metric")
        logger.info(
            "Model service initialized (custom=%s, backbone=%s, gpu=%s, sha256=%s)",
            disease_model.has_custom_model(),
            disease_model.has_backbone(),
            settings.model_use_gpu,
            model_sha256,
        )


def is_initialized() -> bool:
    """Return whether the model service completed initialization."""
    return _initialized


def _record_prediction_metrics(result: dict, method: str, elapsed: float) -> None:
    from observability import monitoring

    confidence = max(0.0, min(1.0, float(result.get("confidence", 0.0))))
    disease = str(result.get("disease", "unknown"))
    monitoring.PREDICTIONS.labels(method=method).inc()
    monitoring.INFERENCE_LATENCY.labels(method=method).observe(elapsed)
    monitoring.PREDICTION_CLASSES.labels(disease=disease).inc()
    monitoring.PREDICTION_CONFIDENCE.observe(confidence)
    if result.get("needs_retake"):
        monitoring.UNCERTAIN_PREDICTIONS.inc()


async def initialize_model_async() -> None:
    await run_in_threadpool(initialize_model)


def predict_disease(image: Image.Image) -> dict:
    if not _initialized:
        initialize_model()
    start = time.time()
    result = disease_model.predict_disease(image)
    elapsed = time.time() - start
    # logging + metrics
    try:
        from observability import monitoring

        _record_prediction_metrics(result, "sync", elapsed)
    except Exception:
        logger.debug("Monitoring not available for prediction")

    logger.info("Prediction complete method=sync elapsed=%.3fs disease=%s confidence=%.3f", elapsed, result.get("disease"), result.get("confidence", 0.0))
    return result


async def predict_disease_async(image: Image.Image) -> dict:
    if not _initialized:
        await initialize_model_async()
    start = time.time()
    result = await run_in_threadpool(disease_model.predict_disease, image)
    elapsed = time.time() - start
    try:
        from observability import monitoring

        _record_prediction_metrics(result, "async", elapsed)
    except Exception:
        logger.debug("Monitoring not available for async prediction")

    logger.info("Prediction complete method=async elapsed=%.3fs disease=%s confidence=%.3f", elapsed, result.get("disease"), result.get("confidence", 0.0))
    return result
