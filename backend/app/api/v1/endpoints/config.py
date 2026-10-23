"""Endpoints to read and update validation rule configuration."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import server_access
from app.models.fhir_server import FhirServer
from app.models.user import UserRole
from app.models.validation_config import ValidationConfig
from app.schemas.config import (
    ConfigUpdate,
    FiltersUpdate,
    ResourceConfig,
    RulesBulkUpdate,
    RuleUpdate,
)
from app.services.config_service import load_server_override
from app.services.rules import REGISTRY, RESOURCE_TYPES, default_rules, effective_rules
from app.services.rules.registry import CONFIGURABLE_FIELDS
from app.services.validation_filters import FilterValidationError, validate_filters

router = APIRouter()

# Reading needs access to the server, changing it the editor role on top.
# Servers outside the user's scope answer 404.
viewer_server_access = server_access()
editor_server_access = server_access(UserRole.editor.value)


def _check_type(resource_type: str) -> None:
    if resource_type not in RESOURCE_TYPES:
        raise HTTPException(status_code=404, detail="Unsupported resource type")


def _check_rule(resource_type: str, rule_key: str) -> None:
    if REGISTRY.get(resource_type, rule_key) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Rule '{rule_key}' is not defined for {resource_type}",
        )


def _changes(values: dict) -> dict:
    """Only the fields a server may override are stored."""
    return {k: v for k, v in values.items() if k in CONFIGURABLE_FIELDS and v is not None}


async def _response(server_id: UUID, resource_type: str, db: AsyncSession) -> ResourceConfig:
    override = await load_server_override(server_id, resource_type, db)
    return ResourceConfig(
        resource_type=resource_type,
        rules=effective_rules(resource_type, override.rules if override else None),
        is_server_specific=override is not None,
        filters=(override.filters or {}) if override else {},
    )


async def _get_or_create_override(
    server_id: UUID, resource_type: str, db: AsyncSession
) -> ValidationConfig:
    override = await load_server_override(server_id, resource_type, db)
    if override is None:
        now = datetime.now(timezone.utc)
        override = ValidationConfig(
            server_id=server_id,
            resource_type=resource_type,
            rules={},
            filters={},
            created_at=now,
            updated_at=now,
        )
        db.add(override)
    return override


# ---------------------------------------------------------------------------
# GET /config/defaults/{resource_type}
# ---------------------------------------------------------------------------
@router.get("/config/defaults/{resource_type}", response_model=ResourceConfig)
async def get_defaults(resource_type: str):
    """Default configuration of a resource type, as defined by the rule registry."""
    _check_type(resource_type)
    return ResourceConfig(
        resource_type=resource_type,
        rules=default_rules(resource_type),
        is_server_specific=False,
        filters={},
    )


# ---------------------------------------------------------------------------
# GET /config/servers/{server_id}/{resource_type}
# ---------------------------------------------------------------------------
@router.get(
    "/config/servers/{server_id}/{resource_type}",
    response_model=ResourceConfig,
)
async def get_server_config(
    server_id: UUID,
    resource_type: str,
    db: AsyncSession = Depends(get_db),
    _server: FhirServer = Depends(viewer_server_access),
):
    """Effective configuration: defaults merged with server-specific overrides."""
    _check_type(resource_type)
    return await _response(server_id, resource_type, db)


# ---------------------------------------------------------------------------
# PUT /config/servers/{server_id}/{resource_type}
# ---------------------------------------------------------------------------
@router.put(
    "/config/servers/{server_id}/{resource_type}",
    response_model=ResourceConfig,
)
async def replace_server_config(
    server_id: UUID,
    resource_type: str,
    payload: ConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _server: FhirServer = Depends(editor_server_access),
):
    """Replace the rule overrides of a server for one resource type."""
    _check_type(resource_type)
    for key in payload.rules:
        _check_rule(resource_type, key)

    override = await _get_or_create_override(server_id, resource_type, db)
    override.rules = {k: _changes(v.model_dump()) for k, v in payload.rules.items()}
    override.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return await _response(server_id, resource_type, db)


# ---------------------------------------------------------------------------
# PATCH /config/servers/{server_id}/{resource_type}/rules/{rule_key}
# ---------------------------------------------------------------------------
@router.patch(
    "/config/servers/{server_id}/{resource_type}/rules/{rule_key}",
    response_model=ResourceConfig,
)
async def patch_rule(
    server_id: UUID,
    resource_type: str,
    rule_key: str,
    payload: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    _server: FhirServer = Depends(editor_server_access),
):
    """Change enabled, severity or pattern of one rule for this server."""
    _check_type(resource_type)
    _check_rule(resource_type, rule_key)

    override = await _get_or_create_override(server_id, resource_type, db)
    rules = dict(override.rules or {})
    current = _changes(rules.get(rule_key) or {})
    current.update(_changes(payload.model_dump(exclude_unset=True)))
    rules[rule_key] = current
    override.rules = rules
    override.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return await _response(server_id, resource_type, db)


# ---------------------------------------------------------------------------
# PATCH /config/servers/{server_id}/{resource_type}/rules
# ---------------------------------------------------------------------------
@router.patch(
    "/config/servers/{server_id}/{resource_type}/rules",
    response_model=ResourceConfig,
)
async def patch_rules(
    server_id: UUID,
    resource_type: str,
    payload: RulesBulkUpdate,
    db: AsyncSession = Depends(get_db),
    _server: FhirServer = Depends(editor_server_access),
):
    """Change several rules in one request, e.g. switch a whole category on or off."""
    _check_type(resource_type)
    for key in payload.rules:
        _check_rule(resource_type, key)

    override = await _get_or_create_override(server_id, resource_type, db)
    rules = dict(override.rules or {})
    for key, update in payload.rules.items():
        current = _changes(rules.get(key) or {})
        current.update(_changes(update.model_dump(exclude_unset=True)))
        rules[key] = current
    override.rules = rules
    override.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return await _response(server_id, resource_type, db)


# ---------------------------------------------------------------------------
# DELETE /config/servers/{server_id}/{resource_type}
# ---------------------------------------------------------------------------
@router.delete("/config/servers/{server_id}/{resource_type}")
async def delete_server_config(
    server_id: UUID,
    resource_type: str,
    db: AsyncSession = Depends(get_db),
    _server: FhirServer = Depends(editor_server_access),
):
    """Remove the server override entirely, falling back to the defaults."""
    override = await load_server_override(server_id, resource_type, db)
    if not override:
        raise HTTPException(
            status_code=404,
            detail="No server-specific override exists for this resource type",
        )
    await db.delete(override)
    await db.commit()
    return {"status": "deleted", "fallback": "defaults"}


@router.get("/config/resource-types", response_model=list[str])
async def list_resource_types():
    """All resource types Verity can validate."""
    return RESOURCE_TYPES


# ---------------------------------------------------------------------------
# PUT /config/servers/{server_id}/{resource_type}/filters
# ---------------------------------------------------------------------------
@router.put(
    "/config/servers/{server_id}/{resource_type}/filters",
    response_model=ResourceConfig,
)
async def update_server_filters(
    server_id: UUID,
    resource_type: str,
    payload: FiltersUpdate,
    db: AsyncSession = Depends(get_db),
    _server: FhirServer = Depends(editor_server_access),
):
    """
    Set the FHIR search filters for a resource type on a server.
    Empty filters clear the scope (validate everything again).
    """
    _check_type(resource_type)
    try:
        cleaned = validate_filters(payload.filters.model_dump(exclude_none=True))
    except FilterValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    override = await _get_or_create_override(server_id, resource_type, db)
    override.filters = cleaned
    override.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return await _response(server_id, resource_type, db)
