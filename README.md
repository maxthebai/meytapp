# Meytapp - Schießergebnisse

Eine Streamlit-App zur Verarbeitung und Speicherung von Meyton ESTA 5 QR-Code-Ergebnissen.

## Features

- **Authentifizierung**: Benutzerregistrierung und Login mit streamlit-authenticator
- PDF-Download und Text-Extraktion aus Meyton ESTA 5 URLs
- Automatische Extraktion von: Datum, Schütze, Disziplin, Serien, Gesamtergebnis
- SQLite-Datenbank mit Benutzer-Trennung
- Tabelle aller bisherigen Schießen
- Liniendiagramm zur Visualisierung der Ringzahl-Entwicklung

## Voraussetzungen

- Python 3.10+
- pip

## Installation

```bash
pip install -r requirements.txt
```

## Starten

```bash
streamlit run app.py
```

Die App öffnet sich dann unter `http://localhost:8501`.

## Erste Schritte

1. App starten
2. Tab "Neuen Account erstellen" nutzen, um sich zu registrieren
3. Mit E-Mail und Passwort anmelden
4. Ergebnisse importieren via URL oder QR-Code

## Authentifizierung

- Registrierung mit Name, E-Mail und Passwort
- Login mit E-Mail und Passwort
- Sitzungstoken via Cookie (30 Tage)
- Jeder Benutzer sieht nur seine eigenen Daten

## Datenbank

Die Daten werden in `meytapp.db` (SQLite) gespeichert. Die Datenbank wird automatisch beim ersten Start erstellt.

### Gespeicherte Felder

- `id`: Eindeutige ID
- `user_id`: ID des Benutzers (aus Auth-System)
- `date`: Datum des Schießens
- `shooter`: Name des Schützen
- `discipline`: Schießdisziplin
- `total_score`: Gesamtringzahl
- `series`: Komma-getrennte Einzelserien
- `url`: Original-URL des QR-Codes
- `created_at`: Zeitstempel des Imports

## Projektstruktur

```
meytapp/
├── app.py           # Streamlit Frontend
├── auth.py          # Authentifizierung
├── database.py      # SQLite Datenbank-Funktionen
├── pdf_parser.py    # PDF-Download und -Parsing
├── credentials.yaml # (wird automatisch erstellt)
├── requirements.txt
├── README.md
└── meytapp.db       # (wird automatisch erstellt)
```

## ⚖️ Haftungsausschluss (Disclaimer)

Wichtiger Hinweis: Dieses Projekt ist ein rein privates Open-Source-Tool und steht in keinerlei Verbindung zur Meyton Elektronik GmbH.

Die Begriffe "Meyton" und "ESTA 5" sind geschützte Markenzeichen der jeweiligen Eigentümer.

Diese App dient lediglich der statistischen Aufarbeitung von Schießergebnissen, die vom Nutzer selbst über die bereitgestellten QR-Codes der Meyton-Anlagen bezogen wurden.

Die Nutzung erfolgt auf eigene Gefahr. Es wird keine Haftung für die Richtigkeit der Datenextraktion oder etwaige Serverprobleme übernommen.
