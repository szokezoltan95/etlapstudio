@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo A program futtatasahoz Python 3 szukseges. Telepites: https://www.python.org/downloads/
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Elso inditas: a helyi futtatasi kornyezet letrehozasa...
  py -3 -m venv ".venv"
  if errorlevel 1 (
    echo A Python kornyezet letrehozasa sikertelen.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -c "import PyQt6, PIL" >nul 2>nul
if errorlevel 1 (
  echo A Qt6 es grafikai modulok telepitese folyamatban...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 (
    echo A modulok telepitese sikertelen. Ellenorizd az internetkapcsolatot.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" "qt_app.pyw"
if errorlevel 1 (
  echo Az alkalmazas varatlanul leallt.
  pause
)
