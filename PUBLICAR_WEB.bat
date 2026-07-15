@echo off
setlocal
cd /d "%~dp0"

for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
if /I not "%BRANCH%"=="main" (
  echo ERROR: estas en la rama "%BRANCH%". El despliegue solo sale desde main.
  exit /b 1
)

echo Comprobando el proyecto antes de publicar...
python -m pytest -q
if errorlevel 1 (
  echo ERROR: las pruebas han fallado. No se publicara nada.
  exit /b 1
)

git add -A
git diff --cached --quiet
if not errorlevel 1 (
  echo No hay cambios para publicar.
  exit /b 0
)

set "MESSAGE=%~1"
if not defined MESSAGE set "MESSAGE=Actualizar Liga de Maestros"

echo Archivos que se publicaran:
git diff --cached --stat
git commit -m "%MESSAGE%"
if errorlevel 1 exit /b 1

git push origin main
if errorlevel 1 exit /b 1

echo.
echo Cambios enviados. GitHub comprobara, desplegara y reiniciara Alwaysdata.
echo Estado: https://github.com/Purplerave/liga-maestros-web/actions
