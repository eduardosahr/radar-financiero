# Radar Financiero

Herramienta personal que descarga precios de mercados y datos macroeconómicos de México y EE. UU., los guarda en SQLite y muestra un resumen diario. La IA (Claude) se usa para resumir y clasificar información, no para adivinar precios.

## Estado

- [x] Fase 0: entorno (Python 3.12, entorno virtual, dependencias)
- [x] Fase 1: precios de 16 activos (Yahoo Finance) y 9 series macro (Banxico SIE y FRED) en SQLite, descarga incremental, resumen con variaciones a 1 día, 5 días y 1 mes
- [ ] Fase 2: noticias (RSS y GDELT)
- [ ] Fase 3: análisis de noticias con Claude (resumen, activos afectados, impacto probable, confianza)
- [ ] Fase 4: fichas de empresa (SEC EDGAR, BMV) y razones financieras
- [ ] Fase 5: informe diario y panel en Streamlit
- [ ] Fase 6: medir aciertos del análisis contra el movimiento real del mercado

## Instalación (una sola vez)

En PowerShell, dentro de esta carpeta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

Luego abre `.env` y pega tus llaves gratuitas:

- **BANXICO_TOKEN:** https://www.banxico.org.mx/SieAPIRest/service/v1/token
- **FRED_API_KEY:** https://fred.stlouisfed.org/docs/api/api_key.html

## Uso diario

```powershell
.\.venv\Scripts\python.exe -m radar.actualizar   # descarga lo nuevo
.\.venv\Scripts\python.exe -m radar.resumen      # muestra el resumen
```

La primera vez descarga la historia desde 2020 (precios) y 2015 (macro); después solo lo nuevo.

## Agregar o quitar activos

Edita `config/watchlist.yaml`. Los tickers usan el formato de Yahoo Finance (emisoras mexicanas terminan en `.MX`). Las series de Banxico se buscan en su [catálogo](https://www.banxico.org.mx/SieAPIRest/service/v1/doc/catalogoSeries) y las de FRED en https://fred.stlouisfed.org.

## Estructura

```
config/watchlist.yaml       activos y series a seguir
radar/config.py             rutas, lista de seguimiento y llaves
radar/db.py                 esquema SQLite y guardado
radar/collectors/precios.py Yahoo Finance (yfinance)
radar/collectors/macro.py   Banxico SIE y FRED
radar/actualizar.py         descarga todo
radar/resumen.py            resumen de mercados y macro (consultas SQL)
data/radar.db               base de datos (no se sube a GitHub)
```

## Practicar SQL con tus datos

La base `data/radar.db` se puede abrir con [DB Browser for SQLite](https://sqlitebrowser.org/) o desde Python. Ejercicios sugeridos:

1. Rendimiento anual de cada emisora por año.
2. Los 10 días de mayor caída del IPC y qué hizo el USD/MXN esos días.
3. Correlación entre Banorte y el IPC (en pandas).
4. Volatilidad de 30 días de cada activo (función de ventana).
