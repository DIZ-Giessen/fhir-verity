# Datenbank

Verity nutzt PostgreSQL für seine eigenen Daten (Server, Läufe, invalide Ressourcen, Konfiguration, Benutzer, Audit). Diese Datenbank ist getrennt von
der Datenbank des geprüften FHIR-Servers — Verity fasst die FHIR-Server-DB nie direkt an, sondern spricht den Server ausschließlich über dessen HTTP-API an.

Es gibt zwei Wege, Verity an eine Datenbank zu bringen.

## Weg A: externe Datenbank (Standard)

Die meisten Standorte betreiben bereits eine verwaltete PostgreSQL mit Backups und Monitoring. Verity bekommt dort eine eigene Datenbank; die `docker-compose.yml` ist für diesen Weg vorbereitet und muss nicht angepasst werden. In der `.env` zeigt die `DATABASE_URL` auf den externen Host:

```bash
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<externer-host>:5432/<dbname>
```

Der Verity-Benutzer muss im Schema Tabellen anlegen dürfen, sonst scheitert die erste Migration mit `permission denied for schema public`. Seit PostgreSQL 15 hat `PUBLIC` dort standardmäßig kein CREATE-Recht mehr. Einmalig als Datenbank-Administrator ausführen:

```sql
CREATE USER verity WITH PASSWORD '<passwort>';
CREATE DATABASE verity OWNER verity;
\c verity
ALTER SCHEMA public OWNER TO verity;
```

Soll die Datenbank einem anderen Benutzer gehören, reicht statt der letzten Zeile `GRANT USAGE, CREATE ON SCHEMA public TO verity;`.

## Weg B: mitgelieferte Datenbank

Für Standorte ohne eigene PostgreSQL bringt der Stack einen Datenbank-Container mit. Er steht in der `docker-compose.yml` auskommentiert bereit; dafür die drei mit „Weg B“ markierten Blöcke einkommentieren (den `db`-Service, das `depends_on` beim `backend` und das Volume `pgdata`).

Beim allerersten Start liest das offizielle PostgreSQL-Image drei Umgebungsvariablen aus und legt daraus Benutzer, Passwort und Datenbank automatisch an:

```bash
POSTGRES_USER      # dieser Benutzer wird angelegt
POSTGRES_PASSWORD  # mit diesem Passwort
POSTGRES_DB        # und diese Datenbank
```

Diese drei Werte kommen aus der `.env`. Es muss also nichts vorbereitet werden — weder eine Datenbank angelegt noch Rechte gesetzt. Der so angelegte Benutzer ist automatisch Eigentümer der neuen Datenbank, das Rechteproblem aus Weg A tritt nicht auf.

Wichtig für die Verbindung: Der Host in der `DATABASE_URL` ist der Compose-Servicename der Datenbank, nicht `localhost`:

```bash
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@db:5432/<dbname>
```

Der Benutzerteil dieser URL und die drei `POSTGRES_*`-Variablen müssen exakt zusammenpassen, sonst startet die Datenbank mit anderen Zugangsdaten, als das Backend erwartet.

Die Daten liegen physisch im Docker-Volume `pgdata`, das die Container-Neustarts überlebt. Ein `docker compose down` lässt das Volume und damit die Daten in Ruhe. Nur `docker compose down -v` (mit `-v`) löscht auch die Volumes — dieser Zusatz darf in Produktion nie versehentlich verwendet werden. Backups sind bei diesem Weg Sache des Standorts, zum Beispiel:

```bash
docker compose exec db pg_dump -U <user> <dbname> > verity-backup.sql
```

Ein Detail, das gern übersehen wird: Die `POSTGRES_*`-Variablen wirken nur bei der **Erstinitialisierung** eines leeren Volumes. Ändert man später das Passwort in der `.env`, ändert sich das Passwort der bereits bestehenden Datenbank im Volume nicht mit. Ein Passwortwechsel erfordert also entweder ein Setzen direkt in der Datenbank oder ein bewusstes Neuaufsetzen des Volumes.

## Migrationen mit Alembic

Das Datenbankschema wird über Alembic-Migrationen verwaltet. Der Backend-Container führt beim Start automatisch `alembic upgrade head` aus (über
`docker-entrypoint.sh`), bevor die Anwendung startet. Auf einer frischen, leeren Datenbank legt das die komplette Struktur an; auf einer bestehenden
Datenbank werden nur die noch fehlenden Migrationen nachgezogen.

Eine neue Migration nach einer Modelländerung:

```bash
cd backend
alembic revision --autogenerate -m "kurze beschreibung"
# erzeugte Datei unter alembic/versions/ prüfen, dann
alembic upgrade head
```
