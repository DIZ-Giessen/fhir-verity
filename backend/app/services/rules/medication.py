"""Medication: MII KDS Medikation."""

from app.services.rules.fhir import (
    ASK,
    ATC_DE,
    ATC_WHO,
    CAS,
    EDQM,
    SNOMED,
    UNII,
    codes_of,
    coded_with,
    forbidden,
    get,
    mii_profile,
    one_of,
    present,
    required,
    ucum_quantity,
)
from app.services.rules.medication_common import (
    MEDICATION_SYSTEMS,
    atc_format,
    pzn_format,
)
from app.services.rules.registry import rules_for

R = rules_for("Medication", profile="MII KDS Medikation (Medication)")


@R(
    "code_required",
    category="completeness",
    severity="error",
    enabled=True,
    description="Medication.code must be present with a coding or a text.",
)
def code_required(r, ctx):
    code = r.get("code", {})
    if not code or (not code.get("coding") and not code.get("text")):
        return "Medication.code is missing or has neither coding nor text."


@R(
    "code_coding_present",
    category="completeness",
    severity="warning",
    enabled=True,
    description="Medication.code must contain a coding; a text alone cannot be analysed.",
)
def code_coding_present(r, ctx):
    code = r.get("code", {})
    if code and not code.get("coding"):
        return "Medication.code.coding is missing."


@R(
    "ingredient_item_check",
    category="plausibility",
    severity="warning",
    enabled=True,
    description="Every Medication.ingredient must have item[x] (itemCodeableConcept or itemReference).",
)
def ingredient_item_check(r, ctx):
    for ingredient in r.get("ingredient", []):
        if not ingredient.get("itemCodeableConcept") and not ingredient.get("itemReference"):
            return "Medication.ingredient has no itemCodeableConcept or itemReference."


# --- rules beyond the original set -----------------------------------------

R(
    "text_forbidden",
    category="privacy",
    severity="info",
    description="Medication.text (narrative) must not be present; it may contain cleartext personal data.",
)(forbidden("Medication.text is present. Narratives may contain cleartext personal data.", "text"))

R(
    "status_valid",
    category="coding",
    severity="error",
    description="Medication.status must be active, inactive or entered-in-error.",
)(one_of("Medication.status", "status", ("active", "inactive", "entered-in-error")))

R(
    "code_coding_known_system",
    category="coding",
    severity="warning",
    description="Medication.code must contain a PZN or ATC coding (MII Medikation).",
)(coded_with("Medication.code", "code", *MEDICATION_SYSTEMS))


@R(
    "atc_version_required",
    category="coding",
    severity="warning",
    description="An ATC coding in Medication.code must state the version (MII Medikation).",
)
def atc_version_required(r, ctx):
    for system in (ATC_DE, ATC_WHO):
        for c in codes_of(get(r, "code"), system):
            if not present(c.get("version")):
                return "Medication.code ATC coding has no version."


R(
    "atc_code_format",
    category="coding",
    severity="error",
    description="An ATC code in Medication.code must be a valid ATC code (e.g. N02BE01).",
)(atc_format("Medication.code", "code"))

R(
    "pzn_code_format",
    category="coding",
    severity="error",
    description="A PZN in Medication.code must have 8 digits.",
)(pzn_format("Medication.code", "code"))

R(
    "ingredient_required",
    category="completeness",
    severity="warning",
    description="Medication.ingredient must be present (required by MII Medikation).",
)(required("Medication.ingredient is missing.", "ingredient"))

R(
    "ingredient_coding_known_system",
    category="coding",
    severity="info",
    description="Medication.ingredient.itemCodeableConcept must be coded with ASK, UNII, CAS or SNOMED CT.",
)(coded_with("Medication.ingredient.itemCodeableConcept", "ingredient.itemCodeableConcept", ASK, UNII, CAS, SNOMED))

_strength_numerator = ucum_quantity("Medication.ingredient.strength.numerator", "ingredient.strength.numerator")
_strength_denominator = ucum_quantity(
    "Medication.ingredient.strength.denominator", "ingredient.strength.denominator"
)


@R(
    "ingredient_strength_ucum",
    category="coding",
    severity="warning",
    description="Medication.ingredient.strength must use UCUM units in numerator and denominator.",
)
def ingredient_strength_ucum(r, ctx):
    return _strength_numerator(r, ctx) or _strength_denominator(r, ctx)

R(
    "form_edqm",
    category="coding",
    severity="info",
    description="Medication.form must be coded with EDQM Standard Terms.",
)(coded_with("Medication.form", "form", EDQM))

R(
    "meta_profile_mii",
    category="completeness",
    severity="info",
    description="Medication.meta.profile must reference an MII core data set profile.",
)(mii_profile("Medication"))
