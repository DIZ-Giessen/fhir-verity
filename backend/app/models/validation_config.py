"""Model for Validation Config"""

import uuid
from sqlalchemy import Column, String, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin


class ValidationConfig(Base, TimestampMixin):
    """
    Validation rules per resource type, optionally scoped to a FHIR server

    server_id = NULL ---> global default (MII KDS baseline)
    server_id = UUID ---> serverspecific override

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
