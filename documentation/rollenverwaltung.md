# Rollenverwaltung und Zugriffskontrolle

## Anmeldung über Keycloak

Die Authentifizierung läuft über Keycloak per OpenID Connect im Backend-for-Frontend-Muster (BFF). Das Backend führt den OIDC-Ablauf durch und
hält die Session in einem signierten Cookie, das nur die Benutzer-ID enthält; das Frontend besitzt kein Token. Rolle und Rechte liest das Backend
bei jeder Anfrage frisch aus der Datenbank, eine Rollenänderung wirkt also sofort. Der Ablauf im Einzelnen:

1. Das Frontend ruft `/api/v1/auth/login` auf.
2. Das Backend leitet zu Keycloak weiter.
3. Nach erfolgreicher Anmeldung leitet Keycloak zurück auf
   `/api/v1/auth/callback`.
4. Das Backend legt bzw. aktualisiert den Benutzer, setzt das Session-Cookie und leitet zurück in die Oberfläche.

`/api/v1/auth/me` liefert den aktuell angemeldeten Benutzer; ist niemand angemeldet, antwortet der Endpunkt mit 401 — das ist der Normalfall, solange
kein Login stattgefunden hat, und kein Fehler.

Das Session-Cookie wird im Produktionsmodus mit dem `Secure`-Flag gesetzt und erfordert damit HTTPS. Das ist der Grund, warum der Produktionsbetrieb zwingend über HTTPS läuft.

„Sign out“ löscht die Verity-Session und leitet danach zu Keycloak weiter, um auch die Keycloak-Sitzung zu beenden. Ohne diesen Schritt würde ein
erneutes „Sign in“ ohne Passwort sofort wieder anmelden. Dafür muss beim Keycloak-Client die Post-Logout-Redirect-URI eingetragen sein (siehe
[deployment.md](deployment.md#keycloak)).

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

Die globale Rolle legt fest, **was** jemand tun darf. **Auf welchen Servern** das gilt, regeln Eigentum und Freigaben (nächster Abschnitt).

| Aktion                                                     | viewer | editor | admin |
| ---------------------------------------------------------- | :----: | :----: | :---: |
| Server, Läufe, invalide Ressourcen und Regeln ansehen      |   ✓    |   ✓    |   ✓   |
| Server anlegen                                             |        |   ✓    |   ✓   |
| Läufe starten, fortsetzen, abbrechen                       |        |   ✓    |   ✓   |
| Regeln und Filter ändern                                   |        |   ✓    |   ✓   |
| Ressourcen löschen oder korrigieren (einzeln und gesammelt) |        |   ✓    |   ✓   |
| Server bearbeiten, Authentifizierung, teilen, löschen      |        | Owner  |   ✓   |
| alle Server sehen, Benutzer und Rollen verwalten, Audit-Log |        |        |   ✓   |

Neue Benutzer sind beim ersten Login **viewer**. Die Rechte werden im Backend durchgesetzt; die Oberfläche blendet Aktionen, die jemand nicht
ausführen darf, nur zusätzlich aus.

## Erste Administratoren

Damit es überhaupt jemanden gibt, der Rollen vergeben kann, wird über die `.env`-Variable `INITIAL_ADMIN_USERS` festgelegt, welche Benutzer beim ersten
Login automatisch die admin-Rolle erhalten. Verglichen wird ohne Beachtung der Groß-/Kleinschreibung mit dem Benutzernamen und mit der E-Mail-Adresse,
die Keycloak liefert. Die E-Mail-Adresse zählt nur, wenn Keycloak sie als verifiziert meldet (`email_verified`); sonst könnte jemand, der seine
E-Mail-Adresse selbst ändern darf, eine gelistete Adresse übernehmen. Beim mitgelieferten Keycloak ist das `verity-admin`.

Befördert wird beim Anlegen des Benutzers. Bereits bekannte Benutzer werden nur befördert, solange es noch gar keinen Admin gibt. Ein gelisteter Admin
lässt sich also später in der Benutzerverwaltung herabstufen, ohne dass er beim nächsten Login wieder Admin wird.

```bash
#  Beispiel: INITIAL_ADMIN_USERS=meine-email@institut.de,admin2@institut.de
#  Weitere Admins werden danach über die Benutzerverwaltung in der Oberfläche ernannt.
```

## Server-Eigentum und Freigaben

Wer einen Server anlegt, ist sein **Owner**. Ein Benutzer sieht einen Server, wenn er Admin ist, ihn besitzt oder der Server für ihn
**freigegeben** wurde. Freigeben können der Owner (mit Rolle editor) und Admins über **Servers → ⋯ → Share**. Was der Benutzer auf dem
freigegebenen Server tun darf, folgt aus seiner Rolle: ein viewer sieht ihn nur an, ein editor kann Läufe starten, Regeln ändern und Ressourcen
korrigieren. Bearbeiten, Authentifizierung, weitere Freigaben und Löschen bleiben beim Owner und den Admins.

Ein neuer viewer sieht deshalb zunächst keinen Server, sondern den Hinweis, sich an einen Admin oder Owner zu wenden.

Greift ein Benutzer auf einen Server zu, den er nicht sehen darf, antwortet das Backend mit **404 Not Found**, nicht mit 403 Forbidden. Ein 403 würde
verraten, dass der Server existiert. Darf er den Server sehen, aber die Aktion nicht ausführen, antwortet es mit 403. Diese Logik ist zentral im
Backend gebündelt, damit sie überall gleich greift.

### Zugangsdaten und Server-URL

Ändert jemand die Base-URL eines Servers auf einen anderen Host, verwirft Verity die gespeicherten Zugangsdaten. Sie wurden für den alten Host
eingegeben und dürfen nicht an einen anderen geschickt werden; die Änderung steht im Audit-Log. Aus demselben Grund folgt Verity beim Blättern
durch Suchergebnisse keinem `next`-Link auf einen fremden Host.

## Audit

Jede ausgeführte Bereinigungsaktion wird protokolliert. Bei Einzelaktionen (Löschen oder Korrigieren einer Ressource) werden der ausführende Benutzer, der exakte an den FHIR-Server gesendete Befehl, der Zustand der Ressource vor der Änderung, das Ergebnis, eine Begründung und der Zeitpunkt festgehalten. Damit ist jede Veränderung am FHIR-Bestand nachvollziehbar, wer sie wann und mit welchem Ergebnis
durchgeführt hat.

Sammelaktionen auf der Cleanup-Seite schreiben einen einzigen Eintrag pro Vorgang: Benutzer, Filter, Zeitpunkt, Begründung, die Liste aller geänderten Ressourcen und die Fehlschläge nach Fehlermeldung gruppiert. So bleibt das Audit-Log auch nach einer Bereinigung von 50.000 Ressourcen lesbar.

Außerdem protokolliert werden Änderungen an Verity selbst:

| Aktion               | Inhalt                                                                  |
| -------------------- | ----------------------------------------------------------------------- |
| `SERVER_DELETE`      | Stammdaten des gelöschten Servers                                       |
| `SERVER_AUTH_CHANGE` | alte und neue Auth-Art, Namen der geänderten Felder (nie die Werte)     |
| `SERVER_SHARE`       | Freigabe für einen Benutzer                                             |
| `SERVER_UNSHARE`     | Entzug einer Freigabe                                                   |
| `USER_ROLE_CHANGE`   | betroffener Benutzer, alte und neue Rolle                               |

Die Audit-Einträge eines gelöschten Servers bleiben erhalten; sie sind danach über die Server-URL zuzuordnen. Struktur der Audit-Tabelle siehe
[schema.md](schema.md).
