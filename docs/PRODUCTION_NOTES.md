Production changes applied and notes

- Healthcheck: container healthcheck updated to query `/health/ready`. Orchestrators should only mark the service healthy once the TF model is warmed.
- Single-worker runtime: Dockerfile now runs Uvicorn without multiple workers to avoid multiple TensorFlow processes inside one container. For scale, run multiple replicas (or use Gunicorn with careful process management).
- Metrics protection: `/metrics` is now served via a wrapper that requires `X-Metrics-Token` when `METRICS_TOKEN` is set in the environment; set this in your `.env` for production scraping.
- TensorFlow compatibility check: `scripts/check_tensorflow.py` runs during the Docker build to verify `import tensorflow` and will fail the build if TF cannot be imported.

Recommended next steps

1. Add `METRICS_TOKEN` to your production `.env` and configure Prometheus to include the `X-Metrics-Token` header when scraping.
2. Run the full test suite and the frontend build locally or in CI before deploying.
3. Consider a logging sink (structured JSON) and limit public exposure of `/metrics` via network rules.
4. If GPU inference is required, build a GPU-compatible image (use NVIDIA base images) and set `MODEL_USE_GPU=true` and `MODEL_GPU_MEMORY_LIMIT_MB` appropriately.
