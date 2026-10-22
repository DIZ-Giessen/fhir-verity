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
    project_id: str | None = None
    is_active: bool
    write_fhir_reports: bool = True
    has_auth_config: bool = False
    auth_type: Literal["none", "basic", "oauth2_client_credentials"] = "none"
    owner_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    write_fhir_reports: bool | None = Field(
        default=None,
        description=(
            "Post TestScript, TestReport and List resources to "
            "this FHIR server after each completed run."
        ),
    )

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


class ServerMetadata(BaseModel):
    """Result of a CapabilityStatement read against a FHIR server."""

    ok: bool
    response_ms: int | None = None
    fhir_version: str | None = None
    software_name: str | None = None
    software_version: str | None = None
    publisher: str | None = None
    error: str | None = None


class ResourceCount(BaseModel):
    """Count of resources of a given type on a FHIR server."""

    resource_type: str
    total: int
    ok: bool
    error: str | None = None
