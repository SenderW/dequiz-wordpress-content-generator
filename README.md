# dequiz-wordpress-content-generator
Automatisierte Erstellung strukturierter Quiz-, Eignungstest- und Fakteninhalte für WordPress-Beiträge mit Python und OpenAI.

## Zweck

Das Skript ruft WordPress-Beiträge über die REST-API ab, prüft, für welche Beiträge noch kein Quiz erzeugt wurde, erstellt Quiz-Inhalte mit der OpenAI-API und speichert die Ergebnisse lokal in einer Textdatei.

## Funktionen

- Abruf von WordPress-Beiträgen über die REST-API
- Vermeidung doppelter Verarbeitung bereits gespeicherter Beiträge
- Erstellung strukturierter Quiz-Inhalte auf Deutsch
- lokale Speicherung in `quiz-fragen.txt`
- einfache Qualitätssicherung mit Backup-Datei und Korrekturregeln
- sichere Nutzung über Umgebungsvariablen statt Klartext-Zugangsdaten

## Voraussetzungen

- Python 3.11 oder neuer
- WordPress mit aktivierter REST-API
- WordPress-Benutzer mit passendem Zugriff und Application Password
- OpenAI-API-Schlüssel

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Konfiguration

Lege eine Datei `.env` an oder setze die Variablen in deiner Shell:

```env
DEQUIZ_BASE_URL=https://example.com
DEQUIZ_WP_USER=wordpress-benutzer
DEQUIZ_WP_APP_PASSWORD=wordpress-application-password
OPENAI_API_KEY=dein-openai-schluessel
DEQUIZ_OPENAI_MODEL=gpt-4o-mini
DEQUIZ_OUTPUT_FILE=quiz-fragen.txt
DEQUIZ_ARCHIVE_DIR=Archiv
DEQUIZ_POLL_INTERVAL_SECONDS=300
DEQUIZ_HTTP_TIMEOUT_SECONDS=30
DEQUIZ_MAX_IDLE_HOURS=3
DEQUIZ_START_PAGE=1
```

## Start

```bash
python dequiz.py
```

## Projektstruktur

```text
.
├── dequiz.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
└── quiz-fragen.txt
