# Validierungsregeln

Dieses Dokument beschreibt alle Ressourcentypen, die Verity prüft, und jede einzelne Regel: was sie genau prüft, wann sie anschlägt, mit welcher
Schwere und ob es dafür einen Auto-Fix gibt. Maßgeblich ist das Verhalten im Code, nicht der Beschreibungstext in der Oberfläche.

Die Regeln sind in zwei Dateien definiert:

| Datei                                      | Inhalt                                                                                 |
| ------------------------------------------ | -------------------------------------------------------------------------------------- |
| `backend/app/services/config_defaults.py`  | `MII_KDS_DEFAULTS`: welche Regeln es gibt, Kategorie, Schwere, Standard an/aus, Muster |
| `backend/app/services/validation_rules.py` | ein Validator je Ressourcentyp mit der eigentlichen Prüflogik                          |
| `backend/app/services/fix_templates.py`    | JSON-Patch-Vorlagen für Regeln mit Auto-Fix                                            |

> **Pflege:** Wer eine Regel hinzufügt, ändert oder entfernt, passt dieses Dokument im selben Commit an. Die Checkliste dafür steht am Ende unter
> [Neue Regel hinzufügen](#neue-regel-hinzufügen).

## Inhalt

- [Grundlagen](#grundlagen)
- [Übersicht der Ressourcentypen](#übersicht-der-ressourcentypen)
- [Patient](#patient)
- [Encounter](#encounter)
- [Condition](#condition)
- [Observation](#observation)
- [Medication](#medication)
- [MedicationRequest](#medicationrequest)
- [MedicationAdministration](#medicationadministration)
- [MedicationStatement](#medicationstatement)
- [Procedure](#procedure)
- [DiagnosticReport](#diagnosticreport)
- [Bekannte Lücken und Einschränkungen](#bekannte-lücken-und-einschränkungen)
- [Neue Regel hinzufügen](#neue-regel-hinzufügen)

## Grundlagen

### Aufbau einer Regel

Jede Regel ist ein Eintrag in `MII_KDS_DEFAULTS[<Ressourcentyp>][<Regelschlüssel>]`:

```python
"name_forbidden": {
    "enabled": True,          # Standard an/aus
    "severity": "error",      # error | warning | info
    "category": "privacy",    # privacy | completeness | plausibility | integrity
    "description": "...",     # Text in der Oberfläche und im FHIR-TestScript
    "pattern": "^20[0-9]{7}$" # nur bei Muster-Regeln (Pseudonymisierung)
},
```

Der Regelschlüssel (`name_forbidden`) ist die stabile Kennung. Er steht in der Datenbank (`invalid_resource_issues.rule`), in den Laufstatistiken und in
den FHIR-Reports und darf deshalb nach dem ersten produktiven Einsatz nicht mehr umbenannt werden.

### Kategorien

| Kategorie      | Bedeutung                                                                                   |
| -------------- | ------------------------------------------------------------------------------------------- |
| `privacy`      | Datenschutz und Pseudonymisierung: Klartext, Kontaktdaten, nicht pseudonymisierte Kennungen |
| `completeness` | Vollständigkeit: Pflichtfelder und für die Auswertung nötige Angaben                        |
| `plausibility` | Plausibilität: zeitliche und logische Stimmigkeit                                           |
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

Für jeden Lauf wird die Konfiguration pro Ressourcentyp so zusammengesetzt:

1. **Globale Grundkonfiguration**: Zeile in `validation_configs` mit `server_id = NULL`. Sie wird beim ersten Start aus `MII_KDS_DEFAULTS` angelegt.
2. **Server-Override**: Zeile mit der `server_id` des Servers. Sie entsteht, sobald jemand auf der Konfigurationsseite eines Servers eine Regel ändert.
   Überschrieben wird regelweise: Eine geänderte Regel ersetzt die globale vollständig, alle anderen gelten unverändert weiter.

Pro Regel lassen sich `enabled`, `severity` und `pattern` ändern. Neue Regeln lassen sich über die Oberfläche nicht anlegen, nur solche, die in
`MII_KDS_DEFAULTS` definiert sind.

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

Diese Details gelten für alle Typen und erklären Grenzfälle:

- **„fehlt“** heißt: Feld nicht vorhanden, `null`, leere Zeichenkette, leere Liste oder leeres Objekt.
- **Zukunftsprüfungen** vergleichen mit der aktuellen Zeit in UTC. Ein Datum ohne Zeitzone (`2026-10-07`) wird als Mitternacht UTC gelesen. Nicht
  lesbare Werte schlagen nicht an.
- **Referenzformat** (`subject_reference_format`) prüft nur, ob `subject.reference` mit `Patient/` beginnt. Ob der Patient auf dem Server existiert,
  wird nicht geprüft. Fehlt `subject.reference` ganz, schlägt diese Regel nicht an; das deckt `subject_required` ab. Absolute URLs
  (`https://…/Patient/123`), `urn:uuid:`-Verweise und reine `identifier`-Verweise gelten als Verstoß.
- **Freitext-Regeln** (`note_cleartext_check`, `value_string_cleartext_forbidden`) erkennen keine Namen, sondern schlagen bei langen Texten an
  (Schwellwerte je Regel unten). Sie sind ein Hinweis zum manuellen Nachsehen.
- Eine Regel meldet pro Ressource höchstens einen Befund, auch wenn mehrere Einträge eines Feldes betroffen sind. Ausnahme:
  `Encounter.pseudonym_format_check` kann für `id` und `identifier` je einen Befund melden.

## Übersicht der Ressourcentypen

| Ressourcentyp            | MII-KDS-Modul  | Regeln | Standardmäßig aktiv | Validator |
| ------------------------ | -------------- | -----: | ------------------: | --------- |
| Patient                  | Person         |     15 |                  11 | ja        |
| Encounter                | Fall           |     11 |                   9 | ja        |
| Condition                | Diagnose       |      7 |                   4 | ja        |
| Observation              | Labor          |      9 |                   8 | ja        |
| Medication               | Medikation     |      3 |                   3 | ja        |
| MedicationRequest        | Medikation     |      8 |                   8 | ja        |
| MedicationAdministration | Medikation     |      8 |                   8 | ja        |
| MedicationStatement      | Medikation     |      4 |                   4 | **nein**  |
| Procedure                | Prozedur       |      6 |                   6 | ja        |
| DiagnosticReport         | Labor (Befund) |      5 |                   5 | ja        |

Regeln, die in der Konfiguration stehen, aber im Validator noch keine Prüflogik haben, sind unten mit **nicht implementiert** markiert. Sie lassen sich
in der Oberfläche schalten, schlagen aber nie an. Die Liste steht gesammelt unter [Bekannte Lücken](#bekannte-lücken-und-einschränkungen).

Spalten der Regeltabellen: **Std.** = standardmäßig aktiv, **Fix** = Auto-Fix verfügbar (siehe [Auto-Fix](#auto-fix)).

## Patient

Profil: MII KDS Person, `Patient` (pseudonymisiert).

| Regel                           | Kategorie    | Schwere | Std. | Fix | Schlägt an, wenn …                                                                           |
| ------------------------------- | ------------ | ------- | :--: | :-: | -------------------------------------------------------------------------------------------- |
| `text_forbidden`                | privacy      | info    | aus  |  –  | `Patient.text` (Narrative) vorhanden ist                                                     |
| `name_forbidden`                | privacy      | error   |  an  | ja  | `Patient.name` vorhanden ist                                                                 |
| `address_forbidden`             | privacy      | error   |  an  | ja  | die **erste** Adresse `line`, `city` oder `text` enthält; Postleitzahl und Land sind erlaubt |
| `telecom_forbidden`             | privacy      | error   |  an  | ja  | `Patient.telecom` (Telefon, E-Mail …) vorhanden ist                                          |
| `photo_forbidden`               | privacy      | error   |  an  | ja  | `Patient.photo` vorhanden ist                                                                |
| `pseudonym_format_check`        | privacy      | error   |  an  |  –  | `Patient.id` auf das Muster passt, also wie eine echte Klinik-ID aussieht (siehe unten)      |
| `identifier_pseudonym_check`    | privacy      | error   |  an  |  –  | ein `identifier.value` auf das Muster passt                                                  |
| `identifier_required`           | completeness | error   |  an  |  –  | kein `identifier` vorhanden ist                                                              |
| `birthdate_required`            | completeness | warning |  an  |  –  | `birthDate` fehlt                                                                            |
| `gender_required`               | completeness | warning |  an  |  –  | `gender` fehlt                                                                               |
| `managingorganization_required` | completeness | info    | aus  |  –  | **nicht implementiert**                                                                      |
| `has_observation`               | completeness | warning | aus  |  –  | zum Patienten keine einzige Observation existiert (`Observation?subject=Patient/<id>`)       |
| `has_condition`                 | completeness | warning | aus  |  –  | zum Patienten keine einzige Condition existiert (`Condition?subject=Patient/<id>`)           |
| `birthdate_not_future`          | plausibility | error   |  an  |  –  | `birthDate` in der Zukunft liegt                                                             |
| `birthdate_plausible_range`     | plausibility | warning |  an  |  –  | das Geburtsjahr mehr als 150 Jahre zurückliegt (verglichen wird nur das Jahr)                |

**Muster-Regeln (`pseudonym_format_check`, `identifier_pseudonym_check`):** Das Muster (Standard `^20[0-9]{7}$`) beschreibt das Format der
**originalen, nicht pseudonymisierten** Kennungen des Quellsystems, zum Beispiel einer Patientennummer aus dem KIS. Passt eine ID darauf, ist sie
vermutlich nicht pseudonymisiert und die Regel schlägt an. Jeder Standort muss das Muster auf seine eigenen Klinik-IDs anpassen. Ein leeres Muster
(`null` oder leer) schaltet die Prüfung ab, auch wenn die Regel aktiv ist. Verglichen wird mit `re.match`, also ab dem Anfang der Zeichenkette.

**`has_observation` / `has_condition`:** Für jeden Patienten wird eine eigene Zählanfrage an den FHIR-Server gestellt (bis zu 20 parallel). Das
verlängert Läufe bei großen Beständen deutlich. Schlägt eine Zählanfrage fehl, wird der Patient als „ohne Verknüpfung“ gewertet.

## Encounter

Profil: MII KDS Fall, `Encounter` (Kontakt Gesundheitseinrichtung).

| Regel                       | Kategorie    | Schwere | Std. | Fix | Schlägt an, wenn …                                                                            |
| --------------------------- | ------------ | ------- | :--: | :-: | --------------------------------------------------------------------------------------------- |
| `pseudonym_format_check`    | privacy      | error   |  an  |  –  | `Encounter.id` **oder** ein `identifier.value` auf das Muster passt (Standard `^20[0-9]{8}$`) |
| `status_required`           | completeness | error   |  an  |  –  | `status` fehlt (der Wert selbst wird nicht gegen das ValueSet geprüft)                        |
| `class_required`            | completeness | error   |  an  |  –  | `class` fehlt                                                                                 |
| `subject_required`          | completeness | error   |  an  |  –  | `subject` fehlt                                                                               |
| `period_start_required`     | completeness | error   |  an  |  –  | `period` oder `period.start` fehlt                                                            |
| `servicetype_required`      | completeness | info    | aus  |  –  | **nicht implementiert**                                                                       |
| `diagnosis_present`         | completeness | info    | aus  |  –  | **nicht implementiert**                                                                       |
| `period_end_after_start`    | plausibility | error   |  an  |  –  | `period.end` vorhanden ist und nicht **nach** `period.start` liegt (gleich zählt als Verstoß) |
| `period_not_future`         | plausibility | warning |  an  |  –  | **nicht implementiert** (obwohl standardmäßig aktiv)                                          |
| `period_plausible_duration` | plausibility | warning |  an  |  –  | `period.end` vorhanden ist und der Aufenthalt länger als 730 Tage dauert                      |
| `subject_reference_format`  | integrity    | error   |  an  |  –  | `subject.reference` nicht mit `Patient/` beginnt                                              |

Das Muster folgt derselben Logik wie beim Patient: Es beschreibt die originale Fallnummer, nicht das Pseudonym.

## Condition

Profil: MII KDS Diagnose, `Condition`.

| Regel                         | Kategorie    | Schwere | Std. | Fix | Schlägt an, wenn …                                                                 |
| ----------------------------- | ------------ | ------- | :--: | :-: | ---------------------------------------------------------------------------------- |
| `note_cleartext_check`        | privacy      | warning |  an  |  –  | ein `note.text` länger als 50 Zeichen ist                                          |
| `code_required`               | completeness | error   |  an  |  –  | `code` fehlt (ob ein ICD-10-GM-Code enthalten ist, wird nicht geprüft)             |
| `subject_required`            | completeness | error   |  an  |  –  | `subject` fehlt                                                                    |
| `clinicalstatus_required`     | completeness | warning | aus  |  –  | `clinicalStatus` fehlt                                                             |
| `verificationstatus_required` | completeness | info    | aus  |  –  | `verificationStatus` fehlt                                                         |
| `onset_present`               | completeness | info    | aus  |  –  | keines von `onsetDateTime`, `onsetAge`, `onsetPeriod`, `onsetRange`, `onsetString` |
| `subject_reference_format`    | integrity    | error   |  an  |  –  | `subject.reference` nicht mit `Patient/` beginnt                                   |

## Observation

Profil: MII KDS Labor, `Observation` (Laboruntersuchung).

| Regel                              | Kategorie    | Schwere | Std. | Fix | Schlägt an, wenn …                                                                                 |
| ---------------------------------- | ------------ | ------- | :--: | :-: | -------------------------------------------------------------------------------------------------- |
| `value_string_cleartext_forbidden` | privacy      | error   | aus  | ja  | `valueString` länger als 50 Zeichen ist                                                            |
| `note_cleartext_check`             | privacy      | warning |  an  |  –  | **nicht implementiert** (obwohl standardmäßig aktiv)                                               |
| `status_required`                  | completeness | error   |  an  |  –  | `status` fehlt                                                                                     |
| `code_required`                    | completeness | error   |  an  |  –  | `code` fehlt (ob ein LOINC-Code enthalten ist, wird nicht geprüft)                                 |
| `subject_required`                 | completeness | error   |  an  |  –  | `subject` fehlt                                                                                    |
| `effective_required`               | completeness | warning |  an  |  –  | keines von `effectiveDateTime`, `effectivePeriod`, `effectiveInstant`                              |
| `value_present`                    | completeness | warning |  an  |  –  | kein `value[x]` und kein `dataAbsentReason` vorhanden ist (siehe unten)                            |
| `effective_not_future`             | plausibility | warning |  an  |  –  | `effectiveDateTime` bzw. `effectiveInstant` in der Zukunft liegt; `effectivePeriod` wird ignoriert |
| `subject_reference_format`         | integrity    | error   |  an  |  –  | `subject.reference` nicht mit `Patient/` beginnt                                                   |

**`value_present`** akzeptiert `valueQuantity`, `valueCodeableConcept`, `valueString`, `valueBoolean`, `valueInteger`, `valueRange`, `valueRatio`,
`valueSampledData`, `valueTime`, `valueDateTime`, `valuePeriod` oder `dataAbsentReason`. Ein Wert, der als falsy gilt (`valueBoolean: false`,
`valueInteger: 0`), zählt dabei als fehlend. Werte nur in `component` werden nicht berücksichtigt.

## Medication

Profil: MII KDS Medikation, `Medication`.

| Regel                   | Kategorie    | Schwere | Std. | Fix | Schlägt an, wenn …                                                                             |
| ----------------------- | ------------ | ------- | :--: | :-: | ---------------------------------------------------------------------------------------------- |
| `code_required`         | completeness | error   |  an  |  –  | `code` fehlt oder weder `code.coding` noch `code.text` enthält                                 |
| `code_coding_present`   | completeness | warning |  an  |  –  | `code` vorhanden ist, aber kein `code.coding` hat (nur Freitext ist für Auswertungen zu wenig) |
| `ingredient_item_check` | plausibility | warning |  an  |  –  | ein `ingredient` weder `itemCodeableConcept` noch `itemReference` hat                          |

`ingredient_item_check` prüft nur, ob mindestens eines der beiden Felder vorhanden ist. Sind beide gesetzt, schlägt die Regel nicht an.

## MedicationRequest

Profil: MII KDS Medikation, `MedicationRequest`.

| Regel                      | Kategorie    | Schwere | Std. | Fix | Schlägt an, wenn …                                                                              |
| -------------------------- | ------------ | ------- | :--: | :-: | ----------------------------------------------------------------------------------------------- |
| `note_cleartext_check`     | privacy      | warning |  an  |  –  | **nicht implementiert** (obwohl standardmäßig aktiv)                                            |
| `status_required`          | completeness | error   |  an  |  –  | `status` fehlt                                                                                  |
| `intent_required`          | completeness | error   |  an  |  –  | `intent` fehlt                                                                                  |
| `medication_required`      | completeness | error   |  an  |  –  | weder `medicationReference` noch `medicationCodeableConcept` vorhanden ist                      |
| `subject_required`         | completeness | error   |  an  |  –  | `subject` fehlt                                                                                 |
| `authored_on_required`     | completeness | warning |  an  |  –  | `authoredOn` fehlt **und** keine `dosageInstruction[].timing.repeat.boundsPeriod` vorhanden ist |
| `authored_not_future`      | plausibility | warning |  an  |  –  | `authoredOn` in der Zukunft liegt                                                               |
| `subject_reference_format` | integrity    | error   |  an  |  –  | `subject.reference` nicht mit `Patient/` beginnt                                                |

## MedicationAdministration

Profil: MII KDS Medikation, `MedicationAdministration`.

| Regel                              | Kategorie    | Schwere | Std. | Fix | Schlägt an, wenn …                                                                   |
| ---------------------------------- | ------------ | ------- | :--: | :-: | ------------------------------------------------------------------------------------ |
| `note_cleartext_check`             | privacy      | warning |  an  |  –  | **nicht implementiert** (obwohl standardmäßig aktiv)                                 |
| `status_required`                  | completeness | error   |  an  |  –  | `status` fehlt                                                                       |
| `medication_required`              | completeness | error   |  an  |  –  | weder `medicationReference` noch `medicationCodeableConcept` vorhanden ist           |
| `subject_required`                 | completeness | error   |  an  |  –  | `subject` fehlt                                                                      |
| `effective_required`               | completeness | error   |  an  |  –  | weder `effectiveDateTime` noch `effectivePeriod` vorhanden ist                       |
| `effective_not_future`             | plausibility | warning |  an  |  –  | `effectiveDateTime` in der Zukunft liegt; `effectivePeriod` wird ignoriert           |
| `effective_period_end_after_start` | plausibility | error   |  an  |  –  | `effectivePeriod.end` vorhanden ist und nicht **nach** `effectivePeriod.start` liegt |
| `subject_reference_format`         | integrity    | error   |  an  |  –  | `subject.reference` nicht mit `Patient/` beginnt                                     |

## MedicationStatement

Profil: ergänzend zum MII-KDS-Modul Medikation.

**Für diesen Typ gibt es keinen Validator.** Die Regeln sind konfiguriert und in der Oberfläche sichtbar, ein Lauf überspringt `MedicationStatement`
aber, auch wenn der Typ ausgewählt wurde. Es entstehen keine Befunde und keine Statistik.

| Regel                      | Kategorie    | Schwere | Std. | Fix | Vorgesehene Prüfung                              |
| -------------------------- | ------------ | ------- | :--: | :-: | ------------------------------------------------ |
| `status_required`          | completeness | error   |  an  |  –  | `status` fehlt                                   |
| `medication_required`      | completeness | error   |  an  |  –  | `medication[x]` fehlt                            |
| `subject_required`         | completeness | error   |  an  |  –  | `subject` fehlt                                  |
| `subject_reference_format` | integrity    | error   |  an  |  –  | `subject.reference` beginnt nicht mit `Patient/` |

## Procedure

Profil: MII KDS Prozedur, `Procedure`.

| Regel                      | Kategorie    | Schwere | Std. | Fix | Schlägt an, wenn …                                                                                     |
| -------------------------- | ------------ | ------- | :--: | :-: | ------------------------------------------------------------------------------------------------------ |
| `note_cleartext_check`     | privacy      | warning |  an  |  –  | ein `note.text` länger als 50 Zeichen ist                                                              |
| `status_required`          | completeness | error   |  an  |  –  | `status` fehlt                                                                                         |
| `code_required`            | completeness | error   |  an  |  –  | `code` fehlt (ob ein OPS-Code enthalten ist, wird nicht geprüft)                                       |
| `subject_required`         | completeness | error   |  an  |  –  | `subject` fehlt                                                                                        |
| `performed_required`       | completeness | warning |  an  |  –  | keines von `performedDateTime`, `performedPeriod`, `performedString`, `performedAge`, `performedRange` |
| `subject_reference_format` | integrity    | error   |  an  |  –  | `subject.reference` nicht mit `Patient/` beginnt                                                       |

## DiagnosticReport

Profil: MII KDS Labor, `DiagnosticReport` (Befundbericht).

| Regel                      | Kategorie    | Schwere | Std. | Fix | Schlägt an, wenn …                                                                                    |
| -------------------------- | ------------ | ------- | :--: | :-: | ----------------------------------------------------------------------------------------------------- |
| `note_cleartext_check`     | privacy      | warning |  an  |  –  | `conclusion` länger als 50 Zeichen **oder** `text.div` (Narrative, inkl. HTML) länger als 100 Zeichen |
| `status_required`          | completeness | error   |  an  |  –  | `status` fehlt                                                                                        |
| `code_required`            | completeness | error   |  an  |  –  | `code` fehlt                                                                                          |
| `subject_required`         | completeness | error   |  an  |  –  | `subject` fehlt                                                                                       |
| `subject_reference_format` | integrity    | error   |  an  |  –  | `subject.reference` nicht mit `Patient/` beginnt                                                      |

## Auto-Fix

Für einige Regeln gibt es eine feste Korrektur als JSON-Patch (`fix_templates.py`). In der Bereinigung wird der exakte Patch vor dem Ausführen angezeigt
und jede Ausführung im Audit-Log festgehalten.

| Ressourcentyp | Regel                              | Patch                                                                                    |
| ------------- | ---------------------------------- | ---------------------------------------------------------------------------------------- |
| Patient       | `name_forbidden`                   | `remove /name`                                                                           |
| Patient       | `telecom_forbidden`                | `remove /telecom`                                                                        |
| Patient       | `photo_forbidden`                  | `remove /photo`                                                                          |
| Patient       | `address_forbidden`                | entfernt `line`, `city` und `text` aus **allen** Adressen; Postleitzahl und Land bleiben |
| Observation   | `value_string_cleartext_forbidden` | `remove /valueString`                                                                    |

Alle anderen Befunde lassen sich nur manuell korrigieren oder die Ressource wird gelöscht.

## Bekannte Lücken und Einschränkungen

Stand dieses Dokuments. Wer eine Lücke schließt, entfernt sie hier und passt die Tabelle des Typs an.

**Konfiguriert, aber ohne Prüflogik.** Diese Regeln lassen sich in der Oberfläche schalten, schlagen aber nie an. Die mit „an“ markierten sind sogar
standardmäßig aktiv und erwecken so den Eindruck, geprüft zu werden:

| Ressourcentyp            | Regel                             | Std. |
| ------------------------ | --------------------------------- | :--: |
| Patient                  | `managingorganization_required`   | aus  |
| Encounter                | `servicetype_required`            | aus  |
| Encounter                | `diagnosis_present`               | aus  |
| Encounter                | `period_not_future`               |  an  |
| Observation              | `note_cleartext_check`            |  an  |
| MedicationRequest        | `note_cleartext_check`            |  an  |
| MedicationAdministration | `note_cleartext_check`            |  an  |
| MedicationStatement      | alle vier Regeln (kein Validator) |  an  |

**Weitere Einschränkungen:**

- **Muster-Regeln:** Die Beschreibung in der Konfiguration („matches the expected pseudonym format“) sagt das Gegenteil dessen, was geprüft wird. Das
  Muster beschreibt die _originale_ Kennung (siehe [Patient](#patient)).
- **`Patient.address_forbidden`** prüft nur die erste Adresse. Der Auto-Fix bereinigt dagegen alle Adressen.
- **Gemischte Zeitangaben:** Hat ein Zeitraum ein Datum ohne Zeitzone (`2024-01-01`) und einen Zeitpunkt mit Zeitzone (`2024-01-05T10:00:00+01:00`),
  scheitert der Vergleich in `period_end_after_start`, `period_plausible_duration` (Encounter) und `effective_period_end_after_start`
  (MedicationAdministration) mit einem Fehler, der den Lauf abbricht.
- **Codes und ValueSets** werden nicht geprüft: Es wird nur festgestellt, ob `code`, `status` usw. vorhanden sind, nicht ob der Wert aus dem erwarteten
  CodeSystem (ICD-10-GM, OPS, LOINC, ATC/PZN) oder ValueSet stammt.
- **Beschreibungstexte:** `Patient.photo_forbidden` hat den Beschreibungstext von `name_forbidden` („Checks whether the field 'name' is present“).

## Neue Regel hinzufügen

1. **Definition** in `config_defaults.py` unter dem Ressourcentyp eintragen: Schlüssel in `snake_case`, `enabled`, `severity`, `category`,
   `description` und bei Muster-Regeln `pattern`. Die `description` erscheint in der Oberfläche und im FHIR-TestScript.
2. **Prüflogik** im Validator des Typs in `validation_rules.py` ergänzen, nach dem Schema der vorhandenen Regeln:

   ```python
   if rule_enabled(config, "mein_regelschluessel"):
       if <Bedingung für den Verstoß>:
           issues.append(
               {
                   "rule": "mein_regelschluessel",
                   "severity": config["mein_regelschluessel"]["severity"],
                   "message": "Patient.xyz ...",  # konkret, mit Feldpfad
               }
           )
           metrics["mein_regelschluessel"] = False
   ```

   Die Schwere immer aus `config` lesen, nie fest eintragen, sonst greift die Einstellung in der Oberfläche nicht.

3. **Optional Auto-Fix** in `fix_templates.py` ergänzen: statisch (`_STATIC_TEMPLATES`) für „Feld komplett entfernen“, dynamisch
   (`_DYNAMIC_TEMPLATES`) wenn Teile des Feldes erhalten bleiben sollen.
4. **Bestehende Installationen:** Die globale Grundkonfiguration wird nur beim allerersten Start angelegt. Eine neue Regel in `MII_KDS_DEFAULTS`
   kommt deshalb in bestehenden Datenbanken nicht an: Sie fehlt in der Oberfläche und wird im Lauf nie ausgeführt. Bis das automatisch passiert, die
   globale Zeile des Typs löschen und das Backend neu starten, dann wird sie aus den aktuellen Defaults neu angelegt:

   ```sql
   DELETE FROM validation_configs WHERE server_id IS NULL AND resource_type = 'Patient';
   ```

   Server-Overrides bleiben dabei erhalten. Die globale Zeile lässt sich über die Oberfläche nicht ändern, es geht also nichts verloren.

5. **Dieses Dokument** anpassen: Zeile in der Tabelle des Typs, Zähler in der [Übersicht](#übersicht-der-ressourcentypen) und gegebenenfalls
   [Auto-Fix](#auto-fix) und [Bekannte Lücken](#bekannte-lücken-und-einschränkungen).

Für einen **neuen Ressourcentyp** zusätzlich einen Validator nach dem Muster der vorhandenen Klassen anlegen und in `VALIDATORS` am Ende von
`validation_rules.py` registrieren. Ohne diesen Eintrag wird der Typ im Lauf stillschweigend übersprungen (wie derzeit `MedicationStatement`).
