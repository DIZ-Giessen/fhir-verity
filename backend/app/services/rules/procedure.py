"""Procedure: MII KDS Prozedur."""

from app.services.rules.fhir import (
    OPS,
    OPS_CODE,
    SNOMED,
    cleartext,
    code_format,
    code_versioned,
    coded_with,
    forbidden,
    has_coding,
    is_reference_to,
    mii_profile,
    not_future,
    one_of,
    period_in_order,
    present,
    references,
)
from app.services.rules.registry import rules_for

R = rules_for("Procedure", profile="MII KDS Prozedur (Procedure)")

STATUS = (
    "preparation",
    "in-progress",
    "not-done",
    "on-hold",
    "stopped",
    "completed",
    "entered-in-error",
    "unknown",
)


R(
    "note_cleartext_check",
    category="privacy",
    severity="warning",
    enabled=True,
    description="Procedure.note.text must not be longer than 50 characters; long free text may contain personal data.",
)(cleartext("Procedure.note", "note.text"))


@R(
    "status_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Procedure.status must be present.",
)
def status_required(r, ctx):
    if not r.get("status"):
        return "Procedure.status is missing."


@R(
    "code_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Procedure.code must be present.",
)
def code_required(r, ctx):
    if not r.get("code"):
        return "Procedure.code is missing."


@R(
    "subject_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Procedure.subject must be present.",
)
def subject_required(r, ctx):
    if not r.get("subject"):
        return "Procedure.subject is missing."


@R(
    "performed_required",
    category="completeness",
    severity="warning",
    enabled=True,
    description="Procedure.performed[x] must be present.",
)
def performed_required(r, ctx):
    if not (
        r.get("performedDateTime")
        or r.get("performedPeriod")
        or r.get("performedString")
        or r.get("performedAge")
        or r.get("performedRange")
    ):
        return "Procedure.performed[x] is missing."


@R(
    "subject_reference_format",
    category="integrity",
    severity="error",
    enabled=True,
    description="Procedure.subject.reference must have the form 'Patient/{id}'.",
)
def subject_reference_format(r, ctx):
    ref = r.get("subject", {}).get("reference", "")
    if ref and not is_reference_to(ref, "Patient"):
        return f"Procedure.subject.reference '{ref}' must follow 'Patient/{{id}}' format."


# --- rules beyond the original set -----------------------------------------

R(
    "text_forbidden",
    category="privacy",
    severity="info",
    description="Procedure.text (narrative) must not be present; it may contain cleartext personal data.",
)(forbidden("Procedure.text is present. Narratives may contain cleartext personal data.", "text"))

R(
    "status_valid",
    category="coding",
    severity="error",
    description="Procedure.status must be a value of the FHIR EventStatus value set.",
)(one_of("Procedure.status", "status", STATUS))

R(
    "code_coding_known_system",
    category="coding",
    severity="warning",
    description="Procedure.code must contain an OPS or SNOMED CT coding (MII invariant sct-ops-1).",
)(coded_with("Procedure.code", "code", OPS, SNOMED))

R(
    "ops_version_required",
    category="coding",
    severity="error",
    description="An OPS coding in Procedure.code must state the catalogue version (coding.version).",
)(code_versioned("Procedure.code", "code", OPS))

R(
    "ops_code_format",
    category="coding",
    severity="error",
    description="An OPS code must match the format of the German base profile, e.g. 5-470.11.",
)(code_format("Procedure.code", "code", OPS, OPS_CODE))


@R(
    "ops_requires_category",
    category="coding",
    severity="warning",
    description="A Procedure coded with OPS must have a SNOMED CT category (MII invariant proc-mii-1).",
)
def ops_requires_category(r, ctx):
    if has_coding(r.get("code"), OPS) and not has_coding(r.get("category"), SNOMED):
        return "Procedure is coded with OPS but has no SNOMED CT category."


@R(
    "performed_datetime_or_period",
    category="plausibility",
    severity="warning",
    description="Procedure.performed[x] must be a dateTime or Period; MII Prozedur does not allow string, Age or Range.",
)
def performed_datetime_or_period(r, ctx):
    for name in ("performedString", "performedAge", "performedRange"):
        if present(r.get(name)):
            return f"Procedure uses {name}; only performedDateTime or performedPeriod are allowed."


R(
    "performed_not_future",
    category="plausibility",
    severity="warning",
    description="Procedure.performedDateTime and performedPeriod.start must not lie in the future.",
)(not_future("Procedure.performed", "performedDateTime", "performedPeriod.start"))

R(
    "performed_period_end_after_start",
    category="plausibility",
    severity="error",
    description="Procedure.performedPeriod.end must not lie before start (FHIR invariant per-1).",
)(period_in_order("Procedure.performedPeriod", "performedPeriod"))

R(
    "bodysite_snomed",
    category="coding",
    severity="info",
    description="Procedure.bodySite must be coded with SNOMED CT (MII Prozedur).",
)(coded_with("Procedure.bodySite", "bodySite", SNOMED))

R(
    "encounter_reference_format",
    category="integrity",
    severity="error",
    description="Procedure.encounter.reference must have the form 'Encounter/{id}'.",
)(references("Procedure.encounter", "encounter", "Encounter"))

R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="Procedure.meta.profile must reference an MII core data set profile.",
)(mii_profile("Procedure"))
