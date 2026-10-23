"""Consent: MII KDS Consent (Einwilligung)."""

from app.services.rules.fhir import (
    LOINC,
    codings,
    get,
    has_coding,
    mii_profile,
    not_future,
    one_of,
    period_in_order,
    present,
    references,
    required,
)
from app.services.rules.registry import rules_for

R = rules_for("Consent", profile="MII KDS Consent (Einwilligung)")

CONSENT_SCOPE = "http://terminology.hl7.org/CodeSystem/consentscope"
MII_POLICY = "urn:oid:2.16.840.1.113883.3.1937.777.24.5.3"
STATUS = ("draft", "proposed", "active", "rejected", "inactive", "entered-in-error")

R(
    "status_required",
    category="completeness",
    severity="error",
    description="Consent.status must be present.",
)(required("Consent.status is missing.", "status"))

R(
    "patient_required",
    category="completeness",
    severity="error",
    description="Consent.patient must be present (required by MII Consent).",
)(required("Consent.patient is missing.", "patient"))

R(
    "datetime_required",
    category="completeness",
    severity="error",
    description="Consent.dateTime must be present (required by MII Consent).",
)(required("Consent.dateTime is missing.", "dateTime"))

R(
    "policy_required",
    category="completeness",
    severity="warning",
    description="Consent.policy.uri must be present (required by MII Consent).",
)(required("Consent.policy.uri is missing.", "policy.uri"))

R(
    "provision_period_required",
    category="completeness",
    severity="warning",
    description="Consent.provision.period.start must be present (required by MII Consent).",
)(required("Consent.provision.period.start is missing.", "provision.period.start"))


@R(
    "nested_provision_complete",
    category="completeness",
    severity="warning",
    description=(
        "Every nested Consent.provision.provision must have type, code and "
        "period.start (required by MII Consent)."
    ),
)
def nested_provision_complete(r, ctx):
    for p in get(r, "provision.provision"):
        if not isinstance(p, dict):
            continue
        missing = [
            name
            for name, value in (
                ("type", p.get("type")),
                ("code", p.get("code")),
                ("period.start", (p.get("period") or {}).get("start")),
            )
            if not present(value)
        ]
        if missing:
            return f"Consent.provision.provision without {', '.join(missing)}."


R(
    "status_valid",
    category="coding",
    severity="error",
    description="Consent.status must be a value of the FHIR consent-state-codes value set.",
)(one_of("Consent.status", "status", STATUS))


@R(
    "scope_research",
    category="coding",
    severity="warning",
    description="Consent.scope must be 'research' from the consentscope code system (MII Consent).",
)
def scope_research(r, ctx):
    if not has_coding(r.get("scope"), CONSENT_SCOPE, "research"):
        return "Consent.scope is not consentscope#research."


@R(
    "category_loinc",
    category="coding",
    severity="warning",
    description="Consent.category must contain LOINC 57016-8 (Privacy policy acknowledgment, MII Consent).",
)
def category_loinc(r, ctx):
    if not any(has_coding(c, LOINC, "57016-8") for c in get(r, "category")):
        return "Consent.category has no LOINC 57016-8 coding."


@R(
    "provision_codes_mii",
    category="coding",
    severity="warning",
    description="Nested Consent.provision.provision.code must use the MII consent policy code system.",
)
def provision_codes_mii(r, ctx):
    for p in get(r, "provision.provision"):
        for c in codings(p.get("code") if isinstance(p, dict) else None):
            if c.get("system") != MII_POLICY:
                return f"Consent.provision.provision.code uses system '{c.get('system')}' instead of {MII_POLICY}."


@R(
    "provision_type_valid",
    category="coding",
    severity="error",
    description="Consent.provision.type and nested provision types must be 'permit' or 'deny'.",
)
def provision_type_valid(r, ctx):
    for value in get(r, "provision.type") + get(r, "provision.provision.type"):
        if value not in ("permit", "deny"):
            return f"Consent.provision.type '{value}' is not permit or deny."


R(
    "datetime_not_future",
    category="plausibility",
    severity="warning",
    description="Consent.dateTime must not lie in the future.",
)(not_future("Consent.dateTime", "dateTime"))

R(
    "provision_period_end_after_start",
    category="plausibility",
    severity="error",
    description="Consent.provision.period.end must not lie before start (FHIR invariant per-1).",
)(period_in_order("Consent.provision.period", "provision.period"))

R(
    "nested_period_end_after_start",
    category="plausibility",
    severity="error",
    description="Nested Consent.provision.provision.period.end must not lie before start (FHIR invariant per-1).",
)(period_in_order("Consent.provision.provision.period", "provision.provision.period"))

R(
    "patient_reference_format",
    category="integrity",
    severity="error",
    description="Consent.patient.reference must have the form 'Patient/{id}'.",
)(references("Consent.patient", "patient", "Patient"))

R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="Consent.meta.profile must reference an MII core data set profile.",
)(mii_profile("Consent"))
