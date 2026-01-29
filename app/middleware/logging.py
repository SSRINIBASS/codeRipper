"""
Request Logging Middleware - Structured request/response logging.
"""

import time
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.correlation import get_correlation_id

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request/response logging."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        start_time = time.perf_counter()
        
        # Log request
        await logger.ainfo(
            "request_started",
            correlation_id=get_correlation_id(),
            method=request.method,
            path=request.url.path,
            query=str(request.query_params),
            client_host=request.client.host if request.client else None,
        )
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log response
            await logger.ainfo(
                "request_completed",
                correlation_id=get_correlation_id(),
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
            
            return response
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            await logger.aerror(
                "request_failed",
                correlation_id=get_correlation_id(),
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=round(duration_ms, 2),
            )
            raise
