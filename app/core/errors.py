"""
Repo Intelligence Platform - Standardized Error Handling

This module provides canonical error codes, exception classes, and FastAPI
exception handlers for consistent error responses across the API.
"""

from enum import Enum
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorCode(str, Enum):
    """Canonical error codes as specified in the design doc."""

    # Repository errors
    INVALID_REPO_URL = "INVALID_REPO_URL"
    REPO_NOT_FOUND = "REPO_NOT_FOUND"
    REPO_TOO_LARGE = "REPO_TOO_LARGE"
    REPO_NOT_READY = "REPO_NOT_READY"
    REPO_ALREADY_EXISTS = "REPO_ALREADY_EXISTS"

    # Job errors
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_FAILED = "JOB_FAILED"
    JOB_IN_PROGRESS = "JOB_IN_PROGRESS"

    # Tutor errors
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    ANSWER_NOT_FOUND = "ANSWER_NOT_FOUND"

    # Auth errors
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_API_KEY = "INVALID_API_KEY"
    RATE_LIMITED = "RATE_LIMITED"

    # General errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class ErrorResponse(BaseModel):
    """Standardized error response format."""

    error_code: ErrorCode
    message: str
    details: dict[str, Any] = {}
    retry_after: int | None = None


class AppException(Exception):
    """Base application exception with structured error info."""

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
        retry_after: int | None = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.retry_after = retry_after
        super().__init__(message)

    def to_response(self) -> ErrorResponse:
        """Convert to error response model."""
        return ErrorResponse(
            error_code=self.error_code,
            message=self.message,
            details=self.details,
            retry_after=self.retry_after,
        )


# Specific exception classes for common errors
class InvalidRepoURLError(AppException):
    """Raised when repository URL is invalid."""

    def __init__(self, url: str, reason: str = "Invalid URL format") -> None:
        super().__init__(
            error_code=ErrorCode.INVALID_REPO_URL,
            message=f"Invalid repository URL: {reason}",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"url": url},
        )


class RepoNotFoundError(AppException):
    """Raised when repository is not found."""

    def __init__(self, repo_id: str) -> None:
        super().__init__(
            error_code=ErrorCode.REPO_NOT_FOUND,
            message=f"Repository not found: {repo_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"repo_id": repo_id},
        )


class RepoTooLargeError(AppException):
    """Raised when repository exceeds size limits."""

    def __init__(self, size_mb: float, limit_mb: int) -> None:
        super().__init__(
            error_code=ErrorCode.REPO_TOO_LARGE,
            message=f"Repository size ({size_mb:.1f}MB) exceeds limit ({limit_mb}MB)",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            details={"size_mb": size_mb, "limit_mb": limit_mb},
        )


class RepoNotReadyError(AppException):
    """Raised when repository hasn't reached required state."""

    def __init__(
        self, repo_id: str, current_state: str, required_state: str
    ) -> None:
        super().__init__(
            error_code=ErrorCode.REPO_NOT_READY,
            message=f"Repository not ready. Current: {current_state}, Required: {required_state}",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "repo_id": repo_id,
                "current_state": current_state,
                "required_state": required_state,
            },
        )


class JobNotFoundError(AppException):
    """Raised when job is not found."""

    def __init__(self, job_id: str) -> None:
        super().__init__(
            error_code=ErrorCode.JOB_NOT_FOUND,
            message=f"Job not found: {job_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"job_id": job_id},
        )


class JobFailedError(AppException):
    """Raised when job has failed."""

    def __init__(self, job_id: str, error_message: str) -> None:
        super().__init__(
            error_code=ErrorCode.JOB_FAILED,
            message=f"Job failed: {error_message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"job_id": job_id, "error": error_message},
        )


class SessionNotFoundError(AppException):
    """Raised when tutor session is not found."""

    def __init__(self, session_id: str) -> None:
        super().__init__(
            error_code=ErrorCode.SESSION_NOT_FOUND,
            message=f"Session not found: {session_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"session_id": session_id},
        )


class AnswerNotFoundError(AppException):
    """Raised when tutor cannot find answer in codebase."""

    def __init__(self, query: str) -> None:
        super().__init__(
            error_code=ErrorCode.ANSWER_NOT_FOUND,
            message="This could not be found in the repository.",
            status_code=status.HTTP_200_OK,  # Not an error, but indicates no answer
            details={"query": query},
        )


class UnauthorizedError(AppException):
    """Raised when authentication fails."""

    def __init__(self, reason: str = "Invalid or missing credentials") -> None:
        super().__init__(
            error_code=ErrorCode.UNAUTHORIZED,
            message=reason,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class RateLimitedError(AppException):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int = 60) -> None:
        super().__init__(
            error_code=ErrorCode.RATE_LIMITED,
            message="Rate limit exceeded. Please retry later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            retry_after=retry_after,
        )


# FastAPI exception handlers
async def app_exception_handler(
    request: Request, exc: AppException
) -> JSONResponse:
    """Handle application exceptions."""
    response = exc.to_response()
    headers = {}
    if response.retry_after:
        headers["Retry-After"] = str(response.retry_after)
    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(exclude_none=True),
        headers=headers,
    )


async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """Handle standard HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=ErrorCode.INTERNAL_ERROR,
            message=str(exc.detail),
        ).model_dump(exclude_none=True),
    )


async def general_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle unhandled exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error_code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred",
        ).model_dump(exclude_none=True),
    )
