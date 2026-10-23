"""DiagnosticReport: FHIR R4, laboratory rules from MII KDS Laborbefund (DiagnosticReportLab)."""

from app.services.rules.fhir import (
    LOINC,
    V2_0074,
    before,
    coding_complete,
    forbidden,
    get,
    has_coding,
    is_reference_to,
    mii_profile,
    not_future,
    one_of,
    period_in_order,
    present,
    references,
    required,
)
from app.services.rules.registry import RuleContext, rules_for

R = rules_for("DiagnosticReport", profile="FHIR R4, Laborregeln aus MII KDS Laborbefund (DiagnosticReportLab)")

STATUS = (
    "registered",
    "partial",
    "preliminary",
    "final",
    "amended",
    "corrected",
    "appended",
    "cancelled",
    "entered-in-error",
    "unknown",
)


def is_lab(r: dict, ctx: RuleContext) -> bool:
    return ctx.remember(
        "lab",
        lambda: any(
            has_coding(c, V2_0074, "LAB") or has_coding(c, LOINC, "26436-6")
            for c in get(r, "category")
        ),
    )


@R(
    "note_cleartext_check",
    category="privacy",
    severity="warning",
    enabled=True,
    description=(
        "DiagnosticReport.conclusion must not be longer than 50 characters and text.div "
        "not longer than 100 characters; long free text may contain personal data."
    ),
)
def note_cleartext_check(r, ctx):
    conclusion = r.get("conclusion", "")
    narrative = r.get("text", {}).get("div", "")
    if (conclusion and len(conclusion) > 50) or (narrative and len(narrative) > 100):
        return (
            "DiagnosticReport.conclusion or text.div contains a long free-text string "
            "that may include personal data."
        )


@R(
    "status_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="DiagnosticReport.status must be present.",
)
def status_required(r, ctx):
    if not r.get("status"):
        return "DiagnosticReport.status is missing."


@R(
    "code_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="DiagnosticReport.code must be present.",
)
def code_required(r, ctx):
    if not r.get("code"):
        return "DiagnosticReport.code is missing."


@R(
    "subject_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="DiagnosticReport.subject must be present.",
)
def subject_required(r, ctx):
    if not r.get("subject"):
        return "DiagnosticReport.subject is missing."


@R(
    "subject_reference_format",
    category="integrity",
    severity="error",
    enabled=True,
    description="DiagnosticReport.subject.reference must have the form 'Patient/{id}'.",
)
def subject_reference_format(r, ctx):
    ref = r.get("subject", {}).get("reference", "")
    if ref and not is_reference_to(ref, "Patient"):
        return f"DiagnosticReport.subject.reference '{ref}' must follow 'Patient/{{id}}' format."


# --- rules beyond the original set -----------------------------------------

R(
    "text_forbidden",
    category="privacy",
    severity="info",
    description="DiagnosticReport.text (narrative) must not be present; it may contain cleartext personal data.",
)(forbidden("DiagnosticReport.text is present. Narratives may contain cleartext personal data.", "text"))

R(
    "status_valid",
    category="coding",
    severity="error",
    description="DiagnosticReport.status must be a value of the FHIR DiagnosticReportStatus value set.",
)(one_of("DiagnosticReport.status", "status", STATUS))

R(
    "category_required",
    category="completeness",
    severity="warning",
    description="DiagnosticReport.category must be present.",
)(required("DiagnosticReport.category is missing.", "category"))

R(
    "identifier_required",
    category="completeness",
    severity="info",
    description="DiagnosticReport.identifier must be present (report number, required by MII DiagnosticReportLab).",
)(required("DiagnosticReport.identifier is missing.", "identifier"))

R(
    "effective_required",
    category="completeness",
    severity="warning",
    description="DiagnosticReport.effective[x] must be present.",
)(required("DiagnosticReport.effective[x] is missing.", "effectiveDateTime", "effectivePeriod"))

R(
    "issued_required",
    category="completeness",
    severity="info",
    description="DiagnosticReport.issued must be present.",
)(required("DiagnosticReport.issued is missing.", "issued"))

R(
    "code_coding_complete",
    category="coding",
    severity="warning",
    description="Every DiagnosticReport.code.coding must carry both system and code.",
)(coding_complete("DiagnosticReport.code", "code"))

R(
    "effective_not_future",
    category="plausibility",
    severity="warning",
    description="DiagnosticReport.effectiveDateTime must not lie in the future.",
)(not_future("DiagnosticReport.effectiveDateTime", "effectiveDateTime"))

R(
    "issued_not_future",
    category="plausibility",
    severity="warning",
    description="DiagnosticReport.issued must not lie in the future.",
)(not_future("DiagnosticReport.issued", "issued"))


@R(
    "issued_after_effective",
    category="plausibility",
    severity="warning",
    description="DiagnosticReport.issued must not lie before effectiveDateTime.",
)
def issued_after_effective(r, ctx):
    if before(r.get("effectiveDateTime"), r.get("issued")):
        return (
            f"DiagnosticReport.issued '{r['issued']}' is before effectiveDateTime "
            f"'{r['effectiveDateTime']}'."
        )


R(
    "effective_period_end_after_start",
    category="plausibility",
    severity="error",
    description="DiagnosticReport.effectivePeriod.end must not lie before start (FHIR invariant per-1).",
)(period_in_order("DiagnosticReport.effectivePeriod", "effectivePeriod"))

R(
    "result_reference_format",
    category="integrity",
    severity="error",
    description="DiagnosticReport.result.reference must have the form 'Observation/{id}'.",
)(references("DiagnosticReport.result", "result", "Observation"))

R(
    "basedon_reference_format",
    category="integrity",
    severity="warning",
    description="DiagnosticReport.basedOn.reference must point to a request resource, usually 'ServiceRequest/{id}'.",
)(
    references(
        "DiagnosticReport.basedOn",
        "basedOn",
        "ServiceRequest",
        "CarePlan",
        "ImmunizationRecommendation",
        "MedicationRequest",
        "NutritionOrder",
    )
)

R(
    "encounter_reference_format",
    category="integrity",
    severity="error",
    description="DiagnosticReport.encounter.reference must have the form 'Encounter/{id}'.",
)(references("DiagnosticReport.encounter", "encounter", "Encounter"))


@R(
    "lab_category_coding",
    category="coding",
    severity="warning",
    description=(
        "A laboratory DiagnosticReport must be categorized with both LOINC 26436-6 and "
        "v2-0074 LAB (MII DiagnosticReportLab)."
    ),
)
def lab_category_coding(r, ctx):
    if not is_lab(r, ctx):
        return None
    cats = get(r, "category")
    if not (any(has_coding(c, LOINC, "26436-6") for c in cats) and any(has_coding(c, V2_0074, "LAB") for c in cats)):
        return "Laboratory DiagnosticReport.category lacks LOINC 26436-6 or v2-0074 LAB."


@R(
    "lab_code_loinc",
    category="coding",
    severity="warning",
    description="A laboratory DiagnosticReport.code must contain LOINC 11502-2 (Laboratory report).",
)
def lab_code_loinc(r, ctx):
    if is_lab(r, ctx) and not has_coding(r.get("code"), LOINC, "11502-2"):
        return "Laboratory DiagnosticReport.code has no LOINC 11502-2 coding."


@R(
    "lab_result_required",
    category="completeness",
    severity="warning",
    description="A laboratory DiagnosticReport must reference its results (MII DiagnosticReportLab).",
)
def lab_result_required(r, ctx):
    if is_lab(r, ctx) and not present(r.get("result")):
        return "Laboratory DiagnosticReport has no result."


@R(
    "lab_basedon_required",
    category="completeness",
    severity="info",
    description="A laboratory DiagnosticReport must reference its order in basedOn (MII DiagnosticReportLab).",
)
def lab_basedon_required(r, ctx):
    if is_lab(r, ctx) and not present(r.get("basedOn")):
        return "Laboratory DiagnosticReport has no basedOn."


R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="DiagnosticReport.meta.profile must reference an MII core data set profile.",
)(mii_profile("DiagnosticReport"))
