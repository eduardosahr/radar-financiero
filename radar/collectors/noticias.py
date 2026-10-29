"""Descarga titulares de feeds RSS de medios y de búsquedas en Google Noticias."""

import hashlib
import html
import re
import time
import unicodedata
import urllib.parse
from datetime import datetime, timedelta, timezone

import feedparser
import pandas as pd
import requests

from radar import db

CABECERAS = {"User-Agent": "Mozilla/5.0 (RadarFinanciero; uso personal)"}
URL_GOOGLE = "https://news.google.com/rss/search"


def huella(titulo: str) -> str:
    """Identificador de la nota: el mismo titular en dos fuentes produce la misma huella."""
    t = unicodedata.normalize("NFKD", titulo.lower())
    t = "".join(c for c in t if c.isalnum() or c.isspace())
    return hashlib.sha1(" ".join(t.split()).encode()).hexdigest()[:16]


def limpiar(texto: str) -> str:
    """Quita etiquetas HTML y espacios sobrantes del resumen."""
    texto = re.sub(r"<[^>]+>", " ", html.unescape(texto or ""))
    return " ".join(texto.split())[:1000]


def fecha_utc(entrada) -> str | None:
    t = entrada.get("published_parsed") or entrada.get("updated_parsed")
    return time.strftime("%Y-%m-%d %H:%M:%S", t) if t else None


def leer_feed(url: str) -> list:
    r = requests.get(url, headers=CABECERAS, timeout=30)
    r.raise_for_status()
    return feedparser.parse(r.content).entries


def a_filas(entradas: list, origen: str, medio: str | None, clave: str | None) -> pd.DataFrame:
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    filas = []
    for e in entradas:
        titulo, fuente = e.get("title", "").strip(), medio
        if not titulo:
            continue
        if fuente is None:  # Google Noticias agrega " - Medio" al titular
            fuente = e.get("source", {}).get("title")
            if fuente and titulo.endswith(" - " + fuente):
                titulo = titulo[: -len(fuente) - 3]
        resumen = limpiar(e.get("summary", ""))
        filas.append({
            "id": huella(titulo),
            "publicada": fecha_utc(e),
            "medio": fuente,
            "titulo": titulo,
            # El resumen de Google Noticias solo repite el titular.
            "resumen": None if clave or resumen.startswith(titulo) else resumen,
            "url": e.get("link"),
            "origen": origen,
            "clave": clave,
            "descargada": ahora,
        })
    return pd.DataFrame(filas).drop_duplicates("id") if filas else pd.DataFrame()


def actualizar(con, watchlist: dict) -> None:
    cfg = watchlist["noticias"]

    # Primero las búsquedas: así una nota que también sale en un feed general queda ligada a su emisora.
    for clave, consulta in cfg["busquedas"].items():
        url = URL_GOOGLE + "?" + urllib.parse.urlencode({
            "q": f"{consulta} when:{cfg['dias_busqueda']}d", "hl": "es-419", "gl": "MX", "ceid": "MX:es-419"})
        try:
            n = db.guardar(con, "noticias", a_filas(leer_feed(url), f"google:{clave}", None, clave), reemplazar=False)
            print(f"  Google: {clave:<16} {n:>4} nuevas")
        except Exception as e:  # una fuente caída no debe detener a las demás
            print(f"  Google: {clave:<16} ERROR: {e}")

    for nombre, url in cfg["feeds"].items():
        try:
            medio = nombre.split(" (")[0]
            n = db.guardar(con, "noticias", a_filas(leer_feed(url), nombre, medio, None), reemplazar=False)
            print(f"  {nombre:<32} {n:>4} nuevas")
        except Exception as e:
            print(f"  {nombre:<32} ERROR: {e}")


def recientes(con, horas: int = 24) -> pd.DataFrame:
    desde = (datetime.now(timezone.utc) - timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
    return pd.read_sql(
        "SELECT publicada, medio, titulo, clave, url FROM noticias WHERE publicada >= ? ORDER BY publicada DESC",
        con, params=(desde,))
