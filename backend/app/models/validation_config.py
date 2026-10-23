"""Model for Validation Config"""

import uuid
from sqlalchemy import Column, String, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin


class ValidationConfig(Base, TimestampMixin):
    """
    Server-specific override of the rule defaults for one resource type:
    enabled/severity/pattern per rule and the crawl filters. The defaults
    themselves are defined in app.services.rules.
    """

    __tablename__ = "validation_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fhir_servers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    resource_type = Column(String(100), nullable=False)
    filters = Column(JSON, nullable=False, default=dict, server_default="{}")
    rules = Column(JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint(
            "server_id",
            "resource_type",
            name="uq_config_server_resource",
        ),
    )
