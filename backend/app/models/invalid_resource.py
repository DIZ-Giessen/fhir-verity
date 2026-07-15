"""Model for invalid FHIR resources found during validation."""

import uuid
from sqlalchemy import (
    BigInteger,
    Column,
    Index,
    String,
    JSON,
    Float,
    ForeignKey,
    DateTime,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin


class InvalidResource(Base, TimestampMixin):
    """
    A FHIR resource that failed validation.

    Acts as a deduplicated work-list per server: each (server, resource_type,
    resource_id) combination exists at most once. Tracking fields record
    when this resource first became invalid and when it was last seen invalid.
    """

    __tablename__ = "invalid_resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Server context — primary filter for all queries
    server_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fhir_servers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    server_base_url = Column(String, nullable=False)

    # Resource identity
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(String, nullable=False)

    # Validation findings (latest snapshot)
    issues = Column(JSON, nullable=False)
    metrics = Column(JSON, nullable=False)

    # Optional: full FHIR resource body, used by LLM-Assistant (Block 3)
    raw_resource = Column(JSON, nullable=True)

    # ML scores (Block 2) — populated by scoring service after validation
    anomaly_score = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)

    # LLM-generated correction/deletion suggestions (Block 3)
    llm_suggestions = Column(JSON, nullable=True)

    # Run-tracking — when first detected vs. when last confirmed
    first_seen_run_id = Column(UUID(as_uuid=True), nullable=False)
    first_seen_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_run_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "server_id",
            "resource_type",
            "resource_id",
            name="uq_server_resource_type_id",
        ),
    )


class InvalidResourceIssue(Base):
    """
    Normalized issue rows for filterable rule/severity queries.
    One row per issue of an invalid resource; replaced on every re-validation.
    """

    __tablename__ = "invalid_resource_issues"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    invalid_resource_id = Column(
        UUID(as_uuid=True),
        ForeignKey("invalid_resources.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule = Column(String(200), nullable=False)
    severity = Column(String(50), nullable=False)

    __table_args__ = (
        Index("ix_invalid_resource_issues_res_rule", "invalid_resource_id", "rule"),
    )
