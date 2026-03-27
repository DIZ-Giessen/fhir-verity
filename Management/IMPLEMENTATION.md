# Umsetzungsplan (ca. 3–4 Monate Praxisphase)

## Phase 1 – Grundgerüst (Woche 1–3)

- FastAPI-Projekt aufsetzen + FHIR-Client
- PostgreSQL-Schema für Reports & Invalid-Liste
- Übernahme der bestehenden Validierungsregeln als Python-Funktionen
- Einfaches Next.js-Frontend mit Formular (Server-URL + Start-Button)

## Phase 2 – Kern-Validierung (Woche 4–6)

- Vollständige Batch-Verarbeitung mit Nextlink
- Speicherung von Test-Reports als FHIR-Resource
- Live-Progress im Dashboard

## Phase 3 – Machine Learning (Woche 7–9)

- Feature-Extraktion aus Bundles
- IsolationForest für Anomaly Detection
- XGBoostClassifier für Risiko-Score (valid/invalid)
- SHAP-Erklärungen

## Phase 4 – LLM-Assistent (Woche 10–12)

- Ollama-Integration
- Prompt-Template für Korrektur-/Löschvorschläge
- Anzeige exakter FHIR-Befehle (DELETE / PATCH) im Dashboard
- Manuelle Bestätigung + Ausführung

## Phase 5 – Polishing & Übergabe (Woche 13–14)

- Schönes Dashboard, Export-Funktionen, Heatmaps
- Docker-Compose
- Dokumentation + Übergabe an DIZ-Team

## Meilensteine

- Ende Woche 4: Regelbasierte Validierung läuft ohne Mirth
- Ende Woche 9: ML-Scoring live
- Ende Woche 12: LLM-Vorschläge funktionieren
