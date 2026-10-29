"""Rutas del proyecto, lista de seguimiento y llaves de API."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
RUTA_DB = RAIZ / "data" / "radar.db"
RUTA_WATCHLIST = RAIZ / "config" / "watchlist.yaml"

load_dotenv(RAIZ / ".env")


def cargar_watchlist() -> dict:
    with open(RUTA_WATCHLIST, encoding="utf-8") as f:
        return yaml.safe_load(f)


def llave(nombre: str) -> str | None:
    """Devuelve la llave de API del archivo .env, o None si está vacía."""
    valor = os.getenv(nombre, "").strip()
    return valor or None
