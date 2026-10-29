"""Descarga todo lo nuevo y lo guarda en data/radar.db.

Uso:  python -m radar.actualizar
"""

import warnings

from radar import db
from radar.collectors import macro, noticias, precios
from radar.config import cargar_watchlist

# yfinance aún usa funciones de pandas que pandas 3 marca como obsoletas; no afectan los datos.
warnings.filterwarnings("ignore", module="yfinance")


def main() -> None:
    watchlist = cargar_watchlist()
    con = db.conectar()
    print("Precios (Yahoo Finance):")
    precios.actualizar(con, watchlist)
    print("Macro (Banxico y FRED):")
    macro.actualizar(con, watchlist)
    print("Noticias (Google Noticias y RSS):")
    noticias.actualizar(con, watchlist)
    con.close()
    print("Listo. Ver resumen con:  python -m radar.resumen")


if __name__ == "__main__":
    main()
