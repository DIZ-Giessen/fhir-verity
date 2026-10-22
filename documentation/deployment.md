# Deployment

Diese Anleitung beschreibt das Deployment mit Docker Compose. Sie deckt beide Datenbank-Optionen ab (externe oder mitgelieferte Container Datenbank), beide Keycloak-Optionen (eigener oder mitgelieferter Container Keycloak), Zertifikate und die häufigsten Stolpersteine bei der ersten Inbetriebnahme.

## Voraussetzungen

Auf dem Zielserver:

- Docker Engine und das Compose-Plugin.
- Ein freier Port für den Reverse Proxy (443 für HTTPS; siehe Abschnitt Ports).
- Netzwerkzugriff vom Server zum FHIR-Server und, falls genutzt, zum eigenen Keycloak, zur externen Datenbank und zum SMTP-Server für die Email Vergabe.

Außerhalb des Servers:

- Bei eigenem Keycloak: ein Client für Verity mit korrekt eingetragener Redirect-URI (siehe [Keycloak](#keycloak)). Gibt es am Standort keinen Keycloak, nutzen SIe die Option 2 bei Keycloak, es muss dann nichts vorbereitet werden.
- Bei externer Datenbank: eine für Verity angelegte Datenbank mit passenden Schema-Rechten (siehe [datenbank.md](datenbank.md)).

Prüfen, ob Docker einsatzbereit ist:

```bash
docker --version
docker compose version
docker ps
```

## Ports prüfen

Der Reverse Proxy braucht seinen Port exklusiv. Läuft auf dem Server bereits etwas auf Port 80 oder 443, kollidiert das. Prüfen:

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
| DATABASE_URL                                    | vollständige Verbindungs-URL; externer Host (Option A) oder `db` (Option B)     |
| POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB | nur bei Option B: Zugangsdaten der mitgelieferten Datenbank                     |
| ENVIRONMENT                                     | `production` setzt das Secure-Cookie                                            |
| CORS_ORIGINS                                    | erlaubte Origin; im Single-Origin-Betrieb die eigene Domain                     |
| AUTH_ENABLED                                    | im Betrieb immer `true`; `false` nur mit `ENVIRONMENT=development`              |
| SESSION_SECRET_KEY                              | zufälliger Schlüssel, siehe unten                                               |
| BACKEND_BASE_URL / FRONTEND_BASE_URL            | beide die eigene Domain (Single-Origin)                                         |
| KEYCLOAK_DISCOVERY_URL                          | die OIDC-Discovery-URL des Realms                                               |
| KEYCLOAK_CLIENT_ID / KEYCLOAK_CLIENT_SECRET     | Zugangsdaten des Keycloak-Clients                                               |
| INITIAL_ADMIN_USERS                             | Kennungen, die beim ersten Login admin werden                                   |
| COMPOSE_FILE / COMPOSE_PATH_SEPARATOR           | nur beim mitgelieferten Keycloak: schaltet `docker-compose.keycloak.yml` zu     |
| KEYCLOAK_DB_PASSWORD / KEYCLOAK_ADMIN_PASSWORD  | nur beim mitgelieferten Keycloak: Datenbank und Admin-Konsole                   |
| VERITY_ADMIN_EMAIL / VERITY_ADMIN_PASSWORD      | nur beim mitgelieferten Keycloak: erster Benutzer `verity-admin`                |
| FHIR_REPORT_PUBLISHER                           | Name des Standorts, der in den FHIR-Reports als Herausgeber erscheint           |
| VERITY_CANONICAL_BASE                           | optional; kanonische Basis der Reports, Standard ist die Projekt-URL            |
| EMAIL                                           | SMTP-Zugang für Email Benachrichtigungen                                        |

Den Session-Schlüssel mit einem echten Zufallswert setzen:

```bash
openssl rand -hex 32
```

## Welche Datenbank?

Verity braucht eine PostgreSQL-Datenbank für seine eigenen Daten (Server, Läufe, invalide Ressourcen, Audit-Log). Welcher Option passt, hängt davon ab, ob am Standort bereits eine PostgreSQL betrieben wird:

| Situation                                                          | Option                               |
| ------------------------------------------------------------------ | ------------------------------------ |
| Es gibt eine PostgreSQL, die von der IT betreut und gesichert wird | **A — externe Datenbank** (Standard) |
| Es gibt keine, Verity soll möglichst ohne Vorarbeit laufen         | **B — mitgelieferte Datenbank**      |

Die `docker-compose.yml` ist für Option A vorbereitet; der Datenbank-Container für Option B steht auskommentiert darin und ist mit Option B“ markiert.

## Option A : externe Datenbank (Standard)

An der `docker-compose.yml` muss nichts geändert werden. In der `.env` zeigt die `DATABASE_URL` auf den externen Host:

```bash
DATABASE_URL=postgresql+asyncpg://verity:<passwort>@db-host.example.org:5432/verity
```

Der Verity-Benutzer muss Eigentümer des Schemas dieser Datenbank sein oder CREATE-Rechte haben — andernfalls scheitert die Migration mit `permission denied for schema public`[datenbank.md](datenbank.md).

## Option B: mitgelieferte Datenbank

Verity bringt einen eigenen PostgreSQL-Container mit. Es muss nichts vorbereitet werden — der Container legt Datenbank und Benutzer beim ersten Start an, der Benutzer ist automatisch Eigentümer.

1. In der `docker-compose.yml` die drei mit „Option B“ markierten Blöcke einkommentieren: den `db`-Service, das `depends_on` beim `backend` und das Volume `pgdata`.
2. In der `.env` die Zugangsdaten setzen und die `DATABASE_URL` auf den Host `db` zeigen lassen:

```bash
POSTGRES_USER=verity
POSTGRES_PASSWORD=<zufälliges-passwort>
POSTGRES_DB=verity
DATABASE_URL=postgresql+asyncpg://verity:<zufälliges-passwort>@db:5432/verity
```

Die Daten liegen im Docker-Volume `pgdata`

## Keycloak

Verity meldet Benutzer über Keycloak an (OpenID Connect). Im Betrieb ist das Pflicht: Ohne Anmeldung gäbe es keine Rollen und keine Trennung der Server nach Eigentümer, und jeder, der Verity erreicht, könnte als Admin FHIR-Ressourcen löschen. Das Backend startet deshalb nicht, wenn `AUTH_ENABLED=false`
mit `ENVIRONMENT=production` kombiniert wird.

| Situation                                                   | Option                                    |
| ----------------------------------------------------------- | ----------------------------------------- |
| Am Standort gibt es bereits einen Keycloak                  | **1 — eigener Keycloak** (Standard)       |
| Es gibt keinen, Verity soll ohne Vorarbeit laufen           | **2 — mitgelieferter Keycloak**           |
| Nur lokal ausprobieren oder entwickeln, ohne jede Anmeldung | **ohne Anmeldung** (`AUTH_ENABLED=false`) |

### Option 1: eigener Keycloak (Standard)

Verity braucht einen Keycloak-Client im richtigen Realm. Der Realm ist der aus der `KEYCLOAK_DISCOVERY_URL` (der Teil `.../realms/<Realm>/...`). Beim Client:

- **Client-ID** entspricht `KEYCLOAK_CLIENT_ID`.
- **Client authentication**
- **Valid redirect URIs**: exakt `https://<DOMAIN>/api/v1/auth/callback`.
- **Web origins**: `https://<DOMAIN>` (oder `+`).
- **Valid post logout redirect URIs**: `https://<DOMAIN>`, sonst schlägt der
  Logout-Redirect fehl.

Der häufigste Fehler beim ersten Login ist „Ungültiger Parameter: redirect_uri". Das heißt fast immer: Die eingetragene Redirect-URI weicht vom gesendeten Wert ab, sie steht im falschen Realm oder Client, oder es wurde nach dem Eintragen nicht gespeichert. Zum Eingrenzen hilft, testweise zusätzlich `https://<DOMAIN>/*` als Redirect-URI einzutragen; klappt der Login damit, lag es am exakten Pfad. Für Produktion danach wieder auf den exakten Pfad zurück.

Prüfen, dass der Realm erreichbar ist und der Name stimmt:

```bash
curl -k -s https://<keycloak-host>/.../realms/<Realm>/.well-known/openid-configuration | head -c 300
```

### Option 2: mitgelieferter Keycloak

Verity bringt einen fertig eingerichteten Keycloak mit eigener PostgreSQL mit (`docker-compose.keycloak.yml`). Er läuft hinter demselben Caddy unter `https://<DOMAIN>/kc`, braucht also weder eigene Domain noch eigenes Zertifikat. Beim ersten Start wird `keycloak/verity-realm.json` importiert: der Realm `verity`, der Client für Verity mit der passenden Redirect-URI und ein erster Benutzer `verity-admin`.

1. In der `.env` den Block „Option 2“ einkommentieren und die beiden Zeilen von Option 1 auskommentieren:

   ```bash
   COMPOSE_PATH_SEPARATOR=:
   COMPOSE_FILE=docker-compose.yml:docker-compose.keycloak.yml
   KEYCLOAK_DISCOVERY_URL=http://keycloak:8080/kc/realms/verity/.well-known/openid-configuration
   INITIAL_ADMIN_USERS=verity-admin
   KEYCLOAK_CLIENT_SECRET=<zufälliger-wert>
   KEYCLOAK_DB_PASSWORD=<zufälliger-wert>
   KEYCLOAK_ADMIN_PASSWORD=<zufälliger-wert>
   VERITY_ADMIN_EMAIL=admin@dein-standort.de
   VERITY_ADMIN_PASSWORD=<startpasswort>
   KEYCLOAK_CLIENT_ID=fhir-verity
   KEYCLOAK_CLIENT_SECRET=change_me
   ```

   `COMPOSE_FILE` sorgt dafür, dass `docker compose` die Keycloak-Datei automatisch mitlädt; alle Befehle bleiben gleich. Fehlt einer der Werte, bricht `docker compose up` ab und nennt die fehlende Variable.

2. Wie gewohnt starten (siehe „Bauen und Starten“). Keycloak braucht beim ersten Start etwa eine Minute.
3. `https://<DOMAIN>` öffnen, „Sign in with Keycloak“ wählen und als `verity-admin` mit dem Startpasswort anmelden. Keycloak verlangt dabei ein neues
   Passwort. Verity macht `verity-admin` über `INITIAL_ADMIN_USERS` zum Admin.
4. Weitere Benutzer in der Keycloak-Admin-Konsole anlegen: `https://<DOMAIN>/kc/admin`, Benutzer `admin`, Passwort `KEYCLOAK_ADMIN_PASSWORD`. Oben links
   den Realm `verity` wählen, dann unter „Users“ einen Benutzer anlegen und im Reiter „Credentials“ ein Passwort setzen. Neue Benutzer starten in Verity als viewer, die
   Rolle vergibt ein Admin in Verity auf der „Users Page“.

Hinweise:

- Das Backend spricht Keycloak intern über `http://keycloak:8080` an, der Browser über `https://<DOMAIN>/kc`. Keycloak trennt beides selbst (`KC_HOSTNAME_BACKCHANNEL_DYNAMIC`), deshalb steht in `KEYCLOAK_DISCOVERY_URL` die interne Adresse.
- Der Realm wird nur importiert, solange er noch nicht existiert. Spätere Änderungen an `verity-realm.json` oder an `KEYCLOAK_CLIENT_SECRET` wirken nicht mehr automatisch; dann in der Admin-Konsole anpassen (Client `fhir-verity` → „Credentials“).
- Wird `DOMAIN` später geändert, in der Admin-Konsole beim Client die Redirect-URI und die Web Origins nachziehen.
- Die Keycloak-Daten liegen im Volume `keycloak_pgdata`. Sicherung etwa mit `docker compose exec keycloak-db pg_dump -U keycloak keycloak > keycloak.sql`.

### Ohne Anmeldung (nur Entwicklung und Demo)

Mit `AUTH_ENABLED=false` gibt es keine Anmeldung. Das Backend arbeitet dann für jede Anfrage als eingebauter Benutzer `dev` mit der Rolle admin. Die
Keycloak-Variablen und `SESSION_SECRET_KEY` dürfen leer bleiben. Das bedeutet:

- Alle sehen und ändern alle Server, Läufe und Ressourcen; im Audit-Log steht immer `dev`.
- Die Oberfläche zeigt keine Login-Seite und kein „Sign out“, dafür einen gelben Hinweisbalken.
- Erlaubt nur mit `ENVIRONMENT=development`. Mit `production` bricht das Backend beim Start mit einer Fehlermeldung ab.
- Server, die in diesem Modus angelegt werden, gehören `dev`. Wird später auf `AUTH_ENABLED=true` umgestellt, sehen diese Server nur noch Admins.

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

`docker compose down` lässt die Volumes und damit die Datenbanken (auch die des mitgelieferten Keycloak) in Ruhe. `docker compose down -v` löscht auch die Volumes — dieser Zusatz darf in Produktion nie versehentlich verwendet werden.
