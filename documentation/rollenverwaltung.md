# Rollenverwaltung und Zugriffskontrolle

## Anmeldung über Keycloak

Die Authentifizierung läuft über Keycloak per OpenID Connect im Backend-for-Frontend-Muster (BFF). Das Backend führt den OIDC-Ablauf durch und
hält eine serverseitige Session; das Frontend besitzt kein Token, sondern nur ein Session-Cookie. Der Ablauf im Einzelnen:

1. Das Frontend ruft `/api/v1/auth/login` auf.
2. Das Backend leitet zu Keycloak weiter.
3. Nach erfolgreicher Anmeldung leitet Keycloak zurück auf
   `/api/v1/auth/callback`.
4. Das Backend legt bzw. aktualisiert den Benutzer, setzt das Session-Cookie und leitet zurück in die Oberfläche.

`/api/v1/auth/me` liefert den aktuell angemeldeten Benutzer; ist niemand angemeldet, antwortet der Endpunkt mit 401 — das ist der Normalfall, solange
kein Login stattgefunden hat, und kein Fehler.

Das Session-Cookie wird im Produktionsmodus mit dem `Secure`-Flag gesetzt und erfordert damit HTTPS. Das ist der Grund, warum der Produktionsbetrieb zwingend über HTTPS läuft.

Wer keinen eigenen Keycloak hat, nutzt den mitgelieferten (siehe [deployment.md](deployment.md#weg-2-mitgelieferter-keycloak)). Rollen, Ownership und
Audit funktionieren damit genauso.

### Entwicklungsmodus ohne Keycloak

Für lokale Entwicklung und Demos lässt sich die Anmeldung mit `AUTH_ENABLED=false` abschalten. Dann gilt:

- Jede Anfrage läuft als eingebauter Benutzer `dev` (feste ID `00000000-0000-0000-0000-000000000000`, Rolle **admin**). Er wird beim Start in der
  Datenbank angelegt, damit Eigentümer- und Audit-Einträge auf ihn verweisen können, und bleibt immer admin.
- Es gibt keine Trennung nach Benutzern: alle sehen alle Server, Läufe und Audit-Einträge.
- `/api/v1/auth/config` meldet `auth_enabled: false`. Die Oberfläche blendet daraufhin Login-Seite und „Sign out“ aus und zeigt einen Hinweisbalken.
- Keycloak-Variablen und `SESSION_SECRET_KEY` werden nicht gebraucht.
- Mit `ENVIRONMENT=production` startet das Backend in diesem Modus nicht.

Beim Wechsel zurück auf `AUTH_ENABLED=true` bleibt `dev` in der Datenbank, taucht aber in der Benutzerverwaltung nicht mehr auf und zählt nicht als
Admin. Server, die unter `dev` angelegt wurden, sind dann nur noch für Admins sichtbar.

## Die drei Rollen

Verity kennt drei Rollen mit aufsteigenden Rechten:

- **viewer** — Lesezugriff. Kann nur seine Server, Läufe und invalide Ressourcen einsehen
  und Validierungen betrachten.
- **editor** — zusätzlich Schreibzugriff auf die Konfiguration. Kann Validierungsregeln anpassen und die FHIR ressourcen fixen bzw reparieren aber auf dem Server, der er erstellt hat
- **admin** — zusätzlich Benutzerverwaltung. Kann Rollen zuweisen und Benutzer verwalten. Alle Server sehen die erstellt wurden und auch kann auch die Ressourcen löschen fixen bzw reparieren für alle Server.

Die Rechte werden im Backend beim Einbinden der jeweiligen Router durchgesetzt. Lesende Bereiche (Server, Validierung, Bereinigungsaktionen) verlangen
mindestens viewer, die Konfiguration verlangt editor, die Benutzerverwaltung ist den Administratoren vorbehalten.

## Erste Administratoren

Damit es überhaupt jemanden gibt, der Rollen vergeben kann, wird über die `.env`-Variable `INITIAL_ADMIN_USERS` festgelegt, welche Benutzer beim ersten
Login automatisch die admin-Rolle erhalten. Verglichen wird mit dem Benutzernamen und der E-Mail-Adresse, die Keycloak zurückliefert, ohne Beachtung der
Groß-/Kleinschreibung. Mehrere Einträge werden durch Komma getrennt. Beim mitgelieferten Keycloak ist das `verity-admin`.

```bash
#  Beispiel: INITIAL_ADMIN_USERS=meine-email@institut.de,admin2@institut.de
#  Um mehrere Benutzer als Administratoren festzulegen, können sie per Komma getrennt angegeben werden.
#  Die Zuweisung weiterer Admins kann später komfortabel über die Benutzerverwaltung in der Oberfläche erfolgen.
```

## Server-Ownership

Jeder registrierte FHIR-Server hat optional einen Eigentümer (`owner_id`). Der Zugriff auf einen Server ist an diese Ownership gebunden: Ein Benutzer(viewer/editor) sieht und bearbeitet nur die Server, für die er berechtigt ist.

Ein wichtiges Detail bei der Umsetzung: Greift ein Benutzer auf einen Server zu, für den er nicht berechtigt ist, antwortet das Backend mit **404 Not Found**, nicht mit 403 Forbidden. Der Grund ist bewusst gewählt — ein 403 würde verraten, dass der Server existiert, nur eben für diesen Benutzer gesperrt ist.

Ein 404 lässt offen, ob der Server überhaupt existiert, und vermeidet damit, Rückschlüsse auf fremde Ressourcen zu ermöglichen. Diese Logik ist zentral im
Backend gebündelt, damit sie überall gleich greift.

## Audit

Jede ausgeführte Bereinigungsaktion wird protokolliert. Bei Einzelaktionen (Löschen oder Korrigieren einer Ressource) werden der ausführende Benutzer, der exakte an den FHIR-Server gesendete Befehl, der Zustand der Ressource vor der Änderung, das Ergebnis, eine Begründung und der Zeitpunkt festgehalten. Damit ist jede Veränderung am FHIR-Bestand nachvollziehbar, wer sie wann und mit welchem Ergebnis
durchgeführt hat.

Sammelaktionen auf der Cleanup-Seite und die DB-Bereinigung schreiben einen einzigen Eintrag pro Vorgang: Benutzer, Filter, Zeitpunkt, Begründung, die Liste aller geänderten Ressourcen und die Fehlschläge nach Fehlermeldung gruppiert. So bleibt das Audit-Log auch nach einer Bereinigung von 50.000 Ressourcen lesbar.
Struktur der Audit-Tabelle siehe [schema.md](schema.md).
