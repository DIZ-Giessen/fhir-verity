import uuid
from sqlalchemy import Column, String, Boolean, JSON
from app.models.base import Base, TimestampMixin
from sqlalchemy.dialects.postgresql import UUID


class FhirServer(Base, TimestampMixin):
    """Model for FHIR server."""
    __tablename__ = "fhir_servers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    base_url = Column(String, nullable=False, unique=True)
    project_id = Column(String, nullable=False)
    auth_config = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
