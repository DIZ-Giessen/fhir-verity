# Validierungsregeln

Dieses Dokument beschreibt alle Ressourcentypen, die Verity prüft, und jede einzelne Regel. Die Regeltabellen weiter unten werden aus dem Code
erzeugt und sind damit immer auf dem Stand der Prüflogik.

## Inhalt

- [Grundlagen](#grundlagen)
- [Übersicht der Ressourcentypen](#übersicht-der-ressourcentypen)
- [Auto-Fix](#auto-fix)
- [Grenzen](#grenzen)
- [Neue Regel hinzufügen](#neue-regel-hinzufügen)
- [Neuen Ressourcentyp hinzufügen](#neuen-ressourcentyp-hinzufügen)

## Grundlagen

### Wo die Regeln stehen

| Datei                                     | Inhalt                                                                        |
| ----------------------------------------- | ----------------------------------------------------------------------------- |
| `backend/app/services/rules/<typ>.py`     | alle Regeln eines Ressourcentyps, je Regel Definition und Prüflogik zusammen  |
| `backend/app/services/rules/registry.py`  | Registry: Regeln registrieren, Konfiguration zusammensetzen, Regeln ausführen |
| `backend/app/services/rules/fhir.py`      | Hilfsfunktionen und wiederkehrende Prüfungen (Pflichtfeld, Codesystem, Datum) |
| `backend/app/services/fix_templates.py`   | JSON-Patch-Vorlagen für Regeln mit Auto-Fix                                   |
| `backend/tests/fixtures/rule_examples.py` | je Typ eine gültige Ressource und je Regel ein Beispiel, das sie verletzt     |

### Aufbau einer Regel

Jede Regel ist eine Funktion, die sich mit `@R(...)` in der Registry einträgt. Definition und Prüfung stehen an derselben Stelle; eine Regel ohne
Prüflogik kann es dadurch nicht geben.

```python
R = rules_for("Encounter")

@R(
    "finished_has_end",
    category="plausibility",          # privacy | completeness | coding | plausibility | integrity
    severity="error",                 # error | warning | info
    description="A finished Encounter must have period.end (MII invariant mii-enc-1).",
)
def finished_has_end(r, ctx):
    if r.get("status") == "finished" and not (r.get("period") or {}).get("end"):
        return "Encounter is finished but has no period.end."
```

Die Funktion bekommt die Ressource und gibt `None` zurück, wenn sie besteht, sonst die Meldung. Einfache Regeln entstehen aus Bausteinen in
`fhir.py`, zum Beispiel:

```python
R("recorded_date_required", category="completeness", severity="warning",
  description="Condition.recordedDate must be present (required by MII Diagnose).",
)(required("Condition.recordedDate is missing.", "recordedDate"))
```

Weitere Felder: `enabled=True` schaltet eine Regel standardmäßig ein (Standard ist aus), `pattern=` gibt Muster-Regeln einen Startwert, und
`prepare=` erlaubt Regeln, die pro Seite zusätzliche Anfragen an den Server stellen (`Patient.has_observation`).

Der Regelschlüssel (`finished_has_end`) ist die stabile Kennung. Er steht in der Datenbank (`invalid_resource_issues.rule`), in den Laufstatistiken
und in den FHIR-Reports und darf nach dem ersten produktiven Einsatz nicht mehr umbenannt werden.

### Kategorien

| Kategorie      | Bedeutung                                                                                   |
| -------------- | ------------------------------------------------------------------------------------------- |
| `privacy`      | Datenschutz und Pseudonymisierung: Klartext, Kontaktdaten, nicht pseudonymisierte Kennungen |
| `completeness` | Vollständigkeit: Pflicht- und Must-Support-Felder der MII-Profile                           |
| `coding`       | Codierung: erwartetes Codesystem, Format des Codes, Version, erlaubte Werte, UCUM-Einheiten |
| `plausibility` | Plausibilität: zeitliche und logische Stimmigkeit, FHIR- und MII-Invarianten                |
| `integrity`    | Referenzielle Integrität: Form der Verweise zwischen Ressourcen                             |

### Schweregrade

| Schwere   | Bedeutung                                                                 |
| --------- | ------------------------------------------------------------------------- |
| `error`   | Die Ressource verletzt eine harte Anforderung (Datenschutz, Pflichtfeld). |
| `warning` | Die Ressource ist auffällig und sollte geprüft werden.                    |
| `info`    | Hinweis ohne Handlungsdruck.                                              |

Eine Ressource gilt als **invalide**, sobald mindestens eine aktive Regel anschlägt, unabhängig von der Schwere. Die Schwere steuert Darstellung,
Filter und Statistik. Im FHIR-TestScript werden `warning`- und `info`-Regeln als `warningOnly` geführt.

### Welche Konfiguration gilt

Die Standardwerte jeder Regel (an/aus, Schwere, Muster) stehen im Code. Ändert jemand auf der Konfigurationsseite eines Servers eine Regel, entsteht
ein **Server-Override** in `validation_configs`. Er speichert pro Regel nur `enabled`, `severity` und `pattern`; Beschreibung und Kategorie kommen
immer aus dem Code. Neue Regeln stehen deshalb nach einem Update sofort in der Oberfläche, ohne Eingriff in die Datenbank.

Alle Regeln, die mit der Registry neu hinzugekommen sind, sind standardmäßig **aus**. Jeder Standort schaltet ein, was für seine Daten sinnvoll ist;
auf der Konfigurationsseite lassen sich Regeln suchen und ganze Kategorien auf einmal an- oder ausschalten.

### Filter

Pro Server und Ressourcentyp kann der Crawl eingeschränkt werden. Die Filter werden als FHIR-Suchparameter an den Server weitergegeben:

| Filter              | Suchparameter           |
| ------------------- | ----------------------- |
| `last_updated_from` | `_lastUpdated=ge<Wert>` |
| `last_updated_to`   | `_lastUpdated=le<Wert>` |
| `profile`           | `_profile=<Wert>`       |
| `tag`               | `_tag=<Wert>`           |

Ist ein Filter aktiv, werden nicht mehr alle Ressourcen des Typs besucht. Verity räumt dann nach dem Lauf **keine** veralteten Einträge aus
`invalid_resources` auf, weil nicht feststeht, ob eine nicht besuchte Ressource inzwischen korrigiert wurde.

### Allgemeine Prüfregeln

- **„fehlt“** heißt: Feld nicht vorhanden, `null`, leere Zeichenkette, leere Liste oder leeres Objekt.
- **Zukunftsprüfungen** vergleichen mit der aktuellen Zeit in UTC. Ein Datum ohne Zeitzone (`2026-10-07`) wird als Mitternacht UTC gelesen. Nicht
  lesbare Werte schlagen nicht an.
- **Zeiträume** (`…_end_after_start`, FHIR-Invariante per-1): Ende gleich Beginn ist erlaubt. Ein Datum und ein Zeitpunkt werden in der geringeren
  Genauigkeit verglichen, also auf Tagesebene.
- **Referenzformat** (`…_reference_format`) prüft nur die Form `Typ/id`. Ob die Zielressource existiert, wird nicht geprüft. Fehlt die Referenz
  ganz, schlägt die Formatregel nicht an; das deckt die zugehörige Pflichtregel ab. Absolute URLs, `urn:uuid:` und reine `identifier`-Verweise
  gelten als Verstoß.
- **Codesystem-Regeln** (`…_known_system`, `coded_with`) schlagen nur an, wenn das Feld vorhanden ist, aber keine Codierung aus den erwarteten
  Systemen enthält.
- **Laborregeln** (`lab_…`) gelten nur für Ressourcen, die als Labor kategorisiert sind (`observation-category#laboratory`, bei DiagnosticReport
  auch `v2-0074#LAB` oder LOINC 26436-6). Vitalstatus, Vitalzeichen und andere Observations sind davon nicht betroffen.
- **Freitext-Regeln** (`note_cleartext_check`, `value_string_cleartext_forbidden`) erkennen keine Namen, sondern schlagen bei langen Texten an. Sie
  sind ein Hinweis zum manuellen Nachsehen.
- Eine Regel meldet pro Ressource höchstens einen Befund. Ausnahme: `Encounter.pseudonym_format_check` meldet für `id` und `identifier` je einen.
- Kann eine Regel eine fehlerhaft aufgebaute Ressource nicht auswerten, gilt sie für diese Ressource als bestanden; der Lauf bricht nicht ab.

Spalten der Regeltabellen: **Std.** = standardmäßig aktiv, **Fix** = Auto-Fix verfügbar.

<!-- rules:start -->

## Übersicht der Ressourcentypen

| Ressourcentyp                                         | Profil                                                             | Regeln | Standard an |
| ----------------------------------------------------- | ------------------------------------------------------------------ | :----: | :---------: |
| [Patient](#patient)                                   | MII KDS Person (Patient, PatientPseudonymisiert)                   |   27   |     11      |
| [Encounter](#encounter)                               | MII KDS Fall (KontaktGesundheitseinrichtung)                       |   27   |      8      |
| [Condition](#condition)                               | MII KDS Diagnose (Diagnose)                                        |   22   |      4      |
| [Observation](#observation)                           | FHIR R4, Laborregeln aus MII KDS Laborbefund (ObservationLab)      |   28   |      7      |
| [Medication](#medication)                             | MII KDS Medikation (Medication)                                    |   14   |      3      |
| [MedicationRequest](#medicationrequest)               | MII KDS Medikation (MedicationRequest)                             |   20   |      7      |
| [MedicationAdministration](#medicationadministration) | MII KDS Medikation (MedicationAdministration)                      |   18   |      7      |
| [MedicationStatement](#medicationstatement)           | MII KDS Medikation (MedicationStatement)                           |   18   |      0      |
| [Procedure](#procedure)                               | MII KDS Prozedur (Procedure)                                       |   18   |      6      |
| [DiagnosticReport](#diagnosticreport)                 | FHIR R4, Laborregeln aus MII KDS Laborbefund (DiagnosticReportLab) |   24   |      5      |
| [ServiceRequest](#servicerequest)                     | FHIR R4, Laborregeln aus MII KDS Laborbefund (ServiceRequestLab)   |   20   |      0      |
| [Specimen](#specimen)                                 | MII KDS Biobank (Bioprobe)                                         |   22   |      0      |
| [Consent](#consent)                                   | MII KDS Consent (Einwilligung)                                     |   16   |      0      |
| [ImagingStudy](#imagingstudy)                         | MII KDS Bildgebung (Bildgebungsstudie)                             |   17   |      0      |

Insgesamt 291 Regeln.

## Patient

Profil: MII KDS Person (Patient, PatientPseudonymisiert)

| Regel                           | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                                                                                                                |
| ------------------------------- | ------------ | ------- | :--: | :-: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `text_forbidden`                | privacy      | info    | aus  | ja  | Patient.text (narrative) must not be present; it may contain cleartext personal data.                                                                                                |
| `name_forbidden`                | privacy      | error   |  an  | ja  | Patient.name must not be present in pseudonymized data.                                                                                                                              |
| `address_forbidden`             | privacy      | error   |  an  | ja  | The first Patient.address must not contain line, city or text; postal code and country are allowed.                                                                                  |
| `telecom_forbidden`             | privacy      | error   |  an  | ja  | Patient.telecom (phone numbers, e-mail addresses) must not be present.                                                                                                               |
| `photo_forbidden`               | privacy      | error   |  an  | ja  | Patient.photo must not be present.                                                                                                                                                   |
| `pseudonym_format_check`        | privacy      | error   |  an  |  –  | Reports a Patient.id that matches the pattern of an original, non-pseudonymized patient ID. Set the pattern to your site's original ID format. Muster: `^20[0-9]{7}$`.               |
| `identifier_pseudonym_check`    | privacy      | error   |  an  |  –  | Reports a Patient.identifier value that matches the pattern of an original, non-pseudonymized patient ID. Set the pattern to your site's original ID format. Muster: `^20[0-9]{7}$`. |
| `has_observation`               | completeness | warning | aus  |  –  | The patient must have at least one Observation on the server. Sends one extra request per patient and noticeably slows down runs.                                                    |
| `has_condition`                 | completeness | warning | aus  |  –  | The patient must have at least one Condition on the server. Sends one extra request per patient and noticeably slows down runs.                                                      |
| `identifier_required`           | completeness | error   |  an  |  –  | Patient.identifier must contain at least one identifier.                                                                                                                             |
| `birthdate_required`            | completeness | warning |  an  |  –  | Patient.birthDate must be present.                                                                                                                                                   |
| `gender_required`               | completeness | warning |  an  |  –  | Patient.gender must be present.                                                                                                                                                      |
| `birthdate_not_future`          | plausibility | error   |  an  |  –  | Patient.birthDate must not lie in the future.                                                                                                                                        |
| `birthdate_plausible_range`     | plausibility | warning |  an  |  –  | The year of Patient.birthDate must not lie more than 150 years in the past.                                                                                                          |
| `managingorganization_required` | completeness | info    | aus  |  –  | Patient.managingOrganization must be present.                                                                                                                                        |
| `contact_forbidden`             | privacy      | error   | aus  | ja  | Patient.contact (relatives, guardians) must not be present in pseudonymized data.                                                                                                    |
| `pseudonymized_identifier_type` | privacy      | warning | aus  |  –  | At least one Patient.identifier must be marked as pseudonymized (type PSEUDED from v3-ObservationValue), as required by MII PatientPseudonymisiert.                                  |
| `birthdate_precision`           | privacy      | warning | aus  |  –  | Reports a Patient.birthDate given to the day. Enable it if your pseudonymization keeps only the year or year and month.                                                              |
| `gender_valid`                  | coding       | error   | aus  |  –  | Patient.gender must be one of male, female, other, unknown.                                                                                                                          |
| `gender_other_amtlich`          | coding       | warning | aus  |  –  | Patient.gender 'other' must carry the extension gender-amtlich-de with the German administrative gender (MII invariant mii-pat-1).                                                   |
| `birthdate_format`              | plausibility | error   | aus  |  –  | Patient.birthDate must be a FHIR date (YYYY, YYYY-MM or YYYY-MM-DD).                                                                                                                 |
| `deceased_after_birth`          | plausibility | error   | aus  |  –  | Patient.deceasedDateTime must not lie before Patient.birthDate.                                                                                                                      |
| `deceased_not_future`           | plausibility | warning | aus  |  –  | Patient.deceasedDateTime must not lie in the future.                                                                                                                                 |
| `address_postalcode_required`   | completeness | warning | aus  |  –  | Every Patient.address must contain a postal code (MII address of type 'both').                                                                                                       |
| `address_country_required`      | completeness | info    | aus  |  –  | Every Patient.address must contain a country.                                                                                                                                        |
| `address_country_code`          | coding       | warning | aus  |  –  | Patient.address.country must be an ISO 3166 country code with 2 or 3 letters.                                                                                                        |
| `meta_profile_mii`              | completeness | info    | aus  |  –  | Patient.meta.profile must reference an MII core data set profile.                                                                                                                    |

## Encounter

Profil: MII KDS Fall (KontaktGesundheitseinrichtung)

| Regel                               | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                                                                                                                                 |
| ----------------------------------- | ------------ | ------- | :--: | :-: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pseudonym_format_check`            | privacy      | error   |  an  |  –  | Reports an Encounter.id or Encounter.identifier value that matches the pattern of an original, non-pseudonymized case number. Set the pattern to your site's original format. Muster: `^20[0-9]{8}$`. |
| `status_required`                   | completeness | error   |  an  |  –  | Encounter.status must be present.                                                                                                                                                                     |
| `class_required`                    | completeness | error   |  an  |  –  | Encounter.class must be present.                                                                                                                                                                      |
| `subject_required`                  | completeness | error   |  an  |  –  | Encounter.subject must be present.                                                                                                                                                                    |
| `period_start_required`             | completeness | error   |  an  |  –  | Encounter.period.start must be present.                                                                                                                                                               |
| `period_end_after_start`            | plausibility | error   |  an  |  –  | Encounter.period.end must not lie before period.start (FHIR invariant per-1). Values are compared at the precision of the less precise one.                                                           |
| `period_plausible_duration`         | plausibility | warning |  an  |  –  | An Encounter should not last longer than 730 days; very long stays usually mean the discharge was not documented.                                                                                     |
| `subject_reference_format`          | integrity    | error   |  an  |  –  | Encounter.subject.reference must have the form 'Patient/{id}'.                                                                                                                                        |
| `servicetype_required`              | completeness | info    | aus  |  –  | Encounter.serviceType (department, Fachabteilung) must be present.                                                                                                                                    |
| `diagnosis_present`                 | completeness | info    | aus  |  –  | Encounter.diagnosis must reference at least one Condition.                                                                                                                                            |
| `period_not_future`                 | plausibility | warning | aus  |  –  | Encounter.period.start must not lie more than 24 hours in the future.                                                                                                                                 |
| `text_forbidden`                    | privacy      | info    | aus  | ja  | Encounter.text (narrative) must not be present; it may contain cleartext personal data.                                                                                                               |
| `status_valid`                      | coding       | error   | aus  |  –  | Encounter.status must be a value of the FHIR EncounterStatus value set.                                                                                                                               |
| `class_coded`                       | coding       | warning | aus  |  –  | Encounter.class must carry both system and code (MII EncounterClassDE, e.g. v3-ActCode IMP, AMB).                                                                                                     |
| `kontaktebene_required`             | completeness | warning | aus  |  –  | Encounter.type must contain the contact level (Kontaktebene: einrichtungskontakt, abteilungskontakt, versorgungsstellenkontakt).                                                                      |
| `servicetype_fachabteilung`         | coding       | warning | aus  |  –  | Encounter.serviceType must be coded with the Fachabteilungsschlüssel (standard or extended).                                                                                                          |
| `aufnahmenummer_required`           | completeness | info    | aus  |  –  | Encounter.identifier must contain the admission number (Aufnahmenummer, identifier type VN).                                                                                                          |
| `finished_has_end`                  | plausibility | error   | aus  |  –  | A finished Encounter must have period.end (MII invariant mii-enc-1).                                                                                                                                  |
| `planned_without_period`            | plausibility | warning | aus  |  –  | A planned Encounter must not have a period (MII invariant mii-enc-3).                                                                                                                                 |
| `ongoing_has_start`                 | plausibility | error   | aus  |  –  | An Encounter that is in progress, on leave or unknown must have period.start (MII invariants mii-enc-5 to mii-enc-7).                                                                                 |
| `diagnosis_use_required`            | completeness | warning | aus  |  –  | Every Encounter.diagnosis must state its use (Diagnosetyp).                                                                                                                                           |
| `diagnosis_reference_format`        | integrity    | error   | aus  |  –  | Encounter.diagnosis.condition.reference must have the form 'Condition/{id}'.                                                                                                                          |
| `partof_reference_format`           | integrity    | error   | aus  |  –  | Encounter.partOf.reference must have the form 'Encounter/{id}'.                                                                                                                                       |
| `location_reference_format`         | integrity    | warning | aus  |  –  | Encounter.location.location.reference must have the form 'Location/{id}'.                                                                                                                             |
| `service_provider_reference_format` | integrity    | warning | aus  |  –  | Encounter.serviceProvider.reference must have the form 'Organization/{id}'.                                                                                                                           |
| `admit_source_required`             | completeness | info    | aus  |  –  | If Encounter.hospitalization is present, it must contain admitSource (Aufnahmeanlass).                                                                                                                |
| `meta_profile_mii`                  | completeness | info    | aus  |  –  | Encounter.meta.profile must reference an MII core data set profile.                                                                                                                                   |

## Condition

Profil: MII KDS Diagnose (Diagnose)

| Regel                                     | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                                                                                                      |
| ----------------------------------------- | ------------ | ------- | :--: | :-: | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `note_cleartext_check`                    | privacy      | warning |  an  |  –  | Condition.note.text must not be longer than 50 characters; long free text may contain personal data.                                                                       |
| `code_required`                           | completeness | error   |  an  |  –  | Condition.code must be present.                                                                                                                                            |
| `subject_required`                        | completeness | error   |  an  |  –  | Condition.subject must be present.                                                                                                                                         |
| `clinicalstatus_required`                 | completeness | warning | aus  |  –  | Condition.clinicalStatus must be present.                                                                                                                                  |
| `verificationstatus_required`             | completeness | info    | aus  |  –  | Condition.verificationStatus must be present.                                                                                                                              |
| `onset_present`                           | completeness | info    | aus  |  –  | Condition.onset[x] must be present.                                                                                                                                        |
| `subject_reference_format`                | integrity    | error   |  an  |  –  | Condition.subject.reference must have the form 'Patient/{id}'.                                                                                                             |
| `text_forbidden`                          | privacy      | info    | aus  | ja  | Condition.text (narrative) must not be present; it may contain cleartext personal data.                                                                                    |
| `recorded_date_required`                  | completeness | warning | aus  |  –  | Condition.recordedDate must be present (required by MII Diagnose).                                                                                                         |
| `recorded_date_not_future`                | plausibility | warning | aus  |  –  | Condition.recordedDate must not lie in the future.                                                                                                                         |
| `onset_not_future`                        | plausibility | warning | aus  |  –  | Condition.onsetDateTime and onsetPeriod.start must not lie in the future.                                                                                                  |
| `abatement_after_onset`                   | plausibility | error   | aus  |  –  | Condition.abatementDateTime must not lie before onsetDateTime.                                                                                                             |
| `code_coding_known_system`                | coding       | warning | aus  |  –  | Condition.code must contain a coding from ICD-10-GM, Alpha-ID, SNOMED CT or Orphanet (MII Diagnose).                                                                       |
| `icd10gm_version_required`                | coding       | error   | aus  |  –  | An ICD-10-GM coding in Condition.code must state the catalogue version (coding.version).                                                                                   |
| `icd10gm_code_format`                     | coding       | error   | aus  |  –  | An ICD-10-GM code must match the format of the German base profile, e.g. I10 or S72.01; markers such as +, \* or ! belong in the Mehrfachcodierungs-Kennzeichen extension. |
| `clinicalstatus_valid`                    | coding       | error   | aus  |  –  | Condition.clinicalStatus must be coded with the FHIR condition-clinical code system.                                                                                       |
| `verificationstatus_valid`                | coding       | error   | aus  |  –  | Condition.verificationStatus must be coded with the FHIR condition-ver-status code system.                                                                                 |
| `abatement_clinicalstatus`                | plausibility | warning | aus  |  –  | If Condition.abatement[x] is present, clinicalStatus must be inactive, resolved or remission (FHIR invariant con-4).                                                       |
| `entered_in_error_without_clinicalstatus` | plausibility | warning | aus  |  –  | A Condition with verificationStatus entered-in-error must not have a clinicalStatus (FHIR invariant con-5).                                                                |
| `bodysite_snomed`                         | coding       | info    | aus  |  –  | Condition.bodySite must be coded with SNOMED CT (MII Diagnose).                                                                                                            |
| `encounter_reference_format`              | integrity    | error   | aus  |  –  | Condition.encounter.reference must have the form 'Encounter/{id}'.                                                                                                         |
| `meta_profile_mii`                        | completeness | info    | aus  |  –  | Condition.meta.profile must reference an MII core data set profile.                                                                                                        |

## Observation

Profil: FHIR R4, Laborregeln aus MII KDS Laborbefund (ObservationLab)

| Regel                              | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                                                                                             |
| ---------------------------------- | ------------ | ------- | :--: | :-: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `value_string_cleartext_forbidden` | privacy      | error   | aus  | ja  | Observation.valueString must not be longer than 50 characters; long free text may contain personal data. Results belong in valueQuantity or valueCodeableConcept. |
| `status_required`                  | completeness | error   |  an  |  –  | Observation.status must be present.                                                                                                                               |
| `code_required`                    | completeness | error   |  an  |  –  | Observation.code must be present.                                                                                                                                 |
| `subject_required`                 | completeness | error   |  an  |  –  | Observation.subject must be present.                                                                                                                              |
| `effective_required`               | completeness | warning |  an  |  –  | Observation.effective[x] (dateTime, Period or instant) must be present.                                                                                           |
| `value_present`                    | completeness | warning |  an  |  –  | Observation must have a value[x] or a dataAbsentReason.                                                                                                           |
| `effective_not_future`             | plausibility | warning |  an  |  –  | Observation.effectiveDateTime or effectiveInstant must not lie in the future.                                                                                     |
| `subject_reference_format`         | integrity    | error   |  an  |  –  | Observation.subject.reference must have the form 'Patient/{id}'.                                                                                                  |
| `note_cleartext_check`             | privacy      | warning | aus  |  –  | Observation.note.text must not be longer than 50 characters; long free text may contain personal data.                                                            |
| `text_forbidden`                   | privacy      | info    | aus  | ja  | Observation.text (narrative) must not be present; it may contain cleartext personal data.                                                                         |
| `status_valid`                     | coding       | error   | aus  |  –  | Observation.status must be a value of the FHIR ObservationStatus value set.                                                                                       |
| `category_required`                | completeness | warning | aus  |  –  | Observation.category must be present.                                                                                                                             |
| `code_coding_complete`             | coding       | warning | aus  |  –  | Every Observation.code.coding must carry both system and code.                                                                                                    |
| `encounter_reference_format`       | integrity    | error   | aus  |  –  | Observation.encounter.reference must have the form 'Encounter/{id}'.                                                                                              |
| `specimen_reference_format`        | integrity    | warning | aus  |  –  | Observation.specimen.reference must have the form 'Specimen/{id}'.                                                                                                |
| `effective_period_end_after_start` | plausibility | error   | aus  |  –  | Observation.effectivePeriod.end must not lie before start (FHIR invariant per-1).                                                                                 |
| `issued_not_future`                | plausibility | warning | aus  |  –  | Observation.issued must not lie in the future.                                                                                                                    |
| `issued_after_effective`           | plausibility | warning | aus  |  –  | Observation.issued must not lie before effectiveDateTime; a result cannot be released before it was taken.                                                        |
| `value_absent_exclusive`           | plausibility | error   | aus  |  –  | Observation.dataAbsentReason must only be present if value[x] is absent (FHIR invariant obs-6).                                                                   |
| `value_quantity_ucum`              | coding       | warning | aus  |  –  | Observation.valueQuantity must use a UCUM unit (system http://unitsofmeasure.org with code).                                                                      |
| `value_quantity_value`             | completeness | warning | aus  |  –  | Observation.valueQuantity must contain a numeric value.                                                                                                           |
| `reference_range_order`            | plausibility | warning | aus  |  –  | Observation.referenceRange.low must not be greater than referenceRange.high.                                                                                      |
| `component_code_required`          | completeness | error   | aus  |  –  | Every Observation.component must have a code.                                                                                                                     |
| `lab_category_coding`              | coding       | warning | aus  |  –  | A laboratory Observation must be categorized with both observation-category 'laboratory' and LOINC 26436-6 (MII ObservationLab).                                  |
| `lab_code_loinc`                   | coding       | warning | aus  |  –  | A laboratory Observation.code must contain a LOINC coding (MII ObservationLab).                                                                                   |
| `lab_identifier_required`          | completeness | info    | aus  |  –  | A laboratory Observation must have an identifier (MII ObservationLab).                                                                                            |
| `lab_effective_precision`          | plausibility | info    | aus  |  –  | A laboratory Observation.effectiveDateTime must be precise to at least the day (MII invariant mii-lab-1).                                                         |
| `meta_profile_mii`                 | completeness | info    | aus  |  –  | Observation.meta.profile must reference an MII core data set profile.                                                                                             |

## Medication

Profil: MII KDS Medikation (Medication)

| Regel                            | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                     |
| -------------------------------- | ------------ | ------- | :--: | :-: | ----------------------------------------------------------------------------------------- |
| `code_required`                  | completeness | error   |  an  |  –  | Medication.code must be present with a coding or a text.                                  |
| `code_coding_present`            | completeness | warning |  an  |  –  | Medication.code must contain a coding; a text alone cannot be analysed.                   |
| `ingredient_item_check`          | plausibility | warning |  an  |  –  | Every Medication.ingredient must have item[x] (itemCodeableConcept or itemReference).     |
| `text_forbidden`                 | privacy      | info    | aus  | ja  | Medication.text (narrative) must not be present; it may contain cleartext personal data.  |
| `status_valid`                   | coding       | error   | aus  |  –  | Medication.status must be active, inactive or entered-in-error.                           |
| `code_coding_known_system`       | coding       | warning | aus  |  –  | Medication.code must contain a PZN or ATC coding (MII Medikation).                        |
| `atc_version_required`           | coding       | warning | aus  |  –  | An ATC coding in Medication.code must state the version (MII Medikation).                 |
| `atc_code_format`                | coding       | error   | aus  |  –  | An ATC code in Medication.code must be a valid ATC code (e.g. N02BE01).                   |
| `pzn_code_format`                | coding       | error   | aus  |  –  | A PZN in Medication.code must have 8 digits.                                              |
| `ingredient_required`            | completeness | warning | aus  |  –  | Medication.ingredient must be present (required by MII Medikation).                       |
| `ingredient_coding_known_system` | coding       | info    | aus  |  –  | Medication.ingredient.itemCodeableConcept must be coded with ASK, UNII, CAS or SNOMED CT. |
| `ingredient_strength_ucum`       | coding       | warning | aus  |  –  | Medication.ingredient.strength must use UCUM units in numerator and denominator.          |
| `form_edqm`                      | coding       | info    | aus  |  –  | Medication.form must be coded with EDQM Standard Terms.                                   |
| `meta_profile_mii`               | completeness | info    | aus  |  –  | Medication.meta.profile must reference an MII core data set profile.                      |

## MedicationRequest

Profil: MII KDS Medikation (MedicationRequest)

| Regel                            | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                                                                   |
| -------------------------------- | ------------ | ------- | :--: | :-: | --------------------------------------------------------------------------------------------------------------------------------------- |
| `status_required`                | completeness | error   |  an  |  –  | MedicationRequest.status must be present.                                                                                               |
| `intent_required`                | completeness | error   |  an  |  –  | MedicationRequest.intent must be present.                                                                                               |
| `medication_required`            | completeness | error   |  an  |  –  | MedicationRequest.medication[x] (medicationReference or medicationCodeableConcept) must be present.                                     |
| `subject_required`               | completeness | error   |  an  |  –  | MedicationRequest.subject must be present.                                                                                              |
| `authored_on_required`           | completeness | warning |  an  |  –  | MedicationRequest.authoredOn must be present; a boundsPeriod in dosageInstruction.timing is accepted instead.                           |
| `authored_not_future`            | plausibility | warning |  an  |  –  | MedicationRequest.authoredOn must not lie in the future.                                                                                |
| `subject_reference_format`       | integrity    | error   |  an  |  –  | MedicationRequest.subject.reference must have the form 'Patient/{id}'.                                                                  |
| `note_cleartext_check`           | privacy      | warning | aus  |  –  | MedicationRequest.note.text and dosageInstruction.text must not be longer than 50 characters; long free text may contain personal data. |
| `text_forbidden`                 | privacy      | info    | aus  | ja  | MedicationRequest.text (narrative) must not be present; it may contain cleartext personal data.                                         |
| `status_valid`                   | coding       | error   | aus  |  –  | MedicationRequest.status must be a value of the FHIR medicationrequest-status value set.                                                |
| `intent_valid`                   | coding       | error   | aus  |  –  | MedicationRequest.intent must be a value of the FHIR medicationrequest-intent value set.                                                |
| `medication_coding_known_system` | coding       | warning | aus  |  –  | MedicationRequest.medicationCodeableConcept must contain a PZN or ATC coding.                                                           |
| `atc_code_format`                | coding       | error   | aus  |  –  | An ATC code in medicationCodeableConcept must be a valid ATC code.                                                                      |
| `pzn_code_format`                | coding       | error   | aus  |  –  | A PZN in medicationCodeableConcept must have 8 digits.                                                                                  |
| `medication_reference_format`    | integrity    | error   | aus  |  –  | MedicationRequest.medicationReference.reference must have the form 'Medication/{id}'.                                                   |
| `encounter_reference_format`     | integrity    | error   | aus  |  –  | MedicationRequest.encounter.reference must have the form 'Encounter/{id}'.                                                              |
| `dosage_text_or_structured`      | completeness | warning | aus  |  –  | Every MedicationRequest.dosageInstruction must have text or doseAndRate (MII DosageDE, dsg-1).                                          |
| `bounds_period_end_after_start`  | plausibility | error   | aus  |  –  | dosageInstruction.timing.repeat.boundsPeriod.end must not lie before start (FHIR invariant per-1).                                      |
| `do_not_perform_forbidden`       | plausibility | warning | aus  | ja  | MedicationRequest.doNotPerform must not be used (excluded by MII Medikation).                                                           |
| `meta_profile_mii`               | completeness | info    | aus  |  –  | MedicationRequest.meta.profile must reference an MII core data set profile.                                                             |

## MedicationAdministration

Profil: MII KDS Medikation (MedicationAdministration)

| Regel                              | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                                                               |
| ---------------------------------- | ------------ | ------- | :--: | :-: | ----------------------------------------------------------------------------------------------------------------------------------- |
| `status_required`                  | completeness | error   |  an  |  –  | MedicationAdministration.status must be present.                                                                                    |
| `medication_required`              | completeness | error   |  an  |  –  | MedicationAdministration.medication[x] (medicationReference or medicationCodeableConcept) must be present.                          |
| `subject_required`                 | completeness | error   |  an  |  –  | MedicationAdministration.subject must be present.                                                                                   |
| `effective_required`               | completeness | error   |  an  |  –  | MedicationAdministration.effective[x] (effectiveDateTime or effectivePeriod) must be present.                                       |
| `effective_not_future`             | plausibility | warning |  an  |  –  | MedicationAdministration.effectiveDateTime must not lie in the future.                                                              |
| `effective_period_end_after_start` | plausibility | error   |  an  |  –  | MedicationAdministration.effectivePeriod.end must not lie before start (FHIR invariant per-1).                                      |
| `subject_reference_format`         | integrity    | error   |  an  |  –  | MedicationAdministration.subject.reference must have the form 'Patient/{id}'.                                                       |
| `note_cleartext_check`             | privacy      | warning | aus  |  –  | MedicationAdministration.note.text and dosage.text must not be longer than 50 characters; long free text may contain personal data. |
| `text_forbidden`                   | privacy      | info    | aus  | ja  | MedicationAdministration.text (narrative) must not be present; it may contain cleartext personal data.                              |
| `status_valid`                     | coding       | error   | aus  |  –  | MedicationAdministration.status must be a value of the FHIR medication-admin-status value set.                                      |
| `medication_coding_known_system`   | coding       | warning | aus  |  –  | MedicationAdministration.medicationCodeableConcept must contain a PZN or ATC coding.                                                |
| `atc_code_format`                  | coding       | error   | aus  |  –  | An ATC code in medicationCodeableConcept must be a valid ATC code.                                                                  |
| `pzn_code_format`                  | coding       | error   | aus  |  –  | A PZN in medicationCodeableConcept must have 8 digits.                                                                              |
| `dose_ucum`                        | coding       | warning | aus  |  –  | MedicationAdministration.dosage.dose must use a UCUM unit (required by MII Medikation).                                             |
| `medication_reference_format`      | integrity    | error   | aus  |  –  | MedicationAdministration.medicationReference.reference must have the form 'Medication/{id}'.                                        |
| `context_reference_format`         | integrity    | error   | aus  |  –  | MedicationAdministration.context.reference must have the form 'Encounter/{id}' or 'EpisodeOfCare/{id}'.                             |
| `request_reference_format`         | integrity    | warning | aus  |  –  | MedicationAdministration.request.reference must have the form 'MedicationRequest/{id}'.                                             |
| `meta_profile_mii`                 | completeness | info    | aus  |  –  | MedicationAdministration.meta.profile must reference an MII core data set profile.                                                  |

## MedicationStatement

Profil: MII KDS Medikation (MedicationStatement)

| Regel                              | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                                                          |
| ---------------------------------- | ------------ | ------- | :--: | :-: | ------------------------------------------------------------------------------------------------------------------------------ |
| `status_required`                  | completeness | error   | aus  |  –  | MedicationStatement.status must be present.                                                                                    |
| `medication_required`              | completeness | error   | aus  |  –  | MedicationStatement.medication[x] (medicationReference or medicationCodeableConcept) must be present.                          |
| `subject_required`                 | completeness | error   | aus  |  –  | MedicationStatement.subject must be present.                                                                                   |
| `subject_reference_format`         | integrity    | error   | aus  |  –  | MedicationStatement.subject.reference must have the form 'Patient/{id}'.                                                       |
| `effective_required`               | completeness | warning | aus  |  –  | MedicationStatement.effective[x] must be present (required by MII Medikation).                                                 |
| `note_cleartext_check`             | privacy      | warning | aus  |  –  | MedicationStatement.note.text and dosage.text must not be longer than 50 characters; long free text may contain personal data. |
| `text_forbidden`                   | privacy      | info    | aus  | ja  | MedicationStatement.text (narrative) must not be present; it may contain cleartext personal data.                              |
| `status_valid`                     | coding       | error   | aus  |  –  | MedicationStatement.status must be a value of the FHIR medication-statement-status value set.                                  |
| `medication_coding_known_system`   | coding       | warning | aus  |  –  | MedicationStatement.medicationCodeableConcept must contain a PZN or ATC coding.                                                |
| `atc_code_format`                  | coding       | error   | aus  |  –  | An ATC code in medicationCodeableConcept must be a valid ATC code.                                                             |
| `pzn_code_format`                  | coding       | error   | aus  |  –  | A PZN in medicationCodeableConcept must have 8 digits.                                                                         |
| `effective_not_future`             | plausibility | warning | aus  |  –  | MedicationStatement.effectiveDateTime and effectivePeriod.start must not lie in the future.                                    |
| `effective_period_end_after_start` | plausibility | error   | aus  |  –  | MedicationStatement.effectivePeriod.end must not lie before start (FHIR invariant per-1).                                      |
| `date_asserted_not_future`         | plausibility | warning | aus  |  –  | MedicationStatement.dateAsserted must not lie in the future.                                                                   |
| `dosage_text_or_structured`        | completeness | warning | aus  |  –  | Every MedicationStatement.dosage must have text or doseAndRate (MII DosageDE, dsg-1).                                          |
| `medication_reference_format`      | integrity    | error   | aus  |  –  | MedicationStatement.medicationReference.reference must have the form 'Medication/{id}'.                                        |
| `context_reference_format`         | integrity    | error   | aus  |  –  | MedicationStatement.context.reference must have the form 'Encounter/{id}' or 'EpisodeOfCare/{id}'.                             |
| `meta_profile_mii`                 | completeness | info    | aus  |  –  | MedicationStatement.meta.profile must reference an MII core data set profile.                                                  |

## Procedure

Profil: MII KDS Prozedur (Procedure)

| Regel                              | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                                  |
| ---------------------------------- | ------------ | ------- | :--: | :-: | ------------------------------------------------------------------------------------------------------ |
| `note_cleartext_check`             | privacy      | warning |  an  |  –  | Procedure.note.text must not be longer than 50 characters; long free text may contain personal data.   |
| `status_required`                  | completeness | error   |  an  |  –  | Procedure.status must be present.                                                                      |
| `code_required`                    | completeness | error   |  an  |  –  | Procedure.code must be present.                                                                        |
| `subject_required`                 | completeness | error   |  an  |  –  | Procedure.subject must be present.                                                                     |
| `performed_required`               | completeness | warning |  an  |  –  | Procedure.performed[x] must be present.                                                                |
| `subject_reference_format`         | integrity    | error   |  an  |  –  | Procedure.subject.reference must have the form 'Patient/{id}'.                                         |
| `text_forbidden`                   | privacy      | info    | aus  | ja  | Procedure.text (narrative) must not be present; it may contain cleartext personal data.                |
| `status_valid`                     | coding       | error   | aus  |  –  | Procedure.status must be a value of the FHIR EventStatus value set.                                    |
| `code_coding_known_system`         | coding       | warning | aus  |  –  | Procedure.code must contain an OPS or SNOMED CT coding (MII invariant sct-ops-1).                      |
| `ops_version_required`             | coding       | error   | aus  |  –  | An OPS coding in Procedure.code must state the catalogue version (coding.version).                     |
| `ops_code_format`                  | coding       | error   | aus  |  –  | An OPS code must match the format of the German base profile, e.g. 5-470.11.                           |
| `ops_requires_category`            | coding       | warning | aus  |  –  | A Procedure coded with OPS must have a SNOMED CT category (MII invariant proc-mii-1).                  |
| `performed_datetime_or_period`     | plausibility | warning | aus  |  –  | Procedure.performed[x] must be a dateTime or Period; MII Prozedur does not allow string, Age or Range. |
| `performed_not_future`             | plausibility | warning | aus  |  –  | Procedure.performedDateTime and performedPeriod.start must not lie in the future.                      |
| `performed_period_end_after_start` | plausibility | error   | aus  |  –  | Procedure.performedPeriod.end must not lie before start (FHIR invariant per-1).                        |
| `bodysite_snomed`                  | coding       | info    | aus  |  –  | Procedure.bodySite must be coded with SNOMED CT (MII Prozedur).                                        |
| `encounter_reference_format`       | integrity    | error   | aus  |  –  | Procedure.encounter.reference must have the form 'Encounter/{id}'.                                     |
| `meta_profile_mii`                 | completeness | info    | aus  |  –  | Procedure.meta.profile must reference an MII core data set profile.                                    |

## DiagnosticReport

Profil: FHIR R4, Laborregeln aus MII KDS Laborbefund (DiagnosticReportLab)

| Regel                              | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                                                                                    |
| ---------------------------------- | ------------ | ------- | :--: | :-: | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `note_cleartext_check`             | privacy      | warning |  an  |  –  | DiagnosticReport.conclusion must not be longer than 50 characters and text.div not longer than 100 characters; long free text may contain personal data. |
| `status_required`                  | completeness | error   |  an  |  –  | DiagnosticReport.status must be present.                                                                                                                 |
| `code_required`                    | completeness | error   |  an  |  –  | DiagnosticReport.code must be present.                                                                                                                   |
| `subject_required`                 | completeness | error   |  an  |  –  | DiagnosticReport.subject must be present.                                                                                                                |
| `subject_reference_format`         | integrity    | error   |  an  |  –  | DiagnosticReport.subject.reference must have the form 'Patient/{id}'.                                                                                    |
| `text_forbidden`                   | privacy      | info    | aus  | ja  | DiagnosticReport.text (narrative) must not be present; it may contain cleartext personal data.                                                           |
| `status_valid`                     | coding       | error   | aus  |  –  | DiagnosticReport.status must be a value of the FHIR DiagnosticReportStatus value set.                                                                    |
| `category_required`                | completeness | warning | aus  |  –  | DiagnosticReport.category must be present.                                                                                                               |
| `identifier_required`              | completeness | info    | aus  |  –  | DiagnosticReport.identifier must be present (report number, required by MII DiagnosticReportLab).                                                        |
| `effective_required`               | completeness | warning | aus  |  –  | DiagnosticReport.effective[x] must be present.                                                                                                           |
| `issued_required`                  | completeness | info    | aus  |  –  | DiagnosticReport.issued must be present.                                                                                                                 |
| `code_coding_complete`             | coding       | warning | aus  |  –  | Every DiagnosticReport.code.coding must carry both system and code.                                                                                      |
| `effective_not_future`             | plausibility | warning | aus  |  –  | DiagnosticReport.effectiveDateTime must not lie in the future.                                                                                           |
| `issued_not_future`                | plausibility | warning | aus  |  –  | DiagnosticReport.issued must not lie in the future.                                                                                                      |
| `issued_after_effective`           | plausibility | warning | aus  |  –  | DiagnosticReport.issued must not lie before effectiveDateTime.                                                                                           |
| `effective_period_end_after_start` | plausibility | error   | aus  |  –  | DiagnosticReport.effectivePeriod.end must not lie before start (FHIR invariant per-1).                                                                   |
| `result_reference_format`          | integrity    | error   | aus  |  –  | DiagnosticReport.result.reference must have the form 'Observation/{id}'.                                                                                 |
| `basedon_reference_format`         | integrity    | warning | aus  |  –  | DiagnosticReport.basedOn.reference must point to a request resource, usually 'ServiceRequest/{id}'.                                                      |
| `encounter_reference_format`       | integrity    | error   | aus  |  –  | DiagnosticReport.encounter.reference must have the form 'Encounter/{id}'.                                                                                |
| `lab_category_coding`              | coding       | warning | aus  |  –  | A laboratory DiagnosticReport must be categorized with both LOINC 26436-6 and v2-0074 LAB (MII DiagnosticReportLab).                                     |
| `lab_code_loinc`                   | coding       | warning | aus  |  –  | A laboratory DiagnosticReport.code must contain LOINC 11502-2 (Laboratory report).                                                                       |
| `lab_result_required`              | completeness | warning | aus  |  –  | A laboratory DiagnosticReport must reference its results (MII DiagnosticReportLab).                                                                      |
| `lab_basedon_required`             | completeness | info    | aus  |  –  | A laboratory DiagnosticReport must reference its order in basedOn (MII DiagnosticReportLab).                                                             |
| `meta_profile_mii`                 | completeness | info    | aus  |  –  | DiagnosticReport.meta.profile must reference an MII core data set profile.                                                                               |

## ServiceRequest

Profil: FHIR R4, Laborregeln aus MII KDS Laborbefund (ServiceRequestLab)

| Regel                           | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                                     |
| ------------------------------- | ------------ | ------- | :--: | :-: | --------------------------------------------------------------------------------------------------------- |
| `status_required`               | completeness | error   | aus  |  –  | ServiceRequest.status must be present.                                                                    |
| `intent_required`               | completeness | error   | aus  |  –  | ServiceRequest.intent must be present.                                                                    |
| `subject_required`              | completeness | error   | aus  |  –  | ServiceRequest.subject must be present.                                                                   |
| `code_required`                 | completeness | error   | aus  |  –  | ServiceRequest.code must be present.                                                                      |
| `category_required`             | completeness | warning | aus  |  –  | ServiceRequest.category must be present.                                                                  |
| `authored_on_required`          | completeness | warning | aus  |  –  | ServiceRequest.authoredOn must be present (required by MII ServiceRequestLab).                            |
| `identifier_required`           | completeness | info    | aus  |  –  | ServiceRequest.identifier must be present (order number, required by MII ServiceRequestLab).              |
| `note_cleartext_check`          | privacy      | warning | aus  |  –  | ServiceRequest.note.text must not be longer than 50 characters; long free text may contain personal data. |
| `patient_instruction_forbidden` | privacy      | warning | aus  | ja  | ServiceRequest.patientInstruction must not be used; it is free text (excluded by MII ServiceRequestLab).  |
| `text_forbidden`                | privacy      | info    | aus  | ja  | ServiceRequest.text (narrative) must not be present; it may contain cleartext personal data.              |
| `status_valid`                  | coding       | error   | aus  |  –  | ServiceRequest.status must be a value of the FHIR request-status value set.                               |
| `intent_valid`                  | coding       | error   | aus  |  –  | ServiceRequest.intent must be a value of the FHIR request-intent value set.                               |
| `code_coding_complete`          | coding       | warning | aus  |  –  | Every ServiceRequest.code.coding must carry both system and code.                                         |
| `lab_order_status`              | plausibility | info    | aus  |  –  | A laboratory ServiceRequest should have status 'completed' and intent 'order' (MII ServiceRequestLab).    |
| `authored_not_future`           | plausibility | warning | aus  |  –  | ServiceRequest.authoredOn must not lie in the future.                                                     |
| `body_site_forbidden`           | plausibility | info    | aus  |  –  | ServiceRequest.bodySite must not be used for laboratory orders (excluded by MII ServiceRequestLab).       |
| `subject_reference_format`      | integrity    | error   | aus  |  –  | ServiceRequest.subject.reference must have the form 'Patient/{id}'.                                       |
| `encounter_reference_format`    | integrity    | error   | aus  |  –  | ServiceRequest.encounter.reference must have the form 'Encounter/{id}'.                                   |
| `specimen_reference_format`     | integrity    | warning | aus  |  –  | ServiceRequest.specimen.reference must have the form 'Specimen/{id}'.                                     |
| `meta_profile_mii`              | completeness | info    | aus  |  –  | ServiceRequest.meta.profile must reference an MII core data set profile.                                  |

## Specimen

Profil: MII KDS Biobank (Bioprobe)

| Regel                           | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                                     |
| ------------------------------- | ------------ | ------- | :--: | :-: | --------------------------------------------------------------------------------------------------------- |
| `status_required`               | completeness | error   | aus  |  –  | Specimen.status must be present (required by MII Bioprobe).                                               |
| `type_required`                 | completeness | error   | aus  |  –  | Specimen.type must be present (required by MII Bioprobe).                                                 |
| `subject_required`              | completeness | error   | aus  |  –  | Specimen.subject must be present (required by MII Bioprobe).                                              |
| `collection_required`           | completeness | warning | aus  |  –  | Specimen.collection.collected[x] must be present (required by MII Bioprobe).                              |
| `identifier_required`           | completeness | info    | aus  |  –  | Specimen.identifier must be present.                                                                      |
| `container_type_required`       | completeness | info    | aus  |  –  | Every Specimen.container must have a type (required by MII Bioprobe).                                     |
| `processing_procedure_required` | completeness | info    | aus  |  –  | Every Specimen.processing step must have a procedure (required by MII Bioprobe).                          |
| `note_cleartext_check`          | privacy      | warning | aus  |  –  | Specimen.note.text must not be longer than 50 characters; long free text may contain personal data.       |
| `text_forbidden`                | privacy      | info    | aus  | ja  | Specimen.text (narrative) must not be present; it may contain cleartext personal data.                    |
| `status_valid`                  | coding       | error   | aus  |  –  | Specimen.status must be available, unavailable, unsatisfactory or entered-in-error.                       |
| `type_snomed`                   | coding       | warning | aus  |  –  | Specimen.type must be coded with SNOMED CT (MII Bioprobe sample types).                                   |
| `bodysite_coding`               | coding       | warning | aus  |  –  | Specimen.collection.bodySite must be coded with SNOMED CT or ICD-O-3 topography (MII invariant mii-bb-1). |
| `collection_quantity_ucum`      | coding       | warning | aus  |  –  | Specimen.collection.quantity must use a UCUM unit.                                                        |
| `container_quantity_ucum`       | coding       | info    | aus  |  –  | Specimen.container.capacity and specimenQuantity must use UCUM units.                                     |
| `collected_not_future`          | plausibility | warning | aus  |  –  | Specimen.collection.collectedDateTime must not lie in the future.                                         |
| `received_not_future`           | plausibility | warning | aus  |  –  | Specimen.receivedTime must not lie in the future.                                                         |
| `received_after_collected`      | plausibility | warning | aus  |  –  | Specimen.receivedTime must not lie before collection.collectedDateTime.                                   |
| `subject_reference_format`      | integrity    | error   | aus  |  –  | Specimen.subject.reference must have the form 'Patient/{id}' (MII Bioprobe).                              |
| `parent_reference_format`       | integrity    | error   | aus  |  –  | Specimen.parent.reference must have the form 'Specimen/{id}'.                                             |
| `request_reference_format`      | integrity    | warning | aus  |  –  | Specimen.request.reference must have the form 'ServiceRequest/{id}'.                                      |
| `parent_not_self`               | integrity    | error   | aus  |  –  | Specimen.parent must not reference the specimen itself.                                                   |
| `meta_profile_mii`              | completeness | info    | aus  |  –  | Specimen.meta.profile must reference an MII core data set profile.                                        |

## Consent

Profil: MII KDS Consent (Einwilligung)

| Regel                              | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                                     |
| ---------------------------------- | ------------ | ------- | :--: | :-: | --------------------------------------------------------------------------------------------------------- |
| `status_required`                  | completeness | error   | aus  |  –  | Consent.status must be present.                                                                           |
| `patient_required`                 | completeness | error   | aus  |  –  | Consent.patient must be present (required by MII Consent).                                                |
| `datetime_required`                | completeness | error   | aus  |  –  | Consent.dateTime must be present (required by MII Consent).                                               |
| `policy_required`                  | completeness | warning | aus  |  –  | Consent.policy.uri must be present (required by MII Consent).                                             |
| `provision_period_required`        | completeness | warning | aus  |  –  | Consent.provision.period.start must be present (required by MII Consent).                                 |
| `nested_provision_complete`        | completeness | warning | aus  |  –  | Every nested Consent.provision.provision must have type, code and period.start (required by MII Consent). |
| `status_valid`                     | coding       | error   | aus  |  –  | Consent.status must be a value of the FHIR consent-state-codes value set.                                 |
| `scope_research`                   | coding       | warning | aus  |  –  | Consent.scope must be 'research' from the consentscope code system (MII Consent).                         |
| `category_loinc`                   | coding       | warning | aus  |  –  | Consent.category must contain LOINC 57016-8 (Privacy policy acknowledgment, MII Consent).                 |
| `provision_codes_mii`              | coding       | warning | aus  |  –  | Nested Consent.provision.provision.code must use the MII consent policy code system.                      |
| `provision_type_valid`             | coding       | error   | aus  |  –  | Consent.provision.type and nested provision types must be 'permit' or 'deny'.                             |
| `datetime_not_future`              | plausibility | warning | aus  |  –  | Consent.dateTime must not lie in the future.                                                              |
| `provision_period_end_after_start` | plausibility | error   | aus  |  –  | Consent.provision.period.end must not lie before start (FHIR invariant per-1).                            |
| `nested_period_end_after_start`    | plausibility | error   | aus  |  –  | Nested Consent.provision.provision.period.end must not lie before start (FHIR invariant per-1).           |
| `patient_reference_format`         | integrity    | error   | aus  |  –  | Consent.patient.reference must have the form 'Patient/{id}'.                                              |
| `meta_profile_mii`                 | completeness | info    | aus  |  –  | Consent.meta.profile must reference an MII core data set profile.                                         |

## ImagingStudy

Profil: MII KDS Bildgebung (Bildgebungsstudie)

| Regel                            | Kategorie    | Schwere | Std. | Fix | Prüft                                                                                      |
| -------------------------------- | ------------ | ------- | :--: | :-: | ------------------------------------------------------------------------------------------ |
| `status_required`                | completeness | error   | aus  |  –  | ImagingStudy.status must be present.                                                       |
| `subject_required`               | completeness | error   | aus  |  –  | ImagingStudy.subject must be present.                                                      |
| `started_required`               | completeness | warning | aus  |  –  | ImagingStudy.started must be present.                                                      |
| `study_uid_required`             | completeness | warning | aus  |  –  | ImagingStudy.identifier must contain the DICOM Study Instance UID (system urn:dicom:uid).  |
| `series_uid_required`            | completeness | error   | aus  |  –  | Every ImagingStudy.series must have a uid.                                                 |
| `series_modality_required`       | completeness | error   | aus  |  –  | Every ImagingStudy.series must have a modality.                                            |
| `instance_uid_required`          | completeness | error   | aus  |  –  | Every ImagingStudy.series.instance must have a uid and a sopClass.                         |
| `text_forbidden`                 | privacy      | info    | aus  | ja  | ImagingStudy.text (narrative) must not be present; it may contain cleartext personal data. |
| `status_valid`                   | coding       | error   | aus  |  –  | ImagingStudy.status must be a value of the FHIR ImagingStudyStatus value set.              |
| `modality_dicom`                 | coding       | warning | aus  |  –  | ImagingStudy.modality and series.modality must use the DICOM code system (DCM, CID 33).    |
| `started_not_future`             | plausibility | warning | aus  |  –  | ImagingStudy.started and series.started must not lie in the future.                        |
| `number_of_series_consistent`    | plausibility | warning | aus  |  –  | ImagingStudy.numberOfSeries must match the number of series listed.                        |
| `number_of_instances_consistent` | plausibility | warning | aus  |  –  | ImagingStudy.numberOfInstances must match the number of instances listed in all series.    |
| `subject_reference_format`       | integrity    | error   | aus  |  –  | ImagingStudy.subject.reference must have the form 'Patient/{id}' (MII Bildgebung).         |
| `encounter_reference_format`     | integrity    | error   | aus  |  –  | ImagingStudy.encounter.reference must have the form 'Encounter/{id}'.                      |
| `basedon_reference_format`       | integrity    | warning | aus  |  –  | ImagingStudy.basedOn.reference must point to a request, usually 'ServiceRequest/{id}'.     |
| `meta_profile_mii`               | completeness | info    | aus  |  –  | ImagingStudy.meta.profile must reference an MII core data set profile.                     |

<!-- rules:end -->

## Auto-Fix

Für einige Regeln gibt es eine feste Korrektur als JSON-Patch (`fix_templates.py`). In der Bereinigung wird der exakte Patch vor dem Ausführen
angezeigt und jede Ausführung im Audit-Log festgehalten.

| Regel                                          | Patch                                                                                    |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `text_forbidden` (alle Typen)                  | `remove /text`                                                                           |
| `Patient.name_forbidden`                       | `remove /name`                                                                           |
| `Patient.telecom_forbidden`                    | `remove /telecom`                                                                        |
| `Patient.photo_forbidden`                      | `remove /photo`                                                                          |
| `Patient.contact_forbidden`                    | `remove /contact`                                                                        |
| `Patient.address_forbidden`                    | entfernt `line`, `city` und `text` aus **allen** Adressen; Postleitzahl und Land bleiben |
| `Observation.value_string_cleartext_forbidden` | `remove /valueString`                                                                    |
| `ServiceRequest.patient_instruction_forbidden` | `remove /patientInstruction`                                                             |
| `MedicationRequest.do_not_perform_forbidden`   | `remove /doNotPerform`                                                                   |

Alle anderen Befunde lassen sich nur manuell korrigieren, oder die Ressource wird gelöscht.

## Grenzen

- **Terminologie:** Verity prüft Codesystem, Format und Version eines Codes, aber nicht, ob es den Code im Katalog tatsächlich gibt (z. B. ob ein
  ICD-10-GM-Code im angegebenen Jahr gültig ist). Dafür wäre ein Terminologieserver nötig.
- **Ressourcenübergreifend:** Außer `Patient.has_observation` und `Patient.has_condition` prüft keine Regel andere Ressourcen, also weder ob eine
  referenzierte Ressource existiert noch ob etwa eine Diagnose im Zeitraum des Falls liegt.
- **Profilkonformität:** Die Regeln bilden die wichtigsten Anforderungen der MII-Profile ab, ersetzen aber keine vollständige Profilvalidierung mit
  dem HL7-Validator.
- **`Patient.address_forbidden`** prüft nur die erste Adresse; der Auto-Fix bereinigt alle.
- **Muster-Regeln** (`pseudonym_format_check`, `identifier_pseudonym_check`) beschreiben das Format der _originalen_ Kennung. Das voreingestellte
  Muster stammt aus Gießen und muss an jedem Standort angepasst werden.

## Neue Regel hinzufügen

1. **Regel** in `backend/app/services/rules/<typ>.py` anlegen: Schlüssel in `snake_case`, `category`, `severity`, eine `description`, die genau
   sagt, wann die Regel anschlägt, und die Prüffunktion. Wenn möglich einen Baustein aus `fhir.py` verwenden.
2. **Beispiel** in `backend/tests/fixtures/rule_examples.py` unter `FAILING` eintragen: die Änderung an der gültigen Ressource, die die Regel
   verletzt. Der Test `test_every_rule_has_an_example` schlägt fehl, solange es fehlt; die gültige Ressource muss weiterhin alle Regeln bestehen.
3. **Optional Auto-Fix** in `fix_templates.py` ergänzen.
4. **Doku erzeugen:** `cd backend && python -m app.services.rules.docs`. Der Test `test_rule_docs_are_current` prüft, dass dieses Dokument zum
   Code passt.

Neue Regeln sind standardmäßig aus. `enabled=True` nur setzen, wenn die Regel für jeden Standort sinnvoll ist und keine Fehlalarme erzeugt.

## Neuen Ressourcentyp hinzufügen

1. Modul `backend/app/services/rules/<typ>.py` mit `R = rules_for("<Typ>")` anlegen; der erste Satz des Modul-Docstrings
   (`"<Typ>: <Profil>."`) erscheint in der Übersicht.
2. Das Modul in `backend/app/services/rules/__init__.py` importieren. Damit ist der Typ in der Oberfläche, im Lauf und in den Reports verfügbar.
3. In `rule_examples.py` eine gültige Ressource unter `VALID` und je Regel ein Beispiel unter `FAILING` ergänzen, dann die Doku erzeugen.
