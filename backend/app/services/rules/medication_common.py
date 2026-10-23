"""Checks shared by the MII KDS Medikation profiles."""

from app.services.rules.fhir import (
    ATC_CODE,
    ATC_DE,
    ATC_WHO,
    PZN,
    PZN_CODE,
    codes_of,
    coded_with,
    get,
    present,
    references,
)
from app.services.rules.registry import CheckResult, RuleContext

MEDICATION_SYSTEMS = (PZN, ATC_DE, ATC_WHO)


def medication_known_system(resource_type: str):
    return coded_with(
        f"{resource_type}.medicationCodeableConcept",
        "medicationCodeableConcept",
        *MEDICATION_SYSTEMS,
    )


def medication_reference(resource_type: str):
    return references(
        f"{resource_type}.medicationReference", "medicationReference", "Medication"
    )


def atc_format(label: str, path: str):
    def check(r: dict, ctx: RuleContext) -> CheckResult:
        concepts = get(r, path)
        for system in (ATC_DE, ATC_WHO):
            for c in codes_of(concepts, system):
                code = c.get("code")
                if isinstance(code, str) and not ATC_CODE.match(code):
                    return f"{label} ATC code '{code}' is not a valid ATC code."
        return None

    return check


def pzn_format(label: str, path: str):
    def check(r: dict, ctx: RuleContext) -> CheckResult:
        for c in codes_of(get(r, path), PZN):
            code = c.get("code")
            if isinstance(code, str) and not PZN_CODE.match(code):
                return f"{label} PZN '{code}' does not have 8 digits."
        return None

    return check


def dosage_text_or_structured(label: str, path: str):
    """A Dosage must carry free text or structured doseAndRate (MII DosageDE, dsg-1)."""

    def check(r: dict, ctx: RuleContext) -> CheckResult:
        for dosage in get(r, path):
            if isinstance(dosage, dict) and not (
                present(dosage.get("text")) or present(dosage.get("doseAndRate"))
            ):
                return f"{label} has neither text nor doseAndRate."
        return None

    return check
