@echo off
REM Start Antigravity Cortex (Knowledge Core) Service

echo Starting Antigravity Cortex...
echo.

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Start uvicorn with settings from environment
REM Port can be configured via PORT env variable (default: 8000)
set HOST=0.0.0.0
if not defined PORT set PORT=8000

echo Starting on %HOST%:%PORT%...
uvicorn app.main:app --host %HOST% --port %PORT% --reload

pause
