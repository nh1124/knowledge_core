@echo off
REM Start Antigravity Cortex (Knowledge Core) Service

echo Starting Antigravity Cortex...
echo.

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Start uvicorn with settings from environment
REM Port can be configured via BACKEND_PORT env variable (default: 8000)
set HOST=0.0.0.0
if not defined BACKEND_PORT (
    if defined PORT (
        set BACKEND_PORT=%PORT%
    ) else (
        set BACKEND_PORT=8000
    )
)

echo Starting on %HOST%:%BACKEND_PORT%...
uvicorn app.main:app --host %HOST% --port %BACKEND_PORT% --reload

pause
