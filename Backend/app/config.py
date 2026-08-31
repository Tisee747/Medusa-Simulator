"""Load application settings from the project .env file."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8011"))
STATION_CODE = os.getenv("STATION_CODE", "MAIN_01")

DB_ENGINE = os.getenv("DB_ENGINE", "mariadb").lower()
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "medusa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "simulator_alpro")
SQLITE_PATH = os.getenv("SQLITE_PATH", str(BASE_DIR / "simulator_test.db"))

RUNNER_TIMEOUT_SECONDS = float(os.getenv("RUNNER_TIMEOUT_SECONDS", "4"))
RUNNER_MEMORY_MB = int(os.getenv("RUNNER_MEMORY_MB", "256"))
RUNNER_MAX_OUTPUT = int(os.getenv("RUNNER_MAX_OUTPUT", "20000"))
ANIMATION_ACK_TIMEOUT_SECONDS = int(os.getenv("ANIMATION_ACK_TIMEOUT_SECONDS", "30"))
STATION_FINISHED_AUTO_HOME_SECONDS = int(os.getenv("STATION_FINISHED_AUTO_HOME_SECONDS", "60"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

