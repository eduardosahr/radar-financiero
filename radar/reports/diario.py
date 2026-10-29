"""Informe diario en HTML (un solo archivo, sin dependencias) y su resumen corto para Telegram."""

from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

import pandas as pd

from radar.config import RAIZ

CARPETA = RAIZ / "reportes"
CDMX = timezone(timedelta(hours=-6))  # Ciudad de México no tiene horario de verano desde 2022
UMBRAL_ALERTA_PCT = 3.0
SENALES_POR_ACTIVO = 3
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]  # %A depende del idioma del sistema

ESTILO = """
:root { --fondo:#fff; --texto:#1d1d1f; --suave:#6e6e73; --linea:#e5e5ea; --sube:#0a7d32; --baja:#c0262d; --caja:#f5f5f7; }
@media (prefers-color-scheme: dark) {
  :root { --fondo:#111; --texto:#f2f2f2; --suave:#a1a1a6; --linea:#2c2c2e; --sube:#35c759; --baja:#ff6961; --caja:#1c1c1e; }
}
body { background:var(--fondo); color:var(--texto); font:15px/1.5 -apple-system, "Segoe UI", Roboto, sans-serif;
       max-width:860px; margin:0 auto; padding:16px; }
h1 { font-size:22px; margin:0 0 4px; } h2 { font-size:17px; margin:28px 0 8px; }
.suave { color:var(--suave); font-size:13px; }
table { border-collapse:collapse; width:100%; font-size:14px; }
th, td { padding:6px 8px; border-bottom:1px solid var(--linea); text-align:right; white-space:nowrap; }
th:first-child, td:first-child { text-align:left; }
.sube { color:var(--sube); } .baja { color:var(--baja); }
.caja { background:var(--caja); border-radius:8px; padding:10px 14px; margin:8px 0; }
.caja ul { margin:6px 0 0; padding-left:18px; } a { color:inherit; }
.tabla { overflow-x:auto; }
"""


def _pct(x) -> str:
    if pd.isna(x):
        return "<td>–</td>"
    clase = "sube" if x > 0 else "baja" if x < 0 else ""
    return f'<td class="{clase}">{x:+.2f}%</td>'


def alertas(d: dict) -> list[str]:
    """Movimientos grandes del día y noticias de confianza alta."""
    lista = []
    p = d["precios"]
    if not p.empty:
        for _, f in p[p["1 día %"].abs() >= UMBRAL_ALERTA_PCT].iterrows():
            lista.append(f"{f['nombre']} se movió {f['1 día %']:+.2f}% en la última sesión ({f['fecha']}).")
    s = d["senales"]
    if not s.empty:
        altas = s[(s["confianza"] == "alta") & (s["direccion"] != "incierto")].drop_duplicates("resumen")
        for _, f in altas.head(5).iterrows():
            lista.append(f"{f['nombre']}: {f['direccion']} — {f['resumen']}")
    return lista


def generar(d: dict) -> Path:
    ahora = datetime.now(CDMX)
    partes = [f"<!doctype html><html lang='es'><head><meta charset='utf-8'>"
              f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
              f"<title>Radar Financiero {ahora:%Y-%m-%d}</title><style>{ESTILO}</style></head><body>",
              f"<h1>Radar Financiero</h1><div class='suave'>{DIAS[ahora.weekday()]} {ahora:%d/%m/%Y, %H:%M} (hora CDMX). "
              "Las señales son lectura de noticias hecha por IA, no recomendaciones de inversión.</div>"]

    a = alertas(d)
    partes.append("<h2>Lo importante</h2>")
    partes.append("<div class='caja'><ul>" + "".join(f"<li>{escape(x)}</li>" for x in a) + "</ul></div>"
                  if a else "<p class='suave'>Sin movimientos mayores a 3% ni noticias de confianza alta.</p>")

    p = d["precios"]
    if not p.empty:
        filas = "".join(f"<tr><td>{escape(f['nombre'])}</td><td>{f['cierre']:,.2f}</td>{_pct(f['1 día %'])}"
                        f"{_pct(f['5 días %'])}{_pct(f['1 mes %'])}<td class='suave'>{f['fecha']}</td></tr>"
                        for _, f in p.iterrows())
        partes.append("<h2>Mercados</h2><div class='tabla'><table><tr><th>Activo</th><th>Cierre</th><th>1 día</th>"
                      f"<th>5 días</th><th>1 mes</th><th>Fecha</th></tr>{filas}</table></div>")

    m = d["macro"]
    if not m.empty:
        filas = "".join(f"<tr><td>{escape(f['nombre'])}</td><td>{f['valor']:,.4g}</td>"
                        f"<td class='suave'>{f['fecha']}</td></tr>" for _, f in m.iterrows())
        partes.append("<h2>Macro</h2><div class='tabla'><table><tr><th>Indicador</th><th>Último dato</th>"
                      f"<th>Fecha</th></tr>{filas}</table></div>")

    s = d["senales"]
    partes.append(f"<h2>Señales de noticias</h2><div class='suave'>Últimas 24 h: {d['relevantes']} notas "
                  f"relevantes de {d['analizadas']} analizadas.</div>")
    for (ticker, nombre), g in s.groupby(["ticker", "nombre"], sort=False):
        c = g["direccion"].value_counts()
        items = "".join(
            f"<li><b class='{f['direccion'] if f['direccion'] != 'incierto' else ''}'>{f['direccion']}</b> "
            f"<span class='suave'>({f['confianza']})</span> {escape(f['resumen'])} "
            f"<a class='suave' href='{escape(f['url'] or '#')}'>{escape(f['medio'] or 'nota')}</a></li>"
            for _, f in g.head(SENALES_POR_ACTIVO).iterrows())
        partes.append(f"<div class='caja'><b>{escape(nombre)}</b> <span class='suave'>{escape(ticker)} · "
                      f"sube {c.get('sube', 0)} · baja {c.get('baja', 0)} · incierto {c.get('incierto', 0)}"
                      f"</span><ul>{items}</ul></div>")

    partes.append(f"<p class='suave'>Gasto acumulado en la API de Anthropic: ~US${d['gasto_usd']:.4f}. "
                  "Fuentes: Yahoo Finance, Banxico SIE, FRED, Google Noticias y RSS de medios.</p></body></html>")

    CARPETA.mkdir(exist_ok=True)
    ruta = CARPETA / f"radar_{ahora:%Y-%m-%d}.html"
    ruta.write_text("".join(partes), encoding="utf-8")
    return ruta


def texto_corto(d: dict) -> str:
    """Mensaje de Telegram (máx. 4,096 caracteres; formato HTML de Telegram)."""
    lineas = [f"<b>Radar Financiero</b> · {datetime.now(CDMX):%d/%m/%Y}"]
    p = d["precios"]
    if not p.empty:
        clave = p[p["ticker"].isin(["^MXX", "^GSPC", "MXN=X", "CL=F"])]
        lineas.append("")
        lineas += [f"{escape(f['nombre'])}: {f['cierre']:,.2f} ({f['1 día %']:+.2f}%)" for _, f in clave.iterrows()]
    a = alertas(d)
    if a:
        lineas += ["", "<b>Lo importante</b>"] + [f"• {escape(x)}" for x in a]
    lineas += ["", f"{d['relevantes']} notas relevantes de {d['analizadas']}. Informe completo adjunto."]
    return "\n".join(lineas)[:4000]
