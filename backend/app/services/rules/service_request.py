"""ServiceRequest: FHIR R4, laboratory rules from MII KDS Laborbefund (ServiceRequestLab)."""

from app.services.rules.fhir import (
    OBSERVATION_CATEGORY,
    cleartext,
    coding_complete,
    forbidden,
    get,
    has_coding,
    mii_profile,
    not_future,
    one_of,
    present,
    references,
    required,
)
from app.services.rules.registry import RuleContext, rules_for

R = rules_for("ServiceRequest", profile="FHIR R4, Laborregeln aus MII KDS Laborbefund (ServiceRequestLab)")

STATUS = ("draft", "active", "on-hold", "revoked", "completed", "entered-in-error", "unknown")
INTENT = (
    "proposal",
    "plan",
    "directive",
    "order",
    "original-order",
    "reflex-order",
    "filler-order",
    "instance-order",
    "option",
)


def is_lab(r: dict, ctx: RuleContext) -> bool:
    return ctx.remember(
        "lab",
        lambda: any(has_coding(c, OBSERVATION_CATEGORY, "laboratory") for c in get(r, "category")),
    )


R(
    "status_required",
    category="completeness",
    severity="error",
    description="ServiceRequest.status must be present.",
)(required("ServiceRequest.status is missing.", "status"))

R(
    "intent_required",
    category="completeness",
    severity="error",
    description="ServiceRequest.intent must be present.",
)(required("ServiceRequest.intent is missing.", "intent"))

R(
    "subject_required",
    category="completeness",
    severity="error",
    description="ServiceRequest.subject must be present.",
)(required("ServiceRequest.subject is missing.", "subject"))

R(
    "code_required",
    category="completeness",
    severity="error",
    description="ServiceRequest.code must be present.",
)(required("ServiceRequest.code is missing.", "code"))

R(
    "category_required",
    category="completeness",
    severity="warning",
    description="ServiceRequest.category must be present.",
)(required("ServiceRequest.category is missing.", "category"))

R(
    "authored_on_required",
    category="completeness",
    severity="warning",
    description="ServiceRequest.authoredOn must be present (required by MII ServiceRequestLab).",
)(required("ServiceRequest.authoredOn is missing.", "authoredOn"))

R(
    "identifier_required",
    category="completeness",
    severity="info",
    description="ServiceRequest.identifier must be present (order number, required by MII ServiceRequestLab).",
)(required("ServiceRequest.identifier is missing.", "identifier"))

R(
    "note_cleartext_check",
    category="privacy",
    severity="warning",
    description="ServiceRequest.note.text must not be longer than 50 characters; long free text may contain personal data.",
)(cleartext("ServiceRequest.note", "note.text"))

R(
    "patient_instruction_forbidden",
    category="privacy",
    severity="warning",
    description="ServiceRequest.patientInstruction must not be used; it is free text (excluded by MII ServiceRequestLab).",
)(forbidden("ServiceRequest.patientInstruction is present.", "patientInstruction"))

R(
    "text_forbidden",
    category="privacy",
    severity="info",
    description="ServiceRequest.text (narrative) must not be present; it may contain cleartext personal data.",
)(forbidden("ServiceRequest.text is present. Narratives may contain cleartext personal data.", "text"))

R(
    "status_valid",
    category="coding",
    severity="error",
    description="ServiceRequest.status must be a value of the FHIR request-status value set.",
)(one_of("ServiceRequest.status", "status", STATUS))

R(
    "intent_valid",
    category="coding",
    severity="error",
    description="ServiceRequest.intent must be a value of the FHIR request-intent value set.",
)(one_of("ServiceRequest.intent", "intent", INTENT))

R(
    "code_coding_complete",
    category="coding",
    severity="warning",
    description="Every ServiceRequest.code.coding must carry both system and code.",
)(coding_complete("ServiceRequest.code", "code"))


@R(
    "lab_order_status",
    category="plausibility",
    severity="info",
    description="A laboratory ServiceRequest should have status 'completed' and intent 'order' (MII ServiceRequestLab).",
)
def lab_order_status(r, ctx):
    if is_lab(r, ctx) and (r.get("status") != "completed" or r.get("intent") != "order"):
        return (
            f"Laboratory ServiceRequest has status '{r.get('status')}' and intent "
            f"'{r.get('intent')}' instead of completed/order."
        )


R(
    "authored_not_future",
    category="plausibility",
    severity="warning",
    description="ServiceRequest.authoredOn must not lie in the future.",
)(not_future("ServiceRequest.authoredOn", "authoredOn"))


@R(
    "body_site_forbidden",
    category="plausibility",
    severity="info",
    description="ServiceRequest.bodySite must not be used for laboratory orders (excluded by MII ServiceRequestLab).",
)
def body_site_forbidden(r, ctx):
    if is_lab(r, ctx) and present(r.get("bodySite")):
        return "Laboratory ServiceRequest has a bodySite."


R(
    "subject_reference_format",
    category="integrity",
    severity="error",
    description="ServiceRequest.subject.reference must have the form 'Patient/{id}'.",
)(references("ServiceRequest.subject", "subject", "Patient"))

R(
    "encounter_reference_format",
    category="integrity",
    severity="error",
    description="ServiceRequest.encounter.reference must have the form 'Encounter/{id}'.",
)(references("ServiceRequest.encounter", "encounter", "Encounter"))

R(
    "specimen_reference_format",
    category="integrity",
    severity="warning",
    description="ServiceRequest.specimen.reference must have the form 'Specimen/{id}'.",
)(references("ServiceRequest.specimen", "specimen", "Specimen"))

R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="ServiceRequest.meta.profile must reference an MII core data set profile.",
)(mii_profile("ServiceRequest"))
