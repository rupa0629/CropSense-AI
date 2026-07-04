"""Prometheus metrics and helpers for the CropSense AI service.

Provides counters and histograms for HTTP requests and model inference.
"""
from prometheus_client import Counter, Histogram, Info, make_asgi_app
from typing import Callable


def make_protected_metrics_app(token: str | None):
    """Return an ASGI app that enforces an optional token header before delegating to the Prometheus ASGI app."""
    base_app = make_asgi_app()

    async def app(scope, receive, send):
        # Only handle HTTP
        if scope.get("type") != "http":
            await base_app(scope, receive, send)
            return

        if token:
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            provided = headers.get("x-metrics-token")
            if provided != token:
                from starlette.responses import Response

                resp = Response(status_code=401, content=b"Unauthorized")
                await resp(scope, receive, send)
                return

        await base_app(scope, receive, send)

    return app

# HTTP request metrics
REQUEST_COUNT = Counter(
    "cropsense_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "cropsense_request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)
REQUEST_EXCEPTIONS = Counter(
    "cropsense_request_exceptions_total",
    "Total number of unhandled exceptions during requests",
)

# Model prediction metrics
PREDICTIONS = Counter(
    "cropsense_predictions_total",
    "Total number of model predictions",
    ["method"],
)
INFERENCE_LATENCY = Histogram(
    "cropsense_inference_latency_seconds",
    "Model inference latency in seconds",
    ["method"],
)
PREDICTION_CLASSES = Counter(
    "cropsense_prediction_classes_total",
    "Predicted classes used to detect production distribution drift",
    ["disease"],
)
PREDICTION_CONFIDENCE = Histogram(
    "cropsense_prediction_confidence",
    "Distribution of top prediction confidence",
    buckets=(0.0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0),
)
UNCERTAIN_PREDICTIONS = Counter(
    "cropsense_uncertain_predictions_total",
    "Predictions that require image retake or human review",
)
MODEL_INFO = Info(
    "cropsense_model",
    "Loaded production model identity",
)

# ASGI app that serves /metrics (Prometheus exposition)
metrics_app = make_asgi_app()

__all__ = [
    "REQUEST_COUNT",
    "REQUEST_LATENCY",
    "REQUEST_EXCEPTIONS",
    "PREDICTIONS",
    "INFERENCE_LATENCY",
    "PREDICTION_CLASSES",
    "PREDICTION_CONFIDENCE",
    "UNCERTAIN_PREDICTIONS",
    "MODEL_INFO",
    "metrics_app",
]
