"""
Application Configuration.

Loads settings from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "Scout Code Navigator"
    app_version: str = "3.0.0"
    debug: bool = False
    environment: str = "development"

    # HTTP Server (for mcp_server.py)
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # Repository cloning (for GitHub URLs)
    repo_storage_path: str = "./data/repos"
    repo_cache_ttl_hours: int = 24
    repo_clone_timeout_seconds: int = 300

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
