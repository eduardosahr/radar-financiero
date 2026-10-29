"""Muestra un resumen de la lista de seguimiento a partir de la base de datos.

Uso:  python -m radar.resumen
"""

import pandas as pd

from radar import db

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


def main() -> None:
    con = db.conectar()
    p = pd.read_sql(CONSULTA_PRECIOS, con)
    m = pd.read_sql(CONSULTA_MACRO, con)
    con.close()

    if p.empty and m.empty:
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


if __name__ == "__main__":
    main()
