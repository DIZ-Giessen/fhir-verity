# Features

last Updated 23.10.2026

## Regelbasierte Validierung

Der Kern von Verity ist eine konfigurierbare Regel-Engine mit rund 290 Regeln für 14 Ressourcentypen, abgeleitet aus den Profilen des
MII-Kerndatensatzes. Für jeden Server lässt sich festlegen, welche Regeln geprüft werden. Die Regeln verteilen sich auf fünf
**Qualitätsdimensionen**. Jede einzelne Regel steht in [validierungsregeln.md](validierungsregeln.md).

### 1. Datenschutz und Pseudonymisierung

Prüft, ob Ressourcen tatsächlich pseudonymisiert sind und keine Klarnamen oder andere identifizierende Daten in Feldern auftauchen, in denen sie nicht stehen dürfen — etwa Namen in einem `valueString`, einem Kommentar oder einem sonst freien Textfeld. Diese Dimension ist am DIZ die wichtigste, weil ein
verbliebener Klarname ein echtes Datenschutzproblem ist und nicht nur ein formaler Mangel.

### 2. Vollständigkeit

Prüft, ob Pflichtfelder und für die Nachnutzung notwendige Angaben gefüllt sind. Eine Ressource kann formal gültig sein und trotzdem für Auswertungen unbrauchbar, wenn zentrale Felder fehlen.

### 3. Codierung

Prüft, ob Codes aus dem erwarteten Codesystem stammen und richtig aufgebaut sind: ICD-10-GM und OPS mit Katalogversion und gültigem Format, LOINC
für Laborwerte, PZN und ATC für Medikamente, UCUM für Einheiten, SNOMED CT für Probenart und Körperstelle, erlaubte Statuswerte.

### 4. Plausibilität

Prüft, ob Werte inhaltlich sinnvoll sind — zum Beispiel, ob ein Zeitraum zeitlich stimmig ist (Ende nicht vor Beginn), ein Datum nicht in der Zukunft
liegt oder ein Geburtsdatum in einem plausiblen Bereich. Dazu gehören die Invarianten der FHIR- und MII-Profile, etwa dass ein abgeschlossener
Fall ein Ende hat.

### 5. Referentielle Integrität

Prüft, ob Referenzen zwischen Ressourcen die erwartete Form haben, etwa `subject.reference` als `Patient/<id>`. Ob die verwiesene Ressource auf dem
Server existiert, wird derzeit nicht geprüft.

## Unterstützte Ressourcentypen

| Modul des MII-Kerndatensatzes | Ressourcentypen                                                              |
| ----------------------------- | ---------------------------------------------------------------------------- |
| Person                        | Patient                                                                      |
| Fall                          | Encounter                                                                    |
| Diagnose                      | Condition                                                                    |
| Prozedur                      | Procedure                                                                    |
| Laborbefund                   | Observation, DiagnosticReport, ServiceRequest                                |
| Medikation                    | Medication, MedicationRequest, MedicationAdministration, MedicationStatement |
| Biobank                       | Specimen                                                                     |
| Consent                       | Consent                                                                      |
| Bildgebung                    | ImagingStudy                                                                 |

Ab Werk sind nur die grundlegenden Regeln aktiv. Alle weiteren, darunter die Prüfungen der Codierung und der MII-Invarianten, schaltet jeder
Standort auf der Konfigurationsseite eines Servers ein; Regeln lassen sich dort suchen und kategorienweise an- und ausschalten.

```bash
## Sie möchten weitere Ressourcentypen oder Validierungsmetriken prüfen? Kein Problem – klonen Sie einfach das Repository und passen Sie die Konfiguration nach Ihren Anforderungen an. Oder erstellen Sie gerne ein Issue mit Ihrem Wunsch, damit wir ihn gemeinsam umsetzen können.

```

## Konfigurierbarkeit

Jede Regel ist im Code einmal definiert, zusammen mit ihrer Prüflogik und ihren Standardwerten. Pro Server lässt sich jede Regel an- und
ausschalten, ihre Schwere ändern und bei Muster-Regeln das Muster anpassen. Neue Regeln aus einem Update erscheinen sofort in der Oberfläche,
ohne dass bestehende Einstellungen verloren gehen.

## Server-weiter Crawl

Verity liest den kompletten Bestand eines Servers, nicht nur Stichproben. Das ist technisch der anspruchsvollste Teil, weil ein Lauf über Millionen von
Ressourcen Stunden bis Tage dauern kann und dabei zuverlässig bleiben muss.

Die Paginierung erfolgt über einen Zeitstempel-Wasserzeichen-Ansatz auf Basis von `_lastUpdated` (keyset pagination), nicht über die serverseitigen
Paging-Tokens. Der Hintergrund: Manche FHIR-Server (etwa Blaze) verwenden opake Paging-Cursor, deren Schlüssel nach einiger Zeit rotieren und die damit
für lange Läufe unzuverlässig sind. Der Wasserzeichen-Ansatz ist gegen dieses Verhalten robust.

Zur Ausfallsicherheit gehören außerdem: erneute Versuche mit exponentiell wachsender Wartezeit bei Serverfehlern, kooperatives Abbrechen eines laufenden
Vorgangs, ein Wiederaufnahme-Endpunkt für unterbrochene Läufe und regelmäßige Persistenz des Fortschritts (Checkpoints), sodass ein abgebrochener Lauf nicht von vorn beginnen muss.

## Live-Fortschritt

Während ein Lauf arbeitet, wird der Fortschritt über WebSocket live an die Oberfläche gemeldet. Die Verbindung baut sich bei Unterbrechung automatisch
wieder auf.

## FHIR-konforme Reports

Nach Abschluss erzeugt Verity Report-Ressourcen im FHIR-Format und schreibt sie auf den geprüften Server zurück. Die Qualitätsbewertung wird dadurch
selbst Teil des FHIR-Bestands und ist von anderen Systemen weiterverwendbar, statt nur in Veritys eigener Datenbank zu liegen.

| Ressource    | Anzahl                                  | Inhalt                                                                          |
| ------------ | --------------------------------------- | ------------------------------------------------------------------------------- |
| `TestScript` | eine je Ressourcentyp und Konfiguration | die aktiven Regeln mit Beschreibung, Kategorie und Schwere                      |
| `TestReport` | eine je Ressourcentyp und Lauf          | Ergebnis je Regel mit Anzahl der Verstöße, Score (Anteil valider Ressourcen)    |
| `List`       | eine je Lauf                            | verweist auf alle TestReports des Laufs; die Lauf-ID steht in `List.identifier` |

Ein TestScript wird nicht bei jedem Lauf neu angelegt. Seine `version` ist ein Hash über die aktiven Regeln; vor dem Schreiben sucht Verity auf dem
Server nach einem TestScript mit derselben `url` und `version` und verwendet es wieder. Erst wenn sich die Regelkonfiguration ändert, entsteht eine
neue Version.

Das Zurückschreiben lässt sich pro Server in der Validierungskonfiguration abschalten („Write FHIR reports to the server“), etwa für schreibgeschützte oder produktive Server, auf denen Verity keine Ressourcen anlegen darf. Die Reports werden dann trotzdem berechnet; Score und Ergebnis jedes Laufs bleiben in Verity sichtbar. Der Herausgeber der Reports kommt aus `FHIR_REPORT_PUBLISHER` in der `.env`. `TestScript.url`, Identifier-Systeme und Extension-URLs bauen auf `VERITY_CANONICAL_BASE` auf, standardmäßig die Projekt-URL. Diese Basis ist fest und hängt nicht davon ab, unter welcher Adresse Verity läuft.

## Bereinigungs-Workflow

Für die invaliden Ressourcen gibt es einen Bereinigungs-Workflow mit Sammelaktionen (Löschen oder Korrigieren mehrerer Ressourcen). Vor der
Ausführung gibt es einen Probelauf-Modus (dry run), der zeigt, was passieren würde, ohne etwas zu verändern. Einzelaktionen werden mit
dem exakten FHIR-Befehl, dem Zustand vor der Änderung und dem Ergebnis protokolliert. Eine Sammelaktion erzeugt genau einen Audit-Eintrag mit Filter, allen geänderten Ressourcen und den Fehlern, damit das Log auch bei zehntausenden Ressourcen übersichtlich bleibt (siehe Audit in [rollenverwaltung.md](rollenverwaltung.md)).
Destruktive Aktionen laufen nie unbemerkt, sondern immer nachvollziehbar und protokolliert.

## Oberfläche

Die Weboberfläche umfasst unter anderem eine Serverliste mit Detailansichten, eine Laufliste mit Auswertungsdiagrammen, eine Detailansicht je Lauf, eine Seite mit den invaliden Ressourcen samt serverseitiger Paginierung und Filtern, den Live-Fortschrittsmonitor, die Bereinigungsseite, das Audit-Log, die
Benutzerverwaltung mit Rollenzuweisung und eine Einstellung für E-Mail-Benachrichtigungen je Benutzer.

## E-Mail-Benachrichtigungen

Benutzer können sich optional per E-Mail benachrichtigen lassen. Der Versand läuft über den internen SMTP-Server des Standorts. Die Zustellung istopt-in.
