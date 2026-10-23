"""MedicationAdministration: MII KDS Medikation."""

from app.services.rules.fhir import (
    cleartext,
    end_before_start,
    forbidden,
    is_future,
    is_reference_to,
    mii_profile,
    one_of,
    references,
    ucum_quantity,
)
from app.services.rules.medication_common import (
    atc_format,
    medication_known_system,
    medication_reference,
    pzn_format,
)
from app.services.rules.registry import rules_for

R = rules_for("MedicationAdministration", profile="MII KDS Medikation (MedicationAdministration)")

STATUS = (
    "in-progress",
    "not-done",
    "on-hold",
    "completed",
    "entered-in-error",
    "stopped",
    "unknown",
)


@R(
    "status_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="MedicationAdministration.status must be present.",
)
def status_required(r, ctx):
    if not r.get("status"):
        return "MedicationAdministration.status is missing."


@R(
    "medication_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="MedicationAdministration.medication[x] (medicationReference or medicationCodeableConcept) must be present.",
)
def medication_required(r, ctx):
    if not r.get("medicationReference") and not r.get("medicationCodeableConcept"):
        return "MedicationAdministration.medication[x] is missing."


@R(
    "subject_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="MedicationAdministration.subject must be present.",
)
def subject_required(r, ctx):
    if not r.get("subject"):
        return "MedicationAdministration.subject is missing."


@R(
    "effective_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="MedicationAdministration.effective[x] (effectiveDateTime or effectivePeriod) must be present.",
)
def effective_required(r, ctx):
    if not r.get("effectiveDateTime") and not r.get("effectivePeriod"):
        return "MedicationAdministration.effective[x] is missing."


@R(
    "effective_not_future",
    category="plausibility",
    severity="warning",
    enabled=True,
    description="MedicationAdministration.effectiveDateTime must not lie in the future.",
)
def effective_not_future(r, ctx):
    eff = r.get("effectiveDateTime", "")
    if eff and is_future(eff):
        return f"MedicationAdministration.effectiveDateTime '{eff}' is in the future."


@R(
    "effective_period_end_after_start",
    category="plausibility",
    severity="error",
    enabled=True,
    description="MedicationAdministration.effectivePeriod.end must not lie before start (FHIR invariant per-1).",
)
def effective_period_end_after_start(r, ctx):
    period = r.get("effectivePeriod", {})
    start, end = period.get("start"), period.get("end")
    if start and end and end_before_start(start, end):
        return "MedicationAdministration.effectivePeriod.end is before start."


@R(
    "subject_reference_format",
    category="integrity",
    severity="error",
    enabled=True,
    description="MedicationAdministration.subject.reference must have the form 'Patient/{id}'.",
)
def subject_reference_format(r, ctx):
    ref = r.get("subject", {}).get("reference", "")
    if ref and not is_reference_to(ref, "Patient"):
        return (
            f"MedicationAdministration.subject.reference '{ref}' must follow "
            "'Patient/{id}' format."
        )


# --- rules beyond the original set -----------------------------------------

R(
    "note_cleartext_check",
    category="privacy",
    severity="warning",
    description=(
        "MedicationAdministration.note.text and dosage.text must not be longer than "
        "50 characters; long free text may contain personal data."
    ),
)(cleartext("MedicationAdministration.note or dosage.text", "note.text", "dosage.text"))

R(
    "text_forbidden",
    category="privacy",
    severity="info",
    description="MedicationAdministration.text (narrative) must not be present; it may contain cleartext personal data.",
)(
    forbidden(
        "MedicationAdministration.text is present. Narratives may contain cleartext personal data.",
        "text",
    )
)

R(
    "status_valid",
    category="coding",
    severity="error",
    description="MedicationAdministration.status must be a value of the FHIR medication-admin-status value set.",
)(one_of("MedicationAdministration.status", "status", STATUS))

R(
    "medication_coding_known_system",
    category="coding",
    severity="warning",
    description="MedicationAdministration.medicationCodeableConcept must contain a PZN or ATC coding.",
)(medication_known_system("MedicationAdministration"))

R(
    "atc_code_format",
    category="coding",
    severity="error",
    description="An ATC code in medicationCodeableConcept must be a valid ATC code.",
)(atc_format("MedicationAdministration.medicationCodeableConcept", "medicationCodeableConcept"))

R(
    "pzn_code_format",
    category="coding",
    severity="error",
    description="A PZN in medicationCodeableConcept must have 8 digits.",
)(pzn_format("MedicationAdministration.medicationCodeableConcept", "medicationCodeableConcept"))

R(
    "dose_ucum",
    category="coding",
    severity="warning",
    description="MedicationAdministration.dosage.dose must use a UCUM unit (required by MII Medikation).",
)(ucum_quantity("MedicationAdministration.dosage.dose", "dosage.dose"))

R(
    "medication_reference_format",
    category="integrity",
    severity="error",
    description="MedicationAdministration.medicationReference.reference must have the form 'Medication/{id}'.",
)(medication_reference("MedicationAdministration"))

R(
    "context_reference_format",
    category="integrity",
    severity="error",
    description="MedicationAdministration.context.reference must have the form 'Encounter/{id}' or 'EpisodeOfCare/{id}'.",
)(references("MedicationAdministration.context", "context", "Encounter", "EpisodeOfCare"))

R(
    "request_reference_format",
    category="integrity",
    severity="warning",
    description="MedicationAdministration.request.reference must have the form 'MedicationRequest/{id}'.",
)(references("MedicationAdministration.request", "request", "MedicationRequest"))

R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="MedicationAdministration.meta.profile must reference an MII core data set profile.",
)(mii_profile("MedicationAdministration"))
