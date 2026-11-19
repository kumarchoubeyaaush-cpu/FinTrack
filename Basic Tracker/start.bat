@echo off
title FinTrack Local - Money Tracker
echo ========================================================
echo           Starting FinTrack Local Money Tracker
echo ========================================================
echo.
echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found in PATH! Please ensure Python is installed.
    pause
    exit /b 1
)

echo Starting FinTrack Server on http://127.0.0.1:5000 ...
start "" "http://127.0.0.1:5000"
python server.py
pause
