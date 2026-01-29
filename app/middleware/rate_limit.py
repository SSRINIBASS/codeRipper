"""
Rate Limiting Middleware - Request rate limiting per API key.
"""

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.core.errors import RateLimitedError

settings = get_settings()


class RateLimiter:
    """Simple in-memory rate limiter using sliding window."""

    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.window_size = 60  # 1 minute in seconds
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """
        Check if request is allowed for the given key.
        
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        now = time.time()
        window_start = now - self.window_size
        
        # Clean old requests
        self.requests[key] = [
            ts for ts in self.requests[key] if ts > window_start
        ]
        
        if len(self.requests[key]) >= self.requests_per_minute:
            # Calculate retry after
            oldest = min(self.requests[key])
            retry_after = int(oldest + self.window_size - now) + 1
            return False, retry_after
        
        # Add current request
        self.requests[key].append(now)
        return True, 0


# Global rate limiter instance
rate_limiter = RateLimiter(settings.rate_limit_per_minute)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ("/health", "/ready", "/docs", "/openapi.json"):
            return await call_next(request)
        
        # Use API key or client IP as rate limit key
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            key = f"api:{api_key[:8]}"
        else:
            key = f"ip:{request.client.host if request.client else 'unknown'}"
        
        allowed, retry_after = rate_limiter.is_allowed(key)
        
        if not allowed:
            raise RateLimitedError(retry_after=retry_after)
        
        return await call_next(request)
