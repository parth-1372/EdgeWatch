@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo   EdgeWatch Emulsion Dashboard Launcher
echo ==========================================

:: Check for python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python.
    pause
    exit /b
)

:: Run the server
echo [INFO] Starting Dashboard Server on http://localhost:5005
python "%~dp0src\experiments\emulsion\dashboard\dashboard_server.py"

pause
