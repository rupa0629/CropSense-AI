from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from config.settings import get_settings
from middleware.error_handlers import (
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from middleware.rate_limiter import RateLimiterMiddleware
from middleware.security_headers import SecurityHeadersMiddleware
from observability.logging_setup import configure_logging
from observability import monitoring
from middleware.logging_middleware import LoggingMiddleware
from routers.auth import router as auth_router
from routers.app_routes import router as app_router
from routers.health import router as health_router
from services.model_service import initialize_model_async

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)

if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await initialize_model_async()
    except Exception:
        logger.exception("Failed to initialize model service")
    try:
        from utils.auth_db import init_db
        init_db()
    except Exception:
        logger.exception("Failed to initialize DB")
    yield
    # Cleanup code can go here if needed


app = FastAPI(title=settings.service_name, version="2.0.0", lifespan=lifespan)

# Mount Prometheus metrics endpoint (protected when METRICS_TOKEN set)
metrics_app = monitoring.make_protected_metrics_app(settings.metrics_token)
app.mount("/metrics", metrics_app)

if settings.force_https:
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    SecurityHeadersMiddleware,
    force_https=settings.force_https,
)

allowed_hosts = settings.allowed_hosts_list
if allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origin_list,
    allow_credentials=False,
    allow_methods=settings.allowed_methods_list,
    allow_headers=settings.allow_headers_list,
    max_age=settings.cors_max_age,
)

app.add_middleware(
    RateLimiterMiddleware,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)

# Add request logging + metrics middleware
app.add_middleware(LoggingMiddleware)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(app_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True)
