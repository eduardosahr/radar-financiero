@echo off
rem Lo ejecuta la tarea programada de Windows "RadarFinanciero" (lunes a viernes, 7:30).
rem Cada corrida queda registrada en data\logs\diario.log
cd /d "%~dp0"
if not exist data\logs mkdir data\logs
set PYTHONIOENCODING=utf-8
echo ===== %date% %time% ===== >> "data\logs\diario.log"
".venv\Scripts\python.exe" -m radar.diario >> "data\logs\diario.log" 2>&1
