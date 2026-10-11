@echo off
echo ========================================================
echo   JalRakshak AI — Backend & Dashboard Launcher
echo ========================================================
echo.
echo Choose how to run the backend:
echo   [1] Node.js Server (Port 3000) - Zero dependency
echo   [2] Python FastAPI (Port 8001) - High performance
echo.
set /p choice="Enter choice [1 or 2, default 1]: "

if "%choice%"=="2" (
    echo Starting Python FastAPI backend on http://localhost:8001 ...
    cd backend
    python app.py
) else (
    echo Starting Node.js backend on http://localhost:3000 ...
    node server.js
)
pause
