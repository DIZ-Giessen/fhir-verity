"""MedicationRequest: MII KDS Medikation."""

from app.services.rules.fhir import (
    cleartext,
    forbidden,
    is_future,
    is_reference_to,
    mii_profile,
    one_of,
    period_in_order,
    references,
)
from app.services.rules.medication_common import (
    atc_format,
    dosage_text_or_structured,
    medication_known_system,
    medication_reference,
    pzn_format,
)
from app.services.rules.registry import rules_for

R = rules_for("MedicationRequest", profile="MII KDS Medikation (MedicationRequest)")

STATUS = (
    "active",
    "on-hold",
    "cancelled",
    "completed",
    "entered-in-error",
    "stopped",
    "draft",
    "unknown",
)
INTENT = (
    "proposal",
    "plan",
    "order",
    "original-order",
    "reflex-order",
    "filler-order",
    "instance-order",
    "option",
)


@R(
    "status_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="MedicationRequest.status must be present.",
)
def status_required(r, ctx):
    if not r.get("status"):
        return "MedicationRequest.status is missing."


@R(
    "intent_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="MedicationRequest.intent must be present.",
)
def intent_required(r, ctx):
    if not r.get("intent"):
        return "MedicationRequest.intent is missing."


@R(
    "medication_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="MedicationRequest.medication[x] (medicationReference or medicationCodeableConcept) must be present.",
)
def medication_required(r, ctx):
    if not r.get("medicationReference") and not r.get("medicationCodeableConcept"):
        return "MedicationRequest.medication[x] is missing."


@R(
    "subject_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="MedicationRequest.subject must be present.",
)
def subject_required(r, ctx):
    if not r.get("subject"):
        return "MedicationRequest.subject is missing."


@R(
    "authored_on_required",
    category="completeness",
    severity="warning",
    enabled=True,
    description=(
        "MedicationRequest.authoredOn must be present; a boundsPeriod in "
        "dosageInstruction.timing is accepted instead."
    ),
)
def authored_on_required(r, ctx):
    has_bounds = any(
        d.get("timing", {}).get("repeat", {}).get("boundsPeriod")
        for d in r.get("dosageInstruction", [])
    )
    if not r.get("authoredOn") and not has_bounds:
        return "MedicationRequest.authoredOn is missing and no boundsPeriod in dosageInstruction."


@R(
    "authored_not_future",
    category="plausibility",
    severity="warning",
    enabled=True,
    description="MedicationRequest.authoredOn must not lie in the future.",
)
def authored_not_future(r, ctx):
    authored = r.get("authoredOn", "")
    if authored and is_future(authored):
        return f"MedicationRequest.authoredOn '{authored}' is in the future."


@R(
    "subject_reference_format",
    category="integrity",
    severity="error",
    enabled=True,
    description="MedicationRequest.subject.reference must have the form 'Patient/{id}'.",
)
def subject_reference_format(r, ctx):
    ref = r.get("subject", {}).get("reference", "")
    if ref and not is_reference_to(ref, "Patient"):
        return f"MedicationRequest.subject.reference '{ref}' must follow 'Patient/{{id}}' format."


# --- rules beyond the original set -----------------------------------------

R(
    "note_cleartext_check",
    category="privacy",
    severity="warning",
    description=(
        "MedicationRequest.note.text and dosageInstruction.text must not be longer "
        "than 50 characters; long free text may contain personal data."
    ),
)(cleartext("MedicationRequest.note or dosageInstruction.text", "note.text", "dosageInstruction.text"))

R(
    "text_forbidden",
    category="privacy",
    severity="info",
    description="MedicationRequest.text (narrative) must not be present; it may contain cleartext personal data.",
)(forbidden("MedicationRequest.text is present. Narratives may contain cleartext personal data.", "text"))

R(
    "status_valid",
    category="coding",
    severity="error",
    description="MedicationRequest.status must be a value of the FHIR medicationrequest-status value set.",
)(one_of("MedicationRequest.status", "status", STATUS))

R(
    "intent_valid",
    category="coding",
    severity="error",
    description="MedicationRequest.intent must be a value of the FHIR medicationrequest-intent value set.",
)(one_of("MedicationRequest.intent", "intent", INTENT))

R(
    "medication_coding_known_system",
    category="coding",
    severity="warning",
    description="MedicationRequest.medicationCodeableConcept must contain a PZN or ATC coding.",
)(medication_known_system("MedicationRequest"))

R(
    "atc_code_format",
    category="coding",
    severity="error",
    description="An ATC code in medicationCodeableConcept must be a valid ATC code.",
)(atc_format("MedicationRequest.medicationCodeableConcept", "medicationCodeableConcept"))

R(
    "pzn_code_format",
    category="coding",
    severity="error",
    description="A PZN in medicationCodeableConcept must have 8 digits.",
)(pzn_format("MedicationRequest.medicationCodeableConcept", "medicationCodeableConcept"))

R(
    "medication_reference_format",
    category="integrity",
    severity="error",
    description="MedicationRequest.medicationReference.reference must have the form 'Medication/{id}'.",
)(medication_reference("MedicationRequest"))

R(
    "encounter_reference_format",
    category="integrity",
    severity="error",
    description="MedicationRequest.encounter.reference must have the form 'Encounter/{id}'.",
)(references("MedicationRequest.encounter", "encounter", "Encounter"))

R(
    "dosage_text_or_structured",
    category="completeness",
    severity="warning",
    description="Every MedicationRequest.dosageInstruction must have text or doseAndRate (MII DosageDE, dsg-1).",
)(dosage_text_or_structured("MedicationRequest.dosageInstruction", "dosageInstruction"))

R(
    "bounds_period_end_after_start",
    category="plausibility",
    severity="error",
    description="dosageInstruction.timing.repeat.boundsPeriod.end must not lie before start (FHIR invariant per-1).",
)(
    period_in_order(
        "MedicationRequest.dosageInstruction.timing.repeat.boundsPeriod",
        "dosageInstruction.timing.repeat.boundsPeriod",
    )
)


@R(
    "do_not_perform_forbidden",
    category="plausibility",
    severity="warning",
    description="MedicationRequest.doNotPerform must not be used (excluded by MII Medikation).",
)
def do_not_perform_forbidden(r, ctx):
    if r.get("doNotPerform") is not None:
        return "MedicationRequest.doNotPerform is present."


R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="MedicationRequest.meta.profile must reference an MII core data set profile.",
)(mii_profile("MedicationRequest"))
