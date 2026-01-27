"""
Health Check Endpoints - Application health and status monitoring.
"""

from fastapi import APIRouter, Depends
from datetime import datetime

from app.core.config import get_settings, Settings
from app.models.responses import HealthResponse


router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check if the API is running and healthy"
)
async def health_check(
    settings: Settings = Depends(get_settings)
) -> HealthResponse:
    """
    Basic health check endpoint.

    Returns:
        HealthResponse with status and version info
    """
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        environment=settings.environment,
        timestamp=datetime.utcnow()
    )


@router.get(
    "/ready",
    summary="Readiness Check",
    description="Check if the API is ready to accept requests"
)
async def readiness_check(
    settings: Settings = Depends(get_settings)
) -> dict:
    """
    Readiness check for Kubernetes/container orchestration.

    Verifies that all dependencies are available.
    """
    checks = {
        "api": True,
        "config_loaded": settings is not None,
    }

    # Check if OpenAI API key is configured
    checks["llm_configured"] = bool(settings.openai_api_key)

    all_ready = all(checks.values())

    return {
        "ready": all_ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get(
    "/live",
    summary="Liveness Check",
    description="Simple liveness probe"
)
async def liveness_check() -> dict:
    """
    Liveness check for Kubernetes.

    Just returns OK if the server is running.
    """
    return {"status": "alive"}
