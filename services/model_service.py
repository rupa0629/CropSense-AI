"""Model service: centralize model lifecycle, inference, and runtime tuning.

This service loads TensorFlow models once, exposes async prediction, and
centralizes GPU/CPU runtime configuration for production deployment.
"""
from __future__ import annotations

import logging
import threading
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
        logger.info(
            "Model service initialized (custom=%s, backbone=%s, gpu=%s)",
            disease_model.has_custom_model(),
            disease_model.has_backbone(),
            settings.model_use_gpu,
        )


def is_initialized() -> bool:
    """Return whether the model service completed initialization."""
    return _initialized


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

        monitoring.PREDICTIONS.labels(method="sync").inc()
        monitoring.INFERENCE_LATENCY.labels(method="sync").observe(elapsed)
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

        monitoring.PREDICTIONS.labels(method="async").inc()
        monitoring.INFERENCE_LATENCY.labels(method="async").observe(elapsed)
    except Exception:
        logger.debug("Monitoring not available for async prediction")

    logger.info("Prediction complete method=async elapsed=%.3fs disease=%s confidence=%.3f", elapsed, result.get("disease"), result.get("confidence", 0.0))
    return result
