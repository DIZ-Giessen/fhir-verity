# FHIR  Verity – Intelligentes FHIR-Datenqualitäts-Tool für das DIZ Gießen

## Ziel des Projekts

Entwicklung einer modernen, webbasierten FHIR-Validierungsplattform, die die bestehenden Mirth-Channels vollständig ersetzt.  
Das Tool validiert FHIR-Ressourcen (Patient, Encounter, Medication, Observation, MedicationAdministration) aus dem MII-Kerndatensatz, speichert Test-Reports in PostgreSQL und bietet anschließend intelligente Unterstützung durch **Machine Learning** und einen **LLM-Assistenten**.

## Kern-Features

- Vollständige regelbasierte Validierung (wie in den bestehenden Mirth-Channels)
- Automatische ML-basierte Anomaly Detection & Risiko-Scoring (valid/invalid)
- LLM-Assistent für Korrektur- und Löschvorschläge (immer manuell bestätigt)
- Schönes Next.js-Dashboard mit Live-Progress, Heatmaps und Export-Funktionen
- Komplett lokal und DSGVO-konform

## Warum dieses Projekt?

- Ersetzt das schwer wartbare Mirth-Setup durch eine moderne, wartbare Python/FastAPI + Next.js-Architektur
- Bringt echte Data-Science-Elemente (ML + LLM) in die tägliche DIZ-Arbeit
- Liefert sofort nutzbaren Mehrwert für alle MIRACUM/MII-Use-Cases (GeMTeX, INTERPOLAR, OMI etc.)
- Perfekte Vorbereitung auf den Data-Science-Master
  