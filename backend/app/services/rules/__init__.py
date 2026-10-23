"""
Validation rules, one module per FHIR resource type. Importing this package
registers every rule; the import order below is the order of the resource
types in the UI and in a run.
"""

from app.services.rules import (  # noqa: F401
    patient,
    encounter,
    condition,
    observation,
    medication,
    medication_request,
    medication_administration,
    medication_statement,
    procedure,
    diagnostic_report,
    service_request,
    specimen,
    consent,
    imaging_study,
)
from app.services.rules.registry import (
    CATEGORIES,
    REGISTRY,
    Rule,
    active_rules,
    default_rules,
    effective_rules,
    evaluate,
)

RESOURCE_TYPES: list[str] = REGISTRY.resource_types()

__all__ = [
    "CATEGORIES",
    "REGISTRY",
    "RESOURCE_TYPES",
    "Rule",
    "active_rules",
    "default_rules",
    "effective_rules",
    "evaluate",
]
