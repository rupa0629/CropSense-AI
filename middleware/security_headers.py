from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, force_https: bool = False) -> None:
        super().__init__(app)
        self.force_https = force_https

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["x-frame-options"] = "DENY"
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["referrer-policy"] = "same-origin"
        if self.force_https:
            response.headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
        return response
