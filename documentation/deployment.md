# Deployment

Diese Anleitung beschreibt das Deployment mit Docker Compose. Sie deckt beide Datenbank-Wege ab (mitgelieferte oder externe Datenbank), die Keycloak-
Einrichtung, Zertifikate und die häufigsten Stolpersteine bei der ersten Inbetriebnahme.

## Voraussetzungen

Auf dem Zielserver:

- Docker Engine und das Compose-Plugin (`docker compose`, nicht das alte `docker-compose` mit Bindestrich).
- Ein freier Port für den Reverse Proxy (443 für HTTPS; siehe Abschnitt Ports).
- Netzwerkzugriff vom Server zum FHIR-Server, zum Keycloak und, falls genutzt, zur externen Datenbank und zum SMTP-Server.

Außerhalb des Servers:

- Ein Keycloak-Client für Verity mit korrekt eingetragener Redirect-URI (siehe Keycloak-Abschnitt). falls es nicht genutzt kann deaktiviert werden siehe `.env.exemple`
- Bei externer Datenbank: eine für Verity angelegte Datenbank mit passenden Schema-Rechten (siehe [datenbank.md](datenbank.md)).

Prüfen, ob Docker einsatzbereit ist:

```bash
docker --version
docker compose version
docker ps
```

## Ports prüfen

Der Reverse Proxy braucht seinen Port exklusiv. Läuft auf dem Server bereits etwas auf Port 80 oder 443 (etwa ein anderer Webdienst oder ein FHIR-Server),
kollidiert das. Prüfen:

```bash
sudo ss -tlnp | grep -E ':80 |:443 '
```

Ist Port 80 bereits belegt, aber 443 frei, wird der Reverse Proxy nur auf 443 betrieben. In der `docker-compose.yml` beim `caddy`-Service dann nur:

```yaml
ports:
  - "443:443"
```

Der Zugriff läuft dann ausschließlich über `https://`. Für `tls internal` (selbstsigniertes Zertifikat) wird Port 80 ohnehin nicht benötigt.

## Konfiguration: die .env

Die gesamte standortspezifische Konfiguration liegt in einer zu erstellen `.env` im Repo-Root. Als Vorlage dient `.env.example`:

```bash
cp .env.example .env # danach mit den Werten aufüllen
```

Die wichtigsten Werte:

| Variable                                        | Bedeutung                                                                         |
| ----------------------------------------------- | --------------------------------------------------------------------------------- |
| DOMAIN                                          | die Domain, unter der Verity erreichbar ist                                       |
| POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB | Zugangsdaten der mitgelieferten Datenbank (Weg A)                                 |
| DATABASE_URL                                    | vollständige Verbindungs-URL; Host ist `db` (Weg A) oder der externe Host (Weg B) |
| ENVIRONMENT                                     | `production` setzt das Secure-Cookie                                              |
| CORS_ORIGINS                                    | erlaubte Origin; im Single-Origin-Betrieb die eigene Domain                       |
| AUTH_ENABLED                                    | `true` in Produktion (empfohlen)                                                  |
| SESSION_SECRET_KEY                              | zufälliger Schlüssel, siehe unten                                                 |
| BACKEND_BASE_URL / FRONTEND_BASE_URL            | beide die eigene Domain (Single-Origin)                                           |
| KEYCLOAK_DISCOVERY_URL                          | die OIDC-Discovery-URL des Realms                                                 |
| KEYCLOAK_CLIENT_ID / KEYCLOAK_CLIENT_SECRET     | Zugangsdaten des Keycloak-Clients                                                 |
| INITIAL_ADMIN_USERS                             | Kennungen, die beim ersten Login admin werden                                     |
| EMAIL\_\*                                       | SMTP-Zugang für Benachrichtigungen                                                |

Den Session-Schlüssel mit einem echten Zufallswert setzen:

```bash
openssl rand -hex 32
```

Zwei Dinge, die zusammenpassen müssen, sonst startet nichts sauber:

- Bei Weg A müssen `POSTGRES_PASSWORD` und das Passwort in `DATABASE_URL` identisch sein, und der Host in `DATABASE_URL` ist `db`.
- `BACKEND_BASE_URL`, `FRONTEND_BASE_URL` und `CORS_ORIGINS` zeigen alle auf die eigene Domain.

## Weg A: mitgelieferte Datenbank (Standard)

Der `db`-Service in `docker-compose.yml` bleibt aktiv. In der `.env` zeigt die `DATABASE_URL` auf `@db:5432`. Es muss nichts vorbereitet werden — der Container legt Datenbank und Benutzer beim ersten Start an, der Benutzer ist automatisch Eigentümer. Weiter mit dem Abschnitt „Bauen und Starten".

## Weg B: externe Datenbank

Der `db`-Service wird nicht benötigt. In `docker-compose.yml`:

- den `db`-Service auskommentiert lassen (oder entfernen),
- beim `backend`-Service die `depends_on`-Bedingung auf `db` entfernen,
- das `pgdata`-Volume wird nicht benötigt.

In der `.env` zeigt die `DATABASE_URL` auf den externen Host. Zusätzlich muss der Verity-Benutzer Eigentümer des `public`-Schemas dieser Datenbank sein oder CREATE-Rechte haben — andernfalls scheitert die Migration mit `permission denied for schema public`. Die genauen SQL-Befehle stehen in [datenbank.md](datenbank.md). Dann weiter mit „Bauen und Starten".

## Keycloak einrichten

Verity braucht einen Keycloak-Client im richtigen Realm. Der Realm ist der aus der `KEYCLOAK_DISCOVERY_URL` (der Teil `.../realms/<Realm>/...`). Beim Client:

- **Client-ID** entspricht `KEYCLOAK_CLIENT_ID`.
- **Client authentication**
- **Valid redirect URIs**: exakt `https://<DOMAIN>/api/v1/auth/callback`.
- **Web origins**: `https://<DOMAIN>` (oder `+`).
- **Valid post logout redirect URIs**: `https://<DOMAIN>`, sonst schlägt der
  Logout-Redirect fehl.

Der häufigste Fehler beim ersten Login ist „Ungültiger Parameter: redirect_uri". Das heißt fast immer: Die eingetragene Redirect-URI weicht vom
gesendeten Wert ab, sie steht im falschen Realm oder Client, oder es wurde nach dem Eintragen nicht gespeichert. Zum Eingrenzen hilft, testweise zusätzlich
`https://<DOMAIN>/*` als Redirect-URI einzutragen; klappt der Login damit, lag es am exakten Pfad. Für Produktion danach wieder auf den exakten Pfad zurück.

Prüfen, dass der Realm erreichbar ist und der Name stimmt:

```bash
curl -k -s https://<keycloak-host>/.../realms/<Realm>/.well-known/openid-configuration | head -c 300
```

## Bauen und Starten

```bash
docker compose up -d --build
```

Der erste Build dauert einige Minuten, vor allem das Frontend. Danach den Zustand prüfen:

```bash
docker compose ps
```

Alle Container sollten `Up` sein (die Datenbank `healthy`). Steht ein Container auf `Restarting`, crasht er in einer Schleife — die Ursache steht in seinen Logs. Die Backend-Logs sind der wichtigste Blick, weil dort die Migrationen und
der Anwendungsstart sichtbar werden:

```bash
docker compose logs -f backend
```

Erwartet wird der Ablauf: „Running database migrations", dann eine Alembic-Upgrade-Zeile, dann „Starting application" und schließlich „Application
startup complete". Mit `Strg+C` verlässt man das Log, ohne den Container zu stoppen.

## Erreichbarkeit testen

Auf dem Server selbst (das `-k` akzeptiert das selbstsignierte Zertifikat von `tls internal`):

```bash
curl -k -I https://<DOMAIN>
```

Erwartet wird `HTTP/2 200`. Im Browser dann `https://<DOMAIN>` aufrufen — zwingend mit `https://`, falls der Reverse Proxy nur auf 443 läuft. Bei
`tls internal` zeigt der Browser eine Zertifikatswarnung, die für einen Testserver bestätigt wird. Anschließend den Login testen; ein sauberer Keycloak-Durchlauf endet im Dashboard.

## Zertifikate für Produktion

`tls internal` ist für interne Test- und Betriebsumgebungen gedacht und erzeugt eine Browserwarnung. Für den regulären Produktionsbetrieb gibt es zwei saubere Optionen:

- Ist der Server öffentlich erreichbar, `tls internal` entfernen — Caddy holt
  dann automatisch ein Let's-Encrypt-Zertifikat (dafür muss Port 80 erreichbar
  sein).
- Gibt es ein von der Einrichtung bereitgestelltes Zertifikat, `tls internal`
  durch `tls /pfad/cert.pem /pfad/key.pem` ersetzen und die Dateien in den
  Caddy-Container einbinden.

Alternativ lässt sich die Caddy-Root-CA an die Client-Rechner verteilen, dann verschwindet die Warnung auch bei `tls internal`.

## Betrieb

```bash
docker compose ps                 # Status
docker compose logs -f backend    # Live-Logs eines Dienstes
docker compose restart backend    # Neustart ohne Rebuild
docker compose down               # alles stoppen, Daten bleiben erhalten
docker compose up -d --build      # neu bauen und starten
```

`docker compose down` lässt die Volumes und damit die Datenbank in Ruhe. `docker compose down -v` löscht auch die Volumes — dieser Zusatz darf in Produktion nie versehentlich verwendet werden.
