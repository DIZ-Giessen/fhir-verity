"""Small helpers for reading FHIR JSON and building common checks."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

from app.services.rules.registry import CheckResult, RuleContext

# FHIR date: YYYY, YYYY-MM or YYYY-MM-DD
FHIR_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
FHIR_DATETIME = re.compile(
    r"^\d{4}(-\d{2}(-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?)?)?$"
)

# Code systems used by the MII core data set
LOINC = "http://loinc.org"
SNOMED = "http://snomed.info/sct"
UCUM = "http://unitsofmeasure.org"
ICD10GM = "http://fhir.de/CodeSystem/bfarm/icd-10-gm"
ALPHA_ID = "http://fhir.de/CodeSystem/bfarm/alpha-id"
ORPHANET = "http://www.orpha.net"
OPS = "http://fhir.de/CodeSystem/bfarm/ops"
ATC_DE = "http://fhir.de/CodeSystem/bfarm/atc"
ATC_WHO = "http://www.whocc.no/atc"
PZN = "http://fhir.de/CodeSystem/ifa/pzn"
ASK = "http://fhir.de/CodeSystem/ask"
UNII = "http://fdasis.nlm.nih.gov"
CAS = "http://terminology.hl7.org/CodeSystem/CAS"
EDQM = "http://standardterms.edqm.eu"
V2_0203 = "http://terminology.hl7.org/CodeSystem/v2-0203"
V2_0074 = "http://terminology.hl7.org/CodeSystem/v2-0074"
OBSERVATION_CATEGORY = "http://terminology.hl7.org/CodeSystem/observation-category"
MII_PROFILE_PREFIX = "https://www.medizininformatik-initiative.de/fhir/"

# Patterns from the German base profiles (de.basisprofil.r4)
ICD10GM_CODE = re.compile(r"^[A-Z][0-9][A-Z0-9](\.?[A-Z0-9]{0,4})?$")
OPS_CODE = re.compile(r"^[1|3|5|6|8|9]-[a-zA-Z0-9]{3}([.][a-zA-Z0-9]{1,2})?$")
ATC_CODE = re.compile(r"^[A-Z]([0-9]{2}([A-Z]([A-Z]([0-9]{2})?)?)?)?$")
PZN_CODE = re.compile(r"^[0-9]{8}$")

# Free text longer than this is reported by the cleartext rules
LONG_TEXT = 50


# ---------------------------------------------------------------------------
# Reading values
# ---------------------------------------------------------------------------


def present(value: Any) -> bool:
    """FHIR "missing": absent, null, empty string, empty list or empty object."""
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


def as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def get(resource: dict, path: str) -> list:
    """
    All values at a dotted path, walking through lists:
    get(obs, "code.coding") -> every Coding of Observation.code.
    """
    if "." not in path:
        value = resource.get(path) if isinstance(resource, dict) else None
        return [v for v in as_list(value) if present(v)]
    current = [resource]
    for part in path.split("."):
        nxt = []
        for item in current:
            if isinstance(item, dict) and part in item:
                nxt.extend(as_list(item[part]))
        current = nxt
    return [v for v in current if present(v)]


def first(resource: dict, path: str) -> Any:
    found = get(resource, path)
    return found[0] if found else None


def any_present(resource: dict, *fields: str) -> bool:
    return any(present(resource.get(f)) for f in fields)


def codings(concepts: Any) -> list[dict]:
    """All Codings of one or more CodeableConcepts."""
    return [c for cc in as_list(concepts) if isinstance(cc, dict) for c in as_list(cc.get("coding")) if isinstance(c, dict)]


def has_coding(concepts: Any, system: str, code: str | None = None) -> bool:
    return any(
        c.get("system") == system and (code is None or c.get("code") == code)
        for c in codings(concepts)
    )


def codes_of(concepts: Any, system: str) -> list[dict]:
    return [c for c in codings(concepts) if c.get("system") == system]


def is_reference_to(reference: str, *resource_types: str) -> bool:
    return any(reference.startswith(f"{rt}/") for rt in resource_types)


def long_text(text: Any, limit: int = LONG_TEXT) -> bool:
    return isinstance(text, str) and len(text) > limit


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------


def as_utc(raw: str) -> datetime:
    """Parse a FHIR date/dateTime; values without time zone count as UTC."""
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_future(raw: Any, tolerance: timedelta = timedelta(0)) -> bool:
    if not raw or not isinstance(raw, str):
        return False
    try:
        return as_utc(raw) > datetime.now(timezone.utc) + tolerance
    except ValueError:
        return False


def end_before_start(start: str, end: str) -> bool:
    """
    True if end lies before start (FHIR invariant per-1 allows start == end).
    Values of different precision, e.g. a date against a dateTime, are
    compared at the lower precision. Raises ValueError for values that are
    not FHIR date/dateTime strings.
    """
    if "T" in start and "T" in end:
        return as_utc(end) < as_utc(start)
    start_date = start.split("T")[0]
    end_date = end.split("T")[0]
    if not (FHIR_DATE.match(start_date) and FHIR_DATE.match(end_date)):
        raise ValueError(f"not a FHIR date: {start!r} / {end!r}")
    precision = min(len(start_date), len(end_date))
    return end_date[:precision] < start_date[:precision]


def before(earlier: Any, later: Any) -> bool:
    """True if `later` lies before `earlier`; False if either is unusable."""
    if not (isinstance(earlier, str) and isinstance(later, str)):
        return False
    try:
        return end_before_start(earlier, later)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Check factories for the common cases
# ---------------------------------------------------------------------------

Check = Callable[[dict, RuleContext], CheckResult]


def required(message: str, *paths: str) -> Check:
    """Passes if any of the paths has a value."""

    def check(r: dict, ctx: RuleContext) -> CheckResult:
        return None if any(get(r, p) for p in paths) else message

    return check


def forbidden(message: str, *paths: str) -> Check:
    def check(r: dict, ctx: RuleContext) -> CheckResult:
        return message if any(get(r, p) for p in paths) else None

    return check


def references(label: str, path: str, *targets: str) -> Check:
    """Every reference at `path` must be a relative reference to one of the targets."""
    shown = targets[0]

    def check(r: dict, ctx: RuleContext) -> CheckResult:
        for ref in get(r, f"{path}.reference"):
            if isinstance(ref, str) and not is_reference_to(ref, *targets):
                return f"{label}.reference '{ref}' must follow '{shown}/{{id}}' format."
        return None

    return check


def not_future(label: str, *paths: str, tolerance: timedelta = timedelta(0)) -> Check:
    def check(r: dict, ctx: RuleContext) -> CheckResult:
        for p in paths:
            for value in get(r, p):
                if is_future(value, tolerance):
                    return f"{label} '{value}' is in the future."
        return None

    return check


def period_in_order(label: str, path: str) -> Check:
    def check(r: dict, ctx: RuleContext) -> CheckResult:
        for period in get(r, path):
            if isinstance(period, dict) and before(period.get("start"), period.get("end")):
                return f"{label}.end '{period['end']}' is before start '{period['start']}'."
        return None

    return check


def one_of(label: str, path: str, allowed: Iterable[str]) -> Check:
    allowed = frozenset(allowed)

    def check(r: dict, ctx: RuleContext) -> CheckResult:
        for value in get(r, path):
            if value not in allowed:
                return f"{label} '{value}' is not an allowed value."
        return None

    return check


def coded_with(label: str, path: str, *systems: str) -> Check:
    """If the CodeableConcept is present, one Coding must use one of the systems."""

    def check(r: dict, ctx: RuleContext) -> CheckResult:
        concepts = get(r, path)
        if not concepts:
            return None
        if any(c.get("system") in systems and c.get("code") for c in codings(concepts)):
            return None
        return f"{label} has no coding from {', '.join(systems)}."

    return check


def code_format(label: str, path: str, system: str, pattern: re.Pattern) -> Check:
    def check(r: dict, ctx: RuleContext) -> CheckResult:
        for c in codes_of(get(r, path), system):
            code = c.get("code")
            if isinstance(code, str) and not pattern.match(code):
                return f"{label} code '{code}' does not match the format for {system}."
        return None

    return check


def code_versioned(label: str, path: str, system: str) -> Check:
    def check(r: dict, ctx: RuleContext) -> CheckResult:
        for c in codes_of(get(r, path), system):
            if not present(c.get("version")):
                return f"{label} coding from {system} has no version."
        return None

    return check


def coding_complete(label: str, path: str) -> Check:
    """Every Coding at `path` must carry both system and code."""

    def check(r: dict, ctx: RuleContext) -> CheckResult:
        for c in codings(get(r, path)):
            if not (present(c.get("system")) and present(c.get("code"))):
                return f"{label} has a coding without system or code."
        return None

    return check


def ucum_quantity(label: str, path: str) -> Check:
    """Quantities at `path` must have a value and a UCUM unit code."""

    def check(r: dict, ctx: RuleContext) -> CheckResult:
        for q in get(r, path):
            if not isinstance(q, dict):
                continue
            if q.get("system") != UCUM or not present(q.get("code")):
                return f"{label} has no UCUM unit (system {UCUM} and code)."
        return None

    return check


def cleartext(label: str, *paths: str, limit: int = LONG_TEXT) -> Check:
    def check(r: dict, ctx: RuleContext) -> CheckResult:
        for p in paths:
            if any(long_text(v, limit) for v in get(r, p)):
                return f"{label} contains a long free-text string that may include personal data."
        return None

    return check


def mii_profile(resource_type: str) -> Check:
    def check(r: dict, ctx: RuleContext) -> CheckResult:
        profiles = get(r, "meta.profile")
        if any(isinstance(p, str) and p.startswith(MII_PROFILE_PREFIX) for p in profiles):
            return None
        return f"{resource_type}.meta.profile does not reference an MII core data set profile."

    return check
