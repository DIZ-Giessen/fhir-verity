"""
FHIR Verity - Validation Rule Defaults

Regelkategorien:
  - privacy:     Datenschutz & Pseudonymisierung (Alleinstellungsmerkmal)
  - completeness: Strukturelle Vollständigkeit der Pflichtfelder
  - plausibility: Zeitliche und logische Plausibilität
  - integrity:   Referenzielle Integrität

Jede Regel hat folgende Felder:
  enabled     (bool)   - Ob die Regel aktiv ist
  severity    (str)    - "error" | "warning" | "info"
  category    (str)    - Regelkategorie (s.o.)
  description (str)    - Beschreibung für UI und Dokumentation
  pattern     (str)    - Nur bei Pseudonym-Regeln: Regex, None = deaktiviert

Quellen:
  MII KDS Modul Person:      https://simplifier.net/medizininformatikinitiative-modulperson
  MII KDS Modul Fall:        https://simplifier.net/medizininformatikinitiative-modulfall
  MII KDS Modul Medikation:  https://simplifier.net/medizininformatikinitiative-modulmedikation
  MII KDS Modul Labor:       https://simplifier.net/medizininformatikinitiative-modullabor
  MII KDS Modul Diagnose:    https://simplifier.net/medizininformatikinitiative-moduldiagnose
  FHIR R4 Basisspezifikation: https://hl7.org/fhir/R4/

Stand: MII KDS Version 2024
"""

MII_KDS_DEFAULTS: dict[str, dict[str, dict]] = {
    # =========================================================================
    # PATIENT
    # Basisprofil: MII KDS Patient (KDS_Patient)
    # https://simplifier.net/mii-kerndatensatz-basis/mii_pr_person_patientpseudonymisiert
    # =========================================================================
    "Patient": {
        # --- Privacy & Pseudonymization ---
        "text_forbidden": {
            "enabled": False,
            "severity": "info",
            "category": "privacy",
            "description": ("Checks whether the field 'text' is present."),
        },
        "name_forbidden": {
            "enabled": True,
            "severity": "error",
            "category": "privacy",
            "description": ("Checks whether the field 'name' is present"),
        },
        "address_forbidden": {
            "enabled": True,
            "severity": "error",
            "category": "privacy",
            "description": (
                "Checks whether the address contains fields other than postal code, and whether the postal code is valid and conforms to expected standards."
            ),
        },
        "telecom_forbidden": {
            "enabled": True,
            "severity": "error",
            "category": "privacy",
            "description": (
                "Ensures that no contact information such as phone numbers or email addresses is included in the resource."
            ),
        },
        "photo_forbidden": {
            "enabled": True,
            "severity": "error",
            "category": "privacy",
            "description": ("Checks whether the field 'name' is present"),
        },
        "pseudonym_format_check": {
            "enabled": True,
            "severity": "error",
            "category": "privacy",
            "pattern": "^20[0-9]{7}$",
            "description": (
                "Checks whether the Patient.id matches the expected pseudonym format."
            ),
        },
        "identifier_pseudonym_check": {
            "enabled": True,
            "severity": "error",
            "category": "privacy",
            "pattern": "^20[0-9]{7}$",
            "description": (
                "Checks whether Patient.identifier values conform to the pseudonym format. "
            ),
        },
        # --- Structural Completeness ---
        "identifier_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": ("Checks if the Patient resource has an identifier"),
        },
        "birthdate_required": {
            "enabled": True,
            "severity": "warning",
            "category": "completeness",
            "description": ("Checks if the Patient resource has a birthdate."),
        },
        "gender_required": {
            "enabled": True,
            "severity": "warning",
            "category": "completeness",
            "description": ("Checks if the Patient has a gender."),
        },
        "managingorganization_required": {
            "enabled": False,
            "severity": "info",
            "category": "completeness",
            "description": (
                "Checks if the Patient resource has a managing organization."
            ),
        },
        "has_observation": {
            "enabled": False,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "Checks if the Patient resource has at least one Observation. Note: enabling this can significantly increase run times!"
            ),
        },
        "has_condition": {
            "enabled": False,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "Checks if the Patient resource has at least one Condition.  Note: enabling this can significantly increase run times!"
            ),
        },
        # --- Plausibility ---
        "birthdate_not_future": {
            "enabled": True,
            "severity": "error",
            "category": "plausibility",
            "description": (
                "Checks if the patient's birthdate is plausible and not set in the future."
            ),
        },
        "birthdate_plausible_range": {
            "enabled": True,
            "severity": "warning",
            "category": "plausibility",
            "description": (
                "Checks if the patient's birthdate falls within a plausible range."
            ),
        },
    },
    # =========================================================================
    # ENCOUNTER (Fall)
    # Basisprofil: MII KDS Encounter (Kontakt_Gesundheitseinrichtung)
    # https://simplifier.net/MII-Kerndatensatz-Basis/MII_PR_Fall_KontaktGesundheitseinrichtung/
    # =========================================================================
    "Encounter": {
        # --- Privacy & Pseudonymization ---
        "pseudonym_format_check": {
            "enabled": True,
            "severity": "error",
            "category": "privacy",
            "pattern": "^20[0-9]{8}$",
            "description": (
                "Checks if the Encounter.id matches the expected pseudonym format. "
                "pattern=null disables the regex check."
            ),
        },
        # --- Structural Completeness ---
        "status_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the Encounter.status is present. "
                "Allowed values: planned | arrived | triaged | in-progress | "
                "onleave | finished | cancelled."
            ),
        },
        "class_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": ("Check if the Encounter.class is present. "),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": ("Check if the Encounter.subject is present. "),
        },
        "period_start_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": ("Check if the Encounter.period.start is present. "),
        },
        "servicetype_required": {
            "enabled": False,
            "severity": "info",
            "category": "completeness",
            "description": (
                "Check if the Encounter.serviceType is present. "
                "Allowed values: hospital | ambulatory | community | other."
            ),
        },
        "diagnosis_present": {
            "enabled": False,
            "severity": "info",
            "category": "completeness",
            "description": ("Check if the Encounter.diagnosis is present. "),
        },
        # --- Plausibility ---
        "period_end_after_start": {
            "enabled": True,
            "severity": "error",
            "category": "plausibility",
            "description": (
                "If period.end is present, it must be after period.start. "
            ),
        },
        "period_not_future": {
            "enabled": True,
            "severity": "warning",
            "category": "plausibility",
            "description": (
                "period.start should not be more than 24 hours in the future. "
            ),
        },
        "period_plausible_duration": {
            "enabled": True,
            "severity": "warning",
            "category": "plausibility",
            "description": (
                "If period.end is present, the duration should not be more than "
                "2 years (730 days). Extrem long stays indicate missing discharge data."
            ),
        },
        # --- Referential Integrity ---
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": (
                "subject.reference must be in the format 'Patient/{id}'. "
                "Absolute URLs or other formats are not accepted."
            ),
        },
    },
    # =========================================================================
    # CONDITION (Diagnose)
    # Basisprofil: MII KDS Diagnose (Diagnose)
    # https://simplifier.net/medizininformatikinitiative-moduldiagnose
    # =========================================================================
    "Condition": {
        # --- Privacy & Pseudonymization ---
        "note_cleartext_check": {
            "enabled": True,
            "severity": "warning",
            "category": "privacy",
            "description": (
                "Check before sharing what is in this field."
                "The free text 'note' field may contain personally identifiable information. "
            ),
        },
        # --- Structural Completeness ---
        "code_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the Condition.code is present. "
                "Must contain an ICD-10-GM code. "
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the Condition.subject is present. "
                "Reference to a Patient resource. "
            ),
        },
        "clinicalstatus_required": {
            "enabled": False,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "Check if the Condition.clinicalStatus is present. "
                "Clinical status of the condition (active, resolved etc.). "
            ),
        },
        "verificationstatus_required": {
            "enabled": False,
            "severity": "info",
            "category": "completeness",
            "description": (
                "Check if the Condition.verificationStatus is present. "
                "Allowed values: confirmed | differential | entered-in-error | unknown."
            ),
        },
        "onset_present": {
            "enabled": False,
            "severity": "info",
            "category": "completeness",
            "description": (
                "Check if the Condition.onset[x] is present. "
                "Time of onset of the condition. "
            ),
        },
        # --- Referential Integrity ---
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference must be in the format 'Patient/{id}'. "),
        },
    },
    # =========================================================================
    # OBSERVATION (Laborwert / Messung)
    # Basisprofil: MII KDS Observation (Laboruntersuchung)
    # https://simplifier.net/medizininformatikinitiative-modullabor
    # =========================================================================
    "Observation": {
        # --- Privacy & Pseudonymization ---
        "value_string_cleartext_forbidden": {
            "enabled": False,
            "severity": "error",
            "category": "privacy",
            "description": (
                "The valueString field must not contain personally identifiable information. "
                "Labor values should be stored as valueQuantity, valueCodeableConcept etc., "
                "not as free text with patient data."
            ),
        },
        "note_cleartext_check": {
            "enabled": True,
            "severity": "warning",
            "category": "privacy",
            "description": (
                "The free text field 'note' may contain personally identifiable information."
            ),
        },
        # --- Structural Completeness ---
        "status_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the Observation.status is present. "
                "Allowed values: registered | preliminary | final | amended | corrected | "
                "cancelled | entered-in-error | unknown."
            ),
        },
        "code_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the Observation.code is present. "
                "Should contain a LOINC code. "
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the Observation.subject is present. "
                "Reference to a Patient resource. "
            ),
        },
        "effective_required": {
            "enabled": True,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "Check if the Observation.effective[x] is present. "
                "Time or period of the measurement. "
                "Accepted: effectiveDateTime, effectivePeriod, effectiveInstant."
            ),
        },
        "value_present": {
            "enabled": True,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "Check if the Observation.value[x] is present. it should to be a valueQuantity, valueCodeableConcept, valueString, valueBoolean, valueInteger, valueRange, valueRatio, valueSampledData, valueTime, valueDateTime, valuePeriod, dataAbsentReason. "
            ),
        },
        # --- Plausibility ---
        "effective_not_future": {
            "enabled": True,
            "severity": "warning",
            "category": "plausibility",
            "description": (
                "effective[x] should not be in the future. "
                "Future measurement times indicate data entry errors."
            ),
        },
        # --- Referential Integrity ---
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference must be in the format 'Patient/{id}'. "),
        },
    },
    # =========================================================================
    # MEDICATION
    # Basisprofil: MII KDS Medication
    # https://simplifier.net/medizininformatikinitiative-modulmedikation
    # =========================================================================
    "Medication": {
        # --- Structural Completeness ---
        "code_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the Medication.code is present. "
                "Must contain a code, preferably ATC or PZN."
            ),
        },
        "code_coding_present": {
            "enabled": True,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "Check if the Medication.code.coding is present. "
                "Only code.text without structured coding is insufficient for analysis."
            ),
        },
        # --- Plausibility ---
        "ingredient_item_check": {
            "enabled": True,
            "severity": "warning",
            "category": "plausibility",
            "description": (
                "Check if the Medication.ingredient.item[x] is present. It should contain either itemCodeableConcept OR itemReference, not both. "
            ),
        },
    },
    # =========================================================================
    # MEDICATIONREQUEST
    # Basisprofil: MII KDS MedicationRequest
    # https://simplifier.net/medizininformatikinitiative-modulmedikation
    # =========================================================================
    "MedicationRequest": {
        # --- Privacy & Pseudonymization ---
        "note_cleartext_check": {
            "enabled": True,
            "severity": "warning",
            "category": "privacy",
            "description": (
                "Check if the Medication.note and Medication.dosageInstruction.text are present. They may contain personally identifiable information. "
            ),
        },
        # --- Structural Completeness ---
        "status_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the MedicationRequest.status is present. "
                "Allowed values: active | on-hold | cancelled | completed | "
                "entered-in-error | stopped | draft | unknown."
            ),
        },
        "intent_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the MedicationRequest.intent is present. "
                "Allowed values: proposal | plan | order | original-order | "
                "reflex-order | filler-order | instance-order | option."
            ),
        },
        "medication_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the MedicationRequest.medication[x] is present. "
                "Either medicationReference (Reference to Medication) or "
                "medicationCodeableConcept (coded reference) must be present."
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the MedicationRequest.subject is present. "
                "Reference to a Patient resource. "
            ),
        },
        "authored_on_required": {
            "enabled": True,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "Check if the MedicationRequest.authoredOn is present. "
                "Date and time of the prescription. "
                "Alternatively, boundsPeriod in dosageInstruction is accepted."
            ),
        },
        # --- Plausibility ---
        "authored_not_future": {
            "enabled": True,
            "severity": "warning",
            "category": "plausibility",
            "description": (
                "authoredOn should not be in the future. "
                "Future prescription data indicates planning data."
            ),
        },
        # --- Referential Integrity ---
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference must be in the format 'Patient/{id}'. "),
        },
    },
    # =========================================================================
    # MEDICATIONADMINISTRATION
    # Basisprofil: MII KDS MedicationAdministration
    # https://simplifier.net/medizininformatikinitiative-modulmedikation
    # =========================================================================
    "MedicationAdministration": {
        # --- Privacy & Pseudonymization ---
        "note_cleartext_check": {
            "enabled": True,
            "severity": "warning",
            "category": "privacy",
            "description": (
                "Check if the MedicationAdministration.note and MedicationAdministration.dosage.text are present. They may contain personally identifiable information. "
            ),
        },
        # --- Structural Completeness ---
        "status_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the MedicationAdministration.status is present. "
                "Allowed values: in-progress | not-done | on-hold | completed | "
                "entered-in-error | stopped | unknown."
            ),
        },
        "medication_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the MedicationAdministration.medication[x] is present. "
                "Either medicationReference or medicationCodeableConcept must be present."
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the MedicationAdministration.subject is present. "
                "Reference to a Patient resource. "
            ),
        },
        "effective_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the MedicationAdministration.effective[x] is present. "
                "Either effectiveDateTime or effectivePeriod must be present."
            ),
        },
        # --- Plausibility ---
        "effective_not_future": {
            "enabled": True,
            "severity": "warning",
            "category": "plausibility",
            "description": (
                "effective[x] should not be in the future. "
                "Future administration times are clinically not plausible."
            ),
        },
        "effective_period_end_after_start": {
            "enabled": True,
            "severity": "error",
            "category": "plausibility",
            "description": ("If effectivePeriod is used, end must be after start. "),
        },
        # --- Referential Integrity ---
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference must be in the format 'Patient/{id}'. "),
        },
    },
    # =========================================================================
    # MEDICATIONSTATEMENT
    # Ergänzend zum Medikationsmodul (nicht im KDS Pflicht, aber relevant)
    # =========================================================================
    "MedicationStatement": {
        "status_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the MedicationStatement.status is present. "
                "Allowed values: active | completed | entered-in-error | "
                "intended | stopped | on-hold | unknown | not-taken."
            ),
        },
        "medication_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the MedicationStatement.medication[x] is present. "
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the MedicationStatement.subject is present. "
                "Reference to a Patient resource. "
            ),
        },
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference must be in the format 'Patient/{id}'. "),
        },
    },
    # =========================================================================
    # PROCEDURE (Prozedur)
    # Basisprofil: MII KDS Prozedur
    # https://simplifier.net/medizininformatikinitiative-modulprozeduren
    # =========================================================================
    "Procedure": {
        "note_cleartext_check": {
            "enabled": True,
            "severity": "warning",
            "category": "privacy",
            "description": (
                "Check if the Procedure.note is present. It may contain personally identifiable information. "
            ),
        },
        "status_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the Procedure.status is present. "
                "Allowed values: preparation | in-progress | not-done | on-hold | "
                "stopped | completed | entered-in-error | unknown."
            ),
        },
        "code_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the Procedure.code is present. "
                "Should contain an OPS code. "
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the Procedure.subject is present. "
                "Reference to a Patient resource. "
            ),
        },
        "performed_required": {
            "enabled": True,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "Check if the Procedure.performed[x] is present. "
                "Accepted: performedDateTime, performedPeriod."
            ),
        },
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference must be in the format 'Patient/{id}'. "),
        },
    },
    # =========================================================================
    # DIAGNOSTICREPORT (Befundbericht)
    # Basisprofil: MII KDS DiagnosticReport (Labor)
    # =========================================================================
    "DiagnosticReport": {
        "note_cleartext_check": {
            "enabled": True,
            "severity": "warning",
            "category": "privacy",
            "description": (
                "Check if the DiagnosticReport.conclusion and DiagnosticReport.text are present. They may contain personally identifiable information. "
            ),
        },
        "status_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the DiagnosticReport.status is present. "
                "Allowed values: registered | preliminary | final | amended | corrected | "
                "cancelled | entered-in-error | unknown."
            ),
        },
        "code_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the DiagnosticReport.code is present. "
                "Describes the type of report (e.g. labor report)."
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Check if the DiagnosticReport.subject is present. "
                "Reference to a Patient resource. "
            ),
        },
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference must be in the format 'Patient/{id}'. "),
        },
    },
}


# All resource types that FHIR Verity can validate
SUPPORTED_RESOURCE_TYPES: list[str] = list(MII_KDS_DEFAULTS.keys())


def get_rule_keys_by_category(resource_type: str, category: str) -> list[str]:
    """Returns all rule keys of a specific category for a resource type."""
    rules = MII_KDS_DEFAULTS.get(resource_type, {})
    return [key for key, rule in rules.items() if rule.get("category") == category]


def get_enabled_rules(resource_type: str) -> dict[str, dict]:
    """Returns only enabled rules for a resource type."""
    rules = MII_KDS_DEFAULTS.get(resource_type, {})
    return {key: rule for key, rule in rules.items() if rule.get("enabled", False)}
