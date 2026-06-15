"""
Patch templates for known rule violations.

A template is either:
  - A static list of JSON Patch operations (for fields that should be
    completely removed, e.g. /name, /telecom, /photo)
  - A function (resource: dict) -> list[dict] (for fields where we want to
    preserve allowed sub-fields, e.g. /address/0/line but keep /address/0/postalCode)
"""

from typing import Callable, Optional, Union


# Type: either a static patch list, or a function that builds one from the resource
TemplateFn = Callable[[dict], list[dict]]
Template = Union[list[dict], TemplateFn]


# ---------------------------------------------------------------------------
# Static templates: just remove the whole field
# ---------------------------------------------------------------------------
_STATIC_TEMPLATES: dict[str, dict[str, list[dict]]] = {
    "Patient": {
        "name_forbidden": [{"op": "remove", "path": "/name"}],
        "telecom_forbidden": [{"op": "remove", "path": "/telecom"}],
        "photo_forbidden": [{"op": "remove", "path": "/photo"}],
    },
    "Observation": {
        "value_string_cleartext_forbidden": [
            {"op": "remove", "path": "/valueString"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Dynamic templates: inspect the resource, surgically remove only forbidden bits
# ---------------------------------------------------------------------------
def _patient_address_template(resource: dict) -> list[dict]:
    """
    Remove only forbidden address sub-fields (line, city, text).
    Preserve allowed fields like postalCode and country.
    Processes addresses in reverse index order so that removals don't
    shift indices for later operations.
    """
    ops: list[dict] = []
    addresses = resource.get("address", [])
    for i, addr in enumerate(addresses):
        for field in ("line", "city", "text"):
            if field in addr:
                ops.append({"op": "remove", "path": f"/address/{i}/{field}"})
    return ops


_DYNAMIC_TEMPLATES: dict[str, dict[str, TemplateFn]] = {
    "Patient": {
        "address_forbidden": _patient_address_template,
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_patch_template(
    resource_type: str,
    rule_key: str,
    resource: Optional[dict] = None,
) -> Optional[list[dict]]:
    """
    Return the patch operations for a rule violation.

    If the template is dynamic, `resource` MUST be provided so the template
    can inspect actual content. If static, `resource` is ignored.

    Returns None if no template exists for this combination.
    """
    static = _STATIC_TEMPLATES.get(resource_type, {}).get(rule_key)
    if static is not None:
        return list(static)  # copy to prevent mutation

    fn = _DYNAMIC_TEMPLATES.get(resource_type, {}).get(rule_key)
    if fn is not None:
        if resource is None:
            raise ValueError(
                f"Template for {resource_type}/{rule_key} is dynamic "
                "and requires the resource body"
            )
        return fn(resource)

    return None


def has_template(resource_type: str, rule_key: str) -> bool:
    return rule_key in _STATIC_TEMPLATES.get(
        resource_type, {}
    ) or rule_key in _DYNAMIC_TEMPLATES.get(resource_type, {})


def list_templates() -> list[dict[str, str]]:
    """All (resource_type, rule) combos that have a deterministic patch template."""
    seen: set[tuple[str, str]] = set()
    for mapping in (_STATIC_TEMPLATES, _DYNAMIC_TEMPLATES):
        for rt, rules in mapping.items():
            for rule in rules:
                seen.add((rt, rule))
    return [{"resource_type": rt, "rule": rule} for rt, rule in sorted(seen)]
