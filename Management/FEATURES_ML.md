# Detaillierte Features: ML + LLM

## 1. Machine-Learning-Features

- **Anomaly Detection** (IsolationForest / Autoencoder)  
  Lernt aus validen Ressourcen, was „normal" ist → erkennt subtile Ausreißer (z. B. unmögliche Lab-Werte, unplausible Perioden).
- **Risiko-Score** (XGBoostClassifier)  
  Gibt pro Ressource einen Prozentwert „Wahrscheinlichkeit invalid".  
  Features: Ressourcen-Typ, String-Längen, Reference-Anzahl, historische Fehler etc.  
  Erklärbarkeit durch SHAP-Werte.

## 2. LLM-Assistent (nach Validierung)

- Arbeitet **nur** auf den bereits regelbasiert als invalid markierten Ressourcen.
- Schlägt vor:
  - „Diese Ressource löschen?" → zeigt exakten `DELETE /Patient/123?if-match=ETag`
  - „Diese Observation korrigieren?" → zeigt exakten `PATCH` (z. B. Name-Feld entfernen)
- Erklärung in Klartext: „Klarnamen in Observation.valueString verletzt Datenschutz."
- **Immer manuell bestätigt** – kein automatisches Löschen!

## Warum diese Kombination stark ist

Regeln = deterministisch & erklärbar  
ML = findet neue, unbekannte Fehler  
LLM = macht die Nachbearbeitung intelligent und benutzerfreundlich
