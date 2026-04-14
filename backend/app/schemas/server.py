from datetime import datetime
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any 

from uuid import UUID 

class FhirServerCreate(BaseModel):
    """Schema for creating a new FHIR server."""
    name: str
    base_url: HttpUrl
    project_id: str = None
    auth_config: Optional[Dict[str, Any]] = None

class FhirServerRead(BaseModel):
    """Schema for reading a FHIR server."""
    id: UUID
    name: str
    base_url: str
    project_id: str = None 
    is_active: bool
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True # Konvertiere SQLAlchemy Models zu Pydantic Models

    