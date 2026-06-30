from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time
import logging

from observability import monitoring

logger = logging.getLogger("cropsense.middleware.logging")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        method = request.method
        path = request.url.path
        start = time.time()
        try:
            response = await call_next(request)
            status = getattr(response, "status_code", 200)
            return response
        except Exception:
            status = 500
            monitoring.REQUEST_EXCEPTIONS.inc()
            logger.exception("Unhandled exception processing request %s %s", method, path)
            raise
        finally:
            elapsed = time.time() - start
            try:
                monitoring.REQUEST_COUNT.labels(method=method, endpoint=path, status=str(status)).inc()
                monitoring.REQUEST_LATENCY.labels(method=method, endpoint=path).observe(elapsed)
            except Exception:
                logger.debug("Failed to record metrics for %s %s", method, path)

            logger.info("%s %s %s %.3fs", method, path, status, elapsed)
