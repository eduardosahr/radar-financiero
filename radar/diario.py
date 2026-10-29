"""Rutina diaria: descarga y analiza todo, genera el informe HTML y lo envía por Telegram.

Uso:  python -m radar.diario               (lo que corre la tarea programada)
      python -m radar.diario --abrir       (además abre el informe en el navegador)
      python -m radar.diario --solo-informe (no descarga; usa lo que ya hay en la base)
      python -m radar.diario --telegram-id (muestra tu chat id para configurar Telegram)
"""

import sys
import webbrowser

from radar import actualizar, db, resumen
from radar.reports import diario, telegram


def main() -> None:
    if "--telegram-id" in sys.argv:
        telegram.mostrar_chat_id()
        return

    if "--solo-informe" not in sys.argv:
        actualizar.main()

    con = db.conectar()
    datos = resumen.cargar(con)
    con.close()

    ruta = diario.generar(datos)
    print(f"Informe: {ruta}")

    if telegram.configurado():
        try:
            telegram.enviar(diario.texto_corto(datos), ruta)
            print("Enviado por Telegram.")
        except Exception as e:  # el informe ya quedó guardado aunque falle el envío
            print(f"Telegram: ERROR {e}")
    else:
        print("Telegram no configurado (ver radar/reports/telegram.py).")

    if "--abrir" in sys.argv:
        webbrowser.open(ruta.as_uri())


if __name__ == "__main__":
    main()
