"""Analiza con Claude las notas que aún no tienen análisis.

Uso:  python -m radar.analizar
(radar.actualizar ya lo corre al final; este comando sirve para analizar sin volver a descargar)
"""

from radar import db
from radar.analysis import llm
from radar.config import cargar_watchlist


def main() -> None:
    con = db.conectar()
    print("Análisis de noticias (Claude):")
    llm.actualizar(con, cargar_watchlist())
    con.close()


if __name__ == "__main__":
    main()
