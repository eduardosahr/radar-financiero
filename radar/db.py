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


def guardar(con: sqlite3.Connection, tabla: str, df: pd.DataFrame) -> int:
    """Inserta filas; si ya existen (misma llave), las reemplaza. Devuelve cuántas se escribieron."""
    if df.empty:
        return 0
    columnas = ", ".join(df.columns)
    marcas = ", ".join("?" for _ in df.columns)
    con.executemany(
        f"INSERT OR REPLACE INTO {tabla} ({columnas}) VALUES ({marcas})",
        df.itertuples(index=False, name=None),
    )
    con.commit()
    return len(df)


def ultima_fecha(con: sqlite3.Connection, tabla: str, filtro: str, valor: str) -> str | None:
    """Última fecha guardada para un ticker o serie, para descargar solo lo nuevo."""
    fila = con.execute(f"SELECT MAX(fecha) FROM {tabla} WHERE {filtro} = ?", (valor,)).fetchone()
    return fila[0]
