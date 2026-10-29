"""Ficha de una emisora: perfil, razones financieras, desempeño del precio y señales de noticias.

Uso:  python -m radar.ficha WALMEX.MX          (sin IA)
      python -m radar.ficha WALMEX.MX --ia     (agrega interpretación de Claude, ~US$0.001)
      python -m radar.ficha                    (lista de emisoras disponibles)
"""

import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

from radar import db
from radar.analysis import llm, ratios
from radar.config import cargar_watchlist

PERIODOS_ANUALES = 4
PERIODOS_TRIMESTRALES = 5
DIAS_SENALES = 7


def rendimientos(con, ticker: str) -> dict:
    p = pd.read_sql("SELECT fecha, cierre FROM precios WHERE ticker = ? ORDER BY fecha", con, params=(ticker,))
    if p.empty:
        return {}
    p["fecha"] = pd.to_datetime(p["fecha"])
    s = p.set_index("fecha")["cierre"]
    ultimo = s.iloc[-1]

    def desde(dias):
        previo = s[s.index <= s.index[-1] - timedelta(days=dias)]
        return round((ultimo / previo.iloc[-1] - 1) * 100, 1) if not previo.empty else None

    return {"cierre": round(ultimo, 2), "fecha": s.index[-1].strftime("%Y-%m-%d"),
            "1 mes %": desde(30), "1 año %": desde(365), "3 años %": desde(3 * 365)}


def senales(con, ticker: str) -> pd.DataFrame:
    desde = (datetime.now(timezone.utc) - timedelta(days=DIAS_SENALES)).strftime("%Y-%m-%d %H:%M:%S")
    return pd.read_sql(
        """SELECT substr(n.publicada, 1, 10) AS fecha, e.direccion, a.confianza, a.resumen, n.medio
           FROM efectos e JOIN analisis a ON a.noticia_id = e.noticia_id JOIN noticias n ON n.id = e.noticia_id
           WHERE e.ticker = ? AND n.publicada >= ?
           ORDER BY CASE a.confianza WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END, n.publicada DESC""",
        con, params=(ticker, desde))


def armar(con, ticker: str, nombre: str) -> str:
    """Devuelve la ficha como texto (se imprime y también se le pasa a la IA)."""
    lineas = [f"FICHA: {nombre} ({ticker})"]
    perfil = con.execute("SELECT nombre_largo, sector, industria, moneda, capitalizacion, pu, p_vl, "
                         "rend_dividendo, actualizado FROM perfil WHERE ticker = ?", (ticker,)).fetchone()
    if perfil:
        largo, sector, industria, moneda, cap, pu, pvl, div, act = perfil
        cap_txt = f"{cap / 1e9:,.0f} mil millones {moneda}" if cap else "n.d."
        fmt = lambda x: f"{x:.1f}" if x else "n.d."
        lineas += [f"{largo} | {sector} / {industria}",
                   f"Capitalización: {cap_txt} | P/U: {fmt(pu)} | P/VL: {fmt(pvl)} | "
                   f"Dividendo: {fmt(div)}% | datos al {act[:10]}"]

    r = rendimientos(con, ticker)
    if r:
        lineas.append(f"Precio: {r['cierre']} ({r['fecha']}) | 1 mes: {r['1 mes %']}% | "
                      f"1 año: {r['1 año %']}% | 3 años: {r['3 años %']}%")

    for frecuencia, n in [("anual", PERIODOS_ANUALES), ("trimestral", PERIODOS_TRIMESTRALES)]:
        tabla = ratios.calcular(con, ticker, frecuencia)
        if not tabla.empty:
            lineas += ["", f"Razones financieras ({frecuencia}; mdp = millones de pesos):",
                       tabla.tail(n).T.to_string()]

    s = senales(con, ticker)
    lineas += ["", f"Señales de noticias (últimos {DIAS_SENALES} días): {len(s)}"]
    for _, f in s.head(6).iterrows():
        lineas.append(f"  {f['fecha']} [{f['direccion']}, {f['confianza']}] {f['resumen']} ({f['medio']})")
    return "\n".join(lineas)


def main() -> None:
    w = cargar_watchlist()
    emisoras = w["precios"]["emisoras"]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args or args[0].upper() not in emisoras:
        print("Uso: python -m radar.ficha TICKER [--ia]\nEmisoras:")
        for t, n in emisoras.items():
            print(f"  {t:<14} {n}")
        return

    ticker = args[0].upper()
    con = db.conectar()
    texto = armar(con, ticker, emisoras[ticker])
    print(texto)
    if "--ia" in sys.argv:
        print("\nINTERPRETACIÓN (Claude; educativa, no es recomendación):")
        print(llm.interpretar_ficha(con, w["analisis"], texto))
    con.close()


if __name__ == "__main__":
    main()
