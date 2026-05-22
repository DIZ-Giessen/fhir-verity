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

    model_config = ConfigDict(from_attributes=True)


class ConfigUpdate(BaseModel):
    """Payload to replace the entire server-specific override."""

    rules: dict[str, RuleDefinition]


class RuleUpdate(BaseModel):
    """Payload to patch a single rule. All fields optional."""

    enabled: Optional[bool] = None
    severity: Optional[Literal["error", "warning", "info"]] = None
    pattern: Optional[str] = None
