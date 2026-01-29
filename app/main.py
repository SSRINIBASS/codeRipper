"""
Repo Intelligence Platform - FastAPI Main Application

This is the main entry point for the FastAPI application.
Configures middleware, exception handlers, and routes.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.core.errors import (
    AppException,
    app_exception_handler,
    general_exception_handler,
    http_exception_handler,
)
from app.database import close_db, init_db
from app.middleware import (
    CorrelationMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
)

settings = get_settings()


def configure_logging() -> None:
    """Configure structured logging with structlog."""
    # Determine processors based on environment
    if settings.is_production:
        # JSON output for production
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Pretty console output for development
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    logger = structlog.get_logger(__name__)
    
    # Startup
    await logger.ainfo(
        "application_starting",
        app_name=settings.app_name,
        version=__version__,
        environment=settings.app_env,
    )
    
    # Initialize database
    await init_db()
    await logger.ainfo("database_initialized")
    
    yield
    
    # Shutdown
    await logger.ainfo("application_stopping")
    await close_db()
    await logger.ainfo("database_closed")


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance.
    """
    # Configure logging first
    configure_logging()
    
    # Create FastAPI app
    app = FastAPI(
        title="Repo Intelligence Platform",
        description=(
            "API-first platform for converting undocumented GitHub repositories "
            "into understandable, searchable, and teachable systems."
        ),
        version=__version__,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom middleware (order matters - first added = outermost)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(CorrelationMiddleware)
    
    # Register exception handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    # Register routers
    from app.api.health import router as health_router
    from app.api.repos import router as repos_router
    from app.api.jobs import router as jobs_router
    from app.api.intelligence import router as intelligence_router
    from app.api.tutor import router as tutor_router
    
    app.include_router(health_router)
    app.include_router(repos_router)
    app.include_router(jobs_router)
    app.include_router(intelligence_router)
    app.include_router(tutor_router)
    
    return app


# Create the application instance
app = create_application()
