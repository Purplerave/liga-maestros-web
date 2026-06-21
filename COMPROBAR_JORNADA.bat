@echo off
cd /d "%~dp0"
if "%~1"=="" (
  python AUDITAR_JORNADA_LIGA_MAESTROS.py
) else (
  python AUDITAR_JORNADA_LIGA_MAESTROS.py --jornada %1
)
pause
