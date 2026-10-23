"""
Rule registry: every validation rule is declared once, together with its
check, and registers itself here. Defaults, the configuration UI, the
FHIR TestScript and the documentation are all derived from this registry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable

logger = logging.getLogger(__name__)

CATEGORIES = ("privacy", "completeness", "coding", "plausibility", "integrity")
SEVERITIES = ("error", "warning", "info")

# A check returns None (or "") if the resource passes, otherwise one message
# or a list of messages.
CheckResult = str | list[str] | None


@dataclass(slots=True)
class RuleContext:
    """What a check may need besides the resource itself."""

    resource_id: str
    config: dict[str, Any]
    page: Any = None
    # Shared by all rules evaluated on the same resource
    memo: dict[str, Any] = field(default_factory=dict)

    @property
    def pattern(self) -> str | None:
        return self.config.get("pattern")

    def remember(self, name: str, compute: Callable[[], Any]) -> Any:
        """Compute a value once per resource, e.g. whether it is a lab result."""
        if name not in self.memo:
            self.memo[name] = compute()
        return self.memo[name]


@dataclass(frozen=True)
class Rule:
    resource_type: str
    key: str
    category: str
    severity: str
    description: str
    check: Callable[[dict, RuleContext], CheckResult]
    enabled: bool = False
    pattern: str | None = None
    # Runs once per page of resources before the checks, for rules that need
    # extra requests (e.g. "has at least one Observation").
    prepare: Callable[[Any, list[dict]], Awaitable[Any]] | None = None

    def default_config(self) -> dict[str, Any]:
        cfg: dict[str, Any] = {
            "enabled": self.enabled,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
        }
        if self.pattern is not None:
            cfg["pattern"] = self.pattern
        return cfg


@dataclass
class Registry:
    rules: dict[str, dict[str, Rule]] = field(default_factory=dict)
    # Profile each resource type is checked against, for the documentation
    profiles: dict[str, str] = field(default_factory=dict)

    def add(self, rule: Rule) -> None:
        if rule.category not in CATEGORIES:
            raise ValueError(f"{rule.resource_type}.{rule.key}: unknown category {rule.category}")
        if rule.severity not in SEVERITIES:
            raise ValueError(f"{rule.resource_type}.{rule.key}: unknown severity {rule.severity}")
        bucket = self.rules.setdefault(rule.resource_type, {})
        if rule.key in bucket:
            raise ValueError(f"Rule {rule.resource_type}.{rule.key} is defined twice")
        bucket[rule.key] = rule

    def resource_types(self) -> list[str]:
        return list(self.rules)

    def for_type(self, resource_type: str) -> list[Rule]:
        return list(self.rules.get(resource_type, {}).values())

    def get(self, resource_type: str, key: str) -> Rule | None:
        return self.rules.get(resource_type, {}).get(key)


REGISTRY = Registry()


def rule(
    resource_type: str,
    key: str,
    *,
    category: str,
    severity: str,
    description: str,
    enabled: bool = False,
    pattern: str | None = None,
    prepare: Callable[[Any, list[dict]], Awaitable[Any]] | None = None,
) -> Callable[[Callable[[dict, RuleContext], CheckResult]], Callable]:
    """Register the decorated function as the check of a rule."""

    def decorator(check: Callable[[dict, RuleContext], CheckResult]) -> Callable:
        REGISTRY.add(
            Rule(
                resource_type=resource_type,
                key=key,
                category=category,
                severity=severity,
                description=description,
                check=check,
                enabled=enabled,
                pattern=pattern,
                prepare=prepare,
            )
        )
        return check

    return decorator


def rules_for(resource_type: str, profile: str = ""):
    """rule() with the resource type already filled in, for one module per type."""
    REGISTRY.profiles[resource_type] = profile

    def bound(key: str, **kwargs):
        return rule(resource_type, key, **kwargs)

    return bound


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# The fields a server override may change; the rest always comes from code.
CONFIGURABLE_FIELDS = ("enabled", "severity", "pattern")


def default_rules(resource_type: str) -> dict[str, dict[str, Any]]:
    return {r.key: r.default_config() for r in REGISTRY.for_type(resource_type)}


def effective_rules(
    resource_type: str, override: dict[str, dict] | None = None
) -> dict[str, dict[str, Any]]:
    """Defaults from the registry with a server override applied per rule."""
    rules = default_rules(resource_type)
    for key, changes in (override or {}).items():
        if key not in rules or not isinstance(changes, dict):
            continue
        for name in CONFIGURABLE_FIELDS:
            if name in changes:
                rules[key][name] = changes[name]
    return rules


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def active_rules(resource_type: str, config: dict[str, dict]) -> list[Rule]:
    return [
        r
        for r in REGISTRY.for_type(resource_type)
        if config.get(r.key, {}).get("enabled", False)
    ]


def _messages(result: CheckResult) -> Iterable[str]:
    if not result:
        return ()
    if isinstance(result, str):
        return (result,)
    return [m for m in result if m]


def evaluate(
    resource: dict,
    rules: list[Rule],
    config: dict[str, dict],
    page: dict[str, Any] | None = None,
) -> tuple[list[dict], dict[str, bool]]:
    """
    Run the given rules against one resource. Returns the issues and the
    metrics ({rule: passed}) in the shape stored in invalid_resources.
    """
    resource_id = resource.get("id", "")
    issues: list[dict] = []
    metrics: dict[str, bool] = {r.key: True for r in rules}
    memo: dict[str, Any] = {}
    page = page or {}
    for r in rules:
        rule_config = config.get(r.key, {})
        ctx = RuleContext(resource_id, rule_config, page.get(r.key), memo)
        try:
            messages = _messages(r.check(resource, ctx))
        except Exception as exc:
            # A malformed resource must not abort the whole run.
            logger.debug(
                "Rule %s.%s could not evaluate %s: %s",
                r.resource_type,
                r.key,
                resource_id,
                exc,
            )
            continue
        for message in messages:
            issues.append(
                {
                    "rule": r.key,
                    "severity": rule_config.get("severity", r.severity),
                    "message": message,
                }
            )
            metrics[r.key] = False
    return issues, metrics
