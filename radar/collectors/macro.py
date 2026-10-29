"""Descarga series macroeconómicas de Banxico (SIE) y de la Fed de St. Louis (FRED)."""

from datetime import date, datetime

import pandas as pd
import requests

from radar import db
from radar.config import llave

URL_BANXICO = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/{serie}/datos/{desde}/{hasta}"
URL_FRED = "https://api.stlouisfed.org/fred/series/observations"
HISTORIA_INICIAL = "2015-01-01"


def _a_numero(texto: str) -> float | None:
    """Banxico usa comas de miles y 'N/E' cuando no hay dato; FRED usa '.'."""
    try:
        return float(texto.replace(",", ""))
    except ValueError:
        return None


def descargar_banxico(serie: str, desde: str, token: str) -> pd.DataFrame:
    url = URL_BANXICO.format(serie=serie, desde=desde, hasta=date.today().isoformat())
    r = requests.get(url, headers={"Bmx-Token": token}, timeout=30)
    r.raise_for_status()
    datos = r.json()["bmx"]["series"][0].get("datos", [])
    filas = [
        {
            "fuente": "banxico",
            "serie": serie,
            "fecha": datetime.strptime(d["fecha"], "%d/%m/%Y").date().isoformat(),
            "valor": _a_numero(d["dato"]),
        }
        for d in datos
    ]
    return pd.DataFrame(filas)


def descargar_fred(serie: str, desde: str, api_key: str) -> pd.DataFrame:
    params = {"series_id": serie, "api_key": api_key, "file_type": "json", "observation_start": desde}
    r = requests.get(URL_FRED, params=params, timeout=30)
    r.raise_for_status()
    filas = [
        {"fuente": "fred", "serie": serie, "fecha": o["date"], "valor": _a_numero(o["value"])}
        for o in r.json()["observations"]
    ]
    return pd.DataFrame(filas)


def actualizar(con, watchlist: dict) -> None:
    fuentes = {
        "banxico": (descargar_banxico, llave("BANXICO_TOKEN"), "BANXICO_TOKEN"),
        "fred": (descargar_fred, llave("FRED_API_KEY"), "FRED_API_KEY"),
    }
    for fuente, (descargar, clave_api, nombre_llave) in fuentes.items():
        if not clave_api:
            print(f"  {fuente}: sin {nombre_llave} en .env, se omite")
            continue
        for serie, nombre in watchlist["macro"][fuente].items():
            db.guardar(con, "activos", pd.DataFrame([{"clave": serie, "nombre": nombre, "tipo": fuente}]))
            desde = db.ultima_fecha(con, "macro", "serie", serie) or HISTORIA_INICIAL
            try:
                n = db.guardar(con, "macro", descargar(serie, desde, clave_api))
                print(f"  {serie:<14} {nombre:<32} {n:>5} filas")
            except Exception as e:
                print(f"  {serie:<14} {nombre:<32} ERROR: {e}")
