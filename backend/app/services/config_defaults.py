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
            "enabled": True,
            "severity": "error",
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
                "Prüft ob die Encounter.id dem erwarteten Pseudonym-Format entspricht. "
                "pattern=null deaktiviert die Regex-Prüfung."
            ),
        },
        # --- Structural Completeness ---
        "status_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Ein Fall muss einen Status haben. "
                "Erlaubte Werte: planned | arrived | triaged | in-progress | "
                "onleave | finished | cancelled."
            ),
        },
        "class_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Ein Fall muss einen Class haben."
                "Klassifikation des Kontakts (stationär, ambulant etc.) "
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": ("Muss eine Referenz auf eine Patient-Ressource enthalten."),
        },
        "period_start_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "Der Beginn des Kontakts muss vorhanden und dokumentiert sein."
            ),
        },
        "servicetype_required": {
            "enabled": False,
            "severity": "info",
            "category": "completeness",
            "description": (
                "MII KDS Encounter: serviceType Should-Support. "
                "Art der Leistung (Fachrichtung). Standardmäßig deaktiviert."
            ),
        },
        "diagnosis_present": {
            "enabled": False,
            "severity": "info",
            "category": "completeness",
            "description": (
                "Prüft ob eine Diagnose (Condition-Referenz) im Encounter hinterlegt ist. "
                "Standardmäßig deaktiviert da nicht immer erwartet."
            ),
        },
        # --- Plausibility ---
        "period_end_after_start": {
            "enabled": True,
            "severity": "error",
            "category": "plausibility",
            "description": (
                "Wenn period.end vorhanden, muss es nach period.start liegen. "
                "Umgekehrte Perioden sind Dateneingabefehler."
            ),
        },
        "period_not_future": {
            "enabled": True,
            "severity": "warning",
            "category": "plausibility",
            "description": (
                "period.start sollte nicht mehr als 24 Stunden in der Zukunft liegen. "
                "Zukünftige Aufnahmedaten deuten auf Planungsdaten hin, nicht auf abgeschlossene Fälle."
            ),
        },
        "period_plausible_duration": {
            "enabled": True,
            "severity": "warning",
            "category": "plausibility",
            "description": (
                "Wenn period.end vorhanden, sollte die Aufenthaltsdauer nicht mehr als "
                "2 Jahre (730 Tage) betragen. Extrem lange Aufenthalte deuten auf "
                "fehlende Entlassdaten hin."
            ),
        },
        # --- Referential Integrity ---
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": (
                "subject.reference muss das Format 'Patient/{id}' haben. "
                "Absolute URLs oder andere Formate werden nicht akzeptiert."
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
                "MII KDS Diagnose: code 1..1 Pflichtfeld. "
                "Muss eine ICD-10-GM Kodierung enthalten."
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS Diagnose: subject 1..1 Pflichtfeld. "
                "Referenz auf Patient-Ressource."
            ),
        },
        "clinicalstatus_required": {
            "enabled": True,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "MII KDS Diagnose: clinicalStatus Should-Support. "
                "Klinischer Status der Diagnose (active, resolved etc.)."
            ),
        },
        "verificationstatus_required": {
            "enabled": False,
            "severity": "info",
            "category": "completeness",
            "description": (
                "MII KDS Diagnose: verificationStatus Should-Support. "
                "Standardmäßig deaktiviert."
            ),
        },
        "onset_present": {
            "enabled": False,
            "severity": "info",
            "category": "completeness",
            "description": (
                "MII KDS Diagnose: onset[x] Should-Support. "
                "Zeitpunkt des Auftretens der Diagnose. Standardmäßig deaktiviert."
            ),
        },
        # --- Referential Integrity ---
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference muss das Format 'Patient/{id}' haben."),
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
                "Das Feld valueString darf keine personenidentifizierenden Informationen enthalten. "
                "Laborwerte sollten als valueQuantity, valueCodeableConcept etc. gespeichert werden, "
                "nicht als Freitext mit Patientendaten."
            ),
        },
        "note_cleartext_check": {
            "enabled": True,
            "severity": "warning",
            "category": "privacy",
            "description": (
                "Das Freitextfeld 'note' kann personenidentifizierende Informationen enthalten."
            ),
        },
        # --- Structural Completeness ---
        "status_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS Observation: status 1..1 Pflichtfeld. "
                "Erlaubte Werte: registered | preliminary | final | amended | corrected | "
                "cancelled | entered-in-error | unknown."
            ),
        },
        "code_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS Observation: code 1..1 Pflichtfeld. "
                "Sollte eine LOINC-Kodierung enthalten."
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS Observation: subject 1..1 Pflichtfeld. "
                "Referenz auf Patient-Ressource."
            ),
        },
        "effective_required": {
            "enabled": True,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "MII KDS Observation: effective[x] Must-Support. "
                "Zeitpunkt oder Periode der Messung. "
                "Akzeptiert: effectiveDateTime, effectivePeriod, effectiveInstant."
            ),
        },
        "value_present": {
            "enabled": True,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "Eine Observation sollte entweder einen Wert (value[x]) oder "
                "einen dataAbsentReason enthalten. "
                "Observations ohne beides sind informationslos."
            ),
        },
        # --- Plausibility ---
        "effective_not_future": {
            "enabled": True,
            "severity": "warning",
            "category": "plausibility",
            "description": (
                "effective[x] sollte nicht in der Zukunft liegen. "
                "Zukünftige Messzeitpunkte deuten auf Dateneingabefehler hin."
            ),
        },
        # --- Referential Integrity ---
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference muss das Format 'Patient/{id}' haben."),
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
                "MII KDS Medication: code 1..1 Pflichtfeld. "
                "Muss eine Kodierung enthalten, bevorzugt ATC (WHO oder DIMDI) oder PZN."
            ),
        },
        "code_coding_present": {
            "enabled": True,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "code.coding sollte vorhanden sein. "
                "Nur code.text ohne strukturierte Kodierung ist für Analysen unzureichend."
            ),
        },
        # --- Plausibility ---
        "ingredient_item_check": {
            "enabled": True,
            "severity": "warning",
            "category": "plausibility",
            "description": (
                "MII KDS Medication: ingredient.item[x] ist ein FHIR Choice-Type. "
                "Muss entweder itemCodeableConcept ODER itemReference enthalten, nicht beides. "
                "Fehlende item-Angabe bei vorhandenem ingredient-Element ist ein Strukturfehler."
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
                "Das Freitextfeld 'note' und 'dosageInstruction.text' können "
                "personenidentifizierende Informationen enthalten."
            ),
        },
        # --- Structural Completeness ---
        "status_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS MedicationRequest: status 1..1 Pflichtfeld. "
                "Erlaubte Werte: active | on-hold | cancelled | completed | "
                "entered-in-error | stopped | draft | unknown."
            ),
        },
        "intent_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS MedicationRequest: intent 1..1 Pflichtfeld. "
                "Erlaubte Werte: proposal | plan | order | original-order | "
                "reflex-order | filler-order | instance-order | option."
            ),
        },
        "medication_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS MedicationRequest: medication[x] 1..1 Pflichtfeld. "
                "Entweder medicationReference (Referenz auf Medication) oder "
                "medicationCodeableConcept (kodierte Angabe) muss vorhanden sein."
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS MedicationRequest: subject 1..1 Pflichtfeld. "
                "Referenz auf Patient-Ressource."
            ),
        },
        "authored_on_required": {
            "enabled": True,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "MII KDS MedicationRequest: authoredOn Must-Support. "
                "Datum und Uhrzeit der Verordnung. "
                "Alternativ wird boundsPeriod in dosageInstruction akzeptiert."
            ),
        },
        # --- Plausibility ---
        "authored_not_future": {
            "enabled": True,
            "severity": "warning",
            "category": "plausibility",
            "description": (
                "authoredOn sollte nicht in der Zukunft liegen. "
                "Zukünftige Verordnungsdaten deuten auf Planungsdaten hin."
            ),
        },
        # --- Referential Integrity ---
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference muss das Format 'Patient/{id}' haben."),
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
                "Das Freitextfeld 'note' und 'dosage.text' können "
                "personenidentifizierende Informationen enthalten."
            ),
        },
        # --- Structural Completeness ---
        "status_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS MedicationAdministration: status 1..1 Pflichtfeld. "
                "Erlaubte Werte: in-progress | not-done | on-hold | completed | "
                "entered-in-error | stopped | unknown."
            ),
        },
        "medication_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS MedicationAdministration: medication[x] 1..1 Pflichtfeld. "
                "Entweder medicationReference oder medicationCodeableConcept."
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS MedicationAdministration: subject 1..1 Pflichtfeld. "
                "Referenz auf Patient-Ressource."
            ),
        },
        "effective_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS MedicationAdministration: effective[x] 1..1 Pflichtfeld. "
                "Entweder effectiveDateTime oder effectivePeriod muss vorhanden sein."
            ),
        },
        # --- Plausibility ---
        "effective_not_future": {
            "enabled": True,
            "severity": "warning",
            "category": "plausibility",
            "description": (
                "effective[x] sollte nicht in der Zukunft liegen. "
                "Zukünftige Verabreichungszeitpunkte sind klinisch nicht plausibel."
            ),
        },
        "effective_period_end_after_start": {
            "enabled": True,
            "severity": "error",
            "category": "plausibility",
            "description": (
                "Wenn effectivePeriod verwendet wird, muss end nach start liegen."
            ),
        },
        # --- Referential Integrity ---
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference muss das Format 'Patient/{id}' haben."),
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
                "MedicationStatement: status 1..1 Pflichtfeld. "
                "Erlaubte Werte: active | completed | entered-in-error | "
                "intended | stopped | on-hold | unknown | not-taken."
            ),
        },
        "medication_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": ("MedicationStatement: medication[x] 1..1 Pflichtfeld."),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MedicationStatement: subject 1..1 Pflichtfeld. "
                "Referenz auf Patient-Ressource."
            ),
        },
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference muss das Format 'Patient/{id}' haben."),
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
                "Das Freitextfeld 'note' kann personenidentifizierende Informationen enthalten."
            ),
        },
        "status_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS Prozedur: status 1..1 Pflichtfeld. "
                "Erlaubte Werte: preparation | in-progress | not-done | on-hold | "
                "stopped | completed | entered-in-error | unknown."
            ),
        },
        "code_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS Prozedur: code 1..1 Pflichtfeld. "
                "Sollte OPS-Kodierung enthalten."
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "MII KDS Prozedur: subject 1..1 Pflichtfeld. "
                "Referenz auf Patient-Ressource."
            ),
        },
        "performed_required": {
            "enabled": True,
            "severity": "warning",
            "category": "completeness",
            "description": (
                "MII KDS Prozedur: performed[x] Must-Support. "
                "Akzeptiert: performedDateTime, performedPeriod."
            ),
        },
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference muss das Format 'Patient/{id}' haben."),
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
                "Das Freitextfeld 'conclusion' und 'text' können "
                "personenidentifizierende Informationen enthalten."
            ),
        },
        "status_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": ("DiagnosticReport: status 1..1 Pflichtfeld."),
        },
        "code_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "DiagnosticReport: code 1..1 Pflichtfeld. "
                "Beschreibt die Art des Berichts (z.B. Laborbefund)."
            ),
        },
        "subject_required": {
            "enabled": True,
            "severity": "error",
            "category": "completeness",
            "description": (
                "DiagnosticReport: subject 1..1 Pflichtfeld. "
                "Referenz auf Patient-Ressource."
            ),
        },
        "subject_reference_format": {
            "enabled": True,
            "severity": "error",
            "category": "integrity",
            "description": ("subject.reference muss das Format 'Patient/{id}' haben."),
        },
    },
}


# Alle Ressource-Typen die FHIR Verity validieren kann
SUPPORTED_RESOURCE_TYPES: list[str] = list(MII_KDS_DEFAULTS.keys())


def get_rule_keys_by_category(resource_type: str, category: str) -> list[str]:
    """Gibt alle Regel-Keys einer bestimmten Kategorie für einen Ressource-Typ zurück."""
    rules = MII_KDS_DEFAULTS.get(resource_type, {})
    return [key for key, rule in rules.items() if rule.get("category") == category]


def get_enabled_rules(resource_type: str) -> dict[str, dict]:
    """Gibt nur aktivierte Regeln für einen Ressource-Typ zurück."""
    rules = MII_KDS_DEFAULTS.get(resource_type, {})
    return {key: rule for key, rule in rules.items() if rule.get("enabled", False)}
