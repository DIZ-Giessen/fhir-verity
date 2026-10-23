"""
Runs a validator over in-memory resources, without database or FHIR server,
and returns what it would have stored: {resource_id: {"issues", "metrics"}}.
"""

import asyncio
import sys
import uuid

import httpx


def run_validator(
    validator_class,
    resources: list[dict],
    config: dict,
    patients_with: dict[str, set[str]] | None = None,
) -> dict[str, dict]:
    patients_with = patients_with or {}
    found: dict[str, dict] = {}

    validator = validator_class(
        httpx.AsyncClient(), "https://fhir.example.org/fhir", server_id=uuid.uuid4()
    )

    async def iter_pages(resource_type, run_id, db):
        yield [{"resource": r} for r in resources]

    async def fetch_total(resource_type):
        return 0

    async def save_invalid(run_id, resource_type, resource_id, issues, metrics, db):
        found[resource_id] = {"issues": issues, "metrics": metrics}

    async def noop(*args, **kwargs):
        return None

    async def linked(patient_ids, resource_type):
        return set(patient_ids) & patients_with.get(resource_type, set())

    async def load_config(server_id, resource_type, db):
        return config

    validator.iter_pages = iter_pages
    validator._fetch_total = fetch_total
    validator.save_invalid = save_invalid
    validator._update_run_counters = noop
    validator._emit_progress = noop
    validator._check_linked_resources = linked

    module = sys.modules[validator_class.__module__]
    original = module.get_config_for_run
    module.get_config_for_run = load_config
    try:
        asyncio.run(validator.validate_and_save(uuid.uuid4(), None))
    finally:
        module.get_config_for_run = original
    return found
