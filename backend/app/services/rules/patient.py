"""Patient: MII KDS Person (Patient, PatientPseudonymisiert)."""

import re
from datetime import datetime

from app.services.rules.fhir import (
    FHIR_DATE,
    before,
    forbidden,
    has_coding,
    is_future,
    mii_profile,
    not_future,
    one_of,
    present,
    required,
)
from app.services.rules.registry import rules_for

R = rules_for("Patient", profile="MII KDS Person (Patient, PatientPseudonymisiert)")

PSEUDED = ("http://terminology.hl7.org/CodeSystem/v3-ObservationValue", "PSEUDED")
GENDER_AMTLICH = "http://fhir.de/StructureDefinition/gender-amtlich-de"


async def _with_observation(validator, resources):
    ids = [r.get("id") for r in resources if r.get("id")]
    return await validator._check_linked_resources(ids, "Observation")


async def _with_condition(validator, resources):
    ids = [r.get("id") for r in resources if r.get("id")]
    return await validator._check_linked_resources(ids, "Condition")


# --- privacy ---------------------------------------------------------------


@R(
    "text_forbidden",
    category="privacy",
    severity="info",
    description="Patient.text (narrative) must not be present; it may contain cleartext personal data.",
)
def text_forbidden(r, ctx):
    if r.get("text"):
        return "Patient.text is present. Cleartext are forbidden in pseudonymized data."


@R(
    "name_forbidden",
    category="privacy",
    severity="error",
    enabled=True,
    description="Patient.name must not be present in pseudonymized data.",
)
def name_forbidden(r, ctx):
    if r.get("name"):
        return "Patient.name is present. Cleartext names are forbidden in pseudonymized data."


@R(
    "address_forbidden",
    category="privacy",
    severity="error",
    enabled=True,
    description="The first Patient.address must not contain line, city or text; postal code and country are allowed.",
)
def address_forbidden(r, ctx):
    addresses = r.get("address", [])
    if addresses:
        addr = addresses[0]
        if addr.get("line") or addr.get("city") or addr.get("text"):
            return "Patient.address contains forbidden fields (line, city, or text)."


@R(
    "telecom_forbidden",
    category="privacy",
    severity="error",
    enabled=True,
    description="Patient.telecom (phone numbers, e-mail addresses) must not be present.",
)
def telecom_forbidden(r, ctx):
    if r.get("telecom"):
        return "Patient.telecom is present. Contact data is forbidden in pseudonymized data."


@R(
    "photo_forbidden",
    category="privacy",
    severity="error",
    enabled=True,
    description="Patient.photo must not be present.",
)
def photo_forbidden(r, ctx):
    if r.get("photo"):
        return "Patient.photo is present and must be removed."


@R(
    "pseudonym_format_check",
    category="privacy",
    severity="error",
    enabled=True,
    pattern="^20[0-9]{7}$",
    description=(
        "Reports a Patient.id that matches the pattern of an original, "
        "non-pseudonymized patient ID. Set the pattern to your site's original ID format."
    ),
)
def pseudonym_format_check(r, ctx):
    rid = ctx.resource_id
    if ctx.pattern and re.match(ctx.pattern, rid):
        return f"Patient.id '{rid}' is not pseudonymized."


@R(
    "identifier_pseudonym_check",
    category="privacy",
    severity="error",
    enabled=True,
    pattern="^20[0-9]{7}$",
    description=(
        "Reports a Patient.identifier value that matches the pattern of an original, "
        "non-pseudonymized patient ID. Set the pattern to your site's original ID format."
    ),
)
def identifier_pseudonym_check(r, ctx):
    if not ctx.pattern:
        return None
    for ident in r.get("identifier", []):
        value = ident.get("value", "")
        if value and re.match(ctx.pattern, value):
            return f"Patient.identifier value '{value}' not pseudonymized."


# --- completeness ----------------------------------------------------------


@R(
    "has_observation",
    category="completeness",
    severity="warning",
    prepare=_with_observation,
    description=(
        "The patient must have at least one Observation on the server. "
        "Sends one extra request per patient and noticeably slows down runs."
    ),
)
def has_observation(r, ctx):
    if ctx.resource_id not in ctx.page:
        return f"Patient/{ctx.resource_id} has no linked Observation."


@R(
    "has_condition",
    category="completeness",
    severity="warning",
    prepare=_with_condition,
    description=(
        "The patient must have at least one Condition on the server. "
        "Sends one extra request per patient and noticeably slows down runs."
    ),
)
def has_condition(r, ctx):
    if ctx.resource_id not in ctx.page:
        return f"Patient/{ctx.resource_id} has no linked Condition."


@R(
    "identifier_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Patient.identifier must contain at least one identifier.",
)
def identifier_required(r, ctx):
    if not r.get("identifier"):
        return "Patient.identifier is missing. At least one identifier is required."


@R(
    "birthdate_required",
    category="completeness",
    severity="warning",
    enabled=True,
    description="Patient.birthDate must be present.",
)
def birthdate_required(r, ctx):
    if not r.get("birthDate"):
        return "Patient.birthDate is missing."


@R(
    "gender_required",
    category="completeness",
    severity="warning",
    enabled=True,
    description="Patient.gender must be present.",
)
def gender_required(r, ctx):
    if not r.get("gender"):
        return "Patient.gender is missing."


# --- plausibility ----------------------------------------------------------


@R(
    "birthdate_not_future",
    category="plausibility",
    severity="error",
    enabled=True,
    description="Patient.birthDate must not lie in the future.",
)
def birthdate_not_future(r, ctx):
    bd = r.get("birthDate", "")
    if bd and is_future(bd):
        return f"Patient.birthDate '{bd}' is in the future."


@R(
    "birthdate_plausible_range",
    category="plausibility",
    severity="warning",
    enabled=True,
    description="The year of Patient.birthDate must not lie more than 150 years in the past.",
)
def birthdate_plausible_range(r, ctx):
    bd = r.get("birthDate", "")
    if bd and datetime.now().year - int(bd[:4]) > 150:
        return f"Patient.birthDate '{bd}' is more than 150 years in the past."


# --- rules beyond the original set -----------------------------------------

R(
    "managingorganization_required",
    category="completeness",
    severity="info",
    description="Patient.managingOrganization must be present.",
)(required("Patient.managingOrganization is missing.", "managingOrganization"))

R(
    "contact_forbidden",
    category="privacy",
    severity="error",
    description="Patient.contact (relatives, guardians) must not be present in pseudonymized data.",
)(forbidden("Patient.contact is present. Contact persons are forbidden in pseudonymized data.", "contact"))


@R(
    "pseudonymized_identifier_type",
    category="privacy",
    severity="warning",
    description=(
        "At least one Patient.identifier must be marked as pseudonymized "
        "(type PSEUDED from v3-ObservationValue), as required by MII PatientPseudonymisiert."
    ),
)
def pseudonymized_identifier_type(r, ctx):
    identifiers = r.get("identifier") or []
    if identifiers and not any(has_coding(i.get("type"), *PSEUDED) for i in identifiers if isinstance(i, dict)):
        return "Patient has no identifier of type PSEUDED."


@R(
    "birthdate_precision",
    category="privacy",
    severity="warning",
    description=(
        "Reports a Patient.birthDate given to the day. Enable it if your "
        "pseudonymization keeps only the year or year and month."
    ),
)
def birthdate_precision(r, ctx):
    bd = r.get("birthDate")
    if isinstance(bd, str) and len(bd) >= 10:
        return f"Patient.birthDate '{bd}' contains the full date of birth."


R(
    "gender_valid",
    category="coding",
    severity="error",
    description="Patient.gender must be one of male, female, other, unknown.",
)(one_of("Patient.gender", "gender", ("male", "female", "other", "unknown")))


@R(
    "gender_other_amtlich",
    category="coding",
    severity="warning",
    description=(
        "Patient.gender 'other' must carry the extension gender-amtlich-de "
        "with the German administrative gender (MII invariant mii-pat-1)."
    ),
)
def gender_other_amtlich(r, ctx):
    if r.get("gender") == "other":
        exts = r.get("_gender", {}).get("extension", []) if isinstance(r.get("_gender"), dict) else []
        if not any(e.get("url") == GENDER_AMTLICH for e in exts if isinstance(e, dict)):
            return "Patient.gender is 'other' without extension gender-amtlich-de."


@R(
    "birthdate_format",
    category="plausibility",
    severity="error",
    description="Patient.birthDate must be a FHIR date (YYYY, YYYY-MM or YYYY-MM-DD).",
)
def birthdate_format(r, ctx):
    bd = r.get("birthDate")
    if present(bd) and not (isinstance(bd, str) and FHIR_DATE.match(bd)):
        return f"Patient.birthDate '{bd}' is not a valid FHIR date."


@R(
    "deceased_after_birth",
    category="plausibility",
    severity="error",
    description="Patient.deceasedDateTime must not lie before Patient.birthDate.",
)
def deceased_after_birth(r, ctx):
    if before(r.get("birthDate"), r.get("deceasedDateTime")):
        return (
            f"Patient.deceasedDateTime '{r['deceasedDateTime']}' is before "
            f"birthDate '{r['birthDate']}'."
        )


R(
    "deceased_not_future",
    category="plausibility",
    severity="warning",
    description="Patient.deceasedDateTime must not lie in the future.",
)(not_future("Patient.deceasedDateTime", "deceasedDateTime"))


@R(
    "address_postalcode_required",
    category="completeness",
    severity="warning",
    description="Every Patient.address must contain a postal code (MII address of type 'both').",
)
def address_postalcode_required(r, ctx):
    for addr in r.get("address") or []:
        if isinstance(addr, dict) and not present(addr.get("postalCode")):
            return "Patient.address without postalCode."


@R(
    "address_country_required",
    category="completeness",
    severity="info",
    description="Every Patient.address must contain a country.",
)
def address_country_required(r, ctx):
    for addr in r.get("address") or []:
        if isinstance(addr, dict) and not present(addr.get("country")):
            return "Patient.address without country."


@R(
    "address_country_code",
    category="coding",
    severity="warning",
    description="Patient.address.country must be an ISO 3166 country code with 2 or 3 letters.",
)
def address_country_code(r, ctx):
    for addr in r.get("address") or []:
        country = addr.get("country") if isinstance(addr, dict) else None
        if present(country) and not re.fullmatch(r"[A-Z]{2,3}", str(country)):
            return f"Patient.address.country '{country}' is not an ISO 3166 code."


R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="Patient.meta.profile must reference an MII core data set profile.",
)(mii_profile("Patient"))
