# Datenbankschema

Tabellen in Veritys eigener PostgreSQL-Datenbank. Das Schema wird ausschließlich über Alembic-Migrationen geändert (siehe [datenbank.md](datenbank.md)).
Alle Tabellen außer `server_members` und `invalid_resource_issues` haben zusätzlich `created_at` und `updated_at`.

## Überblick

```
users ─┬─< fhir_servers (owner_id) ─┬─< server_members >── users
       │                            ├─< validation_runs
       │                            ├─< validation_configs   (server_id NULL = globale Defaults)
       │                            ├─< invalid_resources ──< invalid_resource_issues
       └─< audit_logs (actor_id) >──┘   (server_id wird beim Löschen des Servers NULL)
```

Wird ein Server gelöscht, entfernt die Datenbank per `ON DELETE CASCADE` seine Läufe, Konfigurationen, Freigaben und invaliden Ressourcen.
Audit-Einträge bleiben erhalten.

## users

Lokales Abbild der Keycloak-Benutzer, angelegt beim ersten Login.

| Spalte                        | Bedeutung                                                    |
| ----------------------------- | ------------------------------------------------------------ |
| `id`                          | UUID                                                         |
| `keycloak_sub`                | `sub` aus Keycloak, eindeutig                                |
| `username`, `email`, `full_name` | aus den Claims, bei jedem Login aktualisiert              |
| `role`                        | `viewer`, `editor` oder `admin`                              |
| `email_notifications_enabled` | E-Mail nach Abschluss eigener Läufe                          |

## fhir_servers

| Spalte               | Bedeutung                                                                     |
| -------------------- | ----------------------------------------------------------------------------- |
| `name`, `project_id` | Anzeige und Zuordnung                                                         |
| `base_url`           | eindeutig                                                                     |
| `auth_config`        | Zugangsdaten zum FHIR-Server, mit `FIELD_ENCRYPTION_KEY` verschlüsselt (Fernet) |
| `is_active`          | inaktive Server lassen sich nicht validieren                                  |
| `write_fhir_reports` | TestScript, TestReport und List nach jedem Lauf auf den Server schreiben      |
| `owner_id`           | → `users.id`, `SET NULL`                                                      |

## server_members

Freigaben eines Servers für weitere Benutzer. Eindeutig je `(server_id, user_id)`.

| Spalte        | Bedeutung                                   |
| ------------- | ------------------------------------------- |
| `server_id`   | → `fhir_servers.id`, `CASCADE`              |
| `user_id`     | → `users.id`, `CASCADE`                     |
| `added_by_id` | wer freigegeben hat, → `users.id`, `SET NULL` |

## validation_configs

Regelkonfiguration je Ressourcentyp. Eindeutig je `(server_id, resource_type)`.

| Spalte          | Bedeutung                                                                         |
| --------------- | --------------------------------------------------------------------------------- |
| `server_id`     | `NULL` = globale Defaults (beim Start aus `config_defaults.py` angelegt), sonst Override |
| `resource_type` | z. B. `Patient`                                                                   |
| `rules`         | `{regel: {enabled, severity, category, description, pattern?}}`                   |
| `filters`       | Suchfilter für den Crawl (`_lastUpdated`, `_profile`, `_tag`)                     |

## validation_runs

| Spalte                           | Bedeutung                                                                |
| -------------------------------- | ------------------------------------------------------------------------ |
| `server_id`                      | → `fhir_servers.id`, `CASCADE`; höchstens ein Lauf je Server mit `running` |
| `resource_types`                 | geprüfte Typen oder `["All"]`                                            |
| `status`                         | `running`, `completed`, `failed`, `cancelled`                            |
| `total_processed`, `total_invalid` | Zähler über alle Typen                                                 |
| `per_resource_stats`             | Zähler je Typ                                                            |
| `rule_stats`                     | Verstöße je Typ und Regel                                                |
| `checkpoint`                     | `_lastUpdated`-Wasserstand je Typ, für das Fortsetzen                    |
| `cancel_requested`               | Abbruch angefordert                                                      |
| `test_report`                    | Zusammenfassung der FHIR-Reports (IDs, Ergebnis, Score)                  |
| `triggered_by_id`                | → `users.id`, `SET NULL`                                                 |

## invalid_resources

Eine Zeile je invalider Ressource und Server, eindeutig je `(server_id, resource_type, resource_id)`. Ein späterer vollständiger Lauf (ohne
Filter), der die Ressource nicht mehr bemängelt, entfernt die Zeile.

| Spalte                                   | Bedeutung                                         |
| ---------------------------------------- | ------------------------------------------------- |
| `server_id`                              | → `fhir_servers.id`, `CASCADE`                    |
| `issues`                                 | Befunde des letzten Laufs                         |
| `metrics`                                | `{regel: true/false}` je aktiver Regel            |
| `first_seen_run_id`, `first_seen_at`     | erster Lauf, der die Ressource bemängelt hat      |
| `last_seen_run_id`, `last_seen_at`       | letzter Lauf, der sie bestätigt hat               |

## invalid_resource_issues

Normalisierte Befunde für schnelle Filter und Zählungen.

| Spalte                | Bedeutung                              |
| --------------------- | -------------------------------------- |
| `invalid_resource_id` | → `invalid_resources.id`, `CASCADE`    |
| `rule`, `severity`    | Regel und Schwere des Befunds          |

## audit_logs

| Spalte                          | Bedeutung                                                                                   |
| ------------------------------- | ------------------------------------------------------------------------------------------- |
| `server_id`                     | → `fhir_servers.id`, `SET NULL`                                                             |
| `server_base_url`               | URL des Servers zum Zeitpunkt der Aktion; `NULL` bei Rollenänderungen                       |
| `resource_type`, `resource_id`  | Ziel: FHIR-Ressource, bei Verwaltungsaktionen `Server` bzw. `User`                          |
| `action`                        | `DELETE`, `PATCH`, `BULK_DELETE`, `BULK_PATCH`, `SERVER_DELETE`, `SERVER_AUTH_CHANGE`, `SERVER_SHARE`, `SERVER_UNSHARE`, `USER_ROLE_CHANGE` |
| `fhir_request_payload`          | gesendeter Patch, Zusammenfassung einer Sammelaktion oder Details der Verwaltungsaktion      |
| `fhir_response_status`          | HTTP-Status des FHIR-Servers                                                                |
| `resource_before`               | Zustand vor der Änderung                                                                    |
| `status`                        | `SUCCESS` oder `FAILED`                                                                     |
| `error_message`, `reason`       | Fehlermeldung und angegebene Begründung                                                     |
| `actor_id`                      | → `users.id`, `SET NULL`                                                                    |
| `executed_at`                   | Zeitpunkt                                                                                   |
