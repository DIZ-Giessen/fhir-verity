"""
This module defines the Pydantic schemas for FHIR server creation and retrieval.
in FastAPI endpoints handling FHIR Server resources.
"""

from uuid import UUID
from typing import Optional, Dict, Any
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
