"""
config.py — Konfigurasi aplikasi dari environment variable.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID: int = int(os.getenv("ALLOWED_USER_ID", "1091497145"))
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# Zona waktu tampilan (offset jam dari UTC)
TZ_OFFSET_HOURS: int = int(os.getenv("TZ_OFFSET_HOURS", "7"))  # WIB default

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("finance-bot")
