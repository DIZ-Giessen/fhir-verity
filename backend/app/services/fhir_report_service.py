"""
FHIR Report Service

Writes the result of a completed validation run as FHIR R4 resources:
  - TestScript : one per resource type and rule configuration. Reused across
                 runs; its version is a hash of the configuration.
  - TestReport : one per resource type and run, with the result per rule.
  - List       : one per run, referencing the TestReports of that run.

References:
  - TestScript R4:  https://hl7.org/fhir/R4/testscript.html
  - TestReport R4:  https://hl7.org/fhir/R4/testreport.html
  - List R4:        https://hl7.org/fhir/R4/list.html
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.validation_run import ValidationRun
from app.services.config_service import get_config_for_run
from app.services.validation_rules import VALIDATORS
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.fhir_auth import build_httpx_auth

logger = logging.getLogger(__name__)
settings = get_settings()

CANONICAL_BASE = settings.VERITY_CANONICAL_BASE.rstrip("/")
PUBLISHER = settings.FHIR_REPORT_PUBLISHER

RUN_ID_SYSTEM = f"{CANONICAL_BASE}/sid/run-id"
TEST_REPORT_ID_SYSTEM = f"{CANONICAL_BASE}/sid/test-report"

# Part of the TestScript version hash. Increase when the structure of the
# generated TestScript changes, so servers get a new version.
TEST_SCRIPT_LAYOUT = 1

FHIR_HEADERS = {
    "Content-Type": "application/fhir+json",
    "Accept": "application/fhir+json",
}


def _extension_url(name: str) -> str:
    return f"{CANONICAL_BASE}/StructureDefinition/{name}"


def _fhir_instant(dt: datetime | None = None) -> str:
    return (dt or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _score(total_processed: int, total_invalid: int) -> float:
    """Share of valid resources in percent (0–100)."""
    if total_processed == 0:
        return 100.0
    return round((total_processed - total_invalid) / total_processed * 100, 2)


def _extract_resource_types(run: ValidationRun) -> list[str]:
    rt = run.resource_types
    types = rt if isinstance(rt, list) else [rt]
    if "All" in types:
        return list(VALIDATORS.keys())
    return types


# ---------------------------------------------------------------------------
# Data from Verity's database
# ---------------------------------------------------------------------------


async def aggregate_violations(
    run_id: str,
    resource_type: str,
    db: AsyncSession,
) -> dict[str, int]:
    """
    Number of resources per rule that failed in this run, from the metrics
    column of invalid_resources ({"rule_key": false, ...}).
    """
    query = text(
        """
        SELECT
            kv.key   AS rule_key,
            COUNT(*) AS violation_count
        FROM invalid_resources ir,
             jsonb_each(ir.metrics::jsonb) AS kv(key, value)
        WHERE ir.last_seen_run_id = :run_id
          AND ir.resource_type    = :resource_type
          AND kv.key           != 'issues_detail'
          AND kv.value::text    = 'false'
        GROUP BY kv.key
        """
    )
    result = await db.execute(
        query, {"run_id": run_id, "resource_type": resource_type}
    )
    return {row.rule_key: row.violation_count for row in result.fetchall()}


async def get_active_rules(
    server_id: str,
    resource_type: str,
    db: AsyncSession,
) -> dict[str, dict]:
    """Enabled rules of the effective config (global defaults + server override)."""
    rules = await get_config_for_run(server_id, resource_type, db)
    return {k: v for k, v in rules.items() if v.get("enabled", False)}


# ---------------------------------------------------------------------------
# TestScript
# ---------------------------------------------------------------------------


def test_script_url(resource_type: str) -> str:
    return f"{CANONICAL_BASE}/TestScript/{resource_type}"


def test_script_version(resource_type: str, active_rules: dict[str, dict]) -> str:
    """Short hash over everything that ends up in the TestScript."""
    content = {
        "layout": TEST_SCRIPT_LAYOUT,
        "resource_type": resource_type,
        "rules": {
            key: {
                "description": rule.get("description", key),
                "category": rule.get("category", "general"),
                "severity": rule.get("severity", "warning"),
                "pattern": rule.get("pattern"),
            }
            for key, rule in sorted(active_rules.items())
        },
    }
    digest = hashlib.sha256(
        json.dumps(content, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return digest[:12]


def build_test_script(
    resource_type: str,
    active_rules: dict[str, dict],
) -> dict[str, Any]:
    """
    TestScript describing the enabled rules for one resource type. It holds
    no server- or run-specific data, so the same configuration always yields
    the same url and version.
    """
    tests = []
    for rule_key, rule_def in sorted(active_rules.items()):
        description = rule_def.get("description", rule_key)
        category = rule_def.get("category", "general")
        severity = rule_def.get("severity", "warning")
        tests.append(
            {
                "id": rule_key,
                "name": rule_key,
                "description": description,
                "action": [
                    {
                        "assert": {
                            "label": f"{category}:{severity}",
                            "description": description,
                            # Only error rules make the TestReport fail.
                            "warningOnly": severity != "error",
                        }
                    }
                ],
            }
        )

    return {
        "resourceType": "TestScript",
        "url": test_script_url(resource_type),
        "version": test_script_version(resource_type, active_rules),
        "name": f"Verity{resource_type}",
        "title": f"FHIR Verity – {resource_type}",
        "status": "active",
        "experimental": False,
        "date": _fhir_instant(),
        "publisher": PUBLISHER,
        "description": (
            f"Data quality rules applied by FHIR Verity to {resource_type} resources."
        ),
        "setup": {
            "action": [
                {
                    "operation": {
                        "type": {
                            "system": "http://terminology.hl7.org/CodeSystem/testscript-operation-codes",
                            "code": "search",
                        },
                        "resource": resource_type,
                        "description": f"Read all {resource_type} resources",
                        "accept": "json",
                        "encodeRequestUrl": True,
                    }
                }
            ]
        },
        "test": tests,
    }


async def find_test_script(
    url: str,
    version: str,
    base_url: str,
    client: httpx.AsyncClient,
) -> str | None:
    """Server id of an existing TestScript with this url and version, if any."""
    try:
        resp = await client.get(
            f"{base_url}/TestScript",
            params={"url": url, "version": version, "_elements": "id"},
            headers=FHIR_HEADERS,
        )
        resp.raise_for_status()
        entries = resp.json().get("entry") or []
        if entries:
            return entries[0].get("resource", {}).get("id")
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("TestScript lookup on %s failed: %s", base_url, exc)
    return None


# ---------------------------------------------------------------------------
# TestReport
# ---------------------------------------------------------------------------


def build_test_report(
    resource_type: str,
    run_id: str,
    test_script: dict[str, Any],
    test_script_id: str | None,
    active_rules: dict[str, dict],
    violations: dict[str, int],
    total_processed: int,
    total_invalid: int,
    started_at: datetime | None,
    finished_at: datetime | None,
) -> dict[str, Any]:
    """TestReport with one test per enabled rule. Fails if an error rule has violations."""
    issued = _fhir_instant(finished_at)

    test_results = []
    has_error_violation = False
    for rule_key, rule_def in sorted(active_rules.items()):
        description = rule_def.get("description", rule_key)
        severity = rule_def.get("severity", "warning")
        category = rule_def.get("category", "general")
        count = violations.get(rule_key, 0)
        if count and severity == "error":
            has_error_violation = True

        test_results.append(
            {
                "name": rule_key,
                "description": description,
                "action": [
                    {
                        "assert": {
                            "result": "pass" if count == 0 else "fail",
                            "message": (
                                f"{count} {resource_type} resource(s) violate "
                                f"'{rule_key}'"
                            ),
                            "extension": [
                                {
                                    "url": _extension_url("violation-count"),
                                    "valueInteger": count,
                                },
                                {
                                    "url": _extension_url("rule-severity"),
                                    "valueCode": severity,
                                },
                                {
                                    "url": _extension_url("rule-category"),
                                    "valueCode": category,
                                },
                            ],
                        }
                    }
                ],
            }
        )

    if test_script_id:
        script_ref = {"reference": f"TestScript/{test_script_id}"}
    else:
        script_ref = {"display": f"{test_script['url']}|{test_script['version']}"}

    extensions = [
        {"url": _extension_url("total-processed"), "valueInteger": total_processed},
        {"url": _extension_url("total-invalid"), "valueInteger": total_invalid},
    ]
    if started_at and finished_at:
        extensions.append(
            {
                "url": _extension_url("elapsed-seconds"),
                "valueInteger": int((finished_at - started_at).total_seconds()),
            }
        )

    score = _score(total_processed, total_invalid)
    return {
        "resourceType": "TestReport",
        "extension": extensions,
        "identifier": {
            "system": TEST_REPORT_ID_SYSTEM,
            "value": f"{run_id}/{resource_type}",
        },
        "name": f"FHIR Verity – {resource_type} – {issued}",
        "status": "completed",
        "testScript": script_ref,
        "result": "fail" if has_error_violation else "pass",
        "score": score,
        "tester": PUBLISHER,
        "issued": issued,
        "setup": {
            "action": [
                {
                    "operation": {
                        "result": "pass",
                        "message": f"{total_processed} {resource_type} resources read",
                    }
                }
            ]
        },
        "test": test_results,
        "teardown": {
            "action": [
                {
                    "operation": {
                        "result": "pass",
                        "message": (
                            f"{total_processed - total_invalid}/{total_processed} "
                            f"valid ({score}%)"
                        ),
                    }
                }
            ]
        },
    }


# ---------------------------------------------------------------------------
# List (one per run)
# ---------------------------------------------------------------------------


def build_run_list(
    run: ValidationRun,
    test_report_ids: dict[str, str],
) -> dict[str, Any]:
    """List of the TestReports written for one run."""
    run_id = str(run.id)
    return {
        "resourceType": "List",
        "identifier": [{"system": RUN_ID_SYSTEM, "value": run_id}],
        "status": "current",
        "mode": "snapshot",
        "title": f"FHIR Verity run {run_id}",
        "date": _fhir_instant(run.finished_at),
        "source": {"display": PUBLISHER},
        "note": [
            {
                "text": (
                    f"{run.total_processed} resources validated, "
                    f"{run.total_invalid} invalid."
                )
            }
        ],
        "entry": [
            {"item": {"reference": f"TestReport/{report_id}", "display": rt}}
            for rt, report_id in test_report_ids.items()
        ],
    }


# ---------------------------------------------------------------------------
# Writing to the FHIR server
# ---------------------------------------------------------------------------


async def post_to_fhir(
    resource: dict,
    base_url: str,
    client: httpx.AsyncClient,
) -> str | None:
    """POST a resource; returns the server-assigned id, or None on failure."""
    resource_type = resource["resourceType"]
    try:
        resp = await client.post(
            f"{base_url}/{resource_type}", json=resource, headers=FHIR_HEADERS
        )
        resp.raise_for_status()
        server_id = resp.json().get("id")
        logger.info("Posted %s to %s, id %s", resource_type, base_url, server_id)
        return server_id
    except httpx.HTTPStatusError as exc:
        logger.error(
            "HTTP %s posting %s to %s: %s",
            exc.response.status_code,
            resource_type,
            base_url,
            exc.response.text[:300],
        )
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Error posting %s to %s: %s", resource_type, base_url, exc)
    return None


async def generate_and_post_reports(
    run: ValidationRun,
    server_base_url: str,
    server_id: str,
    auth_config: dict,
    db: AsyncSession,
    post_to_server: bool = True,
) -> None:
    """
    Build the reports of a completed run and, if enabled, write them to the
    FHIR server. A summary (ids, result, score, violation counts) is stored in
    ValidationRun.test_report either way.
    """
    run_id = str(run.id)
    base_url = server_base_url.rstrip("/")

    summary: dict[str, Any] = {
        "run_id": run_id,
        "generated_at": _fhir_instant(),
        "posted_to_server": post_to_server,
        "test_scripts": {},
        "test_reports": {},
        "run_list": None,
        "has_errors": False,
    }
    test_report_ids: dict[str, str] = {}

    timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)
    async with httpx.AsyncClient(
        timeout=timeout, auth=build_httpx_auth(auth_config)
    ) as client:
        for resource_type in _extract_resource_types(run):
            active_rules = await get_active_rules(server_id, resource_type, db)
            if not active_rules:
                logger.warning("No active rules for %s, no report", resource_type)
                continue

            violations = await aggregate_violations(run_id, resource_type, db)
            per_stats = (run.per_resource_stats or {}).get(resource_type, {})

            test_script = build_test_script(resource_type, active_rules)
            ts_id: str | None = None
            reused = False
            if post_to_server:
                ts_id = await find_test_script(
                    test_script["url"], test_script["version"], base_url, client
                )
                reused = ts_id is not None
                if not reused:
                    ts_id = await post_to_fhir(test_script, base_url, client)

            summary["test_scripts"][resource_type] = {
                "server_id": ts_id,
                "url": test_script["url"],
                "version": test_script["version"],
                "reused": reused,
            }

            test_report = build_test_report(
                resource_type=resource_type,
                run_id=run_id,
                test_script=test_script,
                test_script_id=ts_id,
                active_rules=active_rules,
                violations=violations,
                total_processed=per_stats.get("processed", 0),
                total_invalid=per_stats.get("invalid", 0),
                started_at=run.started_at,
                finished_at=run.finished_at,
            )
            tr_id = (
                await post_to_fhir(test_report, base_url, client)
                if post_to_server
                else None
            )
            if tr_id:
                test_report_ids[resource_type] = tr_id

            summary["test_reports"][resource_type] = {
                "server_id": tr_id,
                "result": test_report["result"],
                "score": test_report["score"],
                "violation_counts": violations,
            }
            if test_report["result"] == "fail":
                summary["has_errors"] = True

        if test_report_ids:
            list_id = await post_to_fhir(
                build_run_list(run, test_report_ids), base_url, client
            )
            summary["run_list"] = {"server_id": list_id}

    try:
        async with AsyncSessionLocal() as write_db:
            await write_db.execute(
                sa_update(ValidationRun)
                .where(ValidationRun.id == run.id)
                .values(test_report=summary)
            )
            await write_db.commit()
        logger.info("FHIR reports for run %s stored", run_id)
    except Exception as exc:
        logger.error("Failed to store report summary for run %s: %s", run_id, exc)
