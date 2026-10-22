# Datenbank bereinigen

Mit jedem Lauf sammelt Verity die invaliden Ressourcen in der Tabelle `invalid_resources`. Einträge, die ein späterer Lauf nicht mehr bestätigt, räumt Verity selbst auf. Was trotzdem liegen bleibt, etwa alte Einträge eines Ressourcentyps, der nicht mehr geprüft wird, oder Altlasten aus Testläufen, lässt sich direkt per SQL entfernen.

Das betrifft nur Veritys eigene Datenbank. Der FHIR-Server wird dabei nicht angefasst; zum Löschen oder Korrigieren auf dem FHIR-Server ist die Cleanup-Seite da.

Direkte Löschungen in der Datenbank erscheinen **nicht** im Audit-Log von Verity.

## Verbindung zur Datenbank

Welche Datenbank Verity nutzt, steht in [datenbank.md](datenbank.md).

**Option A, externe Datenbank:** mit `psql` direkt auf den Host aus der `DATABASE_URL`. Dabei den Treiberteil `+asyncpg` weglassen:

```bash
psql "postgresql://<user>:<pass>@<externer-host>:5432/<dbname>"
```

**Option B, mitgelieferte Datenbank:** `psql` im Datenbank-Container. Benutzer und Datenbank kommen aus den `POSTGRES_*`-Variablen des Containers:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Die übrigen Schritte sind für beide Optionen gleich.

## Tabellen

| Tabelle                   | Inhalt                                                                                  |
| ------------------------- | --------------------------------------------------------------------------------------- |
| `invalid_resources`       | eine Zeile je invalider Ressource und Server, mit `resource_type`, `last_seen_at` u. a. |
| `invalid_resource_issues` | eine Zeile je Regelverstoß (`rule`, `severity`), hängt an `invalid_resources`           |
| `fhir_servers`            | die registrierten Server, für die `id` zum Filtern                                      |

`invalid_resource_issues` hängt per `ON DELETE CASCADE` an `invalid_resources`. Gelöscht wird deshalb immer nur in `invalid_resources`; die zugehörigen Verstöße verschwinden automatisch mit.

## Vorgehen

Zuerst die Server-ID heraussuchen:

```sql
SELECT id, name, base_url FROM fhir_servers;
```

Dann immer in einer Transaktion arbeiten und vor dem `COMMIT` prüfen, wie viele Zeilen betroffen sind. `DELETE` meldet die Anzahl (`DELETE 1234`). Passt sie nicht, macht `ROLLBACK` alles rückgängig.

```sql
BEGIN;

-- 1. Vorschau: wie viele Einträge passen?
SELECT count(*)
FROM invalid_resources
WHERE server_id = '<server-id>'
  AND resource_type = 'Encounter';

-- 2. Löschen mit genau derselben Bedingung
DELETE FROM invalid_resources
WHERE server_id = '<server-id>'
  AND resource_type = 'Encounter';

-- 3. Passt die Zahl? Dann:
COMMIT;
-- sonst:
-- ROLLBACK;
```

## Häufige Filter

Die Bedingungen lassen sich frei kombinieren. Sie gehören jeweils in die `WHERE`-Klausel von Vorschau und `DELETE`.

Alles eines Servers:

```sql
WHERE server_id = '<server-id>'
```

Einträge, die seit einem Stichtag kein Lauf mehr bestätigt hat:

```sql
WHERE server_id = '<server-id>'
  AND last_seen_at < '2026-01-01'
```

Ressourcen, die gegen eine bestimmte Regel verstoßen:

```sql
WHERE server_id = '<server-id>'
  AND EXISTS (
    SELECT 1 FROM invalid_resource_issues i
    WHERE i.invalid_resource_id = invalid_resources.id
      AND i.rule = 'period_end_after_start'
  )
```

Ressourcen mit mindestens einem Verstoß einer bestimmten Schwere (`error`, `warning`, `info`):

```sql
WHERE server_id = '<server-id>'
  AND EXISTS (
    SELECT 1 FROM invalid_resource_issues i
    WHERE i.invalid_resource_id = invalid_resources.id
      AND i.severity = 'info'
  )
```

## Speicher freigeben

PostgreSQL gibt den Platz gelöschter Zeilen nicht sofort an das Betriebssystem zurück, sondern verwendet ihn für neue Zeilen wieder. Nach einer großen Bereinigung aktualisiert ein `VACUUM` die Statistiken und macht den Platz verfügbar:

```sql
VACUUM ANALYZE invalid_resources;
VACUUM ANALYZE invalid_resource_issues;
```

Bei einer externen Datenbank (Option A) gehört das gegebenenfalls mit dem Betreiber der Datenbank abgestimmt.
