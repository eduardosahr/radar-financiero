# Radar Financiero

Herramienta personal que descarga precios de mercados y datos macroeconómicos de México y EE. UU., los guarda en SQLite y muestra un resumen diario. La IA (Claude) se usa para resumir y clasificar información, no para adivinar precios.

## Estado

- [x] Fase 0: entorno (Python 3.12, entorno virtual, dependencias)
- [x] Fase 1: precios de 16 activos (Yahoo Finance) y 9 series macro (Banxico SIE y FRED) en SQLite, descarga incremental, resumen con variaciones a 1 día, 5 días y 1 mes
- [x] Fase 2: noticias de 8 feeds RSS de medios (El Financiero, El Economista, Expansión, Fed, CNBC, MarketWatch) y 14 búsquedas en Google Noticias (por emisora y por tema), sin duplicados entre fuentes
- [x] Fase 3: análisis de noticias con Claude Haiku 5.5 (relevancia, activos afectados, dirección probable, horizonte, confianza, resumen en español) con salida estructurada validada; ~US$0.01 por cada 100 notas
- [x] Fase 4: estados financieros trimestrales y anuales de las 10 emisoras (Yahoo Finance), razones financieras con control de calidad y ficha por emisora con interpretación opcional de Claude
- [x] Fase 5: informe diario en HTML, envío opcional por Telegram y lanzador para el Programador de tareas de Windows
- [ ] Panel interactivo (Streamlit)
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
- **ANTHROPIC_API_KEY:** https://console.anthropic.com (se paga por uso; configura un límite de gasto mensual en *Limits*)

## Uso diario

```powershell
.\.venv\Scripts\python.exe -m radar.actualizar   # descarga lo nuevo y analiza las notas nuevas
.\.venv\Scripts\python.exe -m radar.resumen      # mercados, macro y señales de noticias
.\.venv\Scripts\python.exe -m radar.analizar     # solo analizar, sin descargar
.\.venv\Scripts\python.exe -m radar.ficha WALMEX.MX --ia   # ficha de una emisora
.\.venv\Scripts\python.exe -m radar.diario --abrir         # todo lo anterior + informe HTML
```

## Fichas de empresa

`radar.ficha TICKER` muestra perfil (sector, capitalización, P/U, P/VL, dividendo), rendimiento del precio a 1 mes, 1 y 3 años, razones financieras anuales y trimestrales, y las señales de noticias de la semana. Con `--ia`, Claude agrega fortalezas, riesgos y qué vigilar (~US$0.001 por ficha).

Razones (`radar/analysis/ratios.py`): margen operativo y neto, ROE y ROA (anuales), deuda/capital, liquidez, flujo libre y crecimiento de ingresos contra el mismo periodo del año anterior. En bancos y FIBRAs algunas no aplican y se omiten. Control de calidad: Yahoo a veces publica ingresos negativos (Banorte 2T25); esas cifras se descartan. Los estados se revisan como máximo una vez por semana.

## Informe diario automático

`radar.diario` corre todo, guarda `reportes/radar_AAAA-MM-DD.html` (alertas, mercados, macro y señales con liga a cada nota) y, si está configurado, lo manda por Telegram (instrucciones en `radar/reports/telegram.py`).

Para que corra solo de lunes a viernes a las 7:30, crea la tarea en el Programador de tareas de Windows (PowerShell, desde esta carpeta):

```powershell
schtasks /Create /TN "RadarFinanciero" /TR "`"$((Resolve-Path .\run_diario.bat).Path)`"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 07:30 /F
```

La computadora debe estar encendida y con tu sesión iniciada. Cada corrida queda en `data/logs/diario.log`. Para quitarla: `schtasks /Delete /TN "RadarFinanciero" /F`.

La primera vez descarga la historia desde 2020 (precios) y 2015 (macro); después solo lo nuevo. Cada nota se analiza una sola vez.

## Análisis con IA

`radar/analysis/llm.py` manda las notas de las últimas 48 horas a Claude en lotes de 20 y recibe, validado con Pydantic, para cada una:

| Campo | Valores |
| --- | --- |
| relevante | sí / no (descarta deportes, espectáculos, crimen sin efecto económico) |
| categoria | política monetaria, macro, resultados de empresa, regulación, materias primas, etc. |
| resumen | una oración en español |
| efectos | ticker de la lista + dirección probable de su precio (sube, baja, incierto) |
| horizonte | días, semanas, meses |
| confianza | baja, media, alta |

Configuración en `watchlist.yaml` → `analisis`: modelo, lote, tope de notas por corrida (protege el gasto) y precios para estimar el costo. Cada corrida queda registrada en la tabla `uso_api`. Para apagarlo sin borrar nada: `activo: false`.

Es una lectura de las noticias, **no un pronóstico**. La fase 6 medirá qué tan seguido la dirección coincide con lo que hizo el precio.

## Agregar o quitar activos y noticias

Edita `config/watchlist.yaml`. Los tickers usan el formato de Yahoo Finance (emisoras mexicanas terminan en `.MX`). Las series de Banxico se buscan en su [catálogo](https://www.banxico.org.mx/SieAPIRest/service/v1/doc/catalogoSeries) y las de FRED en https://fred.stlouisfed.org.

En `noticias.busquedas`, la clave puede ser un ticker (la nota queda ligada a esa emisora) o un tema libre. Usa nombres completos y comillas: `Banorte` a secas trae notas del Estadio Banorte. Las búsquedas de Google Noticias traen algo de ruido; la fase 3 lo filtrará con IA.

Una misma nota publicada en varias fuentes se guarda una sola vez: se identifica por una huella del titular normalizado.

## Estructura

```
config/watchlist.yaml       activos y series a seguir
radar/config.py             rutas, lista de seguimiento y llaves
radar/db.py                 esquema SQLite y guardado
radar/collectors/precios.py Yahoo Finance (yfinance)
radar/collectors/macro.py   Banxico SIE y FRED
radar/collectors/noticias.py feeds RSS y Google Noticias
radar/analysis/llm.py       clasificación de noticias con Claude
radar/analizar.py           solo análisis
radar/collectors/empresas.py estados financieros y perfil (Yahoo Finance)
radar/analysis/ratios.py    razones financieras
radar/ficha.py              ficha por emisora
radar/reports/diario.py     informe HTML y mensaje corto
radar/reports/telegram.py   envío por Telegram
radar/diario.py             rutina diaria completa
run_diario.bat              lanzador para el Programador de tareas
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
5. Cuántas notas tuvo cada emisora por día y si los días con más notas coinciden con movimientos grandes de su precio (JOIN entre `noticias` y `precios`).
6. Porcentaje de notas relevantes por medio (tabla `analisis`): ¿qué fuente trae menos ruido?
7. Para cada emisora, señales "sube" menos señales "baja" por día, junto al rendimiento del día siguiente (`efectos` + `precios`). Es el primer borrador de la fase 6.
8. Ranking de emisoras por ROE del último año (tabla `estados`, conceptos `Net Income Common Stockholders` y `Stockholders Equity`), y compáralo con su P/VL de la tabla `perfil`.
