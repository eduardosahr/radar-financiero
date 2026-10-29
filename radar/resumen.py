"""Muestra un resumen de la lista de seguimiento a partir de la base de datos.

Uso:  python -m radar.resumen
"""

from datetime import datetime, timedelta, timezone

import pandas as pd

from radar import db
from radar.collectors import noticias

TITULARES_POR_TEMA = 3
TITULARES_GENERALES = 10

# Variación del último cierre contra el cierre de hace N sesiones.
CONSULTA_PRECIOS = """
WITH ordenado AS (
    SELECT p.ticker, a.nombre, a.tipo, p.fecha, p.cierre,
           ROW_NUMBER() OVER (PARTITION BY p.ticker ORDER BY p.fecha DESC) AS n
    FROM precios p JOIN activos a ON a.clave = p.ticker
)
SELECT ticker, nombre, tipo,
       MAX(CASE WHEN n = 1  THEN fecha  END) AS fecha,
       MAX(CASE WHEN n = 1  THEN cierre END) AS cierre,
       MAX(CASE WHEN n = 2  THEN cierre END) AS cierre_1d,
       MAX(CASE WHEN n = 6  THEN cierre END) AS cierre_5d,
       MAX(CASE WHEN n = 22 THEN cierre END) AS cierre_1m
FROM ordenado
GROUP BY ticker, nombre, tipo
ORDER BY tipo DESC, nombre
"""

CONSULTA_MACRO = """
WITH ordenado AS (
    SELECT m.fuente, m.serie, a.nombre, m.fecha, m.valor,
           ROW_NUMBER() OVER (PARTITION BY m.serie ORDER BY m.fecha DESC) AS n
    FROM macro m JOIN activos a ON a.clave = m.serie
    WHERE m.valor IS NOT NULL
)
SELECT fuente, serie, nombre, fecha, valor
FROM ordenado WHERE n = 1
ORDER BY fuente, nombre
"""


def variacion(actual: pd.Series, previo: pd.Series) -> pd.Series:
    return ((actual / previo - 1) * 100).round(2)


CONSULTA_SENALES = """
SELECT e.ticker, act.nombre, e.direccion, a.confianza, a.resumen, n.medio, n.publicada
FROM efectos e
JOIN analisis a  ON a.noticia_id = e.noticia_id
JOIN noticias n  ON n.id = e.noticia_id
JOIN activos act ON act.clave = e.ticker
WHERE n.publicada >= ?
ORDER BY act.tipo DESC, act.nombre,
         CASE a.confianza WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END, n.publicada DESC
"""
SENALES_POR_ACTIVO = 3


def imprimir_senales(s: pd.DataFrame, total: int, relevantes: int) -> None:
    print(f"\nSEÑALES DE NOTICIAS (últimas 24 h: {relevantes} relevantes de {total} analizadas)")
    print("  Lo que la IA lee en las notas, no un pronóstico de precio.")
    for (ticker, nombre), g in s.groupby(["ticker", "nombre"], sort=False):
        conteo = g["direccion"].value_counts()
        print(f"\n  {nombre} ({ticker}): sube {conteo.get('sube', 0)}, baja {conteo.get('baja', 0)}, "
              f"incierto {conteo.get('incierto', 0)}")
        for _, f in g.head(SENALES_POR_ACTIVO).iterrows():
            print(f"    [{f['direccion']}, confianza {f['confianza']}] {f['resumen']} ({f['medio']})")


def imprimir_noticias(n: pd.DataFrame, nombres: dict) -> None:
    print(f"\nNOTICIAS (últimas 24 h: {len(n)})")
    if n.empty:
        return
    hora = lambda s: s[11:16] if isinstance(s, str) else "     "

    temas = n[n["clave"].notna()]
    for clave, grupo in temas.groupby("clave", sort=False):
        print(f"\n  {nombres.get(clave, clave)} ({len(grupo)})")
        for _, f in grupo.head(TITULARES_POR_TEMA).iterrows():
            print(f"    {hora(f['publicada'])}  {f['titulo'][:95]}  [{f['medio']}]")

    print("\n  Generales")
    for _, f in n[n["clave"].isna()].head(TITULARES_GENERALES).iterrows():
        print(f"    {hora(f['publicada'])}  {f['titulo'][:95]}  [{f['medio']}]")
    print("\n  Horas en UTC (Ciudad de México = UTC - 6).")


def main() -> None:
    con = db.conectar()
    p = pd.read_sql(CONSULTA_PRECIOS, con)
    m = pd.read_sql(CONSULTA_MACRO, con)
    n = noticias.recientes(con)
    nombres = dict(con.execute("SELECT clave, nombre FROM activos").fetchall())
    desde = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    s = pd.read_sql(CONSULTA_SENALES, con, params=(desde,))
    total, relevantes = con.execute(
        """SELECT COUNT(*), COALESCE(SUM(a.relevante), 0) FROM analisis a
           JOIN noticias n ON n.id = a.noticia_id WHERE n.publicada >= ?""", (desde,)).fetchone()
    gasto = con.execute("SELECT COALESCE(SUM(costo_usd), 0) FROM uso_api").fetchone()[0]
    con.close()

    if p.empty and m.empty and n.empty:
        print("La base está vacía. Corre primero:  python -m radar.actualizar")
        return

    if not p.empty:
        p["1 día %"] = variacion(p["cierre"], p["cierre_1d"])
        p["5 días %"] = variacion(p["cierre"], p["cierre_5d"])
        p["1 mes %"] = variacion(p["cierre"], p["cierre_1m"])
        p["cierre"] = p["cierre"].round(2)
        print("\nMERCADOS")
        print(p[["nombre", "fecha", "cierre", "1 día %", "5 días %", "1 mes %"]].to_string(index=False))

    if not m.empty:
        print("\nMACRO (último dato)")
        print(m[["fuente", "nombre", "fecha", "valor"]].to_string(index=False))

    if total:
        imprimir_senales(s, total, relevantes)
        print(f"\n  Gasto acumulado en la API de Anthropic: ~US${gasto:.4f}")
    else:  # sin análisis todavía: mostrar titulares sin filtrar
        imprimir_noticias(n, nombres)


if __name__ == "__main__":
    main()
