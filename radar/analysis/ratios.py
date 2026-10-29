"""Razones financieras a partir de la tabla `estados`.

Rentabilidad y apalancamiento se calculan con cifras anuales (la utilidad trimestral
subestima el ROE). Márgenes y crecimiento también por trimestre, contra el mismo
trimestre del año anterior para no confundir estacionalidad con crecimiento.
"""

import numpy as np
import pandas as pd

# Conceptos de Yahoo Finance que usan las razones
CONCEPTOS = {
    "Total Revenue": "ingresos",
    "Operating Income": "utilidad_operativa",
    "EBITDA": "ebitda",
    "Net Income Common Stockholders": "utilidad_neta",
    "Stockholders Equity": "capital",
    "Total Assets": "activos",
    "Total Debt": "deuda",
    "Current Assets": "activo_circulante",
    "Current Liabilities": "pasivo_circulante",
    "Free Cash Flow": "flujo_libre",
}


def _dividir(a: pd.Series, b: pd.Series) -> pd.Series:
    return a / b.where(b != 0)


def cifras(con, ticker: str, frecuencia: str) -> pd.DataFrame:
    """Una fila por periodo, una columna por concepto (nombres en español)."""
    marcas = ", ".join("?" for _ in CONCEPTOS)
    df = pd.read_sql(
        f"""SELECT fecha, concepto, valor FROM estados
            WHERE ticker = ? AND frecuencia = ? AND concepto IN ({marcas})""",
        con, params=(ticker, frecuencia, *CONCEPTOS))
    if df.empty:
        return pd.DataFrame()
    tabla = df.pivot_table(index="fecha", columns="concepto", values="valor", aggfunc="first")
    tabla = tabla.rename(columns=CONCEPTOS).reindex(columns=list(CONCEPTOS.values()))
    tabla.index = pd.to_datetime(tabla.index)
    return tabla.sort_index()


def calcular(con, ticker: str, frecuencia: str) -> pd.DataFrame:
    c = cifras(con, ticker, frecuencia)
    if c.empty:
        return c
    # Control de calidad: Yahoo a veces publica ingresos negativos o en cero (p. ej. Banorte 2T25).
    # Se descartan para no contaminar márgenes ni crecimientos.
    c.loc[c["ingresos"] <= 0, "ingresos"] = np.nan
    r = pd.DataFrame(index=c.index)
    r["ingresos_mdp"] = c["ingresos"] / 1e6
    r["margen_operativo_%"] = _dividir(c["utilidad_operativa"], c["ingresos"]) * 100
    r["margen_neto_%"] = _dividir(c["utilidad_neta"], c["ingresos"]) * 100
    if frecuencia == "anual":
        r["roe_%"] = _dividir(c["utilidad_neta"], c["capital"]) * 100
        r["roa_%"] = _dividir(c["utilidad_neta"], c["activos"]) * 100
    r["deuda_capital"] = _dividir(c["deuda"], c["capital"])
    r["liquidez"] = _dividir(c["activo_circulante"], c["pasivo_circulante"])
    r["flujo_libre_mdp"] = c["flujo_libre"] / 1e6

    # Crecimiento contra el mismo periodo del año anterior (si existe en los datos)
    anterior = c["ingresos"].copy()
    anterior.index = anterior.index + pd.DateOffset(years=1)
    r["crec_ingresos_%"] = (_dividir(c["ingresos"], anterior.reindex(c.index)) - 1) * 100

    r = r.replace([np.inf, -np.inf], np.nan).dropna(axis=1, how="all")  # bancos: sin liquidez ni margen operativo
    r.index = r.index.strftime("%Y-%m-%d")
    return r.round(2)
