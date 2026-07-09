# FHIR Verity

## Ausgangslage

Am DIZ Gießen wurde die Datenqualität der FHIR-Server zuvor über mehrere Mirth-Connect-Channels geprüft. Jeder Channel lief in Schleifen über
1000er-Batches, prüfte einen Ressourcentyp auf Pseudonymisierung, Perioden, Klarnamen und Ähnliches, sammelte die invaliden Ressourcen in einer Channel-Map und erzeugte am Ende einen Report. Das funktionierte, war aber schwer wartbar,schlecht nachvollziehbar und nicht ohne Weiteres auf andere Standorte übertragbar.

FHIR Verity ersetzt diesen Aufbau durch eine moderne Web-Anwendung mit einer klar getrennten Backend-/Frontend-Architektur, einer konfigurierbaren
Regel-Engine und einem nachvollziehbaren Bereinigungs-Workflow.

## Was das Tool tut

Verity nimmt einen FHIR-Server, liest dessen kompletten Ressourcen-Bestand ein und prüft jede Ressource gegen ein **konfigurierbares Regelwerk.** Ressourcen, die gegen eine Regel verstoßen, werden mit dem konkreten Befund in der Datenbank festgehalten. Über die Oberfläche lassen sich die Ergebnisse einsehen, filtern und auswerten, und für die invaliden Ressourcen steht ein Bereinigungs-Workflowbereit, der jede Aktion vor der Ausführung als konkreten FHIR-Befehl anzeigt und protokolliert.

Zusätzlich schreibt Verity die Ergebnisse als FHIR-konforme Report-Ressourcen (`VerificationResult`, `TestReport`) Version 4 auf den geprüften Server zurück, sodass die Qualitätsbewertung selbst wieder Teil des FHIR-Datenbestands ist und von anderen Systemen weiterverarbeitet werden kann.

## Was Verity von bestehenden Validatoren unterscheidet

Der übliche FHIR-Validator(HAPI Validator) prüft eine einzelne Ressource oder ein Bundle gegen ein StructureDefinition-Profil oder Kerndatensatz und sagt: konform oder nicht. Das ist notwendig, deckt aber zwei Dinge nicht ab, die für die tägliche DIZ-Arbeit zentral sind.

Erstens die **Server-weite Sicht**. Verity ist darauf ausgelegt, den gesamten Bestand eines Servers durchzugehen, nicht nur Stichproben. Das erfordert eine robuste Crawl-Architektur, die auch über Stunden und über Millionen von Ressourcen zuverlässig bleibt und wieder aufsetzbar ist.

Zweitens **Qualitätskriterien jenseits der Profilkonformität**. Eine Ressource kann profilkonform und trotzdem problematisch sein: Ein Klarname im falschen Feld verletzt den Datenschutz, ein fehlendes Pflichtfeld macht die Ressource für Auswertungen unbrauchbar, ein biologisch unmöglicher Laborwert ist unplausibel, eine Referenz auf eine nicht existierende Ressource bricht die Integrität. Diese vier Dimensionen prüft Verity gezielt. Details dazu in
[features.md](features.md).

## Einordnung im wissenschaftlichen Kontext

Das Tool ist im Rahmen einer Praxisphase und Bachelorarbeit im Studiengang Digitale Medizin entstanden, methodisch als Design-Science-Research-Artefakt.
Die regelbasierte Validierung bildet den evaluierten Kern; die funktionale Gleichwertigkeit zur Mirth-Vorgängerlösung ist die
Regressions-Baseline. [features.md](features.md).

## Zielgruppe der Nachnutzung

Verity ist Open Source und für den Einsatz an beliebigen MII-DIZ oder andere FHIR basierete Institutionen gedacht.
