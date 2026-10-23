"""Effective validation config: rule defaults from code plus a server override."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.validation_config import ValidationConfig
from app.services.rules import effective_rules


async def load_server_override(
    server_id: UUID, resource_type: str, db: AsyncSession
) -> ValidationConfig | None:
    stmt = select(ValidationConfig).where(
        ValidationConfig.server_id == server_id,
        ValidationConfig.resource_type == resource_type,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_config_for_run(
    server_id: UUID,
    resource_type: str,
    db: AsyncSession,
) -> dict[str, dict]:
    """
    Every rule of the resource type with its defaults from the rule registry.
    A server override changes enabled, severity and pattern per rule;
    description and category always come from the code.
    """
    override = await load_server_override(server_id, resource_type, db)
    return effective_rules(resource_type, override.rules if override else None)
