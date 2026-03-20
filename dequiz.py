#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Erstellt Quiz-Inhalte für WordPress-Beiträge und speichert sie lokal in einer Datei.

Sicher für öffentliche Repositories:
- keine Zugangsdaten im Code
- Konfiguration ausschließlich über Umgebungsvariablen
- robuste Fehlerbehandlung
- klare Protokollausgaben
"""

from __future__ import annotations

import base64
import logging
import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from openai import OpenAI


GLOBAL_PROMPT = (
    "Use the title and find 10 technical statements on the topic in German that can be used as a knowledge test. "
    "Only find statements that are difficult to answer. Avoid double negatives in the statements. Never use the word 'not' in the statements. "
    "Do not number. Do not write in front of the statements, do not leave blank lines. There are true and false statements. "
    "Use German measurements and units. Each line of this starts with 'Quizfrage|'. and ends with |true or |false, depending on on the correctness of the statement. "
    "Then create a welcome text in German consisting of 2-3 sentences for 'Welcome to our short quiz on ...' that motivates participation. "
    "Create a 2-3 sentence result description in German that praises participation and interest in the topic and career opportunities in the field. "
    "Do not write that you have learned or improved anything. However, motivate the reader to continue reading the text that follows the quiz on the topic. "
    "Write a quiz headline in German similar to 'Jobs in Germany: Test your knowledge', starting the line with 'Quiztitel|'. "
    "Then write a quiz description in German similar to 'Welcome to our quiz on the topic of "
    "+ title +
    "! Discover how much you know about this job. Are you ready to test your knowledge and learn something new about this exciting perspective? Start now!', "
    "starting the line with 'Quizbeschreibung|'. Schreibe auf Deutsch eine Auswertung zu diesem Quiz beginnend mit dem Text 'Ergebnis|' "
    "in dem Stil wie 'Great and thank you for taking part. You can read more about the topic below and find out more about the subject'. "
    "After this provide in German up to 7 facts and figures about the current topic, each line starting with 'Statistik|' but use different starting words after 'Statistik|'. "
    "Use German measurements and units. After this create in German at minimum 10 aptitude questions that ask about personal suitability for the topic (job, city, skill etc.), "
    "each line starting with: 'Eignungsfrage|' The questions should be suitable for answering with applies, tends to apply, neutral, tends not to apply, does not apply. "
    "This line does not end with a '|'. After this Write in German an introduction to the aptitude test in the form 'Eignungstesteinleitung|' and a heading in German as 'Eignungstestheadline|'. "
    "Do not translate the strings 'Quizfrage|', 'Quiztitel|', 'Quizbeschreibung|', 'Ergebnis|', 'Statistik|', 'Eignungstesteinleitung|', 'Eignungstestheadline|', 'Eignungsfrage|'. "
    "Use German measurements and units. Round numbers where appropriate. Do not use statistical data older than 2 years."
)


@dataclass
class Settings:
    base_url: str
    wp_user: str
    wp_app_password: str
    openai_api_key: str
    output_file: Path = Path("quiz-fragen.txt")
    archive_dir: Path = Path("Archiv")
    model: str = "gpt-4o-mini"
    poll_interval_seconds: int = 300
    http_timeout_seconds: int = 30
    max_idle_hours: int = 3
    start_page: int = 1

    @property
    def wp_posts_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/wp-json/wp/v2/posts"

    @property
    def auth_header(self) -> str:
        raw = f"{self.wp_user}:{self.wp_app_password}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("utf-8")


class QuizGenerator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": settings.auth_header,
            "User-Agent": "dequiz-public/1.0"
        })

    def get_next_post(self, current_retry_delay_minutes: int) -> tuple[Optional[str], Optional[str], int]:
        page = self.settings.start_page

        while True:
            try:
                response = self.session.get(
                    self.settings.wp_posts_url,
                    params={"page": page, "per_page": 100},
                    timeout=self.settings.http_timeout_seconds,
                )

                if response.status_code == 400:
                    logging.info("Keine weiteren Seiten mit Beiträgen vorhanden.")
                    break

                response.raise_for_status()
                posts = response.json()

                if not posts:
                    break

                for post in posts:
                    post_id = str(post.get("id", "")).strip()
                    post_title = post.get("title", {}).get("rendered", "").strip()

                    if post_id and post_title and not self.post_exists_in_file(post_id):
                        return post_id, post_title, current_retry_delay_minutes

                page += 1

            except (requests.exceptions.ConnectionError, requests.exceptions.SSLError, requests.exceptions.Timeout) as exc:
                logging.warning(
                    "Verbindungsfehler beim Abruf der Beiträge: %s. Neuer Versuch in %s Minuten.",
                    exc,
                    current_retry_delay_minutes,
                )
                time.sleep(current_retry_delay_minutes * 60)
                current_retry_delay_minutes = min(current_retry_delay_minutes + 2, 15)

            except requests.HTTPError as exc:
                logging.error("HTTP-Fehler beim Abruf der Beiträge: %s", exc)
                break

            except Exception as exc:  # noqa: BLE001
                logging.exception("Unerwarteter Fehler beim Abruf der Beiträge: %s", exc)
                break

        return None, None, current_retry_delay_minutes

    def post_exists_in_file(self, post_id: str) -> bool:
        if not self.settings.output_file.exists():
            return False
        content = self.settings.output_file.read_text(encoding="utf-8")
        return f"###{post_id}###" in content

    def append_to_quiz_file(self, content: str, post_id: str) -> None:
        with self.settings.output_file.open("a", encoding="utf-8") as file:
            file.write(f"###{post_id}###\n{content.strip()}\n\n")

    def create_quiz_for_post(self, post_id: str, title: str) -> None:
        logging.info("Erstelle Quiz für Beitrag %s: %s", post_id, title)

        response = self.client.chat.completions.create(
            model=self.settings.model,
            temperature=0.4,
            messages=[
                {"role": "system", "content": GLOBAL_PROMPT},
                {"role": "user", "content": title},
            ],
        )

        if not response.choices:
            logging.warning("Keine Antwort für Beitrag %s erhalten.", post_id)
            return

        quiz_content = (response.choices[0].message.content or "").strip()
        if not quiz_content:
            logging.warning("Leere Antwort für Beitrag %s erhalten.", post_id)
            return

        self.append_to_quiz_file(quiz_content, post_id)
        logging.info("Quiz für Beitrag %s gespeichert.", post_id)

    def quality_assurance(self) -> None:
        if not self.settings.output_file.exists():
            logging.info("Keine Ausgabedatei vorhanden. Qualitätssicherung übersprungen.")
            return

        self.settings.archive_dir.mkdir(parents=True, exist_ok=True)

        current_date = datetime.now().strftime("%Y-%m-%d")
        backup_filename = self.settings.archive_dir / f"{current_date}_quiz-fragen.txt"
        shutil.copy(self.settings.output_file, backup_filename)
        logging.info("Sicherungskopie erstellt: %s", backup_filename)

        replacements = {
            "im Praktikums": "im Praktikum",
        }

        lines = self.settings.output_file.read_text(encoding="utf-8").splitlines(keepends=True)

        with self.settings.output_file.open("w", encoding="utf-8") as file:
            for line in lines:
                for old, new in replacements.items():
                    line = line.replace(old, new)

                if line.startswith((
                    "Eignungsfrage|",
                    "Eignungstestheadline|",
                    "Eignungstesteinleitung|",
                    "Statistik|",
                    "Quiztitel|",
                    "Quizbeschreibung|",
                )) and line.endswith("|\n"):
                    line = line[:-2] + "\n"

                file.write(line)

        logging.info("Qualitätssicherung abgeschlossen.")

    def run(self) -> None:
        current_retry_delay_minutes = 5
        start_time = datetime.now()

        while True:
            post_id, title, current_retry_delay_minutes = self.get_next_post(current_retry_delay_minutes)

            if post_id is None or title is None:
                if datetime.now() - start_time > timedelta(hours=self.settings.max_idle_hours):
                    logging.info(
                        "Keine erfolgreiche Verarbeitung seit über %s Stunden. Skript wird beendet.",
                        self.settings.max_idle_hours,
                    )
                    break

                logging.info(
                    "Keine neuen Beiträge zu verarbeiten. Warte %s Sekunden bis zum nächsten Versuch.",
                    self.settings.poll_interval_seconds,
                )
                time.sleep(self.settings.poll_interval_seconds)
                continue

            try:
                self.create_quiz_for_post(post_id, title)
            except Exception as exc:  # noqa: BLE001
                logging.exception("Fehler bei der Quiz-Erstellung für Beitrag %s: %s", post_id, exc)
                time.sleep(10)

        self.quality_assurance()


def load_settings_from_env() -> Settings:
    base_url = os.getenv("DEQUIZ_BASE_URL", "").strip()
    wp_user = os.getenv("DEQUIZ_WP_USER", "").strip()
    wp_app_password = os.getenv("DEQUIZ_WP_APP_PASSWORD", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()

    missing = []
    if not base_url:
        missing.append("DEQUIZ_BASE_URL")
    if not wp_user:
        missing.append("DEQUIZ_WP_USER")
    if not wp_app_password:
        missing.append("DEQUIZ_WP_APP_PASSWORD")
    if not openai_api_key:
        missing.append("OPENAI_API_KEY")

    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Fehlende Umgebungsvariablen: {joined}")

    return Settings(
        base_url=base_url,
        wp_user=wp_user,
        wp_app_password=wp_app_password,
        openai_api_key=openai_api_key,
        output_file=Path(os.getenv("DEQUIZ_OUTPUT_FILE", "quiz-fragen.txt")),
        archive_dir=Path(os.getenv("DEQUIZ_ARCHIVE_DIR", "Archiv")),
        model=os.getenv("DEQUIZ_OPENAI_MODEL", "gpt-4o-mini"),
        poll_interval_seconds=int(os.getenv("DEQUIZ_POLL_INTERVAL_SECONDS", "300")),
        http_timeout_seconds=int(os.getenv("DEQUIZ_HTTP_TIMEOUT_SECONDS", "30")),
        max_idle_hours=int(os.getenv("DEQUIZ_MAX_IDLE_HOURS", "3")),
        start_page=int(os.getenv("DEQUIZ_START_PAGE", "1")),
    )


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def main() -> None:
    configure_logging()
    settings = load_settings_from_env()
    generator = QuizGenerator(settings)
    generator.run()


if __name__ == "__main__":
    main()
