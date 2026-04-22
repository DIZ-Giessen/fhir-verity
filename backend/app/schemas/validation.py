"""The Schemas for Validation"""

from typing import Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel
from app.models.validation_run import ValidationStatus


class ValidationStartRequest(BaseModel):
    """Schema for starting a validation run."""

    server_id: UUID
    resource_types: list[str] = ["All"]


class ValidationRunRead(BaseModel):
    """Schema for reading a validation run."""

    id: UUID
    server_id: UUID
    resource_types: list[str]
    status: ValidationStatus
    total_processed: int = 0
    total_invalid: int = 0
    started_at: datetime
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        """Enable population from ORM attributes"""

        from_attributes = True
