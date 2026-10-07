# Datenbankschema

Dieses Dokument beschreibt die Tabellen, die Verity in seiner eigenen PostgreSQL anlegt. Sie entstehen aus den SQLAlchemy-Modellen über die Alembic-Initial-Migration. Stand: 07.2026

Alle Tabellen verwenden UUID-Primärschlüssel und führen `created_at` und `updated_at` als Zeitstempel mit Zeitzone.

## users

Die Benutzer, die sich über Keycloak anmelden.

| **Spalte**                  | **Typ**   | **Bemerkung**                                                 |
| --------------------------- | --------- | ------------------------------------------------------------- |
| id                          | UUID      | Primärschlüssel                                               |
| keycloak_sub                | String    | eindeutiger Keycloak-Subject-Identifier, indexiert und unique |
| username                    | String    | optional                                                      |
| email                       | String    | optional                                                      |
| full_name                   | String    | optional                                                      |
| email_notifications_enabled | Boolean   | Standard false, opt-in                                        |
| role                        | String    | Rolle: viewer, editor oder admin                              |
| created_at / updated_at     | Timestamp |                                                               |

## fhir_servers

Die in Verity registrierten FHIR-Server.

| Spalte                  | Typ       | Bemerkung                                                  |
| ----------------------- | --------- | ---------------------------------------------------------- |
| id                      | UUID      | Primärschlüssel                                            |
| name                    | String    | Anzeigename                                                |
| base_url                | String    | Basis-URL des FHIR-Servers, unique                         |
| project_id              | String    | Projekt-/Mandantenkennung                                  |
| auth_config             | JSON      | optionale Authentifizierung gegenüber dem FHIR-Server      |
| is_active               | Boolean   |                                                            |
| write_fhir_reports      | Boolean   | Reports nach jedem Lauf auf den Server schreiben (Standard: ja) |
| owner_id                | UUID      | Verweis auf users, bei Löschung des Users auf NULL gesetzt |
| created_at / updated_at | Timestamp |                                                            |

Der `owner_id`-Verweis ist die Grundlage der Server-Ownership (siehe[rollenverwaltung.md](rollenverwaltung.md)).

## validation_configs

Die Regelkonfiguration je Ressourcentyp, optional pro Server.

| Spalte                  | Typ       | Bemerkung                                                             |
| ----------------------- | --------- | --------------------------------------------------------------------- |
| id                      | UUID      | Primärschlüssel                                                       |
| server_id               | UUID      | Verweis auf fhir_servers; NULL bedeutet globale Standardkonfiguration |
| resource_type           | String    | z. B. Patient, Observation                                            |
| filters                 | JSON      | Einschränkung, welche Ressourcen geprüft werden                       |
| rules                   | JSON      | die eigentlichen Regeln                                               |
| created_at / updated_at | Timestamp |                                                                       |

Eindeutig je Kombination aus `server_id` und `resource_type`. Ein `server_id` von NULL steht für die globale Grundkonfiguration, die beim ersten Start mit den MII-KDS-Defaults befüllt wird; ein gesetzter `server_id` überschreibt diese für einen bestimmten Server. Bei Löschung des Servers werden die zugehörigen Konfigurationen mitgelöscht (ON DELETE CASCADE).

## validation_runs

Ein einzelner Validierungslauf.

| Spalte                   | Typ       | Bemerkung                                   |
| ------------------------ | --------- | ------------------------------------------- |
| id                       | UUID      | Primärschlüssel                             |
| server_id                | UUID      | Verweis auf fhir_servers (ON DELETE CASCADE) |
| resource_types           | JSON      | geprüfte Ressourcentypen                    |
| total_processed          | Integer   | Anzahl geprüfter Ressourcen                 |
| total_invalid            | Integer   | Anzahl invalider Ressourcen                 |
| status                   | Enum      | RUNNING, COMPLETED, FAILED, CANCELLED       |
| started_at / finished_at | Timestamp | Beginn und Ende                             |
| verification_result      | JSON      | erzeugter FHIR-VerificationResult           |
| test_report              | JSON      | erzeugter FHIR-TestReport                   |
| error_message            | String    | im Fehlerfall                               |
| per_resource_stats       | JSON      | Kennzahlen je Ressourcentyp                 |
| checkpoint               | JSON      | Fortschritt zur Wiederaufnahme              |
| triggered_by_id          | UUID      | auslösender Benutzer, bei Löschung auf NULL |
| created_at / updated_at  | Timestamp |                                             |

Das `checkpoint`-Feld ist die Grundlage der Wiederaufnahme unterbrochener Läufe; `per_resource_stats` speist die Auswertungsdiagramme.

## invalid_resources

Die als invalide erkannten Ressourcen, dedupliziert je Server.

| Spalte                  | Typ       | Bemerkung                                 |
| ----------------------- | --------- | ----------------------------------------- |
| id                      | UUID      | Primärschlüssel                           |
| server_id               | UUID      | Verweis auf fhir_servers                  |
| server_base_url         | String    | zur Nachvollziehbarkeit mitgeführt        |
| resource_type           | String    | Typ der Ressource                         |
| resource_id             | String    | ID der Ressource auf dem FHIR-Server      |
| issues                  | JSON      | die konkreten Befunde                     |
| metrics                 | JSON      | Kennzahlen zur Ressource                  |
| raw_resource            | JSON      | optional die Ressource selbst             |
| anomaly_score           | Float     | optional, für ML-Ausblick vorgesehen      |
| risk_score              | Float     | optional, für ML-Ausblick vorgesehen      |
| llm_suggestions         | JSON      | optional, für LLM-Ausblick vorgesehen     |
| first_seen_run_id       | UUID      | Lauf, in dem die Ressource zuerst auffiel |
| first_seen_at           | Timestamp |                                           |
| last_seen_run_id        | UUID      | Lauf, in dem sie zuletzt auffiel          |
| last_seen_at            | Timestamp |                                           |
| created_at / updated_at | Timestamp |                                           |

Eindeutig je Kombination aus `server_id`, `resource_type` und `resource_id`. Diese Deduplizierung ist bewusst so gewählt: Eine Ressource, die über mehrere
Läufe hinweg invalide bleibt, erzeugt keinen Doppeleintrag, sondern wird über `first_seen`/`last_seen` fortgeschrieben. Bei Löschung des Servers werden die Einträge mitgelöscht (ON DELETE CASCADE). Die Felder `anomaly_score`, `risk_score` und `llm_suggestions` sind für den ML-/LLM-Ausblick vorgesehen und
im aktuellen Kern nicht befüllt.

## audit_logs

Protokoll aller ausgeführten Bereinigungsaktionen.

| Spalte                  | Typ       | Bemerkung                                    |
| ----------------------- | --------- | -------------------------------------------- |
| id                      | UUID      | Primärschlüssel                              |
| server_id               | UUID      | Verweis auf fhir_servers                     |
| server_base_url         | String    | mitgeführt                                   |
| resource_type           | String    |                                              |
| resource_id             | String    |                                              |
| triggering_run_id       | UUID      | optional auslösender Lauf                    |
| invalid_resource_id     | UUID      | optional zugehöriger Invalid-Eintrag         |
| action                  | Enum      | DELETE, PATCH, BULK_DELETE, BULK_PATCH, PURGE |
| fhir_request_payload    | JSON      | der tatsächlich gesendete FHIR-Befehl        |
| fhir_response_status    | String    | Antwortstatus des FHIR-Servers               |
| resource_before         | JSON      | Zustand vor der Änderung                     |
| status                  | Enum      | SUCCESS oder FAILED                          |
| error_message           | Text      | im Fehlerfall                                |
| reason                  | Text      | Begründung der Aktion                        |
| actor_id                | UUID      | ausführender Benutzer, bei Löschung auf NULL |
| executed_at             | Timestamp | Ausführungszeitpunkt                         |
| created_at / updated_at | Timestamp |                                              |

Das Audit-Log ist bewusst umfangreich: Für jede Einzelaktion (DELETE, PATCH) werden der gesendete Befehl, der Zustand davor, das Ergebnis, die Begründung und der
ausführende Benutzer festgehalten. Damit ist jede Änderung am FHIR-Bestand nachvollziehbar.

Sammelaktionen (BULK_DELETE, BULK_PATCH) und die DB-Bereinigung (PURGE) schreiben dagegen genau **einen** Eintrag pro Vorgang, egal ob 10 oder 50.000 Ressourcen betroffen sind. In `fhir_request_payload` stehen dann der verwendete Filter, die Anzahl der Treffer, Erfolge und Fehler, die Liste aller geänderten Ressourcen (`Typ/id`) sowie die Fehlschläge gruppiert nach Fehlermeldung. `resource_before` bleibt bei Sammelaktionen leer; die vorherigen Versionen hält der FHIR-Server selbst in seiner Versionshistorie (`GET [Typ]/[id]/_history`).

Wird ein Server gelöscht, entfernt die Datenbank per ON DELETE CASCADE alle zugehörigen Läufe, invaliden Ressourcen, Konfigurationen und Audit-Einträge.

## Beziehungen auf einen Blick

`users` und `fhir_servers` sind die Basistabellen. `fhir_servers` verweist über`owner_id` auf `users`. `validation_configs`, `validation_runs`,
`invalid_resources` und `audit_logs` verweisen jeweils auf `fhir_servers`;
Läufe und Audit-Einträge verweisen zusätzlich auf den auslösenden bzw. ausführenden Benutzer. Diese Reihenfolge — erst die Basistabellen, dann die
abhängigen — ist auch die Reihenfolge, in der die Initial-Migration die Tabellen
anlegt, damit die Fremdschlüssel auflösbar sind.
