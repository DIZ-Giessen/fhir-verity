# Sicherheitslücken melden

Bitte melde Sicherheitslücken **nicht** als öffentliches Issue, sondern vertraulich über GitHub:
Reiter **Security** → **Report a vulnerability** in diesem Repository.

Hilfreich sind:

- betroffene Version oder Commit,
- Schritte zum Nachstellen,
- mögliche Auswirkungen (z. B. Zugriff auf fremde Server, Rechteausweitung, Abfluss von Zugangsdaten).

Wir bestätigen den Eingang in der Regel innerhalb weniger Arbeitstage und melden uns, sobald eine Korrektur bereitsteht.
Bitte veröffentliche Details erst, wenn eine korrigierte Version verfügbar ist.

## Unterstützte Versionen

Sicherheitskorrekturen gibt es für den aktuellen Stand des Branches `main` und das jeweils letzte Release.

## Hinweise für den Betrieb

- Verity im Betrieb nur mit `AUTH_ENABLED=true`, `ENVIRONMENT=production` und HTTPS betreiben.
- `FHIR_ALLOWED_HOSTS` auf die FHIR-Server und Token-Endpunkte des Standorts beschränken.
- Den Backend-Port 8000 nicht veröffentlichen; er ist nur für Caddy im Compose-Netz gedacht.

Details stehen in [documentation/deployment.md](documentation/deployment.md).
