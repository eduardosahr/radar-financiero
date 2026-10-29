"""Base de datos SQLite donde el Radar guarda todo lo que descarga."""

import sqlite3

import pandas as pd

from radar.config import RUTA_DB

ESQUEMA = """
CREATE TABLE IF NOT EXISTS precios (
    ticker  TEXT NOT NULL,
    fecha   TEXT NOT NULL,          -- AAAA-MM-DD
    apertura REAL, maximo REAL, minimo REAL, cierre REAL, volumen REAL,
    PRIMARY KEY (ticker, fecha)
);

CREATE TABLE IF NOT EXISTS macro (
    fuente  TEXT NOT NULL,          -- banxico | fred
    serie   TEXT NOT NULL,
    fecha   TEXT NOT NULL,          -- AAAA-MM-DD
    valor   REAL,
    PRIMARY KEY (fuente, serie, fecha)
);

CREATE TABLE IF NOT EXISTS noticias (
    id          TEXT PRIMARY KEY,   -- huella del título normalizado (detecta la misma nota en varias fuentes)
    publicada   TEXT,               -- AAAA-MM-DD HH:MM:SS en UTC
    medio       TEXT,               -- quién la publicó
    titulo      TEXT NOT NULL,
    resumen     TEXT,
    url         TEXT,
    origen      TEXT NOT NULL,      -- nombre del feed, o "google:<clave de búsqueda>"
    clave       TEXT,               -- ticker o tema de la búsqueda que la encontró
    descargada  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_noticias_publicada ON noticias (publicada);

CREATE TABLE IF NOT EXISTS analisis (
    noticia_id  TEXT PRIMARY KEY REFERENCES noticias (id),
    relevante   INTEGER NOT NULL,   -- 1 si puede mover algún activo o el mercado mexicano
    categoria   TEXT,
    horizonte   TEXT,               -- dias | semanas | meses
    confianza   TEXT,               -- baja | media | alta
    resumen     TEXT,
    modelo      TEXT NOT NULL,
    analizada   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS efectos (
    noticia_id  TEXT NOT NULL REFERENCES noticias (id),
    ticker      TEXT NOT NULL,
    direccion   TEXT NOT NULL,      -- sube | baja | incierto (precio del ticker)
    PRIMARY KEY (noticia_id, ticker)
);

CREATE TABLE IF NOT EXISTS uso_api (
    fecha          TEXT NOT NULL,   -- AAAA-MM-DD HH:MM:SS UTC
    modelo         TEXT NOT NULL,
    llamadas       INTEGER NOT NULL,
    tokens_entrada INTEGER NOT NULL,
    tokens_salida  INTEGER NOT NULL,
    costo_usd      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS activos (
    clave   TEXT PRIMARY KEY,       -- ticker o id de serie
    nombre  TEXT NOT NULL,
    tipo    TEXT NOT NULL           -- indice | emisora | banxico | fred
);
"""


def conectar() -> sqlite3.Connection:
    RUTA_DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(RUTA_DB)
    con.executescript(ESQUEMA)
    return con


def guardar(con: sqlite3.Connection, tabla: str, df: pd.DataFrame, reemplazar: bool = True) -> int:
    """Inserta filas. Si ya existen (misma llave), las reemplaza, o las deja como están
    con reemplazar=False. Devuelve cuántas filas nuevas o cambiadas se escribieron."""
    if df.empty:
        return 0
    columnas = ", ".join(df.columns)
    marcas = ", ".join("?" for _ in df.columns)
    accion = "REPLACE" if reemplazar else "IGNORE"
    antes = con.total_changes
    con.executemany(
        f"INSERT OR {accion} INTO {tabla} ({columnas}) VALUES ({marcas})",
        df.itertuples(index=False, name=None),
    )
    con.commit()
    return con.total_changes - antes


def ultima_fecha(con: sqlite3.Connection, tabla: str, filtro: str, valor: str) -> str | None:
    """Última fecha guardada para un ticker o serie, para descargar solo lo nuevo."""
    fila = con.execute(f"SELECT MAX(fecha) FROM {tabla} WHERE {filtro} = ?", (valor,)).fetchone()
    return fila[0]
