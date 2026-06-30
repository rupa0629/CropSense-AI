from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Redis client (initialized when needed)
_redis_client = None


def _get_redis_client():
    """Get or create Redis client for distributed rate limiting."""
    global _redis_client
    if _redis_client is None and settings.redis_use_rate_limiting:
        try:
            import redis
            _redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=True,
            )
            _redis_client.ping()
            logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Falling back to in-memory rate limiting.")
            _redis_client = None
    return _redis_client


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, max_requests: int, window_seconds: int) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path.startswith("/health"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        if self._is_rate_limited(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after_seconds": self.window_seconds,
                },
            )

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, client_ip: str) -> bool:
        """Check if client IP is rate limited using Redis or in-memory fallback."""
        redis_client = _get_redis_client()
        
        if redis_client:
            return self._is_rate_limited_redis(client_ip, redis_client)
        else:
            return self._is_rate_limited_in_memory(client_ip)

    def _is_rate_limited_redis(self, client_ip: str, redis_client) -> bool:
        """Check rate limit using Redis (supports distributed deployments)."""
        key = f"rate_limit:{client_ip}"
        try:
            pipe = redis_client.pipeline()
            now = time.time()
            window_start = now - self.window_seconds
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            # Count current requests in window
            pipe.zcard(key)
            # Add current request
            pipe.zadd(key, {str(now): now})
            # Set expiration
            pipe.expire(key, self.window_seconds)
            
            results = pipe.execute()
            current_count = results[1]
            
            return current_count >= self.max_requests
        except Exception as e:
            logger.error(f"Redis rate limiting failed for {client_ip}: {e}. Falling back to in-memory.")
            return self._is_rate_limited_in_memory(client_ip)

    def _is_rate_limited_in_memory(self, client_ip: str) -> bool:
        """Check rate limit using in-memory storage (fallback for development)."""
        # NOTE: This in-memory fallback has limitations:
        # - Won't work with multiple workers/processes (e.g., gunicorn -w 4)
        # - Won't work with horizontal scaling across multiple containers
        # - Rate limit state is lost on container restarts
        # For production, enable Redis by setting REDIS_USE_RATE_LIMITING=true in .env
        now = time.time()
        with self._lock:
            history = self._requests[client_ip]
            while history and now - history[0] > self.window_seconds:
                history.popleft()
            history.append(now)
            return len(history) > self.max_requests
