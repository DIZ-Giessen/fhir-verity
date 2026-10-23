"""
This module defines the base configuration settings for the FHIR Verity backend application.
It loads environment variables (from .env) using Pydantic to manage settings such as project
metadata, database connection URL, runtime environment, and server host/port parameters.

Use get_settings() to access a cached Settings instance throughout the application.
"""

from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings default value"""

    PROJECT_NAME: str = "FHIR Verity"
    PROJECT_DESCRIPTION: str = "Server-wide data quality validation for FHIR servers"
    PROJECT_VERSION: str = "1.0.0"
    DATABASE_URL: str
    ENVIRONMENT: str = "development"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # --- Encryption at rest ---
    # Fernet key for FhirServer.auth_config (stored credentials to external
    # FHIR servers). Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    FIELD_ENCRYPTION_KEY: str

    # --- Auth (BFF) ---
    # false = demo/development mode without Keycloak: every request runs as a
    # single built-in admin, there is no ownership separation. Refused when
    # ENVIRONMENT=production (see _check_auth). The Keycloak settings and
    # SESSION_SECRET_KEY are only required while auth is enabled.
    AUTH_ENABLED: bool = True
    SESSION_SECRET_KEY: str = ""
    BACKEND_BASE_URL: str = "http://localhost:8000"
    FRONTEND_BASE_URL: str = "http://localhost:3000"
    KEYCLOAK_DISCOVERY_URL: str = ""
    KEYCLOAK_CLIENT_ID: str = "fhir-verity"
    KEYCLOAK_CLIENT_SECRET: str = ""
    INITIAL_ADMIN_USERS: str = ""

    # --- SMTP (email notifications) ---
    EMAIL_ENABLED: bool = True
    EMAIL_HOST: str = ""
    EMAIL_HOST_PORT: int = 465
    EMAIL_ADDRESS: str = ""  # From-Adresse
    EMAIL_USER: str = ""
    EMAIL_PASSWORD: str = ""
    EMAIL_USE_SSL: bool = False  # True = implicit SSL (465), False = STARTTLS
    EMAIL_VERIFY_CERT: bool = True  # False nur für interne Server mit self-signed cert

    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Comma-separated hosts Verity may connect to as FHIR server or token
    # endpoint, e.g. "fhir.example.org,*.diz.example.org". Empty = any host.
    FHIR_ALLOWED_HOSTS: str = ""

    # --- FHIR reports (TestScript / TestReport / List) ---
    # Name shown as publisher/tester in every report.
    FHIR_REPORT_PUBLISHER: str = "FHIR Verity"
    # Canonical base for TestScript.url, identifier systems and extensionURLs.
    VERITY_CANONICAL_BASE: str = (
        "https://mirgitlab.med.uni-giessen.de/povoc1/fhir-verity"
    )

    @model_validator(mode="after")
    def _check_auth(self) -> "Settings":
        if not self.AUTH_ENABLED:
            if self.ENVIRONMENT == "production":
                raise ValueError(
                    "AUTH_ENABLED=false is not allowed with ENVIRONMENT=production: "
                    "everyone who can reach Verity would act as admin. Configure "
                    "Keycloak (or the bundled one, docker compose --profile keycloak) "
                    "or set ENVIRONMENT=development for a demo setup."
                )
            return self
        missing = [
            name
            for name in (
                "SESSION_SECRET_KEY",
                "KEYCLOAK_DISCOVERY_URL",
                "KEYCLOAK_CLIENT_SECRET",
            )
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(
                f"AUTH_ENABLED=true requires {', '.join(missing)} to be set"
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        """Config Class"""

        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
