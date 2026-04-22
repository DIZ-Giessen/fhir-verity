"""
This module defines the base configuration settings for the FHIR Verity backend application.
It loads environment variables (from .env) using Pydantic to manage settings such as project
metadata, database connection URL, runtime environment, and server host/port parameters.

Use get_settings() to access a cached Settings instance throughout the application.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings default value"""

    PROJECT_NAME: str = "FHIR Verity"
    PROJECT_DESCRIPTION: str = "Intelligentes FHIR-Datenqualitäts-tool"
    PROJECT_VERSION: str = "1.0.0"
    DATABASE_URL: str
    ENVIRONMENT: str = "development"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    class Config:
        """Default Config"""

        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
