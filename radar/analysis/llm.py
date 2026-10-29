"""Clasifica noticias con Claude: relevancia, activos afectados, dirección probable y confianza.

La IA resume y clasifica; no predice precios. La fase 6 medirá qué tan seguido acierta.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

import anthropic
import pandas as pd
from pydantic import BaseModel

from radar import db
from radar.config import llave

INSTRUCCIONES = """Eres analista de mercados para un inversionista mexicano. Recibirás titulares \
de noticias, cada uno con un id. Para cada uno decide:

- relevante: true solo si la nota puede mover el precio de algún activo de la lista, los mercados \
mexicanos (IPC, peso, tasas de Banxico) o los mercados globales (tasas de la Fed, S&P 500, \
petróleo, oro). Deportes, espectáculos, crimen sin efecto económico, consejos de finanzas \
personales, trámites y notas que solo mencionan una marca de paso NO son relevantes.
- categoria: el tema principal.
- efectos: los activos de la lista que la nota puede mover y hacia dónde iría su precio \
(sube, baja o incierto). Usa solo tickers de la lista. Lista vacía si no es relevante. \
No asignes al índice (^MXX, ^GSPC) la noticia de una sola empresa que no está en la lista, \
salvo que sea de las más grandes del índice.
- MXN=X es cuántos pesos cuesta un dólar. Dólar más fuerte o peso más débil: MXN=X sube. \
Peso más fuerte o dólar más débil: MXN=X baja. Revisa que la dirección coincida con tu resumen.
- horizonte: en cuánto tiempo se notaría el efecto.
- confianza: alta solo si el efecto es directo y claro (resultados trimestrales, decisión de \
tasas); baja si es especulativo.
- resumen: una oración en español que diga qué pasó y por qué importa. Si no es relevante, \
máximo 10 palabras.

Responde para todos los ids recibidos, sin omitir ninguno.

Activos de la lista:
{activos}"""


class Efecto(BaseModel):
    ticker: str
    direccion: Literal["sube", "baja", "incierto"]


class AnalisisNoticia(BaseModel):
    # El modelo llena los campos en este orden: el resumen va antes de los efectos
    # para que decida la dirección después de explicar qué pasó.
    id: str
    relevante: bool
    categoria: Literal[
        "politica_monetaria", "macroeconomia", "resultados_empresa", "empresa_otro",
        "sector_financiero", "regulacion", "comercio_y_geopolitica", "materias_primas", "mercados", "otro",
    ]
    resumen: str
    efectos: list[Efecto]
    horizonte: Literal["dias", "semanas", "meses"]
    confianza: Literal["baja", "media", "alta"]


class Lote(BaseModel):
    analisis: list[AnalisisNoticia]


def pendientes(con, horas: int, limite: int) -> pd.DataFrame:
    desde = (datetime.now(timezone.utc) - timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
    return pd.read_sql(
        """SELECT n.id, n.publicada, n.medio, n.titulo, n.resumen
           FROM noticias n LEFT JOIN analisis a ON a.noticia_id = n.id
           WHERE a.noticia_id IS NULL AND n.publicada >= ?
           ORDER BY n.publicada DESC LIMIT ?""",
        con, params=(desde, limite))


def como_texto(lote: pd.DataFrame) -> str:
    lineas = []
    for _, n in lote.iterrows():
        linea = f"[{n['id']}] ({n['medio']}, {n['publicada']} UTC) {n['titulo']}"
        if isinstance(n["resumen"], str) and n["resumen"]:  # pandas lee los NULL como NaN
            linea += f" | {n['resumen'][:400]}"
        lineas.append(linea)
    return "\n".join(lineas)


def analizar_lote(client, modelo: str, sistema: str, lote: pd.DataFrame):
    respuesta = client.messages.parse(
        model=modelo,
        max_tokens=16000,
        system=sistema,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": como_texto(lote)}],
        output_format=Lote,
    )
    if respuesta.stop_reason != "end_turn" or respuesta.parsed_output is None:
        raise RuntimeError(f"respuesta incompleta (stop_reason={respuesta.stop_reason})")
    return respuesta.parsed_output.analisis, respuesta.usage


def guardar_resultados(con, resultados: list[AnalisisNoticia], ids_validos: set, tickers: set, modelo: str) -> int:
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    filas, efectos = [], []
    for r in resultados:
        if r.id not in ids_validos:  # el modelo inventó o alteró un id
            continue
        filas.append({"noticia_id": r.id, "relevante": int(r.relevante), "categoria": r.categoria,
                      "horizonte": r.horizonte, "confianza": r.confianza, "resumen": r.resumen,
                      "modelo": modelo, "analizada": ahora})
        if r.relevante:
            efectos += [{"noticia_id": r.id, "ticker": e.ticker, "direccion": e.direccion}
                        for e in r.efectos if e.ticker in tickers]
    db.guardar(con, "analisis", pd.DataFrame(filas))
    db.guardar(con, "efectos", pd.DataFrame(efectos))
    return len(filas)


def actualizar(con, watchlist: dict) -> None:
    cfg = watchlist["analisis"]
    if not cfg["activo"]:
        print("  análisis desactivado en watchlist.yaml")
        return
    if not llave("ANTHROPIC_API_KEY"):
        print("  sin ANTHROPIC_API_KEY en .env, se omite")
        return

    activos = {**watchlist["precios"]["indices_y_mercados"], **watchlist["precios"]["emisoras"]}
    sistema = INSTRUCCIONES.format(activos="\n".join(f"- {t}: {n}" for t, n in activos.items()))
    modelo, tam = cfg["modelo"], cfg["notas_por_llamada"]

    notas = pendientes(con, cfg["horas_atras"], cfg["maximo_por_corrida"])
    if notas.empty:
        print("  no hay notas nuevas por analizar")
        return

    client = anthropic.Anthropic()
    llamadas = entrada = salida = analizadas = 0
    for inicio in range(0, len(notas), tam):
        lote = notas.iloc[inicio:inicio + tam]
        try:
            resultados, uso = analizar_lote(client, modelo, sistema, lote)
        except anthropic.AuthenticationError:
            print("  ERROR: la llave de Anthropic no es válida; revisa .env")
            break
        except anthropic.PermissionDeniedError as e:
            print(f"  ERROR de permisos o saldo: {e.message}")
            break
        except (anthropic.APIError, RuntimeError) as e:  # un lote con error no detiene los demás
            print(f"  lote {inicio // tam + 1}: ERROR {e}")
            continue
        llamadas += 1
        entrada += uso.input_tokens
        salida += uso.output_tokens
        analizadas += guardar_resultados(con, resultados, set(lote["id"]), set(activos), modelo)

    precio = cfg["precio_usd_por_millon"]
    costo = (entrada * precio["entrada"] + salida * precio["salida"]) / 1_000_000
    if llamadas:
        db.guardar(con, "uso_api", pd.DataFrame([{
            "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "modelo": modelo,
            "llamadas": llamadas, "tokens_entrada": entrada, "tokens_salida": salida, "costo_usd": costo}]))
    print(f"  {analizadas} de {len(notas)} notas analizadas en {llamadas} llamadas "
          f"({entrada:,} tokens de entrada, {salida:,} de salida, ~US${costo:.4f})")
