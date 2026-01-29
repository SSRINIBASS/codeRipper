"""
Correlation ID Middleware - Request tracing across async operations.
"""

import contextvars
from typing import Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable for correlation ID
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)

CORRELATION_ID_HEADER = "X-Correlation-ID"


def get_correlation_id() -> str:
    """Get the current correlation ID."""
    return correlation_id_ctx.get()


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID to requests for tracing."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Get correlation ID from header or generate new one
        correlation_id = request.headers.get(
            CORRELATION_ID_HEADER, str(uuid4())[:16]
        )
        
        # Set in context
        token = correlation_id_ctx.set(correlation_id)
        
        try:
            response = await call_next(request)
            # Add to response headers
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            return response
        finally:
            correlation_id_ctx.reset(token)
