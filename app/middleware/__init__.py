"""Middleware package - Production middleware components."""

from app.middleware.auth import require_api_key, validate_api_key
from app.middleware.correlation import (
    CORRELATION_ID_HEADER,
    CorrelationMiddleware,
    get_correlation_id,
)
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

__all__ = [
    # Correlation
    "CorrelationMiddleware",
    "get_correlation_id",
    "CORRELATION_ID_HEADER",
    # Logging
    "LoggingMiddleware",
    # Rate limiting
    "RateLimitMiddleware",
    # Auth
    "validate_api_key",
    "require_api_key",
]
