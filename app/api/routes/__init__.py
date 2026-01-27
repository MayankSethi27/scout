"""
API Routes - FastAPI route modules.

==============================================================================
DEPRECATION NOTICE
==============================================================================
These REST API routes are DEPRECATED in favor of the MCP (Model Context Protocol)
server interface. Use `python mcp_server.py` for the recommended approach.

See README.md for MCP setup instructions.
==============================================================================
"""

from app.api.routes.health import router as health_router
from app.api.routes.analysis import router as analysis_router

__all__ = [
    "health_router",
    "analysis_router",
]
