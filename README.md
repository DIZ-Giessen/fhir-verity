# FHIR Verity

Fhir Verity ist eine Server-weite Datenqualitäts-Validierung und Bereinigung für FHIR-Server im Umfeld der Medizininformatik-Initiative (MII).

FHIR Verity liest den vollständigen Ressourcen-Bestand eines FHIR-Servers, prüft ihn gegen **konfigurierbare Qualitätsregeln** in vier Dimensionen
(**Pseudonymisierung/Datenschutz, Vollständigkeit, Plausibilität, referentielle Integrität**), speichert die invaliden Ressourcen samt Befund und stellt einen Bereinigungs-Workflow bereit. Die Ergebnisse werden zusätzlich als FHIR-konforme Reports (`VerificationResult`, `TestReport`) auf den geprüften
Server zurückgeschrieben.

Das Tool ist als Ersatz für eine bestehende, schwer wartbare Mirth-Connect-Lösung entstanden und von Anfang an so gebaut, dass es an jedem DIZ oder alle andere FHIR Basierte Instituten ohne Codeänderung deploybar ist.

## Ziel

Bestehende FHIR-Validatoren prüfen einzelne Ressourcen oder Bundles gegen Profile. Was in der Praxis fehlt, ist zweierlei: die Prüfung eines
**kompletten Server-Bestands** in einem Durchlauf, und Qualitätskriterien, die über reine Profilkonformität hinausgehen — etwa ob Pseudonymisierung
tatsächlich greift, ob Pflichtfelder gefüllt sind, ob Werte plausibel sind und ob Referenzen ins Leere zeigen oder unplausibel sind. Genau diese Lücke schließt Verity.

## Architektur in einem Satz

Vier Container hinter einem Reverse Proxy: ein FastAPI-Backend, ein TanStack-Start-Frontend, eine PostgreSQL-Datenbank und Caddy als einziger nach
außen offener Dienst. Caddy terminiert TLS und leitet `/api/*` an das Backend, alles andere an das Frontend — dadurch gibt es nur eine Origin, kein CORS und keine standortspezifisch eingebackene Backend-URL. Details in [documentation/architektur.md](documentation/architektur.md).

## Schnellstart

Es gibt zwei Betriebsarten. Für einen produktiven Standort ist Docker der Weg, für die Entwicklung der lokale.

### Mit Docker (empfohlen)

Voraussetzung: Docker Engine und das Compose-Plugin. Standardmäßig bringt der Stack seine eigene PostgreSQL mit — es muss also keine Datenbank vorab
angelegt werden.

```bash
git clone <repo-url> fhir-verity
cd fhir-verity
cp .env.example .env
# .env mit echten Werten füllen (Domain, Passwörter, Keycloak, SMTP)
docker compose up -d --build
docker compose logs -f backend

```

Die vollständige Anleitung inklusive Keycloak-Einrichtung, Zertifikaten und dem Weg mit einer bereits vorhandenen Datenbank steht in [documentation/deployment.md](documentation/deployment.md).

### Lokal ohne Docker

Voraussetzung: Python 3.12+, Node 22+, pnpm(oder Ihre beliebige Packetmanagement), eine lokale PostgreSQL.

1. Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env auf die lokale Datenbank und deinen Keycloak zeigen lassen
alembic upgrade head
uvicorn app.main:app --reload
```

2. Frontend:

```bash
cd frontend
pnpm install # Sie können also auch npm, bun oder yan nutzen.
cp .env.example .env
pnpm dev
```

Das Frontend läuft dann auf `http://localhost:3000`, das Backend auf `http://localhost:8000`. Weil beide auf unterschiedlichen Ports laufen, ist im
lokalen Betrieb CORS aktiv — im Docker-Betrieb entfällt das durch die Single-Origin-Architektur mit Caddy.

## Dokumentation

Die ausführliche Dokumentation liegt im Ordner `documentation/`:

- [fhir-verity.md](documentation/fhir-verity.md) — Was das Tool ist, Kontext, Abgrenzung
- [architektur.md](documentation/architektur.md) — Die vier Container, Single-Origin, Datenfluss
- [features.md](documentation/features.md) — Validierungsdimensionen, Crawl, Reports, Bereinigung
- [datenbank.md](documentation/datenbank.md) — Die beiden DB-Wege, Migrationen, PostgreSQL-Rechte
- [schema.md](documentation/schema.md) — Tabellen, Spalten, Beziehungen
- [rollenverwaltung.md](documentation/rollenverwaltung.md) — RBAC, Server-Ownership, Audit
- [deployment.md](documentation/deployment.md) — Vollständige Deployment-Anleitung
- [weiterentwicklung.md](documentation/weiterentwicklung.md) — Änderungen, neue Pakete, neue Migrationen
- [troubleshooting.md](documentation/troubleshooting.md) — Bekannte Fehler und ihre Ursachen
