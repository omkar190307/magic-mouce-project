@echo off
title AI Air Mouse
echo.
echo  ============================================
echo   AI AIR MOUSE - One-Click Launcher
echo  ============================================
echo.

REM Detect Python executable
set "PY_CMD="
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=py"
    )
)

if "%PY_CMD%"=="" (
    echo  [ERROR] Python is not installed or not in PATH!
    echo  Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

set "VENV_DIR=%~dp0.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo  [1/3] Creating virtual environment...
    "%PY_CMD%" -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo  [WARN] Failed to create virtual environment. Falling back to system Python.
        set "RUN_PYTHON=%PY_CMD%"
    ) else (
        set "RUN_PYTHON=%VENV_PYTHON%"
    )
) else (
    set "RUN_PYTHON=%VENV_PYTHON%"
)

echo  [2/3] Checking dependencies...
"%RUN_PYTHON%" -m pip install -r "%~dp0requirements.txt" --disable-pip-version-check
if %errorlevel% neq 0 (
    echo  [WARN] Package installation gave warnings. Attempting to launch anyway...
)

echo  [3/3] Launching AI Air Mouse...
echo.

"%RUN_PYTHON%" "%~dp0air_mouse.py"

echo.
echo  Session ended.
pause


