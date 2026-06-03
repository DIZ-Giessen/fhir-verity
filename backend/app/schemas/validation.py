"""The Schemas for Validation"""

from typing import Optional, Any
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
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


# ---------------------------------------------------------------------------
# Read schemas — Validation Runs
# ---------------------------------------------------------------------------


class ValidationRunListItem(BaseModel):
    """Kompakte Darstellung für Listen-Views."""

    id: UUID
    server_id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    total_processed: int
    total_invalid: int
    resource_types: list[str]
    test_report: dict | None = None
    model_config = ConfigDict(from_attributes=True)


class PerResourceStats(BaseModel):
    """Statistik pro Ressource-Typ innerhalb eines Runs."""

    resource_type: str
    processed: int
    invalid: int
    invalid_rate: float = Field(
        description="invalid / processed, 0.0 wenn processed == 0"
    )


class ValidationRunDetail(ValidationRunListItem):
    """Volle Run-Details inkl. Aufschlüsselung pro Ressource-Typ."""

    error_message: str | None
    per_resource_stats: list[PerResourceStats] = []
    elapsed_seconds: int | None = None


class PaginatedRuns(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[ValidationRunListItem]


# ---------------------------------------------------------------------------
# Read schemas — Invalid Resources
# ---------------------------------------------------------------------------


class IssueDetail(BaseModel):
    rule: str
    severity: str
    message: str


class InvalidResourceRead(BaseModel):
    id: UUID
    run_id: str
    server_base_url: str
    resource_type: str
    resource_id: str
    issues: list[str]
    issues_detail: list[IssueDetail] = []
    metrics: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedInvalidResources(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[InvalidResourceRead]


# ---------------------------------------------------------------------------
# Summary / Heatmap
# ---------------------------------------------------------------------------


class RuleViolationCount(BaseModel):
    rule: str
    severity: str
    count: int


class ResourceTypeSummary(BaseModel):
    resource_type: str
    total_invalid: int
    by_rule: list[RuleViolationCount]


class RunSummary(BaseModel):
    """
    Summary of a run's validation results.

    Attributes:
        run_id: Unique run identifier.
        total_processed: Number of processed resources.
        total_invalid: Number of invalid resources.
        overall_invalid_rate: Fraction of invalid resources.
        by_resource_type: Details by resource type.
    """

    run_id: UUID
    total_processed: int
    total_invalid: int
    overall_invalid_rate: float
    by_resource_type: list[ResourceTypeSummary]
