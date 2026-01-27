"""
Error Handler Middleware - Global exception handling for the API.

==============================================================================
DEPRECATION NOTICE
==============================================================================
This middleware is part of the DEPRECATED REST API interface.
Use the MCP server (`python mcp_server.py`) instead.

The exception classes in this module are still used internally by the
application for error handling, but the HTTP handlers are deprecated.
==============================================================================

Catches exceptions and returns consistent error responses.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback
from datetime import datetime
from typing import Union

from app.core.config import get_settings


class AppException(Exception):
    """Base exception for application errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: dict = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class RepositoryNotFoundError(AppException):
    """Raised when repository cannot be found or cloned."""

    def __init__(self, repo_url: str):
        super().__init__(
            message=f"Repository not found: {repo_url}",
            error_code="REPO_NOT_FOUND",
            status_code=404,
            details={"repo_url": repo_url}
        )


class IndexingError(AppException):
    """Raised when indexing fails."""

    def __init__(self, message: str, repo_url: str = None):
        super().__init__(
            message=message,
            error_code="INDEXING_ERROR",
            status_code=500,
            details={"repo_url": repo_url} if repo_url else {}
        )


class AnalysisError(AppException):
    """Raised when analysis fails."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            error_code="ANALYSIS_ERROR",
            status_code=500
        )


class SessionNotFoundError(AppException):
    """Raised when session is not found."""

    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session not found: {session_id}",
            error_code="SESSION_NOT_FOUND",
            status_code=404,
            details={"session_id": session_id}
        )


class RateLimitError(AppException):
    """Raised when rate limit is exceeded."""

    def __init__(self):
        super().__init__(
            message="Rate limit exceeded. Please try again later.",
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429
        )


def create_error_response(
    message: str,
    error_code: str = "INTERNAL_ERROR",
    status_code: int = 500,
    details: dict = None
) -> JSONResponse:
    """Create a standardized error response."""
    settings = get_settings()

    content = {
        "success": False,
        "error": message,
        "error_code": error_code,
        "timestamp": datetime.utcnow().isoformat()
    }

    # Include details in debug mode
    if details and settings.debug:
        content["details"] = details

    return JSONResponse(
        status_code=status_code,
        content=content
    )


async def app_exception_handler(
    request: Request,
    exc: AppException
) -> JSONResponse:
    """Handle application-specific exceptions."""
    return create_error_response(
        message=exc.message,
        error_code=exc.error_code,
        status_code=exc.status_code,
        details=exc.details
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
) -> JSONResponse:
    """Handle HTTP exceptions."""
    return create_error_response(
        message=str(exc.detail),
        error_code="HTTP_ERROR",
        status_code=exc.status_code
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """Handle request validation errors."""
    # Format validation errors
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(l) for l in error["loc"])
        errors.append(f"{loc}: {error['msg']}")

    return create_error_response(
        message="Validation error",
        error_code="VALIDATION_ERROR",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={"errors": errors}
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handle unexpected exceptions."""
    settings = get_settings()

    # Log the full traceback
    traceback_str = traceback.format_exc()
    print(f"Unexpected error: {traceback_str}")

    details = None
    if settings.debug:
        details = {
            "exception_type": type(exc).__name__,
            "traceback": traceback_str
        }

    return create_error_response(
        message="An unexpected error occurred",
        error_code="INTERNAL_ERROR",
        status_code=500,
        details=details
    )
