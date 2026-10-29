"""Descarga precios diarios de Yahoo Finance con yfinance."""

import pandas as pd
import yfinance as yf

from radar import db

COLUMNAS = {
    "Open": "apertura",
    "High": "maximo",
    "Low": "minimo",
    "Close": "cierre",
    "Volume": "volumen",
}


def descargar(ticker: str, desde: str) -> pd.DataFrame:
    datos = yf.download(ticker, start=desde, auto_adjust=True, progress=False, multi_level_index=False)
    if datos.empty:
        return pd.DataFrame()
    datos = datos.rename(columns=COLUMNAS)[list(COLUMNAS.values())].dropna(subset=["cierre"])
    datos.insert(0, "fecha", datos.index.strftime("%Y-%m-%d"))
    datos.insert(0, "ticker", ticker)
    return datos.reset_index(drop=True)


def actualizar(con, watchlist: dict) -> None:
    cfg = watchlist["precios"]
    grupos = {"indice": cfg["indices_y_mercados"], "emisora": cfg["emisoras"]}

    for tipo, activos in grupos.items():
        for ticker, nombre in activos.items():
            db.guardar(con, "activos", pd.DataFrame([{"clave": ticker, "nombre": nombre, "tipo": tipo}]))
            # Vuelve a pedir desde la última fecha guardada para completar el último día si cambió.
            desde = db.ultima_fecha(con, "precios", "ticker", ticker) or cfg["historia_inicial"]
            try:
                n = db.guardar(con, "precios", descargar(ticker, desde))
                print(f"  {ticker:<14} {nombre:<32} {n:>5} filas")
            except Exception as e:  # un ticker con error no debe detener a los demás
                print(f"  {ticker:<14} {nombre:<32} ERROR: {e}")
