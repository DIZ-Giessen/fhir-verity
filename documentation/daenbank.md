# Datenbank

Verity nutzt PostgreSQL für seine eigenen Daten (Server, Läufe, invalide Ressourcen, Konfiguration, Benutzer, Audit). Diese Datenbank ist getrennt von
der Datenbank des geprüften FHIR-Servers — Verity fasst die FHIR-Server-DB nie direkt an, sondern spricht den Server ausschließlich über dessen HTTP-API an.

Es gibt zwei Wege, Verity an eine Datenbank zu bringen.

## Weg A: mitgelieferte Datenbank (Standard)

Im Docker-Betrieb bringt der Stack standardmäßig seine eigene PostgreSQL als Container mit. Beim allerersten Start liest das offizielle PostgreSQL-Image
drei Umgebungsvariablen aus und legt daraus Benutzer, Passwort und Datenbank automatisch an:

```bash
POSTGRES_USER      # dieser Benutzer wird angelegt
POSTGRES_PASSWORD  # mit diesem Passwort
POSTGRES_DB        # und diese Datenbank
```

Diese drei Werte kommen aus der `.env`. Es muss also nichts vorbereitet werden — weder eine Datenbank angelegt noch Rechte gesetzt. Der so angelegte Benutzer ist automatisch Eigentümer (Owner) der neuen Datenbank und darf im Schema `public` Tabellen anlegen. Das umgeht ein Berechtigungsproblem, das bei einer extern bereitgestellten Datenbank auftreten kann (siehe Weg B).

Wichtig für die Verbindung: Der Host in der `DATABASE_URL` ist der Compose-Servicename der Datenbank, nicht `localhost`:

```bash
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@db:5432/<dbname>
```

Der Benutzerteil dieser URL und die drei `POSTGRES_*`-Variablen müssen exakt zusammenpassen, sonst startet die Datenbank mit anderen Zugangsdaten, als das
Backend erwartet.

Die Daten liegen physisch im Docker-Volume `pgdata`, das die Container-Neustarts überlebt. Ein `docker compose down` lässt das Volume und damit die Daten in Ruhe. Nur `docker compose down -v` (mit `-v`) löscht auch die Volumes — dieser Zusatz darf in Produktion nie versehentlich verwendet werden.

Ein Detail, das gern übersehen wird: Die `POSTGRES_*`-Variablen wirken nur bei der **Erstinitialisierung** eines leeren Volumes. Ändert man später das Passwort
in der `.env`, ändert sich das Passwort der bereits bestehenden Datenbank im Volume nicht mit. Ein Passwortwechsel erfordert also entweder ein Setzen direkt in der Datenbank oder ein bewusstes Neuaufsetzen des Volumes.

## Weg B: bereits vorhandene, externe Datenbank

Manche Standorte haben bereits eine verwaltete PostgreSQL und wollen Verity dort eine eigene Datenbank geben, statt einen eigenen Container zu betreiben. In dem Fall entfällt der `db`-Service, und die `DATABASE_URL` zeigt auf den externen
Host.

In der Compose-Datei ist der `db`-Service für diesen Fall auskommentiert vorbereitet. Konkret gilt für Weg B:

- Den `db`-Service in `docker-compose.yml` auskommentiert lassen (oder
  entfernen).
- Beim Backend die `depends_on`-Bedingung auf `db` entfernen, sonst wartet Compose auf einen Dienst, den es nicht gibt.
- Das `pgdata`-Volume wird nicht benötigt.
- In der `.env` die `DATABASE_URL` auf den externen Host zeigen lassen:

```bash
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<externer-host>:5432/<dbname>
```

## Migrationen mit Alembic

Das Datenbankschema wird über Alembic-Migrationen verwaltet. Der Backend-Container führt beim Start automatisch `alembic upgrade head` aus (über
`docker-entrypoint.sh`), bevor die Anwendung startet. Auf einer frischen,leeren Datenbank legt das die komplette Struktur an; auf einer bestehenden
Datenbank werden nur die noch fehlenden Migrationen nachgezogen.

Wie man bei Schemaänderungen eine neue Migration erstellt und ausrollt, steht in [weiterentwicklung.md](weiterentwicklung.md).
