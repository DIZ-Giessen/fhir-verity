"""Observation: FHIR R4, laboratory rules from MII KDS Laborbefund (ObservationLab)."""

from app.services.rules.fhir import (
    LOINC,
    OBSERVATION_CATEGORY,
    before,
    cleartext,
    coding_complete,
    forbidden,
    get,
    has_coding,
    is_future,
    is_reference_to,
    mii_profile,
    not_future,
    one_of,
    period_in_order,
    present,
    references,
    required,
    ucum_quantity,
)
from app.services.rules.registry import RuleContext, rules_for

R = rules_for("Observation", profile="FHIR R4, Laborregeln aus MII KDS Laborbefund (ObservationLab)")

VALUE_FIELDS = (
    "valueQuantity",
    "valueCodeableConcept",
    "valueString",
    "valueBoolean",
    "valueInteger",
    "valueRange",
    "valueRatio",
    "valueSampledData",
    "valueTime",
    "valueDateTime",
    "valuePeriod",
)
STATUS = (
    "registered",
    "preliminary",
    "final",
    "amended",
    "corrected",
    "cancelled",
    "entered-in-error",
    "unknown",
)


def is_lab(r: dict, ctx: RuleContext) -> bool:
    return ctx.remember(
        "lab",
        lambda: any(has_coding(c, OBSERVATION_CATEGORY, "laboratory") for c in get(r, "category")),
    )


@R(
    "value_string_cleartext_forbidden",
    category="privacy",
    severity="error",
    description=(
        "Observation.valueString must not be longer than 50 characters; long free "
        "text may contain personal data. Results belong in valueQuantity or valueCodeableConcept."
    ),
)
def value_string_cleartext_forbidden(r, ctx):
    value = r.get("valueString", "")
    if value and len(value) > 50:
        return "Observation.valueString contains a long string that may include personal data."


@R(
    "status_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Observation.status must be present.",
)
def status_required(r, ctx):
    if not r.get("status"):
        return "Observation.status is missing."


@R(
    "code_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Observation.code must be present.",
)
def code_required(r, ctx):
    if not r.get("code"):
        return "Observation.code is missing."


@R(
    "subject_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Observation.subject must be present.",
)
def subject_required(r, ctx):
    if not r.get("subject"):
        return "Observation.subject is missing."


@R(
    "effective_required",
    category="completeness",
    severity="warning",
    enabled=True,
    description="Observation.effective[x] (dateTime, Period or instant) must be present.",
)
def effective_required(r, ctx):
    if not (r.get("effectiveDateTime") or r.get("effectivePeriod") or r.get("effectiveInstant")):
        return "Observation.effective[x] is missing."


@R(
    "value_present",
    category="completeness",
    severity="warning",
    enabled=True,
    description="Observation must have a value[x] or a dataAbsentReason.",
)
def value_present(r, ctx):
    if not any(r.get(f) for f in (*VALUE_FIELDS, "dataAbsentReason")):
        return "Observation has no value[x] and no dataAbsentReason."


@R(
    "effective_not_future",
    category="plausibility",
    severity="warning",
    enabled=True,
    description="Observation.effectiveDateTime or effectiveInstant must not lie in the future.",
)
def effective_not_future(r, ctx):
    eff = r.get("effectiveDateTime") or r.get("effectiveInstant")
    if eff and is_future(eff):
        return f"Observation.effectiveDateTime '{eff}' is in the future."


@R(
    "subject_reference_format",
    category="integrity",
    severity="error",
    enabled=True,
    description="Observation.subject.reference must have the form 'Patient/{id}'.",
)
def subject_reference_format(r, ctx):
    ref = r.get("subject", {}).get("reference", "")
    if ref and not is_reference_to(ref, "Patient"):
        return f"Observation.subject.reference '{ref}' must follow 'Patient/{{id}}' format."


# --- rules beyond the original set -----------------------------------------

R(
    "note_cleartext_check",
    category="privacy",
    severity="warning",
    description="Observation.note.text must not be longer than 50 characters; long free text may contain personal data.",
)(cleartext("Observation.note", "note.text"))

R(
    "text_forbidden",
    category="privacy",
    severity="info",
    description="Observation.text (narrative) must not be present; it may contain cleartext personal data.",
)(forbidden("Observation.text is present. Narratives may contain cleartext personal data.", "text"))

R(
    "status_valid",
    category="coding",
    severity="error",
    description="Observation.status must be a value of the FHIR ObservationStatus value set.",
)(one_of("Observation.status", "status", STATUS))

R(
    "category_required",
    category="completeness",
    severity="warning",
    description="Observation.category must be present.",
)(required("Observation.category is missing.", "category"))

R(
    "code_coding_complete",
    category="coding",
    severity="warning",
    description="Every Observation.code.coding must carry both system and code.",
)(coding_complete("Observation.code", "code"))

R(
    "encounter_reference_format",
    category="integrity",
    severity="error",
    description="Observation.encounter.reference must have the form 'Encounter/{id}'.",
)(references("Observation.encounter", "encounter", "Encounter"))

R(
    "specimen_reference_format",
    category="integrity",
    severity="warning",
    description="Observation.specimen.reference must have the form 'Specimen/{id}'.",
)(references("Observation.specimen", "specimen", "Specimen"))

R(
    "effective_period_end_after_start",
    category="plausibility",
    severity="error",
    description="Observation.effectivePeriod.end must not lie before start (FHIR invariant per-1).",
)(period_in_order("Observation.effectivePeriod", "effectivePeriod"))

R(
    "issued_not_future",
    category="plausibility",
    severity="warning",
    description="Observation.issued must not lie in the future.",
)(not_future("Observation.issued", "issued"))


@R(
    "issued_after_effective",
    category="plausibility",
    severity="warning",
    description="Observation.issued must not lie before effectiveDateTime; a result cannot be released before it was taken.",
)
def issued_after_effective(r, ctx):
    if before(r.get("effectiveDateTime"), r.get("issued")):
        return (
            f"Observation.issued '{r['issued']}' is before effectiveDateTime "
            f"'{r['effectiveDateTime']}'."
        )


@R(
    "value_absent_exclusive",
    category="plausibility",
    severity="error",
    description="Observation.dataAbsentReason must only be present if value[x] is absent (FHIR invariant obs-6).",
)
def value_absent_exclusive(r, ctx):
    if present(r.get("dataAbsentReason")) and any(present(r.get(f)) for f in VALUE_FIELDS):
        return "Observation has both value[x] and dataAbsentReason."


R(
    "value_quantity_ucum",
    category="coding",
    severity="warning",
    description="Observation.valueQuantity must use a UCUM unit (system http://unitsofmeasure.org with code).",
)(ucum_quantity("Observation.valueQuantity", "valueQuantity"))


@R(
    "value_quantity_value",
    category="completeness",
    severity="warning",
    description="Observation.valueQuantity must contain a numeric value.",
)
def value_quantity_value(r, ctx):
    q = r.get("valueQuantity")
    if isinstance(q, dict) and q and not isinstance(q.get("value"), (int, float)):
        return "Observation.valueQuantity has no numeric value."


@R(
    "reference_range_order",
    category="plausibility",
    severity="warning",
    description="Observation.referenceRange.low must not be greater than referenceRange.high.",
)
def reference_range_order(r, ctx):
    for rr in r.get("referenceRange") or []:
        low = (rr.get("low") or {}).get("value") if isinstance(rr, dict) else None
        high = (rr.get("high") or {}).get("value") if isinstance(rr, dict) else None
        if isinstance(low, (int, float)) and isinstance(high, (int, float)) and low > high:
            return f"Observation.referenceRange low {low} is greater than high {high}."


@R(
    "component_code_required",
    category="completeness",
    severity="error",
    description="Every Observation.component must have a code.",
)
def component_code_required(r, ctx):
    for comp in r.get("component") or []:
        if isinstance(comp, dict) and not present(comp.get("code")):
            return "Observation.component without code."


@R(
    "lab_category_coding",
    category="coding",
    severity="warning",
    description=(
        "A laboratory Observation must be categorized with both observation-category "
        "'laboratory' and LOINC 26436-6 (MII ObservationLab)."
    ),
)
def lab_category_coding(r, ctx):
    if is_lab(r, ctx) and not any(has_coding(c, LOINC, "26436-6") for c in get(r, "category")):
        return "Laboratory Observation.category has no LOINC 26436-6 coding."


@R(
    "lab_code_loinc",
    category="coding",
    severity="warning",
    description="A laboratory Observation.code must contain a LOINC coding (MII ObservationLab).",
)
def lab_code_loinc(r, ctx):
    if is_lab(r, ctx) and not has_coding(r.get("code"), LOINC):
        return "Laboratory Observation.code has no LOINC coding."


@R(
    "lab_identifier_required",
    category="completeness",
    severity="info",
    description="A laboratory Observation must have an identifier (MII ObservationLab).",
)
def lab_identifier_required(r, ctx):
    if is_lab(r, ctx) and not present(r.get("identifier")):
        return "Laboratory Observation has no identifier."


@R(
    "lab_effective_precision",
    category="plausibility",
    severity="info",
    description="A laboratory Observation.effectiveDateTime must be precise to at least the day (MII invariant mii-lab-1).",
)
def lab_effective_precision(r, ctx):
    eff = r.get("effectiveDateTime")
    if is_lab(r, ctx) and isinstance(eff, str) and len(eff) < 10:
        return f"Laboratory Observation.effectiveDateTime '{eff}' is less precise than a day."


R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="Observation.meta.profile must reference an MII core data set profile.",
)(mii_profile("Observation"))
