import uuid
from sqlalchemy import Column, String, JSON, Text, Float
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.models.base import Base, TimestampMixin

class InvalidResource(Base, TimestampMixin):
    """Model for invalid resources."""

    __tablename__ = "invalid_resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String(36), nullable=False, index= True)
    server_base_url = Column(String(500), nullable=False)
    resource_Type = Column(String(100), nullable=False, index= True)
    ressource_id = Column(String(1001), nullable=False)

    issues = Column(ARRAY(Text), nullable=False, default=list)
    metrics = Column(JSON, nullable=False)
    raw_ressource = Column(JSON, nullable=True) # Nur bei bedarf gespeichert 


    # Für Verison 2.0 Bachelor Arbeit ML-Phase 
    risk_score = Column(Float, nullable=True)
    anomaly_score = Column(Float, nullable=True)
    llm_suggestions = Column(JSON, nullable=True)
