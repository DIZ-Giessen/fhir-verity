# Technische Spezifikation

## Architektur (Hybrid)

- **Backend:** FastAPI (Python 3.11+)  
  - FHIR-Handling: `fhir.resources` (Pydantic-basiert)  
  - ML: scikit-learn, XGBoost, SHAP  
  - LLM: Ollama (lokales Modell, z. B. Llama-3 oder Mistral)  
  - Datenbank: PostgreSQL (asyncpg + SQLAlchemy)
- **Frontend:** Next.js 15 (App Router) mit TypeScript
- **Kommunikation:** REST + WebSocket (für Live-Progress)
- **Deployment:** Docker-Compose

## Datenfluss

1. Benutzer gibt FHIR-Server-URL ein → Start Validierung
2. FastAPI holt Bundles in 1000er-Batches (Nextlink-Handling)
3. Regelbasierte Validierung (wie bisher)
4. Speicherung invalider Ressourcen + Metriken in PostgreSQL
5. ML-Scoring (Anomaly Detection + Risiko-Score)
6. LLM-Assistent generiert Korrektur-/Löschvorschläge
7. Dashboard zeigt alles an + manuelle Bestätigung von FHIR-Befehlen (DELETE / PATCH)

## Sicherheit & DSGVO

- Alles lokal, keine externen APIs außer Ollama aber self gehosted.
- Nur pseudonymisierte Daten
- Audit-Log für jeden ausgeführten FHIR-Befehl
