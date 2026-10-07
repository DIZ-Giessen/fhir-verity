import uuid
from sqlalchemy import Column, ForeignKey, String, Boolean
from app.models.base import Base, TimestampMixin
from app.core.crypto import EncryptedJSON
from sqlalchemy.dialects.postgresql import UUID


class FhirServer(Base, TimestampMixin):
    """Model for FHIR server."""

    __tablename__ = "fhir_servers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    base_url = Column(String, nullable=False, unique=True)
    project_id = Column(String, nullable=False)
    auth_config = Column(EncryptedJSON, nullable=True)
    is_active = Column(Boolean, default=True)
    # Write TestScript/TestReport/VerificationResult back to this server after
    # each completed run. Reports are always kept in Verity itself.
    write_fhir_reports = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
