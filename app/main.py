"""
GitHub Codebase Analyst - FastAPI Application Entry Point

==============================================================================
DEPRECATION NOTICE
==============================================================================
This REST API interface is DEPRECATED in favor of the MCP (Model Context Protocol)
server. The MCP interface provides direct integration with Claude in Cursor IDE
and other MCP-compatible clients.

To use the recommended MCP interface:
    python mcp_server.py

See README.md for MCP setup instructions.

This FastAPI server is maintained for backwards compatibility only.
New features will only be added to the MCP interface.
==============================================================================

Legacy usage (deprecated):
    uvicorn app.main:app --reload

Or:
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
import warnings

warnings.warn(
    "The FastAPI REST interface is deprecated. Use the MCP server instead: python mcp_server.py",
    DeprecationWarning,
    stacklevel=2
)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.api.routes import health_router, analysis_router
from app.api.middleware.error_handler import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events:
    - Startup: Initialize services, warm up models
    - Shutdown: Cleanup resources, close connections
    """
    # Startup
    settings = get_settings()
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"Environment: {settings.environment}")
    print(f"Debug mode: {settings.debug}")

    # Initialize services here if needed
    # e.g., pre-load embedding models, connect to databases

    yield  # Application runs here

    # Shutdown
    print("Shutting down application...")
    # Cleanup resources here if needed


def create_app() -> FastAPI:
    """
    Application factory function.

    Creates and configures the FastAPI application.
    """
    settings = get_settings()

    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
## GitHub Codebase Analyst API

Analyze any GitHub repository and get answers to your questions about the codebase.

### Features
- **Semantic Code Search**: Find relevant code using natural language
- **AI-Powered Analysis**: Get intelligent answers about code structure and behavior
- **Session Support**: Ask follow-up questions with context preservation

### Quick Start
1. POST `/api/v1/analysis/analyze` with a repo URL and question
2. Use the returned `session_id` for follow-up questions
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Register routers
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(analysis_router, prefix=settings.api_prefix)

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health"
        }

    return app


# Create the app instance
app = create_app()


# For running directly with python app/main.py
if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info"
    )
