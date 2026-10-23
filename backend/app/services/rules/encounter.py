"""Encounter: MII KDS Fall (KontaktGesundheitseinrichtung)."""

import re
from datetime import timedelta

from app.services.rules.fhir import (
    V2_0203,
    as_utc,
    coded_with,
    end_before_start,
    forbidden,
    get,
    has_coding,
    is_future,
    is_reference_to,
    mii_profile,
    one_of,
    present,
    references,
    required,
)
from app.services.rules.registry import rules_for

R = rules_for("Encounter", profile="MII KDS Fall (KontaktGesundheitseinrichtung)")

KONTAKTEBENE = "http://fhir.de/CodeSystem/Kontaktebene"
FACHABTEILUNG = "http://fhir.de/CodeSystem/dkgev/Fachabteilungsschluessel"
FACHABTEILUNG_ERWEITERT = "http://fhir.de/CodeSystem/dkgev/Fachabteilungsschluessel-erweitert"
STATUS = (
    "planned",
    "arrived",
    "triaged",
    "in-progress",
    "onleave",
    "finished",
    "cancelled",
    "entered-in-error",
    "unknown",
)


@R(
    "pseudonym_format_check",
    category="privacy",
    severity="error",
    enabled=True,
    pattern="^20[0-9]{8}$",
    description=(
        "Reports an Encounter.id or Encounter.identifier value that matches the "
        "pattern of an original, non-pseudonymized case number. Set the pattern "
        "to your site's original format."
    ),
)
def pseudonym_format_check(r, ctx):
    if not ctx.pattern:
        return None
    messages = []
    rid = ctx.resource_id
    if re.match(ctx.pattern, rid):
        messages.append(f"Encounter.id '{rid}' is not pseudonymized.")
    for ident in r.get("identifier", []):
        value = ident.get("value", "")
        if value and re.match(ctx.pattern, value):
            messages.append(f"Encounter.identifier value '{value}' is not pseudonymized.")
            break
    return messages


@R(
    "status_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Encounter.status must be present.",
)
def status_required(r, ctx):
    if not r.get("status"):
        return "Encounter.status is missing."


@R(
    "class_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Encounter.class must be present.",
)
def class_required(r, ctx):
    if not r.get("class"):
        return "Encounter.class is missing."


@R(
    "subject_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Encounter.subject must be present.",
)
def subject_required(r, ctx):
    if not r.get("subject"):
        return "Encounter.subject is missing."


@R(
    "period_start_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Encounter.period.start must be present.",
)
def period_start_required(r, ctx):
    period = r.get("period", {})
    if not period or not period.get("start"):
        return "Encounter.period.start is missing."


@R(
    "period_end_after_start",
    category="plausibility",
    severity="error",
    enabled=True,
    description=(
        "Encounter.period.end must not lie before period.start (FHIR invariant per-1). "
        "Values are compared at the precision of the less precise one."
    ),
)
def period_end_after_start(r, ctx):
    period = r.get("period", {})
    start, end = period.get("start"), period.get("end")
    if start and end and end_before_start(start, end):
        return f"Encounter.period.end '{end}' is before period.start '{start}'."


@R(
    "period_plausible_duration",
    category="plausibility",
    severity="warning",
    enabled=True,
    description=(
        "An Encounter should not last longer than 730 days; very long stays "
        "usually mean the discharge was not documented."
    ),
)
def period_plausible_duration(r, ctx):
    period = r.get("period", {})
    start, end = period.get("start"), period.get("end")
    if start and end:
        days = (as_utc(end) - as_utc(start)).days
        if days > 730:
            return f"Encounter duration is {days} days, which exceeds 730 days."


@R(
    "subject_reference_format",
    category="integrity",
    severity="error",
    enabled=True,
    description="Encounter.subject.reference must have the form 'Patient/{id}'.",
)
def subject_reference_format(r, ctx):
    ref = r.get("subject", {}).get("reference", "")
    if ref and not is_reference_to(ref, "Patient"):
        return f"Encounter.subject.reference '{ref}' must follow 'Patient/{{id}}' format."


# --- rules beyond the original set -----------------------------------------

R(
    "servicetype_required",
    category="completeness",
    severity="info",
    description="Encounter.serviceType (department, Fachabteilung) must be present.",
)(required("Encounter.serviceType is missing.", "serviceType"))

R(
    "diagnosis_present",
    category="completeness",
    severity="info",
    description="Encounter.diagnosis must reference at least one Condition.",
)(required("Encounter.diagnosis is missing.", "diagnosis"))


@R(
    "period_not_future",
    category="plausibility",
    severity="warning",
    description="Encounter.period.start must not lie more than 24 hours in the future.",
)
def period_not_future(r, ctx):
    start = (r.get("period") or {}).get("start")
    if is_future(start, timedelta(hours=24)):
        return f"Encounter.period.start '{start}' is more than 24 hours in the future."


R(
    "text_forbidden",
    category="privacy",
    severity="info",
    description="Encounter.text (narrative) must not be present; it may contain cleartext personal data.",
)(forbidden("Encounter.text is present. Narratives may contain cleartext personal data.", "text"))

R(
    "status_valid",
    category="coding",
    severity="error",
    description="Encounter.status must be a value of the FHIR EncounterStatus value set.",
)(one_of("Encounter.status", "status", STATUS))


@R(
    "class_coded",
    category="coding",
    severity="warning",
    description="Encounter.class must carry both system and code (MII EncounterClassDE, e.g. v3-ActCode IMP, AMB).",
)
def class_coded(r, ctx):
    cls = r.get("class")
    if isinstance(cls, dict) and cls and not (present(cls.get("system")) and present(cls.get("code"))):
        return "Encounter.class has no system or no code."


@R(
    "kontaktebene_required",
    category="completeness",
    severity="warning",
    description=(
        "Encounter.type must contain the contact level (Kontaktebene: "
        "einrichtungskontakt, abteilungskontakt, versorgungsstellenkontakt)."
    ),
)
def kontaktebene_required(r, ctx):
    if not any(has_coding(t, KONTAKTEBENE) for t in get(r, "type")):
        return "Encounter.type has no Kontaktebene coding."


R(
    "servicetype_fachabteilung",
    category="coding",
    severity="warning",
    description="Encounter.serviceType must be coded with the Fachabteilungsschlüssel (standard or extended).",
)(coded_with("Encounter.serviceType", "serviceType", FACHABTEILUNG, FACHABTEILUNG_ERWEITERT))


@R(
    "aufnahmenummer_required",
    category="completeness",
    severity="info",
    description="Encounter.identifier must contain the admission number (Aufnahmenummer, identifier type VN).",
)
def aufnahmenummer_required(r, ctx):
    if not any(has_coding(i.get("type"), V2_0203, "VN") for i in get(r, "identifier") if isinstance(i, dict)):
        return "Encounter has no identifier of type VN (Aufnahmenummer)."


@R(
    "finished_has_end",
    category="plausibility",
    severity="error",
    description="A finished Encounter must have period.end (MII invariant mii-enc-1).",
)
def finished_has_end(r, ctx):
    if r.get("status") == "finished" and not (r.get("period") or {}).get("end"):
        return "Encounter is finished but has no period.end."


@R(
    "planned_without_period",
    category="plausibility",
    severity="warning",
    description="A planned Encounter must not have a period (MII invariant mii-enc-3).",
)
def planned_without_period(r, ctx):
    if r.get("status") == "planned" and present(r.get("period")):
        return "Encounter is planned but already has a period."


@R(
    "ongoing_has_start",
    category="plausibility",
    severity="error",
    description=(
        "An Encounter that is in progress, on leave or unknown must have "
        "period.start (MII invariants mii-enc-5 to mii-enc-7)."
    ),
)
def ongoing_has_start(r, ctx):
    status = r.get("status")
    if status in ("in-progress", "onleave", "unknown") and not (r.get("period") or {}).get("start"):
        return f"Encounter has status '{status}' but no period.start."


@R(
    "diagnosis_use_required",
    category="completeness",
    severity="warning",
    description="Every Encounter.diagnosis must state its use (Diagnosetyp).",
)
def diagnosis_use_required(r, ctx):
    for d in r.get("diagnosis") or []:
        if isinstance(d, dict) and not present(d.get("use")):
            return "Encounter.diagnosis without use."


R(
    "diagnosis_reference_format",
    category="integrity",
    severity="error",
    description="Encounter.diagnosis.condition.reference must have the form 'Condition/{id}'.",
)(references("Encounter.diagnosis.condition", "diagnosis.condition", "Condition"))

R(
    "partof_reference_format",
    category="integrity",
    severity="error",
    description="Encounter.partOf.reference must have the form 'Encounter/{id}'.",
)(references("Encounter.partOf", "partOf", "Encounter"))

R(
    "location_reference_format",
    category="integrity",
    severity="warning",
    description="Encounter.location.location.reference must have the form 'Location/{id}'.",
)(references("Encounter.location.location", "location.location", "Location"))

R(
    "service_provider_reference_format",
    category="integrity",
    severity="warning",
    description="Encounter.serviceProvider.reference must have the form 'Organization/{id}'.",
)(references("Encounter.serviceProvider", "serviceProvider", "Organization"))


@R(
    "admit_source_required",
    category="completeness",
    severity="info",
    description="If Encounter.hospitalization is present, it must contain admitSource (Aufnahmeanlass).",
)
def admit_source_required(r, ctx):
    hosp = r.get("hospitalization")
    if isinstance(hosp, dict) and hosp and not present(hosp.get("admitSource")):
        return "Encounter.hospitalization without admitSource."


R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="Encounter.meta.profile must reference an MII core data set profile.",
)(mii_profile("Encounter"))
