#!/usr/bin/env python3
"""
Synthetische, MII-KDS-orientierte Testdaten für FHIR Verity.

Erzeugt pro Patient einen zusammenhängenden Datensatz (Fall, Diagnosen, Labor,
Medikation, Prozeduren, Bioproben, Einwilligung, Bildgebung), baut gezielt
Fehler ein, die einzelne Verity-Regeln verletzen, und lädt alles in
Transaktionen auf einen FHIR-Server. Jede Transaktion enthält die vollständigen
Daten einer Gruppe von Patienten, damit alle Referenzen innerhalb der
Transaktion auflösen.

Standardmengen bei --patients 1000:
  Patient 1000, Encounter 2000, Condition 3000, Observation 3000,
  je 2000 Medication, MedicationRequest, MedicationAdministration,
  MedicationStatement, Procedure, DiagnosticReport, ServiceRequest,
  Specimen, Consent, ImagingStudy

Die Manifest-Datei (CSV) hält fest, welche Ressource welchen Fehler enthält und
welche Verity-Regeln darauf anschlagen sollen. Sie ist die Referenz für die
Auswertung (Sensitivität, Präzision).

Alle Daten sind synthetisch. Codes sind illustrativ, nicht klinisch sinnvoll.
Alle Ressourcen tragen das Tag v3-ActReason#HTEST (test health data).

Beispiele:
  # nur Dateien schreiben
  python verity_testdaten.py --out ./bundles

  # hochladen (Passwort alternativ über FHIR_PASSWORD)
  python verity_testdaten.py --base-url https://server/fhir --user alice --password geheim

  # löschen (Server muss bedingtes Löschen mehrerer Treffer erlauben)
  DELETE [base]/<Typ>?_tag=http://terminology.hl7.org/CodeSystem/v3-ActReason|HTEST
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import random
import sys
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Profile, Systeme, Konstanten
# ---------------------------------------------------------------------------

MII = "https://www.medizininformatik-initiative.de/fhir"
PROFILE = {
    "Patient": f"{MII}/core/modul-person/StructureDefinition/PatientPseudonymisiert",
    "Encounter": f"{MII}/core/modul-fall/StructureDefinition/KontaktGesundheitseinrichtung",
    "Condition": f"{MII}/core/modul-diagnose/StructureDefinition/Diagnose",
    "Observation": f"{MII}/core/modul-labor/StructureDefinition/ObservationLab",
    "DiagnosticReport": f"{MII}/core/modul-labor/StructureDefinition/DiagnosticReportLab",
    "ServiceRequest": f"{MII}/core/modul-labor/StructureDefinition/ServiceRequestLab",
    "Medication": f"{MII}/core/modul-medikation/StructureDefinition/Medication",
    "MedicationRequest": f"{MII}/core/modul-medikation/StructureDefinition/MedicationRequest",
    "MedicationAdministration": f"{MII}/core/modul-medikation/StructureDefinition/MedicationAdministration",
    "MedicationStatement": f"{MII}/core/modul-medikation/StructureDefinition/MedicationStatement",
    "Procedure": f"{MII}/core/modul-prozedur/StructureDefinition/Procedure",
    "Specimen": f"{MII}/core/modul-biobank/StructureDefinition/Specimen",
    "Consent": f"{MII}/modul-consent/StructureDefinition/mii-pr-consent-einwilligung",
    "ImagingStudy": f"{MII}/ext/modul-bildgebung/StructureDefinition/mii-pr-bildgebung-bildgebungsstudie",
}

LOINC = "http://loinc.org"
SNOMED = "http://snomed.info/sct"
UCUM = "http://unitsofmeasure.org"
ICD10GM = "http://fhir.de/CodeSystem/bfarm/icd-10-gm"
OPS = "http://fhir.de/CodeSystem/bfarm/ops"
ATC = "http://fhir.de/CodeSystem/bfarm/atc"
PZN = "http://fhir.de/CodeSystem/ifa/pzn"
ASK = "http://fhir.de/CodeSystem/ask"
EDQM = "http://standardterms.edqm.eu"
V2_0203 = "http://terminology.hl7.org/CodeSystem/v2-0203"
V2_0074 = "http://terminology.hl7.org/CodeSystem/v2-0074"
OBS_CAT = "http://terminology.hl7.org/CodeSystem/observation-category"
DCM = "http://dicom.nema.org/resources/ontology/DCM"
LOCAL = "https://diz.example/fhir/CodeSystem/lokal"
TEST_TAG = {"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "HTEST"}

ORG_ID = "vf-org"
GROUP_ID = "vf-group"
EXTERNAL = "https://andere-klinik.example/fhir"

LONG_TEXT = "Rücksprache mit Herrn Max Mustermann, Tel. 0641 000000, Musterstraße 1, 35390 Gießen"
NARRATIVE = {"status": "generated", "div": '<div xmlns="http://www.w3.org/1999/xhtml">Max Mustermann, geb. 01.02.1960</div>'}
FAKE_NAMES = [("Mustermann", "Max"), ("Musterfrau", "Erika"), ("Beispiel", "Jonas"), ("Test", "Lena"), ("Probe", "Paul")]

LAB = [  # LOINC, Anzeige, UCUM, normal low, normal high
    ("718-7", "Hemoglobin", "g/dL", 12.0, 17.0),
    ("2160-0", "Creatinine", "mg/dL", 0.6, 1.3),
    ("2345-7", "Glucose", "mg/dL", 70.0, 110.0),
    ("6690-2", "Leukocytes", "10*3/uL", 4.0, 10.0),
    ("777-3", "Platelets", "10*3/uL", 150.0, 400.0),
]
ICD = [("I10.90", "Essentielle Hypertonie"), ("E11.90", "Diabetes mellitus Typ 2"), ("J18.9", "Pneumonie"),
       ("N39.0", "Harnwegsinfektion"), ("I21.4", "Akuter Myokardinfarkt"), ("K35.8", "Akute Appendizitis")]
OPS_CODES = [("5-470.11", "Appendektomie, laparoskopisch"), ("8-930", "Monitoring"), ("3-200", "Native CT des Schädels"),
             ("1-632.0", "Ösophagogastroduodenoskopie"), ("5-820.00", "Implantation einer Endoprothese am Hüftgelenk")]
DRUGS = [("N02BE01", "Paracetamol", "01126111", "22279"), ("C09AA05", "Ramipril", "03213452", "26138"),
         ("A02BC02", "Pantoprazol", "02391426", "31393"), ("B01AB05", "Enoxaparin", "04562313", "27166")]
FACHABTEILUNG = [("0100", "Innere Medizin"), ("1500", "Allgemeine Chirurgie"), ("0300", "Kardiologie")]

# Reihenfolge innerhalb einer Transaktion: referenzierte Ressourcen zuerst
ORDER = ["Organization", "Group", "Patient", "Medication", "Condition", "Encounter", "ServiceRequest",
         "Specimen", "Observation", "DiagnosticReport", "Procedure", "MedicationRequest",
         "MedicationAdministration", "MedicationStatement", "Consent", "ImagingStudy"]


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def ts(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def instant(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def cc(system: str, code: str, display: str | None = None, version: str | None = None) -> dict:
    coding = {"system": system, "code": code}
    if version:
        coding["version"] = version
    if display:
        coding["display"] = display
    return {"coding": [coding]}


def ref(rtype: str, rid: str) -> dict:
    return {"reference": f"{rtype}/{rid}"}


def qty(value: float, ucum: str) -> dict:
    return {"value": value, "unit": ucum, "system": UCUM, "code": ucum}


def base(rtype: str, rid: str) -> dict:
    return {"resourceType": rtype, "id": rid, "meta": {"profile": [PROFILE[rtype]], "tag": [dict(TEST_TAG)]}}


def no_profile(r: dict) -> None:
    r["meta"].pop("profile", None)


def future(days: int = 1800) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


# ---------------------------------------------------------------------------
# Fehlerkatalog: Schlüssel -> erwartete Verity-Regeln und Mutation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Defect:
    key: str
    rules: tuple[str, ...]
    apply: Callable[[dict, "Ctx"], None]
    risky: bool = False  # Server lehnt die Ressource möglicherweise ab
    note: str = ""


@dataclass
class Ctx:
    rng: random.Random
    rid: str


def d(key, rules, apply, risky=False, note=""):
    return Defect(key, tuple(rules.split()) if isinstance(rules, str) else tuple(rules), apply, risky, note)


def pop(*paths):
    def f(r, c):
        for p in paths:
            obj = r
            parts = p.split(".")
            for part in parts[:-1]:
                obj = obj[part] if not isinstance(obj, list) else obj[0][part]
            if isinstance(obj, list):
                obj = obj[0]
            obj.pop(parts[-1], None)
    return f


def setv(path, value):
    def f(r, c):
        obj = r
        parts = path.split(".")
        for part in parts[:-1]:
            obj = obj[part] if not isinstance(obj, list) else obj[0][part]
        if isinstance(obj, list):
            obj = obj[0]
        obj[parts[-1]] = value(r, c) if callable(value) else value
    return f


def chain(*fs):
    def f(r, c):
        for g in fs:
            g(r, c)
    return f


GROUP_REF = {"reference": f"Group/{GROUP_ID}"}
IDENT_ONLY = {"identifier": {"system": "https://diz.example/fhir/sid/patient", "value": "P-4711"}}


def ext_ref(rtype):
    return {"reference": f"{EXTERNAL}/{rtype}/123"}


COMMON = lambda subject_field="subject": [  # noqa: E731
    d("text_forbidden", "text_forbidden", setv("text", NARRATIVE)),
    d("meta_profile_mii", "meta_profile_mii", lambda r, c: no_profile(r)),
]

DEFECTS: dict[str, list[Defect]] = {
    "Patient": [
        d("name_forbidden", "name_forbidden", lambda r, c: r.update(name=[{"family": c.rng.choice(FAKE_NAMES)[0], "given": [c.rng.choice(FAKE_NAMES)[1]]}])),
        d("address_forbidden", "address_forbidden", lambda r, c: r["address"][0].update(line=["Musterstraße 1"], city="Gießen")),
        d("telecom_forbidden", "telecom_forbidden", setv("telecom", [{"system": "phone", "value": "+49 641 0000000"}])),
        d("photo_forbidden", "photo_forbidden", setv("photo", [{"contentType": "image/png", "url": "https://diz.example/foto.png"}])),
        d("pseudonym_format_check", "pseudonym_format_check", lambda r, c: None, note="Patient.id im Format ^20[0-9]{7}$"),
        d("identifier_pseudonym_check", "identifier_pseudonym_check",
          lambda r, c: r["identifier"].append({"type": cc(V2_0203, "MR"), "system": "https://diz.example/fhir/sid/patienten", "value": f"20{c.rng.randint(0, 9999999):07d}"})),
        d("identifier_required", "identifier_required", pop("identifier")),
        d("birthdate_required", "birthdate_required", pop("birthDate")),
        d("gender_required", "gender_required", pop("gender")),
        d("birthdate_not_future", "birthdate_not_future", setv("birthDate", lambda r, c: future().date().isoformat())),
        d("birthdate_not_future_month", "birthdate_not_future", setv("birthDate", lambda r, c: future().strftime("%Y-%m")),
          note="Datum nur mit Monat; Verity is_future liest solche Werte derzeit nicht"),
        d("birthdate_plausible_range", "birthdate_plausible_range", setv("birthDate", "1850-03-01")),
        d("managingorganization_required", "managingorganization_required", pop("managingOrganization")),
        d("contact_forbidden", "contact_forbidden", setv("contact", [{"name": {"family": "Mustermann", "given": ["Erika"]}}])),
        d("pseudonymized_identifier_type", "pseudonymized_identifier_type", lambda r, c: r["identifier"][0].update(type=cc(V2_0203, "MR"))),
        d("gender_valid", "gender_valid", setv("gender", "divers"), risky=True, note="ungültiger Code bei required binding"),
        d("gender_other_amtlich", "gender_other_amtlich", setv("gender", "other")),
        d("birthdate_format", "birthdate_format", setv("birthDate", "02.04.1975"), risky=True, note="ungültiger FHIR-date-Wert"),
        d("deceased_after_birth", "deceased_after_birth", lambda r, c: r.update(deceasedDateTime=f"{int(r['birthDate'][:4]) - 3}-06-01T10:00:00Z")),
        d("deceased_not_future", "deceased_not_future", setv("deceasedDateTime", lambda r, c: ts(future()))),
        d("address_postalcode_required", "address_postalcode_required", lambda r, c: r["address"][0].pop("postalCode")),
        d("address_country_required", "address_country_required", lambda r, c: r["address"][0].pop("country")),
        d("address_country_code", "address_country_code", lambda r, c: r["address"][0].update(country="Deutschland")),
        *COMMON(),
    ],
    "Encounter": [
        d("pseudonym_format_check", "pseudonym_format_check", lambda r, c: r["identifier"][0].update(value=f"20{c.rng.randint(0, 99999999):08d}")),
        d("status_required", "status_required", pop("status")),
        d("class_required", "class_required", pop("class")),
        d("subject_required", "subject_required", pop("subject")),
        d("period_start_required", "period_start_required", pop("period.start")),
        d("period_end_after_start", "period_end_after_start",
          lambda r, c: r["period"].update(end=ts(datetime.fromisoformat(r["period"]["start"].replace("Z", "+00:00")) - timedelta(days=2)))),
        d("period_plausible_duration", "period_plausible_duration",
          lambda r, c: r["period"].update(start=ts(datetime.fromisoformat(r["period"]["end"].replace("Z", "+00:00")) - timedelta(days=1100)))),
        d("subject_reference_format", "subject_reference_format", setv("subject", GROUP_REF)),
        d("subject_reference_identifier_only", "subject_reference_format", setv("subject", IDENT_ONLY),
          note="laut validierungsregeln.md ein Verstoß, references() prüft das derzeit nicht"),
        d("servicetype_required", "servicetype_required", pop("serviceType")),
        d("diagnosis_present", "diagnosis_present", pop("diagnosis")),
        d("period_not_future", "period_not_future", lambda r, c: r.update(status="in-progress", period={"start": ts(future())})),
        d("status_valid", "status_valid", setv("status", "abgeschlossen"), risky=True),
        d("class_coded", "class_coded", lambda r, c: r["class"].pop("system")),
        d("kontaktebene_required", "kontaktebene_required", pop("type")),
        d("servicetype_fachabteilung", "servicetype_fachabteilung", setv("serviceType", cc(LOCAL, "INN", "Innere"))),
        d("aufnahmenummer_required", "aufnahmenummer_required", lambda r, c: r["identifier"][0].update(type=cc(V2_0203, "AN"))),
        d("finished_has_end", "finished_has_end", pop("period.end")),
        d("planned_without_period", "planned_without_period", setv("status", "planned")),
        d("ongoing_has_start", "ongoing_has_start period_start_required", lambda r, c: (r.update(status="in-progress"), r.pop("period"))),
        d("diagnosis_use_required", "diagnosis_use_required", lambda r, c: r["diagnosis"][0].pop("use")),
        d("diagnosis_reference_format", "diagnosis_reference_format", lambda r, c: r["diagnosis"][0].update(condition=ext_ref("Condition")), risky=True, note="externe Referenz"),
        d("partof_reference_format", "partof_reference_format", setv("partOf", ext_ref("Encounter")), risky=True, note="externe Referenz"),
        d("location_reference_format", "location_reference_format", setv("location", [{"location": ext_ref("Location")}]), risky=True, note="externe Referenz"),
        d("service_provider_reference_format", "service_provider_reference_format", setv("serviceProvider", ext_ref("Organization")), risky=True, note="externe Referenz"),
        d("admit_source_required", "admit_source_required", lambda r, c: r.update(hospitalization={"dischargeDisposition": cc("http://fhir.de/CodeSystem/dkgev/EntlassungsgrundErsteUndZweiteStelle", "01")})),
        *COMMON(),
    ],
    "Condition": [
        d("note_cleartext_check", "note_cleartext_check", setv("note", [{"text": LONG_TEXT}])),
        d("code_required", "code_required", pop("code")),
        d("subject_required", "subject_required", pop("subject")),
        d("clinicalstatus_required", "clinicalstatus_required", pop("clinicalStatus")),
        d("verificationstatus_required", "verificationstatus_required", pop("verificationStatus")),
        d("onset_present", "onset_present", pop("onsetDateTime")),
        d("subject_reference_format", "subject_reference_format", setv("subject", GROUP_REF)),
        d("recorded_date_required", "recorded_date_required", pop("recordedDate")),
        d("recorded_date_not_future", "recorded_date_not_future", setv("recordedDate", lambda r, c: ts(future()))),
        d("onset_not_future", "onset_not_future", setv("onsetDateTime", lambda r, c: ts(future()))),
        d("abatement_after_onset", "abatement_after_onset",
          lambda r, c: r.update(abatementDateTime="2019-01-01T08:00:00Z", clinicalStatus=cc("http://terminology.hl7.org/CodeSystem/condition-clinical", "resolved"))),
        d("code_coding_known_system", "code_coding_known_system", setv("code", cc(LOCAL, "D-17", "Hausdiagnose"))),
        d("icd10gm_version_required", "icd10gm_version_required", lambda r, c: r["code"]["coding"][0].pop("version")),
        d("icd10gm_code_format", "icd10gm_code_format", lambda r, c: r["code"]["coding"][0].update(code="I10*")),
        d("clinicalstatus_valid", "clinicalstatus_valid", setv("clinicalStatus", cc("http://terminology.hl7.org/CodeSystem/condition-clinical", "aktiv"))),
        d("verificationstatus_valid", "verificationstatus_valid", setv("verificationStatus", cc("http://terminology.hl7.org/CodeSystem/condition-ver-status", "gesichert"))),
        d("abatement_clinicalstatus", "abatement_clinicalstatus",
          lambda r, c: r.update(abatementDateTime=ts(datetime.fromisoformat(r["onsetDateTime"].replace("Z", "+00:00")) + timedelta(days=30)))),
        d("entered_in_error_without_clinicalstatus", "entered_in_error_without_clinicalstatus",
          setv("verificationStatus", cc("http://terminology.hl7.org/CodeSystem/condition-ver-status", "entered-in-error"))),
        d("bodysite_snomed", "bodysite_snomed", setv("bodySite", [cc(LOCAL, "ARM-R", "rechter Arm")])),
        d("encounter_reference_format", "encounter_reference_format", setv("encounter", ext_ref("Encounter")), risky=True, note="externe Referenz"),
        *COMMON(),
    ],
    "Observation": [
        d("value_string_cleartext_forbidden", "value_string_cleartext_forbidden",
          lambda r, c: (r.pop("valueQuantity"), r.pop("referenceRange"), r.update(valueString=LONG_TEXT))),
        d("status_required", "status_required", pop("status")),
        d("code_required", "code_required lab_code_loinc", pop("code")),
        d("subject_required", "subject_required", pop("subject")),
        d("effective_required", "effective_required", pop("effectiveDateTime")),
        d("value_present", "value_present", lambda r, c: (r.pop("valueQuantity"), r.pop("referenceRange"))),
        d("effective_not_future", "effective_not_future", lambda r, c: (r.update(effectiveDateTime=ts(future())), r.pop("issued"))),
        d("subject_reference_format", "subject_reference_format", setv("subject", GROUP_REF)),
        d("note_cleartext_check", "note_cleartext_check", setv("note", [{"text": LONG_TEXT}])),
        d("status_valid", "status_valid", setv("status", "freigegeben"), risky=True),
        d("category_required", "category_required", pop("category")),
        d("code_coding_complete", "code_coding_complete", lambda r, c: r["code"]["coding"].append({"code": "HB"})),
        d("encounter_reference_format", "encounter_reference_format", setv("encounter", ext_ref("Encounter")), risky=True, note="externe Referenz"),
        d("specimen_reference_format", "specimen_reference_format", setv("specimen", ext_ref("Specimen")), risky=True, note="externe Referenz"),
        d("effective_period_end_after_start", "effective_period_end_after_start",
          lambda r, c: r.update(effectivePeriod={"start": r.pop("effectiveDateTime"), "end": "2019-01-01T08:00:00Z"})),
        d("issued_not_future", "issued_not_future", setv("issued", lambda r, c: instant(future()))),
        d("issued_after_effective", "issued_after_effective", setv("issued", "2019-01-01T08:00:00.000Z")),
        d("value_absent_exclusive", "value_absent_exclusive",
          setv("dataAbsentReason", cc("http://terminology.hl7.org/CodeSystem/data-absent-reason", "unknown"))),
        d("value_quantity_ucum", "value_quantity_ucum", lambda r, c: r["valueQuantity"].pop("system")),
        d("value_quantity_value", "value_quantity_value", lambda r, c: r["valueQuantity"].pop("value")),
        d("reference_range_order", "reference_range_order",
          lambda r, c: r["referenceRange"][0].update(low=r["referenceRange"][0]["high"], high=r["referenceRange"][0]["low"])),
        d("component_code_required", "component_code_required", setv("component", [{"valueQuantity": qty(1.0, "g/dL")}])),
        d("lab_category_coding", "lab_category_coding", setv("category", [cc(OBS_CAT, "laboratory")])),
        d("lab_code_loinc", "lab_code_loinc", setv("code", cc(LOCAL, "HB", "Hämoglobin"))),
        d("lab_identifier_required", "lab_identifier_required", pop("identifier")),
        d("lab_effective_precision", "lab_effective_precision", lambda r, c: (r.update(effectiveDateTime=r["effectiveDateTime"][:7]), r.pop("issued"))),
        *COMMON(),
    ],
    "Medication": [
        d("code_required", "code_required", pop("code")),
        d("code_coding_present", "code_coding_present code_coding_known_system", setv("code", {"text": "Paracetamol 500 mg"})),
        d("ingredient_item_check", "ingredient_item_check", lambda r, c: r["ingredient"][0].pop("itemCodeableConcept")),
        d("status_valid", "status_valid", setv("status", "aktiv"), risky=True),
        d("code_coding_known_system", "code_coding_known_system", setv("code", cc(LOCAL, "PCM500", "Paracetamol 500"))),
        d("atc_version_required", "atc_version_required", lambda r, c: r["code"]["coding"][0].pop("version")),
        d("atc_code_format", "atc_code_format", lambda r, c: r["code"]["coding"][0].update(code="N02BE1")),
        d("pzn_code_format", "pzn_code_format", lambda r, c: r["code"]["coding"][1].update(code="1126111")),
        d("ingredient_required", "ingredient_required", pop("ingredient")),
        d("ingredient_coding_known_system", "ingredient_coding_known_system", lambda r, c: r["ingredient"][0].update(itemCodeableConcept=cc(LOCAL, "WS-1", "Wirkstoff"))),
        d("ingredient_strength_ucum", "ingredient_strength_ucum", lambda r, c: r["ingredient"][0]["strength"]["numerator"].pop("system")),
        d("form_edqm", "form_edqm", setv("form", cc(LOCAL, "TAB", "Tablette"))),
        *COMMON(),
    ],
}


def _med_common(rtype, dosage_field):
    """Fehler, die MedicationRequest, -Administration und -Statement teilen."""
    return [
        d("status_required", "status_required", pop("status")),
        d("medication_required", "medication_required", pop("medicationReference")),
        d("subject_required", "subject_required", pop("subject")),
        d("subject_reference_format", "subject_reference_format", setv("subject", GROUP_REF)),
        d("note_cleartext_check", "note_cleartext_check", setv("note", [{"text": LONG_TEXT}])),
        d("status_valid", "status_valid", setv("status", "laufend"), risky=True),
        d("medication_coding_known_system", "medication_coding_known_system",
          lambda r, c: (r.pop("medicationReference"), r.update(medicationCodeableConcept=cc(LOCAL, "PCM500", "Paracetamol 500")))),
        d("atc_code_format", "atc_code_format",
          lambda r, c: (r.pop("medicationReference"), r.update(medicationCodeableConcept=cc(ATC, "N2BE01", "Paracetamol", "2025")))),
        d("pzn_code_format", "pzn_code_format",
          lambda r, c: (r.pop("medicationReference"), r.update(medicationCodeableConcept=cc(PZN, "126111", "Paracetamol")))),
        d("medication_reference_format", "medication_reference_format", setv("medicationReference", ext_ref("Medication")), risky=True, note="externe Referenz"),
        *COMMON(),
    ]


DEFECTS["MedicationRequest"] = _med_common("MedicationRequest", "dosageInstruction") + [
    d("intent_required", "intent_required", pop("intent")),
    d("authored_on_required", "authored_on_required",
      lambda r, c: (r.pop("authoredOn"), r["dosageInstruction"][0]["timing"]["repeat"].pop("boundsPeriod"))),
    d("authored_not_future", "authored_not_future", setv("authoredOn", lambda r, c: ts(future()))),
    d("intent_valid", "intent_valid", setv("intent", "anordnung"), risky=True),
    d("encounter_reference_format", "encounter_reference_format", setv("encounter", ext_ref("Encounter")), risky=True, note="externe Referenz"),
    d("dosage_text_or_structured", "dosage_text_or_structured", lambda r, c: (r["dosageInstruction"][0].pop("text"), r["dosageInstruction"][0].pop("doseAndRate"))),
    d("bounds_period_end_after_start", "bounds_period_end_after_start",
      lambda r, c: r["dosageInstruction"][0]["timing"]["repeat"]["boundsPeriod"].update(end="2019-01-01T08:00:00Z")),
    d("do_not_perform_forbidden", "do_not_perform_forbidden", setv("doNotPerform", False)),
]
DEFECTS["MedicationAdministration"] = _med_common("MedicationAdministration", "dosage") + [
    d("effective_required", "effective_required", pop("effectiveDateTime")),
    d("effective_not_future", "effective_not_future", setv("effectiveDateTime", lambda r, c: ts(future()))),
    d("effective_period_end_after_start", "effective_period_end_after_start",
      lambda r, c: r.update(effectivePeriod={"start": r.pop("effectiveDateTime"), "end": "2019-01-01T08:00:00Z"})),
    d("dose_ucum", "dose_ucum", lambda r, c: r["dosage"]["dose"].pop("system")),
    d("context_reference_format", "context_reference_format", setv("context", ext_ref("Encounter")), risky=True, note="externe Referenz"),
    d("request_reference_format", "request_reference_format", setv("request", ext_ref("MedicationRequest")), risky=True, note="externe Referenz"),
]
DEFECTS["MedicationStatement"] = _med_common("MedicationStatement", "dosage") + [
    d("effective_required", "effective_required", pop("effectivePeriod")),
    d("effective_not_future", "effective_not_future", lambda r, c: r["effectivePeriod"].update(start=ts(future()), end=ts(future(1900)))),
    d("effective_period_end_after_start", "effective_period_end_after_start", lambda r, c: r["effectivePeriod"].update(end="2019-01-01T08:00:00Z")),
    d("date_asserted_not_future", "date_asserted_not_future", setv("dateAsserted", lambda r, c: ts(future()))),
    d("dosage_text_or_structured", "dosage_text_or_structured", lambda r, c: r.update(dosage=[{"asNeededBoolean": False}])),
    d("context_reference_format", "context_reference_format", setv("context", ext_ref("Encounter")), risky=True, note="externe Referenz"),
]
DEFECTS["Procedure"] = [
    d("note_cleartext_check", "note_cleartext_check", setv("note", [{"text": LONG_TEXT}])),
    d("status_required", "status_required", pop("status")),
    d("code_required", "code_required", pop("code")),
    d("subject_required", "subject_required", pop("subject")),
    d("performed_required", "performed_required", pop("performedDateTime")),
    d("subject_reference_format", "subject_reference_format", setv("subject", GROUP_REF)),
    d("status_valid", "status_valid", setv("status", "erledigt"), risky=True),
    d("code_coding_known_system", "code_coding_known_system", setv("code", cc(LOCAL, "OP-1", "Hausprozedur"))),
    d("ops_version_required", "ops_version_required", lambda r, c: r["code"]["coding"][0].pop("version")),
    d("ops_code_format", "ops_code_format", lambda r, c: r["code"]["coding"][0].update(code="5470.11")),
    d("ops_requires_category", "ops_requires_category", pop("category")),
    d("performed_datetime_or_period", "performed_datetime_or_period", lambda r, c: (r.pop("performedDateTime"), r.update(performedString="vor zwei Wochen"))),
    d("performed_not_future", "performed_not_future", setv("performedDateTime", lambda r, c: ts(future()))),
    d("performed_period_end_after_start", "performed_period_end_after_start",
      lambda r, c: r.update(performedPeriod={"start": r.pop("performedDateTime"), "end": "2019-01-01T08:00:00Z"})),
    d("bodysite_snomed", "bodysite_snomed", setv("bodySite", [cc(LOCAL, "BAUCH", "Bauch")])),
    d("encounter_reference_format", "encounter_reference_format", setv("encounter", ext_ref("Encounter")), risky=True, note="externe Referenz"),
    *COMMON(),
]
DEFECTS["DiagnosticReport"] = [
    d("note_cleartext_check", "note_cleartext_check", setv("conclusion", LONG_TEXT)),
    d("status_required", "status_required", pop("status")),
    d("code_required", "code_required lab_code_loinc", pop("code")),
    d("subject_required", "subject_required", pop("subject")),
    d("subject_reference_format", "subject_reference_format", setv("subject", GROUP_REF)),
    d("status_valid", "status_valid", setv("status", "fertig"), risky=True),
    d("category_required", "category_required", pop("category")),
    d("identifier_required", "identifier_required", pop("identifier")),
    d("effective_required", "effective_required", pop("effectiveDateTime")),
    d("issued_required", "issued_required", pop("issued")),
    d("code_coding_complete", "code_coding_complete", lambda r, c: r["code"]["coding"].append({"code": "LAB"})),
    d("effective_not_future", "effective_not_future issued_not_future",
      lambda r, c: r.update(effectiveDateTime=ts(future()), issued=instant(future(1801)))),
    d("issued_not_future", "issued_not_future", setv("issued", lambda r, c: instant(future()))),
    d("issued_after_effective", "issued_after_effective", setv("issued", "2019-01-01T08:00:00.000Z")),
    d("effective_period_end_after_start", "effective_period_end_after_start",
      lambda r, c: (r.update(effectivePeriod={"start": r.pop("effectiveDateTime"), "end": "2019-01-01T08:00:00Z"}))),
    d("result_reference_format", "result_reference_format", setv("result", [ext_ref("Observation")]), risky=True, note="externe Referenz"),
    d("basedon_reference_format", "basedon_reference_format", setv("basedOn", [ext_ref("ServiceRequest")]), risky=True, note="externe Referenz"),
    d("encounter_reference_format", "encounter_reference_format", setv("encounter", ext_ref("Encounter")), risky=True, note="externe Referenz"),
    d("lab_category_coding", "lab_category_coding", setv("category", [cc(V2_0074, "LAB")])),
    d("lab_code_loinc", "lab_code_loinc", setv("code", cc(LOINC, "24323-8", "Comprehensive metabolic panel"))),
    d("lab_result_required", "lab_result_required", pop("result")),
    d("lab_basedon_required", "lab_basedon_required", pop("basedOn")),
    *COMMON(),
]
DEFECTS["ServiceRequest"] = [
    d("status_required", "status_required lab_order_status", pop("status")),
    d("intent_required", "intent_required lab_order_status", pop("intent")),
    d("subject_required", "subject_required", pop("subject")),
    d("code_required", "code_required", pop("code")),
    d("category_required", "category_required", pop("category")),
    d("authored_on_required", "authored_on_required", pop("authoredOn")),
    d("identifier_required", "identifier_required", pop("identifier")),
    d("note_cleartext_check", "note_cleartext_check", setv("note", [{"text": LONG_TEXT}])),
    d("patient_instruction_forbidden", "patient_instruction_forbidden", setv("patientInstruction", "Bitte nüchtern erscheinen")),
    d("status_valid", "status_valid lab_order_status", setv("status", "abgeschlossen"), risky=True),
    d("intent_valid", "intent_valid lab_order_status", setv("intent", "auftrag"), risky=True),
    d("code_coding_complete", "code_coding_complete", lambda r, c: r["code"]["coding"].append({"code": "BB"})),
    d("lab_order_status", "lab_order_status", setv("status", "active")),
    d("authored_not_future", "authored_not_future", setv("authoredOn", lambda r, c: ts(future()))),
    d("body_site_forbidden", "body_site_forbidden", setv("bodySite", [cc(SNOMED, "368209003", "Right upper arm structure")])),
    d("subject_reference_format", "subject_reference_format", setv("subject", GROUP_REF)),
    d("encounter_reference_format", "encounter_reference_format", setv("encounter", ext_ref("Encounter")), risky=True, note="externe Referenz"),
    d("specimen_reference_format", "specimen_reference_format", setv("specimen", [ext_ref("Specimen")]), risky=True, note="externe Referenz"),
    *COMMON(),
]
DEFECTS["Specimen"] = [
    d("status_required", "status_required", pop("status")),
    d("type_required", "type_required", pop("type")),
    d("subject_required", "subject_required", pop("subject")),
    d("collection_required", "collection_required", pop("collection.collectedDateTime")),
    d("identifier_required", "identifier_required", pop("identifier")),
    d("container_type_required", "container_type_required", lambda r, c: r["container"][0].pop("type")),
    d("processing_procedure_required", "processing_procedure_required", lambda r, c: r["processing"][0].pop("procedure")),
    d("note_cleartext_check", "note_cleartext_check", setv("note", [{"text": LONG_TEXT}])),
    d("status_valid", "status_valid", setv("status", "verfuegbar"), risky=True),
    d("type_snomed", "type_snomed", setv("type", cc(LOCAL, "BLUT", "Blut"))),
    d("bodysite_coding", "bodysite_coding", lambda r, c: r["collection"].update(bodySite=cc(LOCAL, "ARM", "Arm"))),
    d("collection_quantity_ucum", "collection_quantity_ucum", lambda r, c: r["collection"]["quantity"].pop("system")),
    d("container_quantity_ucum", "container_quantity_ucum", lambda r, c: r["container"][0]["capacity"].pop("system")),
    d("collected_not_future", "collected_not_future", lambda r, c: (r["collection"].update(collectedDateTime=ts(future())), r.pop("receivedTime"))),
    d("collected_not_future_rcv", "received_not_future", setv("receivedTime", lambda r, c: ts(future()))),
    d("received_after_collected", "received_after_collected", setv("receivedTime", "2019-01-01T08:00:00Z")),
    d("subject_reference_format", "subject_reference_format", setv("subject", GROUP_REF)),
    d("parent_reference_format", "parent_reference_format", setv("parent", [ext_ref("Specimen")]), risky=True, note="externe Referenz"),
    d("request_reference_format", "request_reference_format", setv("request", [ext_ref("ServiceRequest")]), risky=True, note="externe Referenz"),
    d("parent_not_self", "parent_not_self", lambda r, c: r.update(parent=[ref("Specimen", c.rid)])),
    *COMMON(),
]
DEFECTS["Consent"] = [
    d("status_required", "status_required", pop("status")),
    d("patient_required", "patient_required", pop("patient")),
    d("datetime_required", "datetime_required", pop("dateTime")),
    d("policy_required", "policy_required", pop("policy")),
    d("provision_period_required", "provision_period_required", lambda r, c: r["provision"].pop("period")),
    d("nested_provision_complete", "nested_provision_complete", lambda r, c: r["provision"]["provision"][0].pop("code")),
    d("status_valid", "status_valid", setv("status", "aktiv"), risky=True),
    d("scope_research", "scope_research", setv("scope", cc("http://terminology.hl7.org/CodeSystem/consentscope", "patient-privacy"))),
    d("category_loinc", "category_loinc", setv("category", [cc("http://terminology.hl7.org/CodeSystem/consentcategorycodes", "research")])),
    d("provision_codes_mii", "provision_codes_mii", lambda r, c: r["provision"]["provision"][0].update(code=[cc(LOCAL, "MDAT", "Medizinische Daten")])),
    d("provision_type_valid", "provision_type_valid", lambda r, c: r["provision"].update(type="erlauben"), risky=True),
    d("datetime_not_future", "datetime_not_future", setv("dateTime", lambda r, c: ts(future()))),
    d("provision_period_end_after_start", "provision_period_end_after_start", lambda r, c: r["provision"]["period"].update(end="2019-01-01")),
    d("nested_period_end_after_start", "nested_period_end_after_start", lambda r, c: r["provision"]["provision"][0]["period"].update(end="2019-01-01")),
    d("patient_reference_format", "patient_reference_format", setv("patient", ext_ref("Patient")), risky=True, note="externe Referenz"),
    d("meta_profile_mii", "meta_profile_mii", lambda r, c: no_profile(r)),
]
DEFECTS["ImagingStudy"] = [
    d("status_required", "status_required", pop("status")),
    d("subject_required", "subject_required", pop("subject")),
    d("started_required", "started_required", pop("started")),
    d("study_uid_required", "study_uid_required", pop("identifier")),
    d("series_uid_required", "series_uid_required", lambda r, c: r["series"][0].pop("uid")),
    d("series_modality_required", "series_modality_required", lambda r, c: r["series"][0].pop("modality")),
    d("instance_uid_required", "instance_uid_required", lambda r, c: r["series"][0]["instance"][0].pop("sopClass")),
    d("status_valid", "status_valid", setv("status", "verfuegbar"), risky=True),
    d("modality_dicom", "modality_dicom", setv("modality", [{"system": LOCAL, "code": "CT"}])),
    d("started_not_future", "started_not_future", setv("started", lambda r, c: ts(future()))),
    d("number_of_series_consistent", "number_of_series_consistent", setv("numberOfSeries", 3)),
    d("number_of_instances_consistent", "number_of_instances_consistent", setv("numberOfInstances", 7)),
    d("subject_reference_format", "subject_reference_format", setv("subject", GROUP_REF)),
    d("encounter_reference_format", "encounter_reference_format", setv("encounter", ext_ref("Encounter")), risky=True, note="externe Referenz"),
    d("basedon_reference_format", "basedon_reference_format", setv("basedOn", [ext_ref("ServiceRequest")]), risky=True, note="externe Referenz"),
    *COMMON(),
]

# Fehler, die eine Pflichtangabe der FHIR-R4-Basis (1..1) verletzen. HAPI speichert
# solche Ressourcen standardmäßig, andere Server können sie ablehnen. Diese Fälle
# findet auch ein Profilvalidator.
BASE_VIOLATIONS = {
    "Patient": {"birthdate_format"},
    "Encounter": {"status_required", "class_required"},
    "Condition": {"subject_required"},
    "Observation": {"status_required", "code_required", "component_code_required"},
    "Medication": {"ingredient_item_check"},
    "MedicationRequest": {"status_required", "intent_required", "medication_required", "subject_required"},
    "MedicationAdministration": {"status_required", "medication_required", "subject_required", "effective_required"},
    "MedicationStatement": {"status_required", "medication_required", "subject_required"},
    "Procedure": {"status_required", "subject_required"},
    "DiagnosticReport": {"status_required", "code_required"},
    "ServiceRequest": {"status_required", "intent_required", "subject_required"},
    "Consent": {"status_required"},
    "ImagingStudy": {"status_required", "subject_required", "series_uid_required", "series_modality_required", "instance_uid_required"},
}

# Regeln, die der Generator bewusst nicht abdeckt
NOT_COVERED = {
    "Patient.has_observation": "jeder Patient hat Observations",
    "Patient.has_condition": "jeder Patient hat Conditions",
    "Patient.birthdate_precision": "saubere Patienten haben ein vollständiges Geburtsdatum; Regel für diesen Datensatz ausschalten",
}


# ---------------------------------------------------------------------------
# Saubere Ressourcen eines Patienten
# ---------------------------------------------------------------------------

class Builder:
    def __init__(self, rng: random.Random, error_rate: float, risky: bool, base_violations: bool):
        self.rng = rng
        self.error_rate = error_rate
        self.cycles: Counter = Counter()
        self.defects = {
            t: [x for x in ds if (risky or not x.risky) and (base_violations or x.key not in BASE_VIOLATIONS.get(t, ()))]
            for t, ds in DEFECTS.items()
        }
        self.manifest: list[dict] = []

    # -- Fehlerauswahl --------------------------------------------------------

    def pick(self, rtype: str) -> Defect | None:
        pool = self.defects[rtype]
        if not pool or self.rng.random() >= self.error_rate:
            return None
        defect = pool[self.cycles[rtype] % len(pool)]
        self.cycles[rtype] += 1
        return defect

    def finish(self, r: dict, defect: Defect | None) -> dict:
        if defect:
            defect.apply(r, Ctx(self.rng, r["id"]))
        self.manifest.append({
            "resourceType": r["resourceType"],
            "id": r["id"],
            "defect": defect.key if defect else "",
            "expected_rules": ";".join(defect.rules) if defect else "",
            "risky": "ja" if defect and defect.risky else "",
            "fhir_basis_verletzt": "ja" if defect and (defect.risky or defect.key in BASE_VIOLATIONS.get(r["resourceType"], ())) else "",
            "note": defect.note if defect else "",
        })
        return r

    # -- Zeit -----------------------------------------------------------------

    def when(self, start: datetime, max_days: int) -> datetime:
        return start + timedelta(days=self.rng.randint(0, max_days), minutes=self.rng.randint(0, 600))

    def uid(self) -> str:
        return f"2.25.{self.rng.getrandbits(100)}"

    # -- ein Patient ----------------------------------------------------------

    def patient_bundle(self, n: int) -> list[dict]:
        rng = self.rng
        out: list[dict] = []

        p_defect = self.pick("Patient")
        pid = f"20{n:07d}" if p_defect and p_defect.key == "pseudonym_format_check" else f"vf-pat-{n:06d}"
        birth = date(rng.randint(1935, 2005), rng.randint(1, 12), rng.randint(1, 28))
        patient = base("Patient", pid)
        patient.update({
            "identifier": [{
                "type": cc("http://terminology.hl7.org/CodeSystem/v3-ObservationValue", "PSEUDED", "pseudonymized"),
                "system": f"{MII}/sid/pseudonym",
                "value": f"PSN-{rng.getrandbits(40):010x}",
            }],
            "gender": rng.choice(["female", "male"]),
            "birthDate": birth.isoformat(),
            "address": [{"type": "both", "postalCode": rng.choice(["35390", "35392", "35394", "35396", "35398"]), "country": "DE"}],
            "managingOrganization": ref("Organization", ORG_ID),
        })
        out.append(self.finish(patient, p_defect))
        P = ref("Patient", pid)

        # Zeitachse: stationärer Fall e0, später ambulanter Fall e1
        s0 = datetime(2021, 1, 1, 8, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 1700), minutes=rng.randint(0, 600))
        e0_start, e0_end = s0, s0 + timedelta(days=rng.randint(1, 10), hours=rng.randint(1, 8))
        e1_start = e0_end + timedelta(days=rng.randint(30, 150))
        e1_end = e1_start + timedelta(hours=rng.randint(1, 4))
        periods = [(e0_start, e0_end), (e1_start, e1_end)]

        # Medication (2)
        meds = []
        for k in range(2):
            atc, name, pzn, ask = rng.choice(DRUGS)
            mid = f"vf-med-{n:06d}-{k}"
            m = base("Medication", mid)
            m.update({
                "status": "active",
                "code": {"coding": [
                    {"system": ATC, "version": "2025", "code": atc, "display": name},
                    {"system": PZN, "code": pzn, "display": f"{name} 500 mg"},
                ]},
                "form": cc(EDQM, "10219000", "Tablet"),
                "ingredient": [{
                    "itemCodeableConcept": cc(ASK, ask, name),
                    "isActive": True,
                    "strength": {"numerator": qty(500, "mg"), "denominator": qty(1, "1")},
                }],
            })
            out.append(self.finish(m, self.pick("Medication")))
            meds.append(mid)

        # Condition (3): c0, c1 zum stationären Fall, c2 zum ambulanten
        conds = []
        for k in range(3):
            code, disp = rng.choice(ICD)
            onset = periods[0 if k < 2 else 1][0] - timedelta(days=rng.randint(0, 20))
            cid = f"vf-cond-{n:06d}-{k}"
            c = base("Condition", cid)
            c.update({
                "clinicalStatus": cc("http://terminology.hl7.org/CodeSystem/condition-clinical", "active"),
                "verificationStatus": cc("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed"),
                "code": cc(ICD10GM, code, disp, "2025"),
                "bodySite": [cc(SNOMED, "368209003", "Right upper arm structure")],
                "subject": P,
                "onsetDateTime": ts(onset),
                "recordedDate": ts(periods[0 if k < 2 else 1][0] + timedelta(hours=2)),
            })
            out.append(self.finish(c, self.pick("Condition")))
            conds.append(cid)

        # Encounter (2)
        encs = []
        for k, (start, end) in enumerate(periods):
            fa, fa_name = rng.choice(FACHABTEILUNG)
            eid = f"vf-enc-{n:06d}-{k}"
            e = base("Encounter", eid)
            e.update({
                "identifier": [{"type": cc(V2_0203, "VN"), "system": "https://diz.example/fhir/sid/aufnahmenummer", "value": f"A-{n:06d}-{k}"}],
                "status": "finished",
                "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "IMP" if k == 0 else "AMB"},
                "type": [cc("http://fhir.de/CodeSystem/Kontaktebene", "einrichtungskontakt", "Einrichtungskontakt")],
                "serviceType": cc("http://fhir.de/CodeSystem/dkgev/Fachabteilungsschluessel", fa, fa_name),
                "subject": P,
                "period": {"start": ts(start), "end": ts(end)},
                "diagnosis": [
                    {"condition": ref("Condition", cid), "use": cc("http://terminology.hl7.org/CodeSystem/diagnosis-role", "AD" if j == 0 else "CM")}
                    for j, cid in enumerate(conds[:2] if k == 0 else conds[2:])
                ],
                "serviceProvider": ref("Organization", ORG_ID),
            })
            if k == 0:
                e["hospitalization"] = {"admitSource": cc("http://fhir.de/CodeSystem/dgkev/Aufnahmeanlass", "E", "Einweisung durch einen Arzt")}
            out.append(self.finish(e, self.pick("Encounter")))
            encs.append(eid)

        # ServiceRequest (2), Specimen (2)
        srs, sps = [], []
        for k in range(2):
            start = periods[k][0]
            sid = f"vf-sr-{n:06d}-{k}"
            sr = base("ServiceRequest", sid)
            sr.update({
                "identifier": [{"type": cc(V2_0203, "PLAC"), "system": "https://diz.example/fhir/sid/auftrag", "value": f"O-{n:06d}-{k}"}],
                "status": "completed",
                "intent": "order",
                "category": [cc(OBS_CAT, "laboratory")],
                "code": cc(LOINC, "58410-2", "CBC panel - Blood by Automated count"),
                "subject": P,
                "encounter": ref("Encounter", encs[k]),
                "authoredOn": ts(start + timedelta(hours=1)),
            })
            out.append(self.finish(sr, self.pick("ServiceRequest")))
            srs.append(sid)

            spid = f"vf-spec-{n:06d}-{k}"
            sp = base("Specimen", spid)
            collected = start + timedelta(hours=2)
            sp.update({
                "identifier": [{"type": cc(V2_0203, "ACSN"), "system": "https://diz.example/fhir/sid/probe", "value": f"S-{n:06d}-{k}"}],
                "status": "available",
                "type": cc(SNOMED, "119297000", "Blood specimen"),
                "subject": P,
                "receivedTime": ts(collected + timedelta(hours=1)),
                "request": [ref("ServiceRequest", sid)],
                "collection": {
                    "collectedDateTime": ts(collected),
                    "quantity": qty(5, "mL"),
                    "bodySite": cc(SNOMED, "368209003", "Right upper arm structure"),
                },
                "processing": [{"procedure": cc(SNOMED, "9265001", "Specimen processing")}],
                "container": [{"type": cc(SNOMED, "706053007", "General specimen container"),
                               "capacity": qty(10, "mL"), "specimenQuantity": qty(5, "mL")}],
            })
            out.append(self.finish(sp, self.pick("Specimen")))
            sps.append(spid)

        # Observation (3): zwei zum ersten Fall, eine zum zweiten
        obs = []
        for k in range(3):
            fall = 0 if k < 2 else 1
            code, disp, unit, low, high = rng.choice(LAB)
            eff = periods[fall][0] + timedelta(hours=2)
            oid = f"vf-obs-{n:06d}-{k}"
            o = base("Observation", oid)
            o.update({
                "identifier": [{"type": cc(V2_0203, "OBI"), "system": "https://diz.example/fhir/sid/befund", "value": f"B-{n:06d}-{k}"}],
                "status": "final",
                "category": [{"coding": [{"system": OBS_CAT, "code": "laboratory"}, {"system": LOINC, "code": "26436-6"}]}],
                "code": cc(LOINC, code, disp),
                "subject": P,
                "encounter": ref("Encounter", encs[fall]),
                "effectiveDateTime": ts(eff),
                "issued": instant(eff + timedelta(hours=3)),
                "valueQuantity": qty(round(rng.uniform(low * 0.8, high * 1.2), 1), unit),
                "referenceRange": [{"low": qty(low, unit), "high": qty(high, unit)}],
                "specimen": ref("Specimen", sps[fall]),
            })
            out.append(self.finish(o, self.pick("Observation")))
            obs.append(oid)

        # DiagnosticReport (2)
        for k in range(2):
            eff = periods[k][0] + timedelta(hours=2)
            did = f"vf-dr-{n:06d}-{k}"
            dr = base("DiagnosticReport", did)
            dr.update({
                "identifier": [{"type": cc(V2_0203, "FILL"), "system": "https://diz.example/fhir/sid/laborbefund", "value": f"L-{n:06d}-{k}"}],
                "basedOn": [ref("ServiceRequest", srs[k])],
                "status": "final",
                "category": [{"coding": [{"system": LOINC, "code": "26436-6"}, {"system": V2_0074, "code": "LAB"}]}],
                "code": cc(LOINC, "11502-2", "Laboratory report"),
                "subject": P,
                "encounter": ref("Encounter", encs[k]),
                "effectiveDateTime": ts(eff),
                "issued": instant(eff + timedelta(hours=4)),
                "result": [ref("Observation", x) for x in (obs[:2] if k == 0 else obs[2:])],
            })
            out.append(self.finish(dr, self.pick("DiagnosticReport")))

        # Procedure (2)
        for k in range(2):
            code, disp = rng.choice(OPS_CODES)
            prid = f"vf-proc-{n:06d}-{k}"
            pr = base("Procedure", prid)
            pr.update({
                "status": "completed",
                "category": cc(SNOMED, "387713003", "Surgical procedure"),
                "code": cc(OPS, code, disp, "2025"),
                "subject": P,
                "encounter": ref("Encounter", encs[k]),
                "performedDateTime": ts(periods[k][0] + timedelta(hours=5)),
                "bodySite": [cc(SNOMED, "818983003", "Abdomen")],
            })
            out.append(self.finish(pr, self.pick("Procedure")))

        # MedicationRequest, -Administration, -Statement (je 2)
        mreqs = []
        for k in range(2):
            start = periods[k][0]
            mrid = f"vf-mreq-{n:06d}-{k}"
            mr = base("MedicationRequest", mrid)
            mr.update({
                "status": "completed",
                "intent": "order",
                "medicationReference": ref("Medication", meds[k]),
                "subject": P,
                "encounter": ref("Encounter", encs[k]),
                "authoredOn": ts(start + timedelta(hours=1)),
                "dosageInstruction": [{
                    "text": "1-0-1",
                    "timing": {"repeat": {"boundsPeriod": {"start": ts(start + timedelta(hours=2)), "end": ts(start + timedelta(days=3))},
                                          "frequency": 2, "period": 1, "periodUnit": "d"}},
                    "doseAndRate": [{"doseQuantity": qty(1, "1")}],
                }],
            })
            out.append(self.finish(mr, self.pick("MedicationRequest")))
            mreqs.append(mrid)
        for k in range(2):
            start = periods[k][0]
            maid = f"vf-madm-{n:06d}-{k}"
            ma = base("MedicationAdministration", maid)
            ma.update({
                "status": "completed",
                "medicationReference": ref("Medication", meds[k]),
                "subject": P,
                "context": ref("Encounter", encs[k]),
                "effectiveDateTime": ts(start + timedelta(hours=3)),
                "request": ref("MedicationRequest", mreqs[k]),
                "dosage": {"text": "1 Tablette", "dose": qty(1, "1")},
            })
            out.append(self.finish(ma, self.pick("MedicationAdministration")))
        for k in range(2):
            start, end = periods[k]
            msid = f"vf-mstat-{n:06d}-{k}"
            ms = base("MedicationStatement", msid)
            ms.update({
                "status": "completed",
                "medicationReference": ref("Medication", meds[k]),
                "subject": P,
                "context": ref("Encounter", encs[k]),
                "effectivePeriod": {"start": ts(start), "end": ts(end)},
                "dateAsserted": ts(start + timedelta(hours=1)),
                "dosage": [{"text": "1-0-1", "doseAndRate": [{"doseQuantity": qty(1, "1")}]}],
            })
            out.append(self.finish(ms, self.pick("MedicationStatement")))

        # Consent (2)
        for k in range(2):
            signed = periods[0][0] - timedelta(days=1 + k * 30)
            csid = f"vf-cons-{n:06d}-{k}"
            cs = base("Consent", csid)
            p_start, p_end = signed.date(), (signed + timedelta(days=5 * 365)).date()
            cs.update({
                "status": "active",
                "scope": cc("http://terminology.hl7.org/CodeSystem/consentscope", "research"),
                "category": [cc(LOINC, "57016-8", "Privacy policy acknowledgment Document")],
                "patient": P,
                "dateTime": ts(signed),
                "policy": [{"uri": "urn:oid:2.16.840.1.113883.3.1937.777.24.2.1791"}],
                "provision": {
                    "type": "deny",
                    "period": {"start": p_start.isoformat(), "end": p_end.isoformat()},
                    "provision": [{
                        "type": "permit",
                        "period": {"start": p_start.isoformat(), "end": p_end.isoformat()},
                        "code": [cc("urn:oid:2.16.840.1.113883.3.1937.777.24.5.3", "2.16.840.1.113883.3.1937.777.24.5.3.8")],
                    }],
                },
            })
            out.append(self.finish(cs, self.pick("Consent")))

        # ImagingStudy (2)
        for k in range(2):
            started = periods[k][0] + timedelta(hours=4)
            modality = rng.choice([("CT", "1.2.840.10008.5.1.4.1.1.2"), ("MR", "1.2.840.10008.5.1.4.1.1.4")])
            imid = f"vf-img-{n:06d}-{k}"
            im = base("ImagingStudy", imid)
            im.update({
                "identifier": [{"system": "urn:dicom:uid", "value": f"urn:oid:{self.uid()}"}],
                "status": "available",
                "modality": [{"system": DCM, "code": modality[0]}],
                "subject": P,
                "encounter": ref("Encounter", encs[k]),
                "started": ts(started),
                "basedOn": [ref("ServiceRequest", srs[k])],
                "numberOfSeries": 1,
                "numberOfInstances": 2,
                "series": [{
                    "uid": self.uid(),
                    "number": 1,
                    "modality": {"system": DCM, "code": modality[0]},
                    "numberOfInstances": 2,
                    "started": ts(started),
                    "instance": [{"uid": self.uid(), "number": j + 1,
                                  "sopClass": {"system": "urn:ietf:rfc:3986", "code": f"urn:oid:{modality[1]}"}} for j in range(2)],
                }],
            })
            out.append(self.finish(im, self.pick("ImagingStudy")))

        return out


# ---------------------------------------------------------------------------
# Transaktionen und Upload
# ---------------------------------------------------------------------------

def shared_resources() -> list[dict]:
    org = {"resourceType": "Organization", "id": ORG_ID, "meta": {"tag": [dict(TEST_TAG)]}, "name": "Testklinikum (synthetisch)"}
    grp = {"resourceType": "Group", "id": GROUP_ID, "meta": {"tag": [dict(TEST_TAG)]}, "type": "person", "actual": True,
           "name": "FHIR Verity Testgruppe"}
    return [org, grp]


def transaction(resources: list[dict]) -> dict:
    rank = {t: i for i, t in enumerate(ORDER)}
    resources = sorted(resources, key=lambda r: rank[r["resourceType"]])
    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [{"fullUrl": f"{r['resourceType']}/{r['id']}", "resource": r,
                   "request": {"method": "PUT", "url": f"{r['resourceType']}/{r['id']}"}} for r in resources],
    }


def post(base_url: str, bundle: dict, auth: str | None, timeout: int) -> None:
    body = json.dumps(bundle, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base_url.rstrip("/"), data=body, method="POST")
    req.add_header("Content-Type", "application/fhir+json; charset=utf-8")
    req.add_header("Accept", "application/fhir+json")
    req.add_header("Prefer", "return=minimal")
    if auth:
        req.add_header("Authorization", f"Basic {auth}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise SystemExit(f"\nServer lehnt Transaktion ab (HTTP {e.code}):\n{detail[:3000]}\n"
                         "Tipp: ohne --include-risky erneut versuchen, mit --no-base-violations, oder --chunk verkleinern.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", help="FHIR-Basis-URL, z. B. https://server/fhir")
    ap.add_argument("--user", help="Benutzer für Basic Auth")
    ap.add_argument("--password", help="Passwort für Basic Auth (alternativ Umgebungsvariable FHIR_PASSWORD)")
    ap.add_argument("--patients", type=int, default=1000, help="Anzahl Patienten (Standard 1000)")
    ap.add_argument("--error-rate", type=float, default=0.2, help="Anteil fehlerhafter Ressourcen je Typ (Standard 0.2)")
    ap.add_argument("--include-risky", action="store_true", help="auch Fehler einbauen, die Server beim Schreiben ablehnen können")
    ap.add_argument("--no-base-violations", action="store_true",
                    help="keine Fehler einbauen, die Pflichtangaben der FHIR-Basis verletzen (falls der Server sie ablehnt)")
    ap.add_argument("--chunk", type=int, default=20, help="Patienten je Transaktion (Standard 20)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, help="Transaktionen zusätzlich als Dateien in diesen Ordner schreiben")
    ap.add_argument("--manifest", type=Path, default=Path("verity_testdaten_manifest.csv"))
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    if not args.base_url and not args.out:
        ap.error("--base-url oder --out angeben")

    auth = None
    if args.user:
        password = args.password or os.environ.get("FHIR_PASSWORD")
        if password is None:
            ap.error("Passwort fehlt: --password oder FHIR_PASSWORD")
        auth = base64.b64encode(f"{args.user}:{password}".encode()).decode()

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    builder = Builder(random.Random(args.seed), args.error_rate, args.include_risky, not args.no_base_violations)
    total = 0
    for first in range(0, args.patients, args.chunk):
        resources = shared_resources()
        for n in range(first, min(first + args.chunk, args.patients)):
            resources += builder.patient_bundle(n)
        bundle = transaction(resources)
        total += len(resources) - 2
        if args.out:
            (args.out / f"transaction_{first // args.chunk:04d}.json").write_text(
                json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        if args.base_url:
            post(args.base_url, bundle, auth, args.timeout)
        print(f"\r{min(first + args.chunk, args.patients)}/{args.patients} Patienten, {total} Ressourcen", end="", flush=True)
    print()

    with args.manifest.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["resourceType", "id", "defect", "expected_rules", "risky", "fhir_basis_verletzt", "note"])
        w.writeheader()
        w.writerows(builder.manifest)

    per_type = Counter(m["resourceType"] for m in builder.manifest)
    bad = Counter(m["resourceType"] for m in builder.manifest if m["defect"])
    print("\nRessourcentyp              gesamt  fehlerhaft")
    for t in ORDER[2:]:
        print(f"{t:<26}{per_type[t]:>7}{bad[t]:>12}")
    print(f"\nManifest: {args.manifest.resolve()}")
    print("Nicht abgedeckt: " + "; ".join(f"{k} ({v})" for k, v in NOT_COVERED.items()))


if __name__ == "__main__":
    main()
