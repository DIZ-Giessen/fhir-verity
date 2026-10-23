"""MedicationStatement: MII KDS Medikation."""

from app.services.rules.fhir import (
    cleartext,
    forbidden,
    mii_profile,
    not_future,
    one_of,
    period_in_order,
    references,
    required,
)
from app.services.rules.medication_common import (
    atc_format,
    dosage_text_or_structured,
    medication_known_system,
    medication_reference,
    pzn_format,
)
from app.services.rules.registry import rules_for

R = rules_for("MedicationStatement", profile="MII KDS Medikation (MedicationStatement)")

STATUS = (
    "active",
    "completed",
    "entered-in-error",
    "intended",
    "stopped",
    "on-hold",
    "unknown",
    "not-taken",
)

R(
    "status_required",
    category="completeness",
    severity="error",
    description="MedicationStatement.status must be present.",
)(required("MedicationStatement.status is missing.", "status"))

R(
    "medication_required",
    category="completeness",
    severity="error",
    description="MedicationStatement.medication[x] (medicationReference or medicationCodeableConcept) must be present.",
)(
    required(
        "MedicationStatement.medication[x] is missing.",
        "medicationReference",
        "medicationCodeableConcept",
    )
)

R(
    "subject_required",
    category="completeness",
    severity="error",
    description="MedicationStatement.subject must be present.",
)(required("MedicationStatement.subject is missing.", "subject"))

R(
    "subject_reference_format",
    category="integrity",
    severity="error",
    description="MedicationStatement.subject.reference must have the form 'Patient/{id}'.",
)(references("MedicationStatement.subject", "subject", "Patient"))

R(
    "effective_required",
    category="completeness",
    severity="warning",
    description="MedicationStatement.effective[x] must be present (required by MII Medikation).",
)(required("MedicationStatement.effective[x] is missing.", "effectiveDateTime", "effectivePeriod"))

R(
    "note_cleartext_check",
    category="privacy",
    severity="warning",
    description=(
        "MedicationStatement.note.text and dosage.text must not be longer than 50 "
        "characters; long free text may contain personal data."
    ),
)(cleartext("MedicationStatement.note or dosage.text", "note.text", "dosage.text"))

R(
    "text_forbidden",
    category="privacy",
    severity="info",
    description="MedicationStatement.text (narrative) must not be present; it may contain cleartext personal data.",
)(forbidden("MedicationStatement.text is present. Narratives may contain cleartext personal data.", "text"))

R(
    "status_valid",
    category="coding",
    severity="error",
    description="MedicationStatement.status must be a value of the FHIR medication-statement-status value set.",
)(one_of("MedicationStatement.status", "status", STATUS))

R(
    "medication_coding_known_system",
    category="coding",
    severity="warning",
    description="MedicationStatement.medicationCodeableConcept must contain a PZN or ATC coding.",
)(medication_known_system("MedicationStatement"))

R(
    "atc_code_format",
    category="coding",
    severity="error",
    description="An ATC code in medicationCodeableConcept must be a valid ATC code.",
)(atc_format("MedicationStatement.medicationCodeableConcept", "medicationCodeableConcept"))

R(
    "pzn_code_format",
    category="coding",
    severity="error",
    description="A PZN in medicationCodeableConcept must have 8 digits.",
)(pzn_format("MedicationStatement.medicationCodeableConcept", "medicationCodeableConcept"))

R(
    "effective_not_future",
    category="plausibility",
    severity="warning",
    description="MedicationStatement.effectiveDateTime and effectivePeriod.start must not lie in the future.",
)(not_future("MedicationStatement.effective", "effectiveDateTime", "effectivePeriod.start"))

R(
    "effective_period_end_after_start",
    category="plausibility",
    severity="error",
    description="MedicationStatement.effectivePeriod.end must not lie before start (FHIR invariant per-1).",
)(period_in_order("MedicationStatement.effectivePeriod", "effectivePeriod"))

R(
    "date_asserted_not_future",
    category="plausibility",
    severity="warning",
    description="MedicationStatement.dateAsserted must not lie in the future.",
)(not_future("MedicationStatement.dateAsserted", "dateAsserted"))

R(
    "dosage_text_or_structured",
    category="completeness",
    severity="warning",
    description="Every MedicationStatement.dosage must have text or doseAndRate (MII DosageDE, dsg-1).",
)(dosage_text_or_structured("MedicationStatement.dosage", "dosage"))

R(
    "medication_reference_format",
    category="integrity",
    severity="error",
    description="MedicationStatement.medicationReference.reference must have the form 'Medication/{id}'.",
)(medication_reference("MedicationStatement"))

R(
    "context_reference_format",
    category="integrity",
    severity="error",
    description="MedicationStatement.context.reference must have the form 'Encounter/{id}' or 'EpisodeOfCare/{id}'.",
)(references("MedicationStatement.context", "context", "Encounter", "EpisodeOfCare"))

R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="MedicationStatement.meta.profile must reference an MII core data set profile.",
)(mii_profile("MedicationStatement"))
