import json
import re
from pathlib import Path

import pytest

from app.services.rules import CATEGORIES, REGISTRY, RESOURCE_TYPES, effective_rules, evaluate
from fixtures.rule_examples import FAILING, VALID, variant

LEGACY = json.loads(
    (Path(__file__).parent / "fixtures" / "legacy_results.json").read_text(encoding="utf-8")
)
LEGACY_RULES = {
    (rt, issue["rule"])
    for rt, results in LEGACY.items()
    for result in results.values()
    for issue in result["issues"]
}


def run_all_rules(resource_type: str, resource: dict) -> list[dict]:
    config = effective_rules(resource_type)
    for rule in config.values():
        rule["enabled"] = True
    rules = REGISTRY.for_type(resource_type)
    page = {r.key: {resource.get("id")} for r in rules if r.prepare}
    issues, _ = evaluate(resource, rules, config, page)
    return issues


@pytest.mark.parametrize("resource_type", RESOURCE_TYPES)
def test_valid_resource_passes_every_rule(resource_type):
    assert run_all_rules(resource_type, VALID[resource_type]) == []


@pytest.mark.parametrize("resource_type, key", sorted(FAILING))
def test_rule_reports_its_example(resource_type, key):
    resource = variant(VALID[resource_type], FAILING[(resource_type, key)])
    issues = run_all_rules(resource_type, resource)
    assert key in {i["rule"] for i in issues}, issues
    assert all(i["message"] for i in issues)


def test_every_rule_has_an_example():
    missing = [
        f"{r.resource_type}.{r.key}"
        for rt in RESOURCE_TYPES
        for r in REGISTRY.for_type(rt)
        if (rt, r.key) not in FAILING and (rt, r.key) not in LEGACY_RULES
    ]
    assert missing == []


def test_examples_refer_to_existing_rules():
    assert [k for k in FAILING if REGISTRY.get(*k) is None] == []


def test_new_rules_are_disabled_by_default():
    enabled_new = [
        f"{r.resource_type}.{r.key}"
        for rt in RESOURCE_TYPES
        for r in REGISTRY.for_type(rt)
        if r.enabled and (rt, r.key) not in LEGACY_RULES
    ]
    assert enabled_new == []


@pytest.mark.parametrize("resource_type", RESOURCE_TYPES)
def test_rule_metadata(resource_type):
    for r in REGISTRY.for_type(resource_type):
        assert re.fullmatch(r"[a-z][a-z0-9_]*", r.key), r.key
        assert r.category in CATEGORIES, r.key
        assert r.description and r.description.endswith("."), r.key
