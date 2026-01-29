"""
Authentication Middleware - API key and JWT validation.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token, verify_api_key
from app.database import get_db
from app.models import APIKey

settings = get_settings()

# API Key header security scheme
api_key_header = APIKeyHeader(
    name=settings.api_key_header,
    auto_error=False,
)


async def validate_api_key(
    api_key: Annotated[str | None, Security(api_key_header)],
    db: AsyncSession = Depends(get_db),
) -> APIKey | None:
    """
    Validate API key from request header.
    
    In development mode, no API key is required.
    In production, valid API key is mandatory.
    """
    # Allow no auth in development
    if settings.app_env == "development" and not api_key:
        return None
    
    if not api_key:
        raise UnauthorizedError("API key required")
    
    # Extract prefix for lookup
    key_prefix = api_key[:8] if len(api_key) >= 8 else api_key
    
    # Look up API key by prefix
    result = await db.execute(
        select(APIKey).where(APIKey.key_prefix == key_prefix)
    )
    db_key = result.scalar_one_or_none()
    
    if not db_key:
        raise UnauthorizedError("Invalid API key")
    
    # Verify the full key
    if not verify_api_key(api_key, db_key.key_hash):
        raise UnauthorizedError("Invalid API key")
    
    # Check if key is valid
    if not db_key.is_valid:
        if db_key.is_expired:
            raise UnauthorizedError("API key has expired")
        raise UnauthorizedError("API key is disabled")
    
    # Update usage stats (fire and forget)
    db_key.total_requests += 1
    
    return db_key


async def require_api_key(
    api_key: Annotated[APIKey | None, Depends(validate_api_key)],
) -> APIKey:
    """Dependency that requires a valid API key."""
    if api_key is None and settings.app_env != "development":
        raise UnauthorizedError("API key required")
    return api_key  # type: ignore


def get_current_user_from_token(token: str) -> dict | None:
    """
    Extract user info from JWT token.
    
    Returns:
        User claims if token is valid, None otherwise
    """
    return decode_access_token(token)
