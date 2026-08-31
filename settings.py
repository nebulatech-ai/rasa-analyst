from __future__ import annotations

import os


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


ENV = os.environ.get("RASA_ENV", "production").strip().lower()
DEBUG = ENV in {"dev", "development", "local"}
HOST = os.environ.get("RASA_HOST", "127.0.0.1")
PORT = int(os.environ.get("RASA_PORT", "8787"))
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("RASA_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]
DOCS_ON = DEBUG or _flag("RASA_DOCS", False)
