"""Endpoints to read and update validation rule configuration."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.fhir_server import FhirServer
from app.models.validation_config import ValidationConfig
from app.schemas.config import (
    ConfigUpdate,
    ResourceConfig,
    RuleUpdate,
    FiltersUpdate,
)
from app.services.config_defaults import (
    MII_KDS_DEFAULTS,
    SUPPORTED_RESOURCE_TYPES,
)
from app.services.validation_filters import FilterValidationError, validate_filters

router = APIRouter()


# ---------------------------------------------------------------------------
# Internal helper: effective config = global defaults + server overrides
# ---------------------------------------------------------------------------
async def _load_effective_config(
    server_id: UUID,
    resource_type: str,
    db: AsyncSession,
) -> tuple[dict, bool, dict]:
    """Returns (merged_rules, is_server_specific, filters)."""
    stmt_global = select(ValidationConfig).where(
        ValidationConfig.server_id.is_(None),
        ValidationConfig.resource_type == resource_type,
    )
    global_cfg = (await db.execute(stmt_global)).scalar_one_or_none()
    base = dict(global_cfg.rules) if global_cfg else {}

    stmt_server = select(ValidationConfig).where(
        ValidationConfig.server_id == server_id,
        ValidationConfig.resource_type == resource_type,
    )
    server_cfg = (await db.execute(stmt_server)).scalar_one_or_none()

    if server_cfg:
        merged = {**base, **server_cfg.rules}
        return merged, True, (server_cfg.filters or {})
    return base, False, {}


async def _ensure_server_exists(server_id: UUID, db: AsyncSession) -> FhirServer:
    stmt = select(FhirServer).where(FhirServer.id == server_id)
    server = (await db.execute(stmt)).scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="FHIR server not found")
    return server


# ---------------------------------------------------------------------------
# GET /config/defaults/{resource_type}
# ---------------------------------------------------------------------------
@router.get("/config/defaults/{resource_type}", response_model=ResourceConfig)
async def get_defaults(
    resource_type: str,
    db: AsyncSession = Depends(get_db),
):
    """Global default configuration for a resource type (server_id IS NULL)."""
    if resource_type not in SUPPORTED_RESOURCE_TYPES:
        raise HTTPException(status_code=404, detail="Unsupported resource type")

    stmt = select(ValidationConfig).where(
        ValidationConfig.server_id.is_(None),
        ValidationConfig.resource_type == resource_type,
    )
    cfg = (await db.execute(stmt)).scalar_one_or_none()
    rules = cfg.rules if cfg else {}

    return ResourceConfig(
        resource_type=resource_type,
        rules=rules,
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
):
    """Effective configuration: defaults merged with server-specific overrides."""
    if resource_type not in SUPPORTED_RESOURCE_TYPES:
        raise HTTPException(status_code=404, detail="Unsupported resource type")

    await _ensure_server_exists(server_id, db)
    rules, is_specific, filters = await _load_effective_config(
        server_id, resource_type, db
    )

    return ResourceConfig(
        resource_type=resource_type,
        rules=rules,
        is_server_specific=is_specific,
        filters=filters,
    )


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
):
    """Replace the complete server-specific override."""
    if resource_type not in SUPPORTED_RESOURCE_TYPES:
        raise HTTPException(status_code=404, detail="Unsupported resource type")

    await _ensure_server_exists(server_id, db)

    rules_dict = {k: v.model_dump() for k, v in payload.rules.items()}

    stmt = select(ValidationConfig).where(
        ValidationConfig.server_id == server_id,
        ValidationConfig.resource_type == resource_type,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    now = datetime.now()
    if existing:
        existing.rules = rules_dict
        existing.updated_at = now
    else:
        db.add(
            ValidationConfig(
                server_id=server_id,
                resource_type=resource_type,
                rules=rules_dict,
                created_at=now,
                updated_at=now,
            )
        )

    await db.commit()

    rules, is_specific, filters = await _load_effective_config(
        server_id, resource_type, db
    )
    return ResourceConfig(
        resource_type=resource_type,
        rules=rules,
        is_server_specific=is_specific,
        filters=filters,
    )


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
):
    """
    Update a single rule (enabled / severity / pattern).
    Creates a server override on-the-fly if none exists yet,
    starting from the default rule definition.
    """
    if resource_type not in SUPPORTED_RESOURCE_TYPES:
        raise HTTPException(status_code=404, detail="Unsupported resource type")

    defaults = MII_KDS_DEFAULTS.get(resource_type, {})
    if rule_key not in defaults:
        raise HTTPException(
            status_code=404,
            detail=f"Rule '{rule_key}' is not defined for {resource_type}",
        )

    await _ensure_server_exists(server_id, db)

    stmt = select(ValidationConfig).where(
        ValidationConfig.server_id == server_id,
        ValidationConfig.resource_type == resource_type,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    updates = payload.model_dump(exclude_unset=True)
    now = datetime.now()

    if existing:
        rules = dict(existing.rules)
        current_rule = dict(rules.get(rule_key, defaults[rule_key]))
        current_rule.update(updates)
        rules[rule_key] = current_rule
        existing.rules = rules
        existing.updated_at = now
    else:
        new_rule = {**defaults[rule_key], **updates}
        db.add(
            ValidationConfig(
                server_id=server_id,
                resource_type=resource_type,
                rules={rule_key: new_rule},
                created_at=now,
                updated_at=now,
            )
        )

    await db.commit()

    rules, is_specific, filters = await _load_effective_config(
        server_id, resource_type, db
    )
    return ResourceConfig(
        resource_type=resource_type,
        rules=rules,
        is_server_specific=is_specific,
        filters=filters,
    )


# ---------------------------------------------------------------------------
# DELETE /config/servers/{server_id}/{resource_type}
# ---------------------------------------------------------------------------
@router.delete("/config/servers/{server_id}/{resource_type}")
async def delete_server_config(
    server_id: UUID,
    resource_type: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove server override entirely, falling back to global defaults."""
    stmt = select(ValidationConfig).where(
        ValidationConfig.server_id == server_id,
        ValidationConfig.resource_type == resource_type,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if not existing:
        raise HTTPException(
            status_code=404,
            detail="No server-specific override exists for this resource type",
        )

    await db.delete(existing)
    await db.commit()
    return {"status": "deleted", "fallback": "global defaults"}


@router.get("/config/resource-types", response_model=list[str])
async def list_resource_types():
    """Alle Ressourcentypen, die konfiguriert werden können."""
    return SUPPORTED_RESOURCE_TYPES


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
):
    """
    Set the FHIR search filters for a resource type on a server.
    Empty filters clear the scope (validate everything again).
    Creates a server override on-the-fly if none exists yet.
    """
    if resource_type not in SUPPORTED_RESOURCE_TYPES:
        raise HTTPException(status_code=404, detail="Unsupported resource type")

    await _ensure_server_exists(server_id, db)

    # Validate + clean (drops empties/unknowns, checks date format & range)
    try:
        cleaned = validate_filters(payload.filters.model_dump(exclude_none=True))
    except FilterValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    stmt = select(ValidationConfig).where(
        ValidationConfig.server_id == server_id,
        ValidationConfig.resource_type == resource_type,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    now = datetime.now()
    if existing:
        existing.filters = cleaned  # full replace (new dict -> mutation detected)
        existing.updated_at = now
    else:
        db.add(
            ValidationConfig(
                server_id=server_id,
                resource_type=resource_type,
                rules={},  # no rule override, just filters
                filters=cleaned,
                created_at=now,
                updated_at=now,
            )
        )

    await db.commit()

    rules, is_specific, filters = await _load_effective_config(
        server_id, resource_type, db
    )
    return ResourceConfig(
        resource_type=resource_type,
        rules=rules,
        is_server_specific=is_specific,
        filters=filters,
    )
