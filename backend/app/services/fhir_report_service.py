"""
FHIR Report Service

Generates and posts three FHIR R4 resources after each completed validation run:
  - TestScript  : one per resource type — describes which rules were tested
  - TestReport  : one per resource type — results with counts and pass/fail per rule
  - VerificationResult : one per run — overall run summary

References:
  - TestScript R4:          https://hl7.org/fhir/R4/testscript.html
  - TestReport R4:          https://hl7.org/fhir/R4/testreport.html
  - VerificationResult R4:  https://hl7.org/fhir/R4/verificationresult.html
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text, update as sa_update, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.validation_run import ValidationRun
from app.models.validation_config import ValidationConfig
from app.services.validation_rules import VALIDATORS
from app.core.database import AsyncSessionLocal
from app.services.fhir_auth import build_httpx_auth

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Naming System base used for all identifiers
# ---------------------------------------------------------------------------
NAMING_SYSTEM_BASE = "http://dizfhir.med.uni-giessen.de/NamingSystem/validierung"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    """ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _overall_result(violations_by_rule: dict[str, dict]) -> str:
    """
    Determine overall pass/fail based on severity of violations.
    Returns 'pass' only if no error-severity rule has any violations.
    """
    for rule_data in violations_by_rule.values():
        if rule_data.get("severity") == "error" and rule_data.get("count", 0) > 0:
            return "fail"
    return "pass"


def _score(total_processed: int, total_invalid: int) -> float:
    """
    Compute quality score as percentage of valid resources.
    Returns value between 0.0 and 1.0.
    """
    if total_processed == 0:
        return 1.0
    valid = total_processed - total_invalid
    return round(valid / total_processed, 6)


# ---------------------------------------------------------------------------
# Step 1 — Aggregate violations from invalid_resources
# ---------------------------------------------------------------------------


async def aggregate_violations(
    run_id: str,
    resource_type: str,
    db: AsyncSession,
) -> dict[str, int]:
    """
    Query invalid_resources and count how many resources violated each rule.

    The metrics column is a JSONB object like:
        { "birthdate_required": false, "gender_required": true, ... }

    We expand it and count false values per rule key.

    Returns: { "rule_key": violation_count }
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
        ORDER BY violation_count DESC
    """
    )

    result = await db.execute(
        query,
        {"run_id": run_id, "resource_type": resource_type},
    )
    rows = result.fetchall()
    return {row.rule_key: row.violation_count for row in rows}


async def get_processed_count(
    run_id: str,
    resource_type: str,
    db: AsyncSession,
) -> int:
    """Count total resources processed for a given resource type in this run. and accurency"""
    query = text(
        """
        SELECT COUNT(DISTINCT resource_id) AS cnt
        FROM invalid_resources
        WHERE last_seen_run_id = :run_id AND resource_type = :resource_type
    """
    )
    result = await db.execute(query, {"run_id": run_id, "resource_type": resource_type})
    row = result.fetchone()
    # Note: this only counts invalid resources. We need total_processed from the run.
    # We return invalid count here; caller uses ValidationRun.total_processed for totals.
    return row.cnt if row else 0


# ---------------------------------------------------------------------------
# Step 2 — Load active rules for a resource type from validation_configs
# ---------------------------------------------------------------------------


async def get_active_rules(
    server_id: str,
    resource_type: str,
    db: AsyncSession,
) -> dict[str, dict]:
    """
    Load the effective validation config for a resource type.
    Server-specific config takes precedence over global defaults.
    Returns only enabled rules.
    """
    # Global default
    stmt_global = select(ValidationConfig).where(
        ValidationConfig.server_id.is_(None),
        ValidationConfig.resource_type == resource_type,
    )
    result = await db.execute(stmt_global)
    global_config = result.scalar_one_or_none()
    base_rules: dict = dict(global_config.rules) if global_config else {}

    # Server-specific override
    stmt_server = select(ValidationConfig).where(
        ValidationConfig.server_id == server_id,
        ValidationConfig.resource_type == resource_type,
    )
    result = await db.execute(stmt_server)
    server_config = result.scalar_one_or_none()

    if server_config:
        base_rules = {**base_rules, **server_config.rules}

    # Return only enabled rules
    return {k: v for k, v in base_rules.items() if v.get("enabled", False)}


# ---------------------------------------------------------------------------
# Step 3 — Build TestScript (what was tested)
# ---------------------------------------------------------------------------


def build_test_script(
    resource_type: str,
    active_rules: dict[str, dict],
    server_base_url: str,
) -> dict[str, Any]:
    """
    Build a FHIR R4 TestScript resource describing which rules were checked
    for a given resource type.

    One TestScript is created per resource type. It is designed to be
    reusable across runs (same rules = same TestScript content).

    Structure:
      - setup.action: verifies FHIR server reachability
      - test[]: one test per active rule, each with one assert action
    """
    script_id = str(uuid.uuid4())
    now = _utc_now()

    tests = []
    for rule_key, rule_def in active_rules.items():
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
                            # The label encodes category and severity for downstream parsing
                            "label": f"{category}:{severity}",
                            "description": description,
                            # warningOnly=true for warning-severity rules so the TestReport
                            # result is not automatically 'fail' on warnings
                            "warningOnly": severity in ("warning", "info"),
                        }
                    }
                ],
            }
        )

    return {
        "resourceType": "TestScript",
        "id": script_id,
        "url": (f"{NAMING_SYSTEM_BASE}/TestScript/{resource_type}"),
        "identifier": {
            "system": f"{NAMING_SYSTEM_BASE}/testscript",
            "value": f"Verity_{resource_type}",
        },
        "version": "1.0",
        "name": f"Verity_Validierung_{resource_type}",
        "title": f"FHIR Verity Validierung – {resource_type}",
        "status": "active",
        "experimental": False,
        "date": now,
        "publisher": "FHIR Verity – DIZ Gießen.",
        "description": (
            f"Automatisch generiertes TestScript für die Validierung "
            f"von {resource_type}-Ressourcen durch FHIR Verity. "
            f"Ziel-Server: {server_base_url}"
        ),
        "purpose": (
            "Beschreibt die Gesamtheit der aktivierten Validierungsregeln "
            "für diesen Ressourcentyp basierend auf der aktuellen "
            "und server-spezifische Konfiguration."
        ),
        "setup": {
            "action": [
                {
                    "operation": {
                        "type": {
                            "system": "http://terminology.hl7.org/CodeSystem/testscript-operation-codes",
                            "code": "read",
                        },
                        "resource": resource_type,
                        "description": (
                            f"Lade {resource_type}-Bundle vom FHIR-Server: "
                            f"{server_base_url}/{resource_type}"
                        ),
                        "accept": "json",
                        "url": f"{server_base_url}/{resource_type}",
                    }
                }
            ]
        },
        "test": tests,
    }


# ---------------------------------------------------------------------------
# Step 4 — Build TestReport (results)
# ---------------------------------------------------------------------------


def build_test_report(
    resource_type: str,
    run_id: str,
    test_script_id: str,
    test_script_url: str,
    active_rules: dict[str, dict],
    violations: dict[str, int],
    total_processed: int,
    total_invalid: int,
    server_base_url: str,
    started_at: datetime,
    finished_at: datetime | None,
) -> dict[str, Any]:
    """
    Build a FHIR R4 TestReport resource with per-rule results.

    Each active rule becomes one test entry. Violations are counted
    from the aggregated invalid_resources query.

    The score field represents the proportion of valid resources (0.0–1.0).
    """
    report_id = str(uuid.uuid4())
    now = _utc_now()
    issued = finished_at.strftime("%Y-%m-%dT%H:%M:%S+00:00") if finished_at else now

    # Build test results — one per active rule
    test_results = []
    has_error_violation = False

    for rule_key, rule_def in active_rules.items():
        description = rule_def.get("description", rule_key)
        severity = rule_def.get("severity", "warning")
        category = rule_def.get("category", "general")
        count = violations.get(rule_key, 0)
        passed = count == 0

        if not passed and severity == "error":
            has_error_violation = True

        result_value = "pass" if passed else "fail"
        message = (
            f"0 {resource_type}-Ressourcen verletzt Regel '{rule_key}'"
            if passed
            else (
                f"{count} {resource_type}-Ressource(n) verletzt Regel '{rule_key}': "
                f"{description}"
            )
        )

        test_results.append(
            {
                "name": rule_key,
                "description": f"[{category}:{severity}] {description}",
                "action": [
                    {
                        "assert": {
                            "result": result_value,
                            "message": message,
                            # Extension: stores the raw violation count for dashboard use
                            "extension": [
                                {
                                    "url": f"{NAMING_SYSTEM_BASE}/extension/violation-count",
                                    "valueInteger": count,
                                },
                                {
                                    "url": f"{NAMING_SYSTEM_BASE}/extension/severity",
                                    "valueCode": severity,
                                },
                                {
                                    "url": f"{NAMING_SYSTEM_BASE}/extension/category",
                                    "valueCode": category,
                                },
                            ],
                        }
                    }
                ],
            }
        )

    overall_result = "fail" if has_error_violation else "pass"
    quality_score = _score(total_processed, total_invalid)
    quality_score_percent = round(quality_score * 100, 2)

    elapsed_s: int | None = None
    if finished_at and started_at:
        elapsed_s = int((finished_at - started_at).total_seconds())

    return {
        "resourceType": "TestReport",
        "id": report_id,
        "identifier": {
            "system": f"{NAMING_SYSTEM_BASE}/testreport",
            "value": f"{run_id}_{resource_type}",
        },
        "name": (f"Verity_Validierung_{resource_type}_{issued}"),
        "status": "completed",
        "testScript": {
            "reference": f"TestScript/{test_script_id}",
            "identifier": {
                "system": f"{NAMING_SYSTEM_BASE}/testscript",
                "value": f"Verity_{resource_type}",
            },
        },
        "result": overall_result,
        # score: 0.0–100.0 as per FHIR spec (decimal percentage)
        "score": quality_score_percent,
        "tester": "FHIR Verity – DIZ Gießen.",
        "issued": issued,
        # Extensions at root level for run metadata
        "extension": [
            {
                "url": f"{NAMING_SYSTEM_BASE}/extension/run-id",
                "valueString": run_id,
            },
            {
                "url": f"{NAMING_SYSTEM_BASE}/extension/resource-type",
                "valueCode": resource_type,
            },
            {
                "url": f"{NAMING_SYSTEM_BASE}/extension/total-processed",
                "valueInteger": total_processed,
            },
            {
                "url": f"{NAMING_SYSTEM_BASE}/extension/total-invalid",
                "valueInteger": total_invalid,
            },
            {
                "url": f"{NAMING_SYSTEM_BASE}/extension/quality-score",
                "valueDecimal": quality_score,
            },
            {
                "url": f"{NAMING_SYSTEM_BASE}/extension/elapsed-seconds",
                "valueInteger": elapsed_s,
            },
        ],
        "setup": {
            "action": [
                {
                    "operation": {
                        "result": "pass",
                        "message": (
                            f"Bundle mit {total_processed} {resource_type}-Ressourcen "
                            f"erfolgreich geladen von {server_base_url}/{resource_type}"
                        ),
                    }
                },
                {
                    "operation": {
                        "result": "pass",
                        "message": f"{total_invalid} invalide Ressourcen in Datenbank gespeichert",
                    }
                },
            ]
        },
        "test": test_results,
        "teardown": {
            "action": [
                {
                    "operation": {
                        "result": "pass",
                        "message": (
                            f"Validierung abgeschlossen. "
                            f"Qualitätsscore: {quality_score_percent}% "
                            f"({total_processed - total_invalid}/{total_processed} valide). "
                            f"Laufzeit: {elapsed_s}s."
                        ),
                    }
                }
            ]
        },
    }


# ---------------------------------------------------------------------------
# Step 5 — Build VerificationResult (overall run)
# ---------------------------------------------------------------------------


def build_verification_result(
    run: ValidationRun,
    server_base_url: str,
    test_report_references: list[str],
    has_errors: bool,
) -> dict[str, Any]:
    """
    Build a FHIR R4 VerificationResult for the entire validation run only for the version 4.0.

    status codes (from http://hl7.org/fhir/R4/valueset-verificationresult-status.html):
      attested     — data has been declared true
      validated    — data has been confirmed correct
      in-process   — currently being validated
      req-revalid  — requires re-validation (errors found)
      val-fail     — validation failed critically
      reval-fail   — re-validation failed
    """
    now = _utc_now()
    issued = (
        run.finished_at.strftime("%Y-%m-%dT%H:%M:%S+00:00") if run.finished_at else now
    )
    issued_date = (
        run.finished_at.strftime("%Y-%m-%d")
        if run.finished_at
        else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )

    status = "req-revalid" if has_errors else "validated"
    failure_action_code = "warn" if not has_errors else "fatal"
    failure_action_display = "Warning" if not has_errors else "Fatal"

    quality_score = _score(run.total_processed, run.total_invalid)

    # target: links to the validated resource endpoint + all generated TestReports
    target_locations = [
        f"{server_base_url}/{rt}" for rt in _extract_resource_types(run)
    ]
    target_locations.extend(test_report_references)

    elapsed_s: int | None = None
    if run.finished_at and run.started_at:
        elapsed_s = int((run.finished_at - run.started_at).total_seconds())

    return {
        "resourceType": "VerificationResult",
        "id": str(uuid.uuid4()),
        "meta": {
            "tag": [
                {
                    "system": "http://fhir-verity.mii.de/tags",
                    "code": "automated-validation",
                    "display": "Automatische FHIR-Validierung durch FHIR Verity",
                }
            ]
        },
        "targetLocation": target_locations,
        "need": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/need",
                    "code": "periodic",
                    "display": "Periodic",
                }
            ]
        },
        "status": status,
        "statusDate": issued,
        "validationType": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/validation-type",
                    "code": "primary",
                    "display": "Primary Source",
                }
            ]
        },
        "validationProcess": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/validation-process",
                        "code": "edit-check",
                        "display": "Edit Check",
                    }
                ],
                "text": "Regelbasierte FHIR-Validierung durch FHIR Verity",
            }
        ],
        "failureAction": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/failure-action",
                    "code": failure_action_code,
                    "display": failure_action_display,
                }
            ]
        },
        "primarySource": [
            {
                "who": {"display": "FHIR Verity DIZ Gießen"},
                "type": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/primary-source-type",
                                "code": "prim",
                                "display": "Primary Source",
                            }
                        ]
                    }
                ],
                "validationDate": issued,
                "canPushUpdates": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/can-push-updates",
                            "code": "specific",
                            "display": "Specific requested changes only",
                        }
                    ]
                },
            }
        ],
        "attestation": {
            "who": {"display": "FHIR Verity – DIZ Gießen Automatische Validierung"},
            "communicationMethod": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/verificationresult-communication-method",
                        "code": "electronic",
                        "display": "Electronic",
                    }
                ]
            },
            "date": issued_date,
            "sourceIdentityCertificate": f"run_id:{run.id}",
        },
        # Extensions for dashboard use
        "extension": [
            {
                "url": f"{NAMING_SYSTEM_BASE}/extension/run-id",
                "valueString": str(run.id),
            },
            {
                "url": f"{NAMING_SYSTEM_BASE}/extension/total-processed",
                "valueInteger": run.total_processed,
            },
            {
                "url": f"{NAMING_SYSTEM_BASE}/extension/total-invalid",
                "valueInteger": run.total_invalid,
            },
            {
                "url": f"{NAMING_SYSTEM_BASE}/extension/quality-score",
                "valueDecimal": quality_score,
            },
            {
                "url": f"{NAMING_SYSTEM_BASE}/extension/elapsed-seconds",
                "valueInteger": elapsed_s,
            },
            {
                "url": f"{NAMING_SYSTEM_BASE}/extension/resource-types",
                "valueString": ",".join(_extract_resource_types(run)),
            },
            {
                "url": f"{NAMING_SYSTEM_BASE}/extension/server-base-url",
                "valueUri": server_base_url,
            },
        ],
    }


def _extract_resource_types(run: ValidationRun) -> list[str]:
    """Extract the list of resource types from a validation run."""
    rt = run.resource_types
    if isinstance(rt, list):
        return rt
    return [rt]


# ---------------------------------------------------------------------------
# Step 6 — POST to FHIR server
# ---------------------------------------------------------------------------


async def post_to_fhir(
    resource: dict,
    resource_type: str,
    base_url: str,
    client: httpx.AsyncClient,
) -> str | None:
    """
    POST a FHIR resource to the server.
    Returns the server-assigned ID on success, None on failure.
    """
    url = f"{base_url.rstrip('/')}/{resource_type}"
    headers = {
        "Content-Type": "application/fhir+json",
        "Accept": "application/fhir+json",
    }

    try:
        resp = await client.post(url, json=resource, headers=headers)
        resp.raise_for_status()
        created = resp.json()
        server_id = created.get("id")
        logger.info(
            "Posted %s to %s — server ID: %s",
            resource_type,
            base_url,
            server_id,
        )
        return server_id
    except httpx.HTTPStatusError as exc:
        logger.error(
            "HTTP %s posting %s to %s: %s",
            exc.response.status_code,
            resource_type,
            base_url,
            exc.response.text[:300],
        )
        return None
    except Exception as exc:
        logger.error("Error posting %s to %s: %s", resource_type, base_url, exc)
        return None


# ---------------------------------------------------------------------------
# Step 7 — Orchestrator: generate and post all reports for a completed run
# ---------------------------------------------------------------------------


async def generate_and_post_reports(
    run: ValidationRun,
    server_base_url: str,
    server_id: str,
    auth_config: dict,
    db: AsyncSession,
) -> None:
    """
    Main entry point. Called after a validation run completes.

    For each resource type that was validated:
      1. Load active rules from validation_configs
      2. Aggregate violations from invalid_resources
      3. Build and POST TestScript
      4. Build and POST TestReport

    Then:
      5. Build and POST VerificationResult for the entire run

    All generated resource IDs are stored back in ValidationRun.test_report
    as a JSON summary for later retrieval.
    """
    run_id = str(run.id)
    resource_types = _extract_resource_types(run)

    # Filter out "All" if present

    if "All" in resource_types:
        resource_types = list(VALIDATORS.keys())

    test_report_refs: list[str] = []
    report_summary: dict[str, Any] = {
        "run_id": run_id,
        "generated_at": _utc_now(),
        "test_scripts": {},
        "test_reports": {},
        "verification_result": None,
    }

    has_any_error = False

    timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)
    auth = build_httpx_auth(auth_config)

    async with httpx.AsyncClient(timeout=timeout, auth=auth) as client:

        for resource_type in resource_types:

            logger.info(
                "Generating FHIR reports for run %s / %s", run_id, resource_type
            )

            # Load active rules
            active_rules = await get_active_rules(server_id, resource_type, db)
            if not active_rules:
                logger.warning(
                    "No active rules for %s — skipping report generation", resource_type
                )
                continue

            # Aggregate violations
            violations = await aggregate_violations(run_id, resource_type, db)

            # Per-resource statistics directly from the run object — no extra queries needed.
            # These values are written incrementally during validation in _update_run_counters.
            per_stats = (run.per_resource_stats or {}).get(resource_type, {})
            rt_processed = per_stats.get("processed", 0)
            rt_invalid = per_stats.get("invalid", 0)

            # Build TestScript
            test_script = build_test_script(
                resource_type=resource_type,
                active_rules=active_rules,
                server_base_url=server_base_url,
            )

            ts_server_id = await post_to_fhir(
                resource=test_script,
                resource_type="TestScript",
                base_url=server_base_url,
                client=client,
            )

            report_summary["test_scripts"][resource_type] = {
                "local_id": test_script["id"],
                "server_id": ts_server_id,
                "url": test_script["url"],
            }

            # Build TestReport
            test_report = build_test_report(
                resource_type=resource_type,
                run_id=run_id,
                test_script_id=ts_server_id or test_script["id"],
                test_script_url=test_script["url"],
                active_rules=active_rules,
                violations=violations,
                total_processed=rt_processed,
                total_invalid=rt_invalid,
                server_base_url=server_base_url,
                started_at=run.started_at,
                finished_at=run.finished_at,
            )

            tr_server_id = await post_to_fhir(
                resource=test_report,
                resource_type="TestReport",
                base_url=server_base_url,
                client=client,
            )

            tr_ref = (
                f"{server_base_url}/TestReport/{tr_server_id}"
                if tr_server_id
                else f"TestReport/{test_report['id']}"
            )
            test_report_refs.append(tr_ref)

            report_summary["test_reports"][resource_type] = {
                "local_id": test_report["id"],
                "server_id": tr_server_id,
                "result": test_report["result"],
                "score": test_report["score"],
                "violation_counts": violations,
            }

            # Track if any error-severity violation exists across all resource types
            for rule_key, rule_def in active_rules.items():
                if (
                    rule_def.get("severity") == "error"
                    and violations.get(rule_key, 0) > 0
                ):
                    has_any_error = True

        # Build VerificationResult for the entire run
        verification_result = build_verification_result(
            run=run,
            server_base_url=server_base_url,
            test_report_references=test_report_refs,
            has_errors=has_any_error,
        )

        vr_server_id = await post_to_fhir(
            resource=verification_result,
            resource_type="VerificationResult",
            base_url=server_base_url,
            client=client,
        )

        report_summary["verification_result"] = {
            "local_id": verification_result["id"],
            "server_id": vr_server_id,
            "status": verification_result["status"],
            "has_errors": has_any_error,
        }

    # Persist report summary back to the ValidationRun
    try:
        async with AsyncSessionLocal() as write_db:
            await write_db.execute(
                sa_update(ValidationRun)
                .where(ValidationRun.id == run.id)
                .values(test_report=report_summary)
            )
            await write_db.commit()

        logger.info(
            "FHIR reports generated and persisted for run %s. "
            "VerificationResult status: %s",
            run_id,
            verification_result["status"],
        )
    except Exception as exc:
        logger.error("Failed to persist report summary for run %s: %s", run_id, exc)
