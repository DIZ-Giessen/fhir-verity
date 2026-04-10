
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict 

from uuid import UUID 

class FhirServerCreate(BaseModel):
    """Schema for creating a new FHIR server."""
    name: str
    base_url: HttpUrl
    project_id: Optional[UUID] = None
    auth_config: Optional[Dict] = None

class FhirServerRead(BaseModel):
    """Schema for reading a FHIR server."""
    id: UUID
    name: str
    base_url: str
    project_id: Optional[UUID] = None 
    is_active: bool
    created_at: str
    updated_at: str

class Config:
    from_attributes = True # Konvertiere SQLAlchemy Models zu Pydantic Models

