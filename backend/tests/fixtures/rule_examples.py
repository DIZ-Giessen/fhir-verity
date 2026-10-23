"""
One valid, MII-conformant resource per type that passes every rule, and for
each rule added with the registry a variant of it that must fail that rule.
"""

import copy

MII = "https://www.medizininformatik-initiative.de/fhir/"
LOINC = "http://loinc.org"
SNOMED = "http://snomed.info/sct"
UCUM = "http://unitsofmeasure.org"
V2_0203 = "http://terminology.hl7.org/CodeSystem/v2-0203"
OBS_CAT = "http://terminology.hl7.org/CodeSystem/observation-category"
ATC_DE = "http://fhir.de/CodeSystem/bfarm/atc"
PZN = "http://fhir.de/CodeSystem/ifa/pzn"
DCM = "http://dicom.nema.org/resources/ontology/DCM"
MII_POLICY = "urn:oid:2.16.840.1.113883.3.1937.777.24.5.3"

DROP = object()
LONG = "Patient Max Mustermann, wohnhaft in Musterstadt, wurde heute aufgenommen."
FUTURE = "2999-01-01"
OTHER = {"coding": [{"system": "http://example.org/other", "code": "x"}]}


def variant(base: dict, changes: dict) -> dict:
    """Copy of `base` with dotted paths set to new values or removed (DROP)."""
    result = copy.deepcopy(base)
    for path, value in changes.items():
        *parents, last = path.split(".")
        node = result
        for part in parents:
            node = node.setdefault(part, {})
        if value is DROP:
            node.pop(last, None)
        else:
            node[last] = value
    return result


MEDICATION_CODE = {
    "coding": [
        {"system": ATC_DE, "version": "2024", "code": "N02BE01"},
        {"system": PZN, "code": "01234567"},
    ]
}

VALID: dict[str, dict] = {
    "Patient": {
        "resourceType": "Patient",
        "id": "psn-1",
        "meta": {"profile": [MII + "core/modul-person/StructureDefinition/PatientPseudonymisiert"]},
        "identifier": [
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
                            "code": "PSEUDED",
                        }
                    ]
                },
                "system": "urn:example:psn",
                "value": "PSN-0001",
            }
        ],
        "gender": "female",
        "birthDate": "1970-05",
        "deceasedDateTime": "2020-01-01",
        "managingOrganization": {"reference": "Organization/1"},
        "address": [{"type": "both", "postalCode": "35392", "country": "DE"}],
    },
    "Encounter": {
        "resourceType": "Encounter",
        "id": "enc-1",
        "meta": {"profile": [MII + "core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung"]},
        "identifier": [
            {"type": {"coding": [{"system": V2_0203, "code": "VN"}]}, "system": "urn:example:vn", "value": "VN-1"}
        ],
        "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "IMP"},
        "type": [{"coding": [{"system": "http://fhir.de/CodeSystem/Kontaktebene", "code": "abteilungskontakt"}]}],
        "serviceType": {
            "coding": [{"system": "http://fhir.de/CodeSystem/dkgev/Fachabteilungsschluessel", "code": "0100"}]
        },
        "subject": {"reference": "Patient/psn-1"},
        "period": {"start": "2024-01-01T08:00:00+01:00", "end": "2024-01-05T10:00:00+01:00"},
        "diagnosis": [
            {
                "condition": {"reference": "Condition/c-1"},
                "use": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/diagnosis-role", "code": "CC"}]},
            }
        ],
        "hospitalization": {
            "admitSource": {"coding": [{"system": "http://fhir.de/CodeSystem/dgkev/Aufnahmeanlass", "code": "E"}]}
        },
        "location": [{"location": {"reference": "Location/1"}}],
        "serviceProvider": {"reference": "Organization/1"},
        "partOf": {"reference": "Encounter/enc-0"},
    },
    "Condition": {
        "resourceType": "Condition",
        "id": "c-1",
        "meta": {"profile": [MII + "core/modul-diagnose/StructureDefinition/Diagnose"]},
        "clinicalStatus": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "resolved"}]
        },
        "verificationStatus": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]
        },
        "code": {"coding": [{"system": "http://fhir.de/CodeSystem/bfarm/icd-10-gm", "version": "2024", "code": "S72.01"}]},
        "bodySite": [{"coding": [{"system": SNOMED, "code": "71341001"}]}],
        "subject": {"reference": "Patient/psn-1"},
        "encounter": {"reference": "Encounter/enc-1"},
        "onsetDateTime": "2023-12-30",
        "abatementDateTime": "2024-02-01",
        "recordedDate": "2024-01-02",
        "note": [{"text": "kurz"}],
    },
    "Observation": {
        "resourceType": "Observation",
        "id": "o-1",
        "meta": {"profile": [MII + "core/modul-labor/StructureDefinition/ObservationLab"]},
        "identifier": [
            {"type": {"coding": [{"system": V2_0203, "code": "OBI"}]}, "system": "urn:example:obi", "value": "1"}
        ],
        "status": "final",
        "category": [{"coding": [{"system": LOINC, "code": "26436-6"}, {"system": OBS_CAT, "code": "laboratory"}]}],
        "code": {"coding": [{"system": LOINC, "code": "718-7"}]},
        "subject": {"reference": "Patient/psn-1"},
        "encounter": {"reference": "Encounter/enc-1"},
        "specimen": {"reference": "Specimen/s-1"},
        "effectiveDateTime": "2024-01-01T08:00:00+01:00",
        "issued": "2024-01-01T12:00:00+01:00",
        "valueQuantity": {"value": 13.2, "unit": "g/dL", "system": UCUM, "code": "g/dL"},
        "referenceRange": [{"low": {"value": 12}, "high": {"value": 16}}],
        "note": [{"text": "kurz"}],
    },
    "Medication": {
        "resourceType": "Medication",
        "id": "m-1",
        "meta": {"profile": [MII + "core/modul-medikation/StructureDefinition/Medication"]},
        "status": "active",
        "code": MEDICATION_CODE,
        "form": {"coding": [{"system": "http://standardterms.edqm.eu", "code": "10219000"}]},
        "ingredient": [
            {
                "itemCodeableConcept": {"coding": [{"system": "http://fhir.de/CodeSystem/ask", "code": "00001"}]},
                "strength": {
                    "numerator": {"value": 500, "unit": "mg", "system": UCUM, "code": "mg"},
                    "denominator": {"value": 1, "unit": "Tablette", "system": UCUM, "code": "1"},
                },
            }
        ],
    },
    "MedicationRequest": {
        "resourceType": "MedicationRequest",
        "id": "mr-1",
        "meta": {"profile": [MII + "core/modul-medikation/StructureDefinition/MedicationRequest"]},
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": MEDICATION_CODE,
        "subject": {"reference": "Patient/psn-1"},
        "encounter": {"reference": "Encounter/enc-1"},
        "authoredOn": "2024-01-01",
        "dosageInstruction": [
            {"text": "1-0-1", "timing": {"repeat": {"boundsPeriod": {"start": "2024-01-01", "end": "2024-01-10"}}}}
        ],
        "note": [{"text": "kurz"}],
    },
    "MedicationAdministration": {
        "resourceType": "MedicationAdministration",
        "id": "ma-1",
        "meta": {"profile": [MII + "core/modul-medikation/StructureDefinition/MedicationAdministration"]},
        "status": "completed",
        "medicationCodeableConcept": MEDICATION_CODE,
        "subject": {"reference": "Patient/psn-1"},
        "context": {"reference": "Encounter/enc-1"},
        "request": {"reference": "MedicationRequest/mr-1"},
        "effectiveDateTime": "2024-01-01T10:00:00Z",
        "dosage": {"text": "500 mg", "dose": {"value": 500, "unit": "mg", "system": UCUM, "code": "mg"}},
        "note": [{"text": "kurz"}],
    },
    "MedicationStatement": {
        "resourceType": "MedicationStatement",
        "id": "ms-1",
        "meta": {"profile": [MII + "core/modul-medikation/StructureDefinition/MedicationStatement"]},
        "status": "active",
        "medicationCodeableConcept": MEDICATION_CODE,
        "subject": {"reference": "Patient/psn-1"},
        "context": {"reference": "Encounter/enc-1"},
        "effectivePeriod": {"start": "2024-01-01", "end": "2024-01-31"},
        "dateAsserted": "2024-01-01",
        "dosage": [{"text": "1-0-0"}],
        "note": [{"text": "kurz"}],
    },
    "Procedure": {
        "resourceType": "Procedure",
        "id": "pr-1",
        "meta": {"profile": [MII + "core/modul-prozedur/StructureDefinition/Procedure"]},
        "status": "completed",
        "category": {"coding": [{"system": SNOMED, "code": "387713003"}]},
        "code": {"coding": [{"system": "http://fhir.de/CodeSystem/bfarm/ops", "version": "2024", "code": "5-470.11"}]},
        "subject": {"reference": "Patient/psn-1"},
        "encounter": {"reference": "Encounter/enc-1"},
        "performedPeriod": {"start": "2024-01-02T08:00:00Z", "end": "2024-01-02T09:00:00Z"},
        "bodySite": [{"coding": [{"system": SNOMED, "code": "66754008"}]}],
        "note": [{"text": "kurz"}],
    },
    "DiagnosticReport": {
        "resourceType": "DiagnosticReport",
        "id": "dr-1",
        "meta": {"profile": [MII + "core/modul-labor/StructureDefinition/DiagnosticReportLab"]},
        "identifier": [
            {"type": {"coding": [{"system": V2_0203, "code": "FILL"}]}, "system": "urn:example:fill", "value": "1"}
        ],
        "basedOn": [{"reference": "ServiceRequest/sr-1"}],
        "status": "final",
        "category": [
            {
                "coding": [
                    {"system": LOINC, "code": "26436-6"},
                    {"system": "http://terminology.hl7.org/CodeSystem/v2-0074", "code": "LAB"},
                ]
            }
        ],
        "code": {"coding": [{"system": LOINC, "code": "11502-2"}]},
        "subject": {"reference": "Patient/psn-1"},
        "encounter": {"reference": "Encounter/enc-1"},
        "effectiveDateTime": "2024-01-01T08:00:00+01:00",
        "issued": "2024-01-01T12:00:00+01:00",
        "result": [{"reference": "Observation/o-1"}],
        "conclusion": "unauffällig",
    },
    "ServiceRequest": {
        "resourceType": "ServiceRequest",
        "id": "sr-1",
        "meta": {"profile": [MII + "core/modul-labor/StructureDefinition/ServiceRequestLab"]},
        "identifier": [
            {"type": {"coding": [{"system": V2_0203, "code": "PLAC"}]}, "system": "urn:example:plac", "value": "1"}
        ],
        "status": "completed",
        "intent": "order",
        "category": [{"coding": [{"system": OBS_CAT, "code": "laboratory"}]}],
        "code": {"coding": [{"system": LOINC, "code": "26436-6"}]},
        "subject": {"reference": "Patient/psn-1"},
        "encounter": {"reference": "Encounter/enc-1"},
        "authoredOn": "2024-01-01",
        "specimen": [{"reference": "Specimen/s-1"}],
        "note": [{"text": "kurz"}],
    },
    "Specimen": {
        "resourceType": "Specimen",
        "id": "s-1",
        "meta": {"profile": [MII + "ext/modul-biobank/StructureDefinition/Specimen"]},
        "identifier": [{"system": "urn:example:sample", "value": "S-1"}],
        "status": "available",
        "type": {"coding": [{"system": SNOMED, "code": "119297000"}]},
        "subject": {"reference": "Patient/psn-1"},
        "request": [{"reference": "ServiceRequest/sr-1"}],
        "receivedTime": "2024-01-01T10:00:00Z",
        "collection": {
            "collectedDateTime": "2024-01-01T08:00:00Z",
            "quantity": {"value": 5, "unit": "mL", "system": UCUM, "code": "mL"},
            "bodySite": {"coding": [{"system": SNOMED, "code": "368208006"}]},
        },
        "processing": [{"procedure": {"coding": [{"system": SNOMED, "code": "1186936003"}]}}],
        "container": [
            {
                "type": {"coding": [{"system": SNOMED, "code": "702281005"}]},
                "capacity": {"value": 10, "unit": "mL", "system": UCUM, "code": "mL"},
                "specimenQuantity": {"value": 5, "unit": "mL", "system": UCUM, "code": "mL"},
            }
        ],
        "note": [{"text": "kurz"}],
    },
    "Consent": {
        "resourceType": "Consent",
        "id": "co-1",
        "meta": {"profile": [MII + "modul-consent/StructureDefinition/mii-pr-consent-einwilligung"]},
        "status": "active",
        "scope": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/consentscope", "code": "research"}]},
        "category": [
            {"coding": [{"system": LOINC, "code": "57016-8"}]},
            {
                "coding": [
                    {
                        "system": MII + "modul-consent/CodeSystem/mii-cs-consent-version-modules",
                        "code": "2.16.840.1.113883.3.1937.777.24.2.1790",
                    }
                ]
            },
        ],
        "patient": {"reference": "Patient/psn-1"},
        "dateTime": "2024-01-01T10:00:00+01:00",
        "policy": [{"uri": "urn:oid:2.16.840.1.113883.3.1937.777.24.2.1791"}],
        "provision": {
            "type": "deny",
            "period": {"start": "2024-01-01", "end": "2054-01-01"},
            "provision": [
                {
                    "type": "permit",
                    "period": {"start": "2024-01-01", "end": "2029-01-01"},
                    "code": [{"coding": [{"system": MII_POLICY, "code": "2.16.840.1.113883.3.1937.777.24.5.3.1"}]}],
                }
            ],
        },
    },
    "ImagingStudy": {
        "resourceType": "ImagingStudy",
        "id": "is-1",
        "meta": {"profile": [MII + "ext/modul-bildgebung/StructureDefinition/mii-pr-bildgebung-bildgebungsstudie"]},
        "identifier": [{"system": "urn:dicom:uid", "value": "urn:oid:1.2.3.4"}],
        "status": "available",
        "modality": [{"system": DCM, "code": "CT"}],
        "subject": {"reference": "Patient/psn-1"},
        "encounter": {"reference": "Encounter/enc-1"},
        "basedOn": [{"reference": "ServiceRequest/sr-2"}],
        "started": "2024-01-01T10:00:00Z",
        "numberOfSeries": 1,
        "numberOfInstances": 2,
        "series": [
            {
                "uid": "1.2.3.4.1",
                "modality": {"system": DCM, "code": "CT"},
                "started": "2024-01-01T10:00:00Z",
                "instance": [
                    {"uid": "1.2.3.4.1.1", "sopClass": {"system": "urn:ietf:rfc:3986", "code": "urn:oid:1.2.840.10008.5.1.4.1.1.2"}},
                    {"uid": "1.2.3.4.1.2", "sopClass": {"system": "urn:ietf:rfc:3986", "code": "urn:oid:1.2.840.10008.5.1.4.1.1.2"}},
                ],
            }
        ],
    },
}

TEXT = {"text": {"status": "generated", "div": "<div>x</div>"}}

# (resource_type, rule) -> changes to VALID[resource_type] that must violate the rule
FAILING: dict[tuple[str, str], dict] = {
    # Patient
    ("Patient", "managingorganization_required"): {"managingOrganization": DROP},
    ("Patient", "contact_forbidden"): {"contact": [{"name": {"family": "Muster"}}]},
    ("Patient", "pseudonymized_identifier_type"): {"identifier": [{"value": "PSN-1"}]},
    ("Patient", "birthdate_precision"): {"birthDate": "1970-05-01"},
    ("Patient", "gender_valid"): {"gender": "divers"},
    ("Patient", "gender_other_amtlich"): {"gender": "other"},
    ("Patient", "birthdate_format"): {"birthDate": "01.05.1970"},
    ("Patient", "deceased_after_birth"): {"deceasedDateTime": "1960-01-01"},
    ("Patient", "deceased_not_future"): {"deceasedDateTime": FUTURE},
    ("Patient", "address_postalcode_required"): {"address": [{"country": "DE"}]},
    ("Patient", "address_country_required"): {"address": [{"postalCode": "35392"}]},
    ("Patient", "address_country_code"): {"address": [{"postalCode": "35392", "country": "Germany"}]},
    ("Patient", "meta_profile_mii"): {"meta": DROP},
    # Encounter
    ("Encounter", "servicetype_required"): {"serviceType": DROP},
    ("Encounter", "diagnosis_present"): {"diagnosis": DROP},
    ("Encounter", "period_not_future"): {"status": "in-progress", "period": {"start": FUTURE}},
    ("Encounter", "text_forbidden"): TEXT,
    ("Encounter", "status_valid"): {"status": "done"},
    ("Encounter", "class_coded"): {"class": {"code": "IMP"}},
    ("Encounter", "kontaktebene_required"): {"type": DROP},
    ("Encounter", "servicetype_fachabteilung"): {"serviceType": OTHER},
    ("Encounter", "aufnahmenummer_required"): {"identifier": [{"value": "x"}]},
    ("Encounter", "finished_has_end"): {"period": {"start": "2024-01-01"}},
    ("Encounter", "planned_without_period"): {"status": "planned"},
    ("Encounter", "ongoing_has_start"): {"status": "in-progress", "period": DROP},
    ("Encounter", "diagnosis_use_required"): {"diagnosis": [{"condition": {"reference": "Condition/c-1"}}]},
    ("Encounter", "diagnosis_reference_format"): {
        "diagnosis": [{"condition": {"reference": "Procedure/1"}, "use": {"text": "x"}}]
    },
    ("Encounter", "partof_reference_format"): {"partOf": {"reference": "Patient/1"}},
    ("Encounter", "location_reference_format"): {"location": [{"location": {"reference": "Organization/1"}}]},
    ("Encounter", "service_provider_reference_format"): {"serviceProvider": {"reference": "Location/1"}},
    ("Encounter", "admit_source_required"): {"hospitalization": {"dischargeDisposition": {"text": "x"}}},
    ("Encounter", "meta_profile_mii"): {"meta": DROP},
    # Condition
    ("Condition", "text_forbidden"): TEXT,
    ("Condition", "recorded_date_required"): {"recordedDate": DROP},
    ("Condition", "recorded_date_not_future"): {"recordedDate": FUTURE},
    ("Condition", "onset_not_future"): {"onsetDateTime": FUTURE},
    ("Condition", "abatement_after_onset"): {"abatementDateTime": "2023-01-01"},
    ("Condition", "code_coding_known_system"): {"code": OTHER},
    ("Condition", "icd10gm_version_required"): {
        "code": {"coding": [{"system": "http://fhir.de/CodeSystem/bfarm/icd-10-gm", "code": "S72.01"}]}
    },
    ("Condition", "icd10gm_code_format"): {
        "code": {"coding": [{"system": "http://fhir.de/CodeSystem/bfarm/icd-10-gm", "version": "2024", "code": "U69.10!"}]}
    },
    ("Condition", "clinicalstatus_valid"): {
        "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "healed"}]}
    },
    ("Condition", "verificationstatus_valid"): {"verificationStatus": {"text": "sicher"}},
    ("Condition", "abatement_clinicalstatus"): {
        "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]}
    },
    ("Condition", "entered_in_error_without_clinicalstatus"): {
        "verificationStatus": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "entered-in-error"}]
        }
    },
    ("Condition", "bodysite_snomed"): {"bodySite": [{"text": "Hüfte"}]},
    ("Condition", "encounter_reference_format"): {"encounter": {"reference": "EpisodeOfCare/1"}},
    ("Condition", "meta_profile_mii"): {"meta": DROP},
    # Observation
    ("Observation", "note_cleartext_check"): {"note": [{"text": LONG}]},
    ("Observation", "text_forbidden"): TEXT,
    ("Observation", "status_valid"): {"status": "done"},
    ("Observation", "category_required"): {"category": DROP},
    ("Observation", "code_coding_complete"): {"code": {"coding": [{"code": "718-7"}]}},
    ("Observation", "encounter_reference_format"): {"encounter": {"reference": "Patient/1"}},
    ("Observation", "specimen_reference_format"): {"specimen": {"reference": "Patient/1"}},
    ("Observation", "effective_period_end_after_start"): {
        "effectiveDateTime": DROP,
        "effectivePeriod": {"start": "2024-01-02", "end": "2024-01-01"},
    },
    ("Observation", "issued_not_future"): {"issued": FUTURE},
    ("Observation", "issued_after_effective"): {"issued": "2023-12-31T00:00:00Z"},
    ("Observation", "value_absent_exclusive"): {"dataAbsentReason": {"text": "unknown"}},
    ("Observation", "value_quantity_ucum"): {"valueQuantity": {"value": 1, "unit": "g/dL"}},
    ("Observation", "value_quantity_value"): {"valueQuantity": {"unit": "g/dL", "system": UCUM, "code": "g/dL"}},
    ("Observation", "reference_range_order"): {"referenceRange": [{"low": {"value": 20}, "high": {"value": 10}}]},
    ("Observation", "component_code_required"): {"component": [{"valueQuantity": {"value": 1}}]},
    ("Observation", "lab_category_coding"): {"category": [{"coding": [{"system": OBS_CAT, "code": "laboratory"}]}]},
    ("Observation", "lab_code_loinc"): {"code": OTHER},
    ("Observation", "lab_identifier_required"): {"identifier": DROP},
    ("Observation", "lab_effective_precision"): {"effectiveDateTime": "2024-01"},
    ("Observation", "meta_profile_mii"): {"meta": DROP},
    # Medication
    ("Medication", "text_forbidden"): TEXT,
    ("Medication", "status_valid"): {"status": "on"},
    ("Medication", "code_coding_known_system"): {"code": OTHER},
    ("Medication", "atc_version_required"): {"code": {"coding": [{"system": ATC_DE, "code": "N02BE01"}]}},
    ("Medication", "atc_code_format"): {"code": {"coding": [{"system": ATC_DE, "version": "2024", "code": "N02BE1"}]}},
    ("Medication", "pzn_code_format"): {"code": {"coding": [{"system": PZN, "code": "1234"}]}},
    ("Medication", "ingredient_required"): {"ingredient": DROP},
    ("Medication", "ingredient_coding_known_system"): {"ingredient": [{"itemCodeableConcept": OTHER}]},
    ("Medication", "ingredient_strength_ucum"): {
        "ingredient": [
            {
                "itemCodeableConcept": {"coding": [{"system": "http://fhir.de/CodeSystem/ask", "code": "00001"}]},
                "strength": {"numerator": {"value": 500, "unit": "mg"}, "denominator": {"value": 1, "system": UCUM, "code": "1"}},
            }
        ]
    },
    ("Medication", "form_edqm"): {"form": OTHER},
    ("Medication", "meta_profile_mii"): {"meta": DROP},
    # MedicationRequest
    ("MedicationRequest", "note_cleartext_check"): {"note": [{"text": LONG}]},
    ("MedicationRequest", "text_forbidden"): TEXT,
    ("MedicationRequest", "status_valid"): {"status": "running"},
    ("MedicationRequest", "intent_valid"): {"intent": "prescription"},
    ("MedicationRequest", "medication_coding_known_system"): {"medicationCodeableConcept": OTHER},
    ("MedicationRequest", "atc_code_format"): {"medicationCodeableConcept": {"coding": [{"system": ATC_DE, "code": "n02be01"}]}},
    ("MedicationRequest", "pzn_code_format"): {"medicationCodeableConcept": {"coding": [{"system": PZN, "code": "12"}]}},
    ("MedicationRequest", "medication_reference_format"): {
        "medicationCodeableConcept": DROP,
        "medicationReference": {"reference": "Substance/1"},
    },
    ("MedicationRequest", "encounter_reference_format"): {"encounter": {"reference": "Patient/1"}},
    ("MedicationRequest", "dosage_text_or_structured"): {"dosageInstruction": [{"timing": {"code": {"text": "x"}}}]},
    ("MedicationRequest", "bounds_period_end_after_start"): {
        "dosageInstruction": [
            {"text": "1-0-1", "timing": {"repeat": {"boundsPeriod": {"start": "2024-01-10", "end": "2024-01-01"}}}}
        ]
    },
    ("MedicationRequest", "do_not_perform_forbidden"): {"doNotPerform": False},
    ("MedicationRequest", "meta_profile_mii"): {"meta": DROP},
    # MedicationAdministration
    ("MedicationAdministration", "note_cleartext_check"): {"dosage.text": LONG},
    ("MedicationAdministration", "text_forbidden"): TEXT,
    ("MedicationAdministration", "status_valid"): {"status": "given"},
    ("MedicationAdministration", "medication_coding_known_system"): {"medicationCodeableConcept": OTHER},
    ("MedicationAdministration", "atc_code_format"): {
        "medicationCodeableConcept": {"coding": [{"system": ATC_DE, "code": "N02BE01X"}]}
    },
    ("MedicationAdministration", "pzn_code_format"): {"medicationCodeableConcept": {"coding": [{"system": PZN, "code": "ABC"}]}},
    ("MedicationAdministration", "dose_ucum"): {"dosage.dose": {"value": 500, "unit": "mg"}},
    ("MedicationAdministration", "medication_reference_format"): {
        "medicationCodeableConcept": DROP,
        "medicationReference": {"reference": "Patient/1"},
    },
    ("MedicationAdministration", "context_reference_format"): {"context": {"reference": "Patient/1"}},
    ("MedicationAdministration", "request_reference_format"): {"request": {"reference": "Medication/1"}},
    ("MedicationAdministration", "meta_profile_mii"): {"meta": DROP},
    # MedicationStatement
    ("MedicationStatement", "status_required"): {"status": DROP},
    ("MedicationStatement", "medication_required"): {"medicationCodeableConcept": DROP},
    ("MedicationStatement", "subject_required"): {"subject": DROP},
    ("MedicationStatement", "subject_reference_format"): {"subject": {"reference": "Group/1"}},
    ("MedicationStatement", "effective_required"): {"effectivePeriod": DROP},
    ("MedicationStatement", "note_cleartext_check"): {"note": [{"text": LONG}]},
    ("MedicationStatement", "text_forbidden"): TEXT,
    ("MedicationStatement", "status_valid"): {"status": "taking"},
    ("MedicationStatement", "medication_coding_known_system"): {"medicationCodeableConcept": OTHER},
    ("MedicationStatement", "atc_code_format"): {"medicationCodeableConcept": {"coding": [{"system": ATC_DE, "code": "02BE01"}]}},
    ("MedicationStatement", "pzn_code_format"): {"medicationCodeableConcept": {"coding": [{"system": PZN, "code": "123456789"}]}},
    ("MedicationStatement", "effective_not_future"): {"effectivePeriod": {"start": FUTURE}},
    ("MedicationStatement", "effective_period_end_after_start"): {
        "effectivePeriod": {"start": "2024-01-31", "end": "2024-01-01"}
    },
    ("MedicationStatement", "date_asserted_not_future"): {"dateAsserted": FUTURE},
    ("MedicationStatement", "dosage_text_or_structured"): {"dosage": [{"sequence": 1}]},
    ("MedicationStatement", "medication_reference_format"): {
        "medicationCodeableConcept": DROP,
        "medicationReference": {"reference": "Patient/1"},
    },
    ("MedicationStatement", "context_reference_format"): {"context": {"reference": "Patient/1"}},
    ("MedicationStatement", "meta_profile_mii"): {"meta": DROP},
    # Procedure
    ("Procedure", "text_forbidden"): TEXT,
    ("Procedure", "status_valid"): {"status": "done"},
    ("Procedure", "code_coding_known_system"): {"code": OTHER},
    ("Procedure", "ops_version_required"): {
        "code": {"coding": [{"system": "http://fhir.de/CodeSystem/bfarm/ops", "code": "5-470.11"}]}
    },
    ("Procedure", "ops_code_format"): {
        "code": {"coding": [{"system": "http://fhir.de/CodeSystem/bfarm/ops", "version": "2024", "code": "5470"}]}
    },
    ("Procedure", "ops_requires_category"): {"category": DROP},
    ("Procedure", "performed_datetime_or_period"): {"performedString": "gestern"},
    ("Procedure", "performed_not_future"): {"performedPeriod": {"start": FUTURE}},
    ("Procedure", "performed_period_end_after_start"): {
        "performedPeriod": {"start": "2024-01-02T09:00:00Z", "end": "2024-01-02T08:00:00Z"}
    },
    ("Procedure", "bodysite_snomed"): {"bodySite": [{"text": "Hüfte"}]},
    ("Procedure", "encounter_reference_format"): {"encounter": {"reference": "Patient/1"}},
    ("Procedure", "meta_profile_mii"): {"meta": DROP},
    # DiagnosticReport
    ("DiagnosticReport", "text_forbidden"): TEXT,
    ("DiagnosticReport", "status_valid"): {"status": "done"},
    ("DiagnosticReport", "category_required"): {"category": DROP},
    ("DiagnosticReport", "identifier_required"): {"identifier": DROP},
    ("DiagnosticReport", "effective_required"): {"effectiveDateTime": DROP},
    ("DiagnosticReport", "issued_required"): {"issued": DROP},
    ("DiagnosticReport", "code_coding_complete"): {
        "code": {"coding": [{"system": LOINC, "code": "11502-2"}, {"code": "x"}]}
    },
    ("DiagnosticReport", "effective_not_future"): {"effectiveDateTime": FUTURE},
    ("DiagnosticReport", "issued_not_future"): {"issued": FUTURE},
    ("DiagnosticReport", "issued_after_effective"): {"issued": "2023-12-31"},
    ("DiagnosticReport", "effective_period_end_after_start"): {
        "effectiveDateTime": DROP,
        "effectivePeriod": {"start": "2024-01-02", "end": "2024-01-01"},
    },
    ("DiagnosticReport", "result_reference_format"): {"result": [{"reference": "DiagnosticReport/1"}]},
    ("DiagnosticReport", "basedon_reference_format"): {"basedOn": [{"reference": "Patient/1"}]},
    ("DiagnosticReport", "encounter_reference_format"): {"encounter": {"reference": "Patient/1"}},
    ("DiagnosticReport", "lab_category_coding"): {
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0074", "code": "LAB"}]}]
    },
    ("DiagnosticReport", "lab_code_loinc"): {"code": {"coding": [{"system": LOINC, "code": "24331-1"}]}},
    ("DiagnosticReport", "lab_result_required"): {"result": DROP},
    ("DiagnosticReport", "lab_basedon_required"): {"basedOn": DROP},
    ("DiagnosticReport", "meta_profile_mii"): {"meta": DROP},
    # ServiceRequest
    ("ServiceRequest", "status_required"): {"status": DROP},
    ("ServiceRequest", "intent_required"): {"intent": DROP},
    ("ServiceRequest", "subject_required"): {"subject": DROP},
    ("ServiceRequest", "code_required"): {"code": DROP},
    ("ServiceRequest", "category_required"): {"category": DROP},
    ("ServiceRequest", "authored_on_required"): {"authoredOn": DROP},
    ("ServiceRequest", "identifier_required"): {"identifier": DROP},
    ("ServiceRequest", "note_cleartext_check"): {"note": [{"text": LONG}]},
    ("ServiceRequest", "patient_instruction_forbidden"): {"patientInstruction": "nüchtern erscheinen"},
    ("ServiceRequest", "text_forbidden"): TEXT,
    ("ServiceRequest", "status_valid"): {"status": "done"},
    ("ServiceRequest", "intent_valid"): {"intent": "request"},
    ("ServiceRequest", "code_coding_complete"): {"code": {"coding": [{"system": LOINC}]}},
    ("ServiceRequest", "lab_order_status"): {"status": "active"},
    ("ServiceRequest", "authored_not_future"): {"authoredOn": FUTURE},
    ("ServiceRequest", "body_site_forbidden"): {"bodySite": [{"text": "Arm"}]},
    ("ServiceRequest", "subject_reference_format"): {"subject": {"reference": "Group/1"}},
    ("ServiceRequest", "encounter_reference_format"): {"encounter": {"reference": "Patient/1"}},
    ("ServiceRequest", "specimen_reference_format"): {"specimen": [{"reference": "Patient/1"}]},
    ("ServiceRequest", "meta_profile_mii"): {"meta": DROP},
    # Specimen
    ("Specimen", "status_required"): {"status": DROP},
    ("Specimen", "type_required"): {"type": DROP},
    ("Specimen", "subject_required"): {"subject": DROP},
    ("Specimen", "collection_required"): {"collection.collectedDateTime": DROP},
    ("Specimen", "identifier_required"): {"identifier": DROP},
    ("Specimen", "container_type_required"): {
        "container": [{"capacity": {"value": 10, "unit": "mL", "system": UCUM, "code": "mL"}}]
    },
    ("Specimen", "processing_procedure_required"): {"processing": [{"description": "zentrifugiert"}]},
    ("Specimen", "note_cleartext_check"): {"note": [{"text": LONG}]},
    ("Specimen", "text_forbidden"): TEXT,
    ("Specimen", "status_valid"): {"status": "ok"},
    ("Specimen", "type_snomed"): {"type": {"text": "Blut"}},
    ("Specimen", "bodysite_coding"): {"collection.bodySite": OTHER},
    ("Specimen", "collection_quantity_ucum"): {"collection.quantity": {"value": 5, "unit": "mL"}},
    ("Specimen", "container_quantity_ucum"): {
        "container": [{"type": {"text": "Röhrchen"}, "capacity": {"value": 10, "unit": "mL"}}]
    },
    ("Specimen", "collected_not_future"): {"collection.collectedDateTime": FUTURE},
    ("Specimen", "received_not_future"): {"receivedTime": FUTURE},
    ("Specimen", "received_after_collected"): {"receivedTime": "2023-12-31T00:00:00Z"},
    ("Specimen", "subject_reference_format"): {"subject": {"reference": "Group/1"}},
    ("Specimen", "parent_reference_format"): {"parent": [{"reference": "Patient/1"}]},
    ("Specimen", "request_reference_format"): {"request": [{"reference": "Patient/1"}]},
    ("Specimen", "parent_not_self"): {"parent": [{"reference": "Specimen/s-1"}]},
    ("Specimen", "meta_profile_mii"): {"meta": DROP},
    # Consent
    ("Consent", "status_required"): {"status": DROP},
    ("Consent", "patient_required"): {"patient": DROP},
    ("Consent", "datetime_required"): {"dateTime": DROP},
    ("Consent", "policy_required"): {"policy": DROP},
    ("Consent", "provision_period_required"): {"provision.period": {"end": "2054-01-01"}},
    ("Consent", "nested_provision_complete"): {
        "provision.provision": [{"type": "permit", "period": {"start": "2024-01-01"}}]
    },
    ("Consent", "status_valid"): {"status": "signed"},
    ("Consent", "scope_research"): {
        "scope": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/consentscope", "code": "patient-privacy"}]}
    },
    ("Consent", "category_loinc"): {"category": [{"text": "Einwilligung"}]},
    ("Consent", "provision_codes_mii"): {
        "provision.provision": [{"type": "permit", "period": {"start": "2024-01-01"}, "code": [OTHER]}]
    },
    ("Consent", "provision_type_valid"): {"provision.type": "allow"},
    ("Consent", "datetime_not_future"): {"dateTime": FUTURE},
    ("Consent", "provision_period_end_after_start"): {
        "provision.period": {"start": "2024-01-02", "end": "2024-01-01"}
    },
    ("Consent", "nested_period_end_after_start"): {
        "provision.provision": [
            {
                "type": "permit",
                "period": {"start": "2024-01-02", "end": "2024-01-01"},
                "code": [{"coding": [{"system": MII_POLICY, "code": "2.16.840.1.113883.3.1937.777.24.5.3.1"}]}],
            }
        ]
    },
    ("Consent", "patient_reference_format"): {"patient": {"reference": "Group/1"}},
    ("Consent", "meta_profile_mii"): {"meta": DROP},
    # ImagingStudy
    ("ImagingStudy", "status_required"): {"status": DROP},
    ("ImagingStudy", "subject_required"): {"subject": DROP},
    ("ImagingStudy", "started_required"): {"started": DROP},
    ("ImagingStudy", "study_uid_required"): {"identifier": [{"system": "urn:example", "value": "1"}]},
    ("ImagingStudy", "series_uid_required"): {"series": [{"modality": {"system": DCM, "code": "CT"}}]},
    ("ImagingStudy", "series_modality_required"): {"series": [{"uid": "1.2.3.4.1"}]},
    ("ImagingStudy", "instance_uid_required"): {
        "series": [{"uid": "1.2.3.4.1", "modality": {"system": DCM, "code": "CT"}, "instance": [{"uid": "1"}]}]
    },
    ("ImagingStudy", "text_forbidden"): TEXT,
    ("ImagingStudy", "status_valid"): {"status": "done"},
    ("ImagingStudy", "modality_dicom"): {"modality": [{"system": "http://example.org", "code": "CT"}]},
    ("ImagingStudy", "started_not_future"): {"started": FUTURE},
    ("ImagingStudy", "number_of_series_consistent"): {"numberOfSeries": 3},
    ("ImagingStudy", "number_of_instances_consistent"): {"numberOfInstances": 5},
    ("ImagingStudy", "subject_reference_format"): {"subject": {"reference": "Group/1"}},
    ("ImagingStudy", "encounter_reference_format"): {"encounter": {"reference": "Patient/1"}},
    ("ImagingStudy", "basedon_reference_format"): {"basedOn": [{"reference": "Patient/1"}]},
    ("ImagingStudy", "meta_profile_mii"): {"meta": DROP},
}
