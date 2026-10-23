"""ImagingStudy: MII KDS Bildgebung (Bildgebungsstudie)."""

from app.services.rules.fhir import (
    forbidden,
    get,
    mii_profile,
    not_future,
    one_of,
    present,
    references,
    required,
)
from app.services.rules.registry import rules_for

R = rules_for("ImagingStudy", profile="MII KDS Bildgebung (Bildgebungsstudie)")

DICOM_DCM = "http://dicom.nema.org/resources/ontology/DCM"
DICOM_UID_SYSTEM = "urn:dicom:uid"
STATUS = ("registered", "available", "cancelled", "entered-in-error", "unknown")

R(
    "status_required",
    category="completeness",
    severity="error",
    description="ImagingStudy.status must be present.",
)(required("ImagingStudy.status is missing.", "status"))

R(
    "subject_required",
    category="completeness",
    severity="error",
    description="ImagingStudy.subject must be present.",
)(required("ImagingStudy.subject is missing.", "subject"))

R(
    "started_required",
    category="completeness",
    severity="warning",
    description="ImagingStudy.started must be present.",
)(required("ImagingStudy.started is missing.", "started"))


@R(
    "study_uid_required",
    category="completeness",
    severity="warning",
    description="ImagingStudy.identifier must contain the DICOM Study Instance UID (system urn:dicom:uid).",
)
def study_uid_required(r, ctx):
    if not any(
        isinstance(i, dict) and i.get("system") == DICOM_UID_SYSTEM and present(i.get("value"))
        for i in get(r, "identifier")
    ):
        return "ImagingStudy has no identifier with system urn:dicom:uid."


@R(
    "series_uid_required",
    category="completeness",
    severity="error",
    description="Every ImagingStudy.series must have a uid.",
)
def series_uid_required(r, ctx):
    for s in r.get("series") or []:
        if isinstance(s, dict) and not present(s.get("uid")):
            return "ImagingStudy.series without uid."


@R(
    "series_modality_required",
    category="completeness",
    severity="error",
    description="Every ImagingStudy.series must have a modality.",
)
def series_modality_required(r, ctx):
    for s in r.get("series") or []:
        if isinstance(s, dict) and not present(s.get("modality")):
            return "ImagingStudy.series without modality."


@R(
    "instance_uid_required",
    category="completeness",
    severity="error",
    description="Every ImagingStudy.series.instance must have a uid and a sopClass.",
)
def instance_uid_required(r, ctx):
    for inst in get(r, "series.instance"):
        if isinstance(inst, dict) and not (present(inst.get("uid")) and present(inst.get("sopClass"))):
            return "ImagingStudy.series.instance without uid or sopClass."


R(
    "text_forbidden",
    category="privacy",
    severity="info",
    description="ImagingStudy.text (narrative) must not be present; it may contain cleartext personal data.",
)(forbidden("ImagingStudy.text is present. Narratives may contain cleartext personal data.", "text"))

R(
    "status_valid",
    category="coding",
    severity="error",
    description="ImagingStudy.status must be a value of the FHIR ImagingStudyStatus value set.",
)(one_of("ImagingStudy.status", "status", STATUS))


@R(
    "modality_dicom",
    category="coding",
    severity="warning",
    description="ImagingStudy.modality and series.modality must use the DICOM code system (DCM, CID 33).",
)
def modality_dicom(r, ctx):
    for coding in get(r, "modality") + get(r, "series.modality"):
        if isinstance(coding, dict) and coding.get("system") != DICOM_DCM:
            return f"ImagingStudy modality '{coding.get('code')}' is not from {DICOM_DCM}."


R(
    "started_not_future",
    category="plausibility",
    severity="warning",
    description="ImagingStudy.started and series.started must not lie in the future.",
)(not_future("ImagingStudy.started", "started", "series.started"))


@R(
    "number_of_series_consistent",
    category="plausibility",
    severity="warning",
    description="ImagingStudy.numberOfSeries must match the number of series listed.",
)
def number_of_series_consistent(r, ctx):
    stated, series = r.get("numberOfSeries"), r.get("series")
    if isinstance(stated, int) and isinstance(series, list) and series and stated != len(series):
        return f"ImagingStudy.numberOfSeries is {stated}, but {len(series)} series are listed."


@R(
    "number_of_instances_consistent",
    category="plausibility",
    severity="warning",
    description="ImagingStudy.numberOfInstances must match the number of instances listed in all series.",
)
def number_of_instances_consistent(r, ctx):
    stated = r.get("numberOfInstances")
    instances = get(r, "series.instance")
    if isinstance(stated, int) and instances and stated != len(instances):
        return f"ImagingStudy.numberOfInstances is {stated}, but {len(instances)} instances are listed."


R(
    "subject_reference_format",
    category="integrity",
    severity="error",
    description="ImagingStudy.subject.reference must have the form 'Patient/{id}' (MII Bildgebung).",
)(references("ImagingStudy.subject", "subject", "Patient"))

R(
    "encounter_reference_format",
    category="integrity",
    severity="error",
    description="ImagingStudy.encounter.reference must have the form 'Encounter/{id}'.",
)(references("ImagingStudy.encounter", "encounter", "Encounter"))

R(
    "basedon_reference_format",
    category="integrity",
    severity="warning",
    description="ImagingStudy.basedOn.reference must point to a request, usually 'ServiceRequest/{id}'.",
)(references("ImagingStudy.basedOn", "basedOn", "ServiceRequest", "CarePlan", "Appointment", "AppointmentResponse", "Task"))

R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="ImagingStudy.meta.profile must reference an MII core data set profile.",
)(mii_profile("ImagingStudy"))
