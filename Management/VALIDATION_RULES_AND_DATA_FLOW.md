# Validierungsregeln & Datenfluss

## Bestehende Regeln (bereits implementiert in Mirth)

- Patient: Keine Klarnamen, korrekte Pseudonym-ID
- Encounter: Sinnvolle Perioden
- Medication / MedicationAdministration: Korrekte Referenzen und Perioden
- Observation: Keine Klarnamen in valueString / valueQuantity etc.
- Allgemein: Bundle-Validität, Nextlink-Handling, Heap-Management

## Neuer Datenfluss (ohne Mirth)

1. FastAPI → FHIR-Server (GET Bundles)
2. Regel-Engine prüft jede Ressource
3. Invalide Ressourcen + Metriken → PostgreSQL
4. ML-Scoring
5. LLM-Vorschläge (optional)
6. FHIR-Verification-Report zurück in HAPI-Server
