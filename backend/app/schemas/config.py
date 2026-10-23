"""Schemas for validation configuration CRUD."""

from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict


class RuleDefinition(BaseModel):
    """A single validation rule's configuration."""

    enabled: bool
    severity: Literal["error", "warning", "info"]
    category: Optional[str] = None
    description: Optional[str] = None
    pattern: Optional[str] = None  # for pseudonym/identifier format checks


class ResourceConfig(BaseModel):
    """Effective configuration for a resource type."""

    resource_type: str
    rules: dict[str, RuleDefinition]
    is_server_specific: bool
    filters: dict = {}

    model_config = ConfigDict(from_attributes=True)


class ConfigUpdate(BaseModel):
    """Payload to replace the entire server-specific override."""

    rules: dict[str, RuleDefinition]


class RuleUpdate(BaseModel):
    """Payload to patch a single rule. All fields optional."""

    enabled: Optional[bool] = None
    severity: Optional[Literal["error", "warning", "info"]] = None
    pattern: Optional[str] = None


class RulesBulkUpdate(BaseModel):
    """Payload to patch several rules at once, e.g. a whole category."""

    rules: dict[str, RuleUpdate]


class ResourceFilters(BaseModel):
    """Optional FHIR search filters scoping which resources get validated.
    All fields optional; empty = validate everything (unchanged behaviour)."""

    last_updated_from: Optional[str] = None
    last_updated_to: Optional[str] = None
    profile: Optional[str] = None
    tag: Optional[str] = None


class FiltersUpdate(BaseModel):
    """Payload to replace a resource type's filters for a server."""

    filters: ResourceFilters
