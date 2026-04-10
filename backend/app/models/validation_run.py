import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, JSON, Integer, Enum as SQLEnum, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin

class ValidationStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
class ValidationRun(Base, TimestampMixin):
    """Model for validation runs."""

    __tablename__ = "validation_runs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id = Column(UUID(as_uuid=True), ForeignKey("fhir_servers.id"), nullable=False)
    resource_type = Column(JSON, nullable=False)
    total_processed = Column(Integer, default=0)
    total_invalid = Column(Integer, default=0)
    status = Column(SQLEnum(ValidationStatus), default=ValidationStatus.RUNNING)
    started_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    verification_result = Column(JSON, nullable=True)
    test_report = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)