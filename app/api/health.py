"""
Health Check API - Health and readiness endpoints.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    version: str


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    status: str
    timestamp: str
    checks: dict[str, bool]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.
    
    Returns 200 if the service is running.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="0.1.0",
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(
    db: AsyncSession = Depends(get_db),
) -> ReadinessResponse:
    """
    Readiness check endpoint.
    
    Verifies that all dependencies are available and healthy:
    - Database connection
    - Storage paths exist
    """
    from app.config import get_settings
    
    settings = get_settings()
    checks = {}
    
    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False
    
    # Check storage paths
    checks["storage"] = settings.storage_path.exists()
    checks["repos_path"] = settings.repos_path.exists()
    checks["indexes_path"] = settings.indexes_path.exists()
    
    # Overall status
    all_healthy = all(checks.values())
    
    return ReadinessResponse(
        status="ready" if all_healthy else "degraded",
        timestamp=datetime.utcnow().isoformat(),
        checks=checks,
    )
