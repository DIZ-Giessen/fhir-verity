"""
The rule registry must report exactly what the previous engine reported for
the rules that existed before it. tests/fixtures/legacy_results.json was
recorded with that engine; the only changes made to it are whitespace and
two typos in messages ("containsa", a missing space before "must follow").
"""

import json
from pathlib import Path

import pytest

from app.services.rules import REGISTRY, effective_rules
from app.services.validation_rules import VALIDATORS
from engine_harness import run_validator
from fixtures.legacy_resources import (
    PATIENTS_WITH_CONDITION,
    PATIENTS_WITH_OBSERVATION,
    RESOURCES,
)

LEGACY = json.loads(
    (Path(__file__).parent / "fixtures" / "legacy_results.json").read_text(encoding="utf-8")
)


def legacy_rule_keys(resource_type: str) -> set[str]:
    return {
        issue["rule"]
        for result in LEGACY[resource_type].values()
        for issue in result["issues"]
    }


def legacy_config(resource_type: str) -> dict:
    keys = legacy_rule_keys(resource_type)
    config = effective_rules(resource_type)
    for key, rule in config.items():
        rule["enabled"] = key in keys
    return config


@pytest.mark.parametrize("resource_type", sorted(LEGACY))
def test_registry_reports_like_the_previous_engine(resource_type):
    found = run_validator(
        VALIDATORS[resource_type],
        RESOURCES[resource_type],
        legacy_config(resource_type),
        {"Observation": PATIENTS_WITH_OBSERVATION, "Condition": PATIENTS_WITH_CONDITION},
    )
    assert found == LEGACY[resource_type]


@pytest.mark.parametrize("resource_type", sorted(LEGACY))
def test_previous_rules_keep_key_severity_and_default(resource_type):
    previously_enabled = {
        "Patient": {
            "name_forbidden", "address_forbidden", "telecom_forbidden", "photo_forbidden",
            "pseudonym_format_check", "identifier_pseudonym_check", "identifier_required",
            "birthdate_required", "gender_required", "birthdate_not_future",
            "birthdate_plausible_range",
        },
        "Encounter": {
            "pseudonym_format_check", "status_required", "class_required", "subject_required",
            "period_start_required", "period_end_after_start", "period_plausible_duration",
            "subject_reference_format",
        },
        "Condition": {
            "note_cleartext_check", "code_required", "subject_required",
            "subject_reference_format",
        },
        "Observation": {
            "status_required", "code_required", "subject_required", "effective_required",
            "value_present", "effective_not_future", "subject_reference_format",
        },
        "Medication": {"code_required", "code_coding_present", "ingredient_item_check"},
        "MedicationRequest": {
            "status_required", "intent_required", "medication_required", "subject_required",
            "authored_on_required", "authored_not_future", "subject_reference_format",
        },
        "MedicationAdministration": {
            "status_required", "medication_required", "subject_required", "effective_required",
            "effective_not_future", "effective_period_end_after_start",
            "subject_reference_format",
        },
        "Procedure": {
            "note_cleartext_check", "status_required", "code_required", "subject_required",
            "performed_required", "subject_reference_format",
        },
        "DiagnosticReport": {
            "note_cleartext_check", "status_required", "code_required", "subject_required",
            "subject_reference_format",
        },
    }[resource_type]
    for key in legacy_rule_keys(resource_type):
        rule = REGISTRY.get(resource_type, key)
        assert rule is not None, key
        assert rule.enabled == (key in previously_enabled), key
    for key in previously_enabled:
        assert REGISTRY.get(resource_type, key).enabled, key
