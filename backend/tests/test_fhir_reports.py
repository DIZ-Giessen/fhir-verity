import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services import fhir_report_service as reports

RULES = {
    "name_forbidden": {
        "enabled": True,
        "severity": "error",
        "category": "privacy",
        "description": "Checks whether the field 'name' is present.",
    },
    "gender_required": {
        "enabled": True,
        "severity": "warning",
        "category": "completeness",
        "description": "Patient.gender must be present.",
    },
}


def _report(violations: dict[str, int]):
    now = datetime.now(timezone.utc)
    script = reports.build_test_script("Patient", RULES)
    return reports.build_test_report(
        resource_type="Patient",
        run_id="run-1",
        test_script=script,
        test_script_id="ts-1",
        active_rules=RULES,
        violations=violations,
        total_processed=100,
        total_invalid=sum(violations.values()),
        started_at=now - timedelta(seconds=10),
        finished_at=now,
    )


def test_test_script_version_is_stable():
    assert reports.test_script_version("Patient", RULES) == reports.test_script_version(
        "Patient", dict(reversed(RULES.items()))
    )


def test_test_script_version_changes_with_rules():
    changed = {**RULES, "gender_required": {**RULES["gender_required"], "severity": "error"}}
    assert reports.test_script_version("Patient", RULES) != reports.test_script_version(
        "Patient", changed
    )


def test_test_script_has_no_server_or_run_data():
    script = reports.build_test_script("Patient", RULES)
    assert script["url"].endswith("/TestScript/Patient")
    assert "localhost" not in str(script)
    assert "id" not in script


def test_only_error_rules_fail_the_report():
    assert _report({"gender_required": 5})["result"] == "pass"
    assert _report({"name_forbidden": 1})["result"] == "fail"


def test_score_is_share_of_valid_resources():
    assert _report({"gender_required": 5})["score"] == 95.0


def test_run_list_references_test_reports():
    run = SimpleNamespace(
        id=uuid.uuid4(),
        finished_at=datetime.now(timezone.utc),
        total_processed=10,
        total_invalid=1,
    )
    run_list = reports.build_run_list(run, {"Patient": "tr-1", "Encounter": "tr-2"})
    assert run_list["resourceType"] == "List"
    assert run_list["mode"] == "snapshot"
    assert run_list["identifier"][0]["value"] == str(run.id)
    assert [e["item"]["reference"] for e in run_list["entry"]] == [
        "TestReport/tr-1",
        "TestReport/tr-2",
    ]
