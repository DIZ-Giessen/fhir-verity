"""
This module defines the Pydantic schemas for FHIR server creation and retrieval.
in FastAPI endpoints handling FHIR Server resources.
"""

from uuid import UUID
from typing import Literal, Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, HttpUrl, Field, ConfigDict


class FhirServerCreate(BaseModel):
    """Schema for creating a new FHIR server."""

    name: str
    base_url: HttpUrl
    project_id: str = None
    auth_config: Optional[Dict[str, Any]] = None


class FhirServerRead(BaseModel):
    """Schema for reading a FHIR server."""

    id: UUID
    name: str
    base_url: str
    project_id: str = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        "Config"

        from_attributes = True  # Konvertiere SQLAlchemy Models zu Pydantic Models


class FhirServerBase(BaseModel):
    """Server Base"""

    name: str = Field(min_length=1, max_length=255)
    base_url: HttpUrl
    project_id: str = Field(min_length=1, max_length=64)
    is_active: bool = True


class FhirServerUpdate(BaseModel):
    """All fields optional for PATCH."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_url: HttpUrl | None = None
    project_id: str | None = Field(default=None, min_length=1, max_length=64)
    auth_config: dict[str, Any] | None = None
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")


class ServerAuthRead(BaseModel):
    """Non-secret view of a server's auth config (for prefilling the UI)."""

    type: Literal["none", "basic", "oauth2_client_credentials"]
    username: str | None = None
    client_id: str | None = None
    token_url: str | None = None
    scope: str | None = None


class ServerAuthUpdate(BaseModel):
    """
    Set a server's auth. Secret fields (password, client_secret) may be omitted
    to keep the currently stored value.
    """

    type: Literal["none", "basic", "oauth2_client_credentials"]
    username: str | None = None
    password: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    token_url: str | None = None
    scope: str | None = None

    model_config = ConfigDict(extra="forbid")
