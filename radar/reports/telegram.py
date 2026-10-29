"""Envía el informe por Telegram con un bot propio (gratis).

Configuración (una vez):
1. En Telegram, habla con @BotFather, envía /newbot y sigue los pasos. Te da un token.
2. Escríbele cualquier mensaje a tu bot nuevo.
3. Pega el token en .env como TELEGRAM_BOT_TOKEN y corre:  python -m radar.diario --telegram-id
   Eso muestra tu chat id; pégalo en .env como TELEGRAM_CHAT_ID.
"""

from pathlib import Path

import requests

from radar.config import llave

API = "https://api.telegram.org/bot{token}/{metodo}"


def configurado() -> bool:
    return bool(llave("TELEGRAM_BOT_TOKEN") and llave("TELEGRAM_CHAT_ID"))


def _llamar(metodo: str, **kwargs) -> dict:
    r = requests.post(API.format(token=llave("TELEGRAM_BOT_TOKEN"), metodo=metodo), timeout=60, **kwargs)
    datos = r.json()
    if not datos.get("ok"):
        raise RuntimeError(datos.get("description", f"HTTP {r.status_code}"))
    return datos


def enviar(texto: str, archivo: Path) -> None:
    chat = llave("TELEGRAM_CHAT_ID")
    _llamar("sendMessage", data={"chat_id": chat, "text": texto, "parse_mode": "HTML",
                                 "disable_web_page_preview": "true"})
    with open(archivo, "rb") as f:
        _llamar("sendDocument", data={"chat_id": chat}, files={"document": (archivo.name, f, "text/html")})


def mostrar_chat_id() -> None:
    if not llave("TELEGRAM_BOT_TOKEN"):
        print("Falta TELEGRAM_BOT_TOKEN en .env (ver instrucciones en radar/reports/telegram.py).")
        return
    mensajes = _llamar("getUpdates")["result"]
    chats = {m["message"]["chat"]["id"]: m["message"]["chat"].get("first_name", "")
             for m in mensajes if "message" in m}
    if not chats:
        print("No hay mensajes. Escríbele algo a tu bot en Telegram y vuelve a correr este comando.")
    for chat_id, nombre in chats.items():
        print(f"TELEGRAM_CHAT_ID={chat_id}   ({nombre})")
