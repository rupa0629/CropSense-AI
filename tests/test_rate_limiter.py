from middleware.rate_limiter import RateLimiterMiddleware


async def _app(scope, receive, send):
    return None


def test_in_memory_rate_limit_enforces_threshold():
    limiter = RateLimiterMiddleware(_app, max_requests=2, window_seconds=60)
    assert limiter._is_rate_limited_in_memory("192.0.2.1") is False
    assert limiter._is_rate_limited_in_memory("192.0.2.1") is False
    assert limiter._is_rate_limited_in_memory("192.0.2.1") is True


def test_rate_limits_are_separate_per_client():
    limiter = RateLimiterMiddleware(_app, max_requests=1, window_seconds=60)
    assert limiter._is_rate_limited_in_memory("192.0.2.1") is False
    assert limiter._is_rate_limited_in_memory("192.0.2.2") is False
