"""Model for the Validation Run"""

import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    String,
    JSON,
    Integer,
    Enum as SQLEnum,
    ForeignKey,
    DateTime,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class ValidationStatus(str, enum.Enum):
    """# Enum for the status of a validation run."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ValidationRun(Base, TimestampMixin):
    """Model for validation runs."""

    __tablename__ = "validation_runs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    server_id = Column(
        UUID(as_uuid=True), ForeignKey("fhir_servers.id"), nullable=False
    )
    resource_types = Column(JSON, nullable=False)
    total_processed = Column(Integer, default=0)
    total_invalid = Column(Integer, default=0)
    status = Column(SQLEnum(ValidationStatus), default=ValidationStatus.RUNNING)
    started_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    verification_result = Column(JSON, nullable=True)
    test_report = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)

    per_resource_stats: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        server_default="{}",
    )

    checkpoint: Mapped[dict] = mapped_column(
        JSON, default=dict, nullable=False, server_default="{}"
    )
    cancel_requested = Column(Boolean, nullable=False, server_default="false")

    rule_stats: Mapped[dict] = mapped_column(
        JSON, default=dict, nullable=False, server_default="{}"
    )
    triggered_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    triggered_by = relationship("User", lazy="joined", viewonly=True)
