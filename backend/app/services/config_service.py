"""Service layer for loading and merging validation configs."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.validation_config import ValidationConfig
from app.services.config_defaults import MII_KDS_DEFAULTS

logger = logging.getLogger(__name__)


async def get_config_for_run(
    server_id: UUID,
    resource_type: str,
    db: AsyncSession,
) -> dict[str, dict]:
    """
    Load the effective validation config for a given server and resource type.

    Merge strategy:
      1. Start with global MII KDS default (server_id = NULL)
      2. If a server-specific override exists, merge it on top.
         Individual rules are replaced, not partially updated.

    Returns a dict of rule_key -> rule definition with 'enabled' guaranteed.
    """
    # Global default aus DB
    stmt_global = select(ValidationConfig).where(
        ValidationConfig.server_id.is_(None),
        ValidationConfig.resource_type == resource_type,
    )
    result = await db.execute(stmt_global)
    global_config = result.scalar_one_or_none()

    base_rules: dict = {}
    if global_config:
        base_rules = dict(global_config.rules)

    else:

        # Fallback auf in-memory defaults falls DB-Seeding noch nicht gelaufen
        logger.warning(
            "No global config found for %s, using in-memory defaults.", resource_type
        )
        base_rules = dict(MII_KDS_DEFAULTS.get(resource_type, {}))

    # Server-spezifischer Override
    stmt_server = select(ValidationConfig).where(
        ValidationConfig.server_id == server_id,
        ValidationConfig.resource_type == resource_type,
    )
    result = await db.execute(stmt_server)
    server_config = result.scalar_one_or_none()

    if server_config:
        # Override: server-Regeln überschreiben global, rule-by-rule
        merged = {**base_rules, **server_config.rules}
        return merged

    return base_rules


def rule_enabled(config: dict, rule_key: str) -> bool:
    """Convenience: check if a specific rule is enabled in a loaded config."""

    rule = config.get(rule_key, {})
    return bool(rule.get("enabled", False))
