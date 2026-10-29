"""Descarga estados financieros y perfil de cada emisora desde Yahoo Finance.

Los estados cambian una vez por trimestre, así que cada emisora se actualiza como máximo
una vez cada `dias` días.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf

from radar import db

DIAS_ENTRE_DESCARGAS = 7


def descargar_estados(tk: yf.Ticker, ticker: str) -> pd.DataFrame:
    tablas = [
        ("trimestral", "resultados", tk.quarterly_income_stmt),
        ("trimestral", "balance", tk.quarterly_balance_sheet),
        ("trimestral", "flujo", tk.quarterly_cashflow),
        ("anual", "resultados", tk.income_stmt),
        ("anual", "balance", tk.balance_sheet),
        ("anual", "flujo", tk.cashflow),
    ]
    partes = []
    for frecuencia, estado, df in tablas:
        if df is None or df.empty:
            continue
        largo = df.stack().dropna().reset_index()  # renglones: concepto, fecha, valor
        largo.columns = ["concepto", "fecha", "valor"]
        largo["fecha"] = pd.to_datetime(largo["fecha"]).dt.strftime("%Y-%m-%d")
        largo["ticker"], largo["frecuencia"], largo["estado"] = ticker, frecuencia, estado
        partes.append(largo)
    if not partes:
        return pd.DataFrame()
    return pd.concat(partes)[["ticker", "frecuencia", "estado", "fecha", "concepto", "valor"]]


def descargar_perfil(tk: yf.Ticker, ticker: str) -> pd.DataFrame:
    i = tk.info
    return pd.DataFrame([{
        "ticker": ticker, "nombre_largo": i.get("longName"), "sector": i.get("sector"),
        "industria": i.get("industry"), "moneda": i.get("financialCurrency"),
        "capitalizacion": i.get("marketCap"), "pu": i.get("trailingPE"), "p_vl": i.get("priceToBook"),
        "rend_dividendo": i.get("dividendYield"),
        "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }])


def actualizar(con, watchlist: dict, forzar: bool = False) -> None:
    limite = (datetime.now(timezone.utc) - timedelta(days=DIAS_ENTRE_DESCARGAS)).strftime("%Y-%m-%d %H:%M:%S")
    for ticker, nombre in watchlist["precios"]["emisoras"].items():
        fila = con.execute("SELECT actualizado FROM perfil WHERE ticker = ?", (ticker,)).fetchone()
        if fila and fila[0] >= limite and not forzar:
            print(f"  {ticker:<14} {nombre:<32} al día (se revisa cada {DIAS_ENTRE_DESCARGAS} días)")
            continue
        try:
            tk = yf.Ticker(ticker)
            n = db.guardar(con, "estados", descargar_estados(tk, ticker))
            db.guardar(con, "perfil", descargar_perfil(tk, ticker))
            print(f"  {ticker:<14} {nombre:<32} {n:>5} cifras")
        except Exception as e:  # una emisora con error no debe detener a las demás
            print(f"  {ticker:<14} {nombre:<32} ERROR: {e}")
