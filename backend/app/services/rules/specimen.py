"""Specimen: MII KDS Biobank (Bioprobe)."""

from app.services.rules.fhir import (
    SNOMED,
    before,
    cleartext,
    coded_with,
    forbidden,
    get,
    mii_profile,
    not_future,
    one_of,
    present,
    references,
    required,
    ucum_quantity,
)
from app.services.rules.registry import rules_for

R = rules_for("Specimen", profile="MII KDS Biobank (Bioprobe)")

ICD_O_3 = "http://terminology.hl7.org/CodeSystem/icd-o-3"
STATUS = ("available", "unavailable", "unsatisfactory", "entered-in-error")

R(
    "status_required",
    category="completeness",
    severity="error",
    description="Specimen.status must be present (required by MII Bioprobe).",
)(required("Specimen.status is missing.", "status"))

R(
    "type_required",
    category="completeness",
    severity="error",
    description="Specimen.type must be present (required by MII Bioprobe).",
)(required("Specimen.type is missing.", "type"))

R(
    "subject_required",
    category="completeness",
    severity="error",
    description="Specimen.subject must be present (required by MII Bioprobe).",
)(required("Specimen.subject is missing.", "subject"))

R(
    "collection_required",
    category="completeness",
    severity="warning",
    description="Specimen.collection.collected[x] must be present (required by MII Bioprobe).",
)(required("Specimen.collection.collected[x] is missing.", "collection.collectedDateTime", "collection.collectedPeriod"))

R(
    "identifier_required",
    category="completeness",
    severity="info",
    description="Specimen.identifier must be present.",
)(required("Specimen.identifier is missing.", "identifier"))


@R(
    "container_type_required",
    category="completeness",
    severity="info",
    description="Every Specimen.container must have a type (required by MII Bioprobe).",
)
def container_type_required(r, ctx):
    for container in r.get("container") or []:
        if isinstance(container, dict) and not present(container.get("type")):
            return "Specimen.container without type."


@R(
    "processing_procedure_required",
    category="completeness",
    severity="info",
    description="Every Specimen.processing step must have a procedure (required by MII Bioprobe).",
)
def processing_procedure_required(r, ctx):
    for step in r.get("processing") or []:
        if isinstance(step, dict) and not present(step.get("procedure")):
            return "Specimen.processing without procedure."


R(
    "note_cleartext_check",
    category="privacy",
    severity="warning",
    description="Specimen.note.text must not be longer than 50 characters; long free text may contain personal data.",
)(cleartext("Specimen.note", "note.text"))

R(
    "text_forbidden",
    category="privacy",
    severity="info",
    description="Specimen.text (narrative) must not be present; it may contain cleartext personal data.",
)(forbidden("Specimen.text is present. Narratives may contain cleartext personal data.", "text"))

R(
    "status_valid",
    category="coding",
    severity="error",
    description="Specimen.status must be available, unavailable, unsatisfactory or entered-in-error.",
)(one_of("Specimen.status", "status", STATUS))

R(
    "type_snomed",
    category="coding",
    severity="warning",
    description="Specimen.type must be coded with SNOMED CT (MII Bioprobe sample types).",
)(coded_with("Specimen.type", "type", SNOMED))

R(
    "bodysite_coding",
    category="coding",
    severity="warning",
    description="Specimen.collection.bodySite must be coded with SNOMED CT or ICD-O-3 topography (MII invariant mii-bb-1).",
)(coded_with("Specimen.collection.bodySite", "collection.bodySite", SNOMED, ICD_O_3))

R(
    "collection_quantity_ucum",
    category="coding",
    severity="warning",
    description="Specimen.collection.quantity must use a UCUM unit.",
)(ucum_quantity("Specimen.collection.quantity", "collection.quantity"))

_capacity_ucum = ucum_quantity("Specimen.container.capacity", "container.capacity")
_specimen_quantity_ucum = ucum_quantity("Specimen.container.specimenQuantity", "container.specimenQuantity")


@R(
    "container_quantity_ucum",
    category="coding",
    severity="info",
    description="Specimen.container.capacity and specimenQuantity must use UCUM units.",
)
def container_quantity_ucum(r, ctx):
    return _capacity_ucum(r, ctx) or _specimen_quantity_ucum(r, ctx)

R(
    "collected_not_future",
    category="plausibility",
    severity="warning",
    description="Specimen.collection.collectedDateTime must not lie in the future.",
)(not_future("Specimen.collection.collectedDateTime", "collection.collectedDateTime"))

R(
    "received_not_future",
    category="plausibility",
    severity="warning",
    description="Specimen.receivedTime must not lie in the future.",
)(not_future("Specimen.receivedTime", "receivedTime"))


@R(
    "received_after_collected",
    category="plausibility",
    severity="warning",
    description="Specimen.receivedTime must not lie before collection.collectedDateTime.",
)
def received_after_collected(r, ctx):
    collected = (r.get("collection") or {}).get("collectedDateTime")
    if before(collected, r.get("receivedTime")):
        return f"Specimen.receivedTime '{r['receivedTime']}' is before collectedDateTime '{collected}'."


R(
    "subject_reference_format",
    category="integrity",
    severity="error",
    description="Specimen.subject.reference must have the form 'Patient/{id}' (MII Bioprobe).",
)(references("Specimen.subject", "subject", "Patient"))

R(
    "parent_reference_format",
    category="integrity",
    severity="error",
    description="Specimen.parent.reference must have the form 'Specimen/{id}'.",
)(references("Specimen.parent", "parent", "Specimen"))

R(
    "request_reference_format",
    category="integrity",
    severity="warning",
    description="Specimen.request.reference must have the form 'ServiceRequest/{id}'.",
)(references("Specimen.request", "request", "ServiceRequest"))


@R(
    "parent_not_self",
    category="integrity",
    severity="error",
    description="Specimen.parent must not reference the specimen itself.",
)
def parent_not_self(r, ctx):
    own = f"Specimen/{ctx.resource_id}"
    if ctx.resource_id and own in get(r, "parent.reference"):
        return "Specimen.parent references the specimen itself."


R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="Specimen.meta.profile must reference an MII core data set profile.",
)(mii_profile("Specimen"))
