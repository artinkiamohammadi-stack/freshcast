@echo off
title FreshCast Server
echo.
echo  =========================================
echo   FreshCast - Demand Forecasting System
echo  =========================================
echo.
echo  Starting server...
echo  Dashboard will be at: http://localhost:8000
echo  API docs will be at:  http://localhost:8000/docs
echo.
echo  Press CTRL+C to stop the server.
echo.

set DATABASE_URL=sqlite:///./freshcast.db
set MODEL_DIR=%~dp0models
set PYTHONPATH=%~dp0

cd /d "%~dp0"
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1

pause
