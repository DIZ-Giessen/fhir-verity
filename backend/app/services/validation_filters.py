"""Build and validate FHIR search parameters from per-resource-type filters.

A filter dict is stored on ValidationConfig.filters and is entirely optional.
Empty/absent filters produce no parameters, so crawl behaviour is unchanged.

Supported keys (all optional):
  - last_updated_from: str   -> _lastUpdated=ge<value>
  - last_updated_to:   str   -> _lastUpdated=le<value>
  - profile:           str   -> _profile=<value>
  - tag:               str   -> _tag=<value>
"""

import re
from datetime import datetime

# Accept full FHIR dateTime or plain date/year-month/year:
# 2022, 2022-01, 2022-01-31, 2022-01-31T12:00:00Z, with optional offset.
_FHIR_DATE_RE = re.compile(
    r"^\d{4}(-\d{2}(-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?)?)?$"
)

ALLOWED_KEYS = {"last_updated_from", "last_updated_to", "profile", "tag"}


class FilterValidationError(ValueError):
    """Raised when a stored/submitted filter is malformed."""


def validate_filters(filters: dict | None) -> dict:
    """Validate a filter dict. Returns the cleaned dict (unknown keys dropped,
    empty strings removed). Raises FilterValidationError on malformed input."""
    if not filters:
        return {}
    if not isinstance(filters, dict):
        raise FilterValidationError("filters must be an object")

    cleaned: dict = {}
    for key, value in filters.items():
        if key not in ALLOWED_KEYS:
            continue  # silently ignore unknown keys (forward-compatible)
        if value is None or value == "":
            continue
        if not isinstance(value, str):
            raise FilterValidationError(f"'{key}' must be a string")
        cleaned[key] = value.strip()

    for date_key in ("last_updated_from", "last_updated_to"):
        if date_key in cleaned and not _FHIR_DATE_RE.match(cleaned[date_key]):
            raise FilterValidationError(
                f"'{date_key}' must be a FHIR date/dateTime (e.g. 2022 or 2022-01-31)"
            )

    frm = cleaned.get("last_updated_from")
    to = cleaned.get("last_updated_to")
    if frm and to and _as_comparable(frm) > _as_comparable(to):
        raise FilterValidationError(
            "last_updated_from must not be after last_updated_to"
        )

    return cleaned


def _as_comparable(value: str) -> datetime:
    """Best-effort parse for range ordering. Pads partial dates."""
    v = value
    if re.fullmatch(r"\d{4}", v):
        v = f"{v}-01-01"
    elif re.fullmatch(r"\d{4}-\d{2}", v):
        v = f"{v}-01"
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        # If it parsed the regex but not here, treat as minimal — ordering is
        # a soft check; the FHIR server is the final authority.
        return datetime.min


def build_filter_params(filters: dict | None) -> dict:
    """Translate a validated filter dict into FHIR search params.

    _lastUpdated may carry two prefixed values (ge.. and le..); they are
    returned as a list so httpx emits the parameter twice.
    Returns {} for empty filters -> identical behaviour to no filtering.
    """
    if not filters:
        return {}

    params: dict = {}

    last_updated: list[str] = []
    frm = filters.get("last_updated_from")
    to = filters.get("last_updated_to")
    if frm:
        last_updated.append(f"ge{frm}")
    if to:
        last_updated.append(f"le{to}")
    if last_updated:
        params["_lastUpdated"] = last_updated

    if filters.get("profile"):
        params["_profile"] = filters["profile"]
    if filters.get("tag"):
        params["_tag"] = filters["tag"]

    return params
