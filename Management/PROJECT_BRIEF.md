# Projektkurzbeschreibung

## Ausgangssituation

Ich habe als studentische Hilfskraft bereits fünf Mirth-Channels entwickelt, die FHIR-Ressourcen aus dem HAPI FHIR Server in Schleifen von 1000er-Batches validieren (Patient, Encounter, Medication, Observation, MedicationAdministration). Jeder Channel prüft Pseudonymisierung, Perioden, Klarnamen etc., speichert invalide Ressourcen in einer Channel-Map und erzeugt am Ende einen FHIR-Verification-Report.

## Neues Projekt: FHIR Validation Hub

Ich möchte diese Channels durch eine moderne Web-Anwendung ersetzen, die:

1. Die gleiche regelbasierte Validierung (schneller und wartbarer) durchführt
2. Zusätzlich Machine-Learning-basierte Anomaly Detection und Risiko-Scores liefert
3. Nach der Validierung einen LLM-Assistenten anbietet, der konkrete Korrektur- oder Löschvorschläge macht (immer mit exakten FHIR-Befehlen und manueller Bestätigung)

## Vorteile

- Deutlich schnellere Validierung großer Batches
- Automatische Erkennung neuer, bisher unbekannter Fehler
- Intelligente Nachbearbeitung (LLM-Vorschläge) spart Zeit bei der manuellen Bereinigung
- Zentrales Dashboard für alle DIZ-Mitarbeiter und Use-Case-Partner
- Direkter Beitrag zu GeMTeX, OMI und INTERPOLAR (saubere FHIR-Daten)
