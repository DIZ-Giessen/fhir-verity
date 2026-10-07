# Deployment

Diese Anleitung beschreibt das Deployment mit Docker Compose. Sie deckt beide Datenbank-Wege ab (externe oder mitgelieferte Datenbank), die Keycloak-
Einrichtung, Zertifikate und die häufigsten Stolpersteine bei der ersten Inbetriebnahme.

## Voraussetzungen

Auf dem Zielserver:

- Docker Engine und das Compose-Plugin (`docker compose`, nicht das alte `docker-compose` mit Bindestrich).
- Ein freier Port für den Reverse Proxy (443 für HTTPS; siehe Abschnitt Ports).
- Netzwerkzugriff vom Server zum FHIR-Server, zum Keycloak und, falls genutzt, zur externen Datenbank und zum SMTP-Server.

Außerhalb des Servers:

- Ein Keycloak-Client für Verity mit korrekt eingetragener Redirect-URI (siehe Keycloak-Abschnitt). Ohne Keycloak lässt sich die Anmeldung für Tests mit `AUTH_ENABLED=false` abschalten (siehe `.env.example`), in Produktion nicht empfohlen.
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

| Variable                                        | Bedeutung                                                                       |
| ----------------------------------------------- | ------------------------------------------------------------------------------- |
| DOMAIN                                          | die Domain, unter der Verity erreichbar ist                                     |
| DATABASE_URL                                    | vollständige Verbindungs-URL; externer Host (Weg A) oder `db` (Weg B)           |
| POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB | nur bei Weg B: Zugangsdaten der mitgelieferten Datenbank                        |
| ENVIRONMENT                                     | `production` setzt das Secure-Cookie                                            |
| CORS_ORIGINS                                    | erlaubte Origin; im Single-Origin-Betrieb die eigene Domain                     |
| AUTH_ENABLED                                    | `true` in Produktion (empfohlen)                                                |
| SESSION_SECRET_KEY                              | zufälliger Schlüssel, siehe unten                                               |
| BACKEND_BASE_URL / FRONTEND_BASE_URL            | beide die eigene Domain (Single-Origin)                                         |
| KEYCLOAK_DISCOVERY_URL                          | die OIDC-Discovery-URL des Realms                                               |
| KEYCLOAK_CLIENT_ID / KEYCLOAK_CLIENT_SECRET     | Zugangsdaten des Keycloak-Clients                                               |
| INITIAL_ADMIN_USERS                             | Kennungen, die beim ersten Login admin werden                                   |
| FHIR_REPORT_PUBLISHER                           | Name des Standorts, der in den FHIR-Reports als Herausgeber erscheint           |
| FHIR_REPORT_NAMING_SYSTEM                       | kanonische Basis-URL der Report-Identifier; einmal festlegen, dann nicht ändern |
| EMAIL                                           | SMTP-Zugang für Benachrichtigungen                                              |

Den Session-Schlüssel mit einem echten Zufallswert setzen:

```bash
openssl rand -hex 32
```

Zwei Dinge, die zusammenpassen müssen, sonst startet nichts sauber:

- Bei Weg B müssen `POSTGRES_PASSWORD` und das Passwort in `DATABASE_URL` identisch sein, und der Host in `DATABASE_URL` ist `db`.
- `BACKEND_BASE_URL`, `FRONTEND_BASE_URL` und `CORS_ORIGINS` zeigen alle auf die eigene Domain.

## Welche Datenbank?

Verity braucht eine PostgreSQL-Datenbank für seine eigenen Daten (Server, Läufe, invalide Ressourcen, Audit-Log). Welcher Weg passt, hängt davon ab, ob am Standort bereits eine PostgreSQL betrieben wird:

| Situation                                                          | Weg                                  |
| ------------------------------------------------------------------ | ------------------------------------ |
| Es gibt eine PostgreSQL, die von der IT betreut und gesichert wird | **A — externe Datenbank** (Standard) |
| Es gibt keine, Verity soll möglichst ohne Vorarbeit laufen         | **B — mitgelieferte Datenbank**      |

Die `docker-compose.yml` ist für Weg A vorbereitet; der Datenbank-Container für Weg B steht auskommentiert darin und ist mit „Weg B“ markiert.

## Weg A: externe Datenbank (Standard)

An der `docker-compose.yml` muss nichts geändert werden.

In der `.env` zeigt die `DATABASE_URL` auf den externen Host:

```bash
DATABASE_URL=postgresql+asyncpg://verity:<passwort>@db-host.example.org:5432/verity
```

Der Verity-Benutzer muss Eigentümer des Schemas dieser Datenbank sein oder CREATE-Rechte haben — andernfalls scheitert die Migration mit `permission denied for schema public`. Die genauen SQL-Befehle stehen in [datenbank.md](datenbank.md). Backups und Updates der Datenbank laufen dann über die bestehende Infrastruktur. Weiter mit „Bauen und Starten".

## Weg B: mitgelieferte Datenbank

Verity bringt einen eigenen PostgreSQL-Container mit. Es muss nichts vorbereitet werden — der Container legt Datenbank und Benutzer beim ersten Start an, der Benutzer ist automatisch Eigentümer.

1. In der `docker-compose.yml` die drei mit „Weg B“ markierten Blöcke einkommentieren: den `db`-Service, das `depends_on` beim `backend` und das Volume `pgdata`.
2. In der `.env` die Zugangsdaten setzen und die `DATABASE_URL` auf den Host `db` zeigen lassen:

```bash
POSTGRES_USER=verity
POSTGRES_PASSWORD=<zufälliges-passwort>
POSTGRES_DB=verity
DATABASE_URL=postgresql+asyncpg://verity:<zufälliges-passwort>@db:5432/verity
```

Die Daten liegen im Docker-Volume `pgdata` und überleben `docker compose down` und Neustarts. Die Datenbank ist nur im Compose-Netz erreichbar, nicht von außen. Für Backups selbst sorgen, etwa mit `docker compose exec db pg_dump -U verity verity > verity.sql`. Weiter mit „Bauen und Starten".

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

Auf dem Server selbst (`-k` akzeptiert auch ein selbstsigniertes Zertifikat):

```bash
curl -k -I https://<DOMAIN>
```

Erwartet wird `HTTP/2 200`. Im Browser dann `https://<DOMAIN>` aufrufen — zwingend mit `https://`, falls der Reverse Proxy nur auf 443 läuft. Anschließend den Login testen; ein sauberer Keycloak-Durchlauf endet im Dashboard.

## Zertifikate

Die mitgelieferte `Caddyfile` erwartet ein vorhandenes Zertifikat unter `/etc/letsencrypt/live/<DOMAIN>/` (`fullchain.pem` und `privkey.pem`). Das Verzeichnis wird read-only in den Caddy-Container eingebunden, `DOMAIN` muss deshalb exakt dem Ordnernamen entsprechen. Je nach Standort passt eine dieser Varianten besser — dafür die `tls`-Zeile in der `Caddyfile` anpassen:

| Variante                                                            | `tls`-Zeile in der Caddyfile                                                  |
| ------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Zertifikat liegt unter `/etc/letsencrypt` (Standard)                | unverändert lassen                                                            |
| Zertifikat der Einrichtung an anderem Ort                           | `tls /pfad/cert.pem /pfad/key.pem` und Pfad in `docker-compose.yml` einbinden |
| Server öffentlich erreichbar, Caddy soll selbst Let's Encrypt holen | Zeile entfernen, Port 80 zusätzlich freigeben                                 |
| Interner Testserver ohne Zertifikat                                 | `tls internal` (selbstsigniert, Browserwarnung)                               |

## Betrieb

```bash
docker compose ps                 # Status
docker compose logs -f backend    # Live-Logs eines Dienstes
docker compose restart backend    # Neustart ohne Rebuild
docker compose down               # alles stoppen
docker compose up -d --build      # neu bauen und starten
```

`docker compose down` lässt die Volumes und damit die Datenbank in Ruhe. `docker compose down -v` löscht auch die Volumes — dieser Zusatz darf in Produktion nie versehentlich verwendet werden.
