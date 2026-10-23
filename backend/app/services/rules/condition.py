"""Condition: MII KDS Diagnose."""

from app.services.rules.fhir import (
    ALPHA_ID,
    ICD10GM,
    ICD10GM_CODE,
    ORPHANET,
    SNOMED,
    before,
    cleartext,
    code_format,
    code_versioned,
    coded_with,
    codings,
    forbidden,
    is_reference_to,
    mii_profile,
    not_future,
    present,
    references,
    required,
)
from app.services.rules.registry import rules_for

R = rules_for("Condition", profile="MII KDS Diagnose (Diagnose)")

CLINICAL = "http://terminology.hl7.org/CodeSystem/condition-clinical"
VERIFICATION = "http://terminology.hl7.org/CodeSystem/condition-ver-status"
CLINICAL_CODES = ("active", "recurrence", "relapse", "inactive", "remission", "resolved")
VERIFICATION_CODES = (
    "unconfirmed",
    "provisional",
    "differential",
    "confirmed",
    "refuted",
    "entered-in-error",
)
ONSET_FIELDS = ("onsetDateTime", "onsetAge", "onsetPeriod", "onsetRange", "onsetString")
ABATEMENT_FIELDS = (
    "abatementDateTime",
    "abatementAge",
    "abatementPeriod",
    "abatementRange",
    "abatementString",
)


def _status_code(concept, system):
    return next((c.get("code") for c in codings(concept) if c.get("system") == system), None)


R(
    "note_cleartext_check",
    category="privacy",
    severity="warning",
    enabled=True,
    description="Condition.note.text must not be longer than 50 characters; long free text may contain personal data.",
)(cleartext("Condition.note", "note.text"))


@R(
    "code_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Condition.code must be present.",
)
def code_required(r, ctx):
    if not r.get("code"):
        return "Condition.code is missing."


@R(
    "subject_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Condition.subject must be present.",
)
def subject_required(r, ctx):
    if not r.get("subject"):
        return "Condition.subject is missing."


@R(
    "clinicalstatus_required",
    category="completeness",
    severity="warning",
    description="Condition.clinicalStatus must be present.",
)
def clinicalstatus_required(r, ctx):
    if not r.get("clinicalStatus"):
        return "Condition.clinicalStatus is missing."


@R(
    "verificationstatus_required",
    category="completeness",
    severity="info",
    description="Condition.verificationStatus must be present.",
)
def verificationstatus_required(r, ctx):
    if not r.get("verificationStatus"):
        return "Condition.verificationStatus is missing."


@R(
    "onset_present",
    category="completeness",
    severity="info",
    description="Condition.onset[x] must be present.",
)
def onset_present(r, ctx):
    if not any(r.get(f) for f in ONSET_FIELDS):
        return "Condition.onset[x] is missing."


@R(
    "subject_reference_format",
    category="integrity",
    severity="error",
    enabled=True,
    description="Condition.subject.reference must have the form 'Patient/{id}'.",
)
def subject_reference_format(r, ctx):
    ref = r.get("subject", {}).get("reference", "")
    if ref and not is_reference_to(ref, "Patient"):
        return f"Condition.subject.reference '{ref}' must follow 'Patient/{{id}}' format."


# --- rules beyond the original set -----------------------------------------

R(
    "text_forbidden",
    category="privacy",
    severity="info",
    description="Condition.text (narrative) must not be present; it may contain cleartext personal data.",
)(forbidden("Condition.text is present. Narratives may contain cleartext personal data.", "text"))

R(
    "recorded_date_required",
    category="completeness",
    severity="warning",
    description="Condition.recordedDate must be present (required by MII Diagnose).",
)(required("Condition.recordedDate is missing.", "recordedDate"))

R(
    "recorded_date_not_future",
    category="plausibility",
    severity="warning",
    description="Condition.recordedDate must not lie in the future.",
)(not_future("Condition.recordedDate", "recordedDate"))

R(
    "onset_not_future",
    category="plausibility",
    severity="warning",
    description="Condition.onsetDateTime and onsetPeriod.start must not lie in the future.",
)(not_future("Condition.onset", "onsetDateTime", "onsetPeriod.start"))


@R(
    "abatement_after_onset",
    category="plausibility",
    severity="error",
    description="Condition.abatementDateTime must not lie before onsetDateTime.",
)
def abatement_after_onset(r, ctx):
    if before(r.get("onsetDateTime"), r.get("abatementDateTime")):
        return (
            f"Condition.abatementDateTime '{r['abatementDateTime']}' is before "
            f"onsetDateTime '{r['onsetDateTime']}'."
        )


R(
    "code_coding_known_system",
    category="coding",
    severity="warning",
    description="Condition.code must contain a coding from ICD-10-GM, Alpha-ID, SNOMED CT or Orphanet (MII Diagnose).",
)(coded_with("Condition.code", "code", ICD10GM, ALPHA_ID, SNOMED, ORPHANET))

R(
    "icd10gm_version_required",
    category="coding",
    severity="error",
    description="An ICD-10-GM coding in Condition.code must state the catalogue version (coding.version).",
)(code_versioned("Condition.code", "code", ICD10GM))

R(
    "icd10gm_code_format",
    category="coding",
    severity="error",
    description=(
        "An ICD-10-GM code must match the format of the German base profile, e.g. I10 or "
        "S72.01; markers such as +, * or ! belong in the Mehrfachcodierungs-Kennzeichen extension."
    ),
)(code_format("Condition.code", "code", ICD10GM, ICD10GM_CODE))


@R(
    "clinicalstatus_valid",
    category="coding",
    severity="error",
    description="Condition.clinicalStatus must be coded with the FHIR condition-clinical code system.",
)
def clinicalstatus_valid(r, ctx):
    status = r.get("clinicalStatus")
    if present(status) and _status_code(status, CLINICAL) not in CLINICAL_CODES:
        return "Condition.clinicalStatus has no valid condition-clinical code."


@R(
    "verificationstatus_valid",
    category="coding",
    severity="error",
    description="Condition.verificationStatus must be coded with the FHIR condition-ver-status code system.",
)
def verificationstatus_valid(r, ctx):
    status = r.get("verificationStatus")
    if present(status) and _status_code(status, VERIFICATION) not in VERIFICATION_CODES:
        return "Condition.verificationStatus has no valid condition-ver-status code."


@R(
    "abatement_clinicalstatus",
    category="plausibility",
    severity="warning",
    description=(
        "If Condition.abatement[x] is present, clinicalStatus must be inactive, "
        "resolved or remission (FHIR invariant con-4)."
    ),
)
def abatement_clinicalstatus(r, ctx):
    if not any(present(r.get(f)) for f in ABATEMENT_FIELDS):
        return None
    code = _status_code(r.get("clinicalStatus"), CLINICAL)
    if code is not None and code not in ("inactive", "resolved", "remission"):
        return f"Condition has abatement[x] but clinicalStatus '{code}'."


@R(
    "entered_in_error_without_clinicalstatus",
    category="plausibility",
    severity="warning",
    description="A Condition with verificationStatus entered-in-error must not have a clinicalStatus (FHIR invariant con-5).",
)
def entered_in_error_without_clinicalstatus(r, ctx):
    if _status_code(r.get("verificationStatus"), VERIFICATION) == "entered-in-error" and present(
        r.get("clinicalStatus")
    ):
        return "Condition is entered-in-error but has a clinicalStatus."


R(
    "bodysite_snomed",
    category="coding",
    severity="info",
    description="Condition.bodySite must be coded with SNOMED CT (MII Diagnose).",
)(coded_with("Condition.bodySite", "bodySite", SNOMED))

R(
    "encounter_reference_format",
    category="integrity",
    severity="error",
    description="Condition.encounter.reference must have the form 'Encounter/{id}'.",
)(references("Condition.encounter", "encounter", "Encounter"))

R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="Condition.meta.profile must reference an MII core data set profile.",
)(mii_profile("Condition"))
