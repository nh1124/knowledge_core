@echo off
REM Start Antigravity Cortex (Knowledge Core) Service

echo Starting Antigravity Cortex...
echo.

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Load environment variables from .env if it exists
if exist .env (
    for /f "usebackq eol=# tokens=*" %%i in (".env") do set %%i
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

echo Starting backend on %HOST%:%BACKEND_PORT%...

REM Check if we should start a separate frontend server
if defined FRONTEND_PORT (
    if NOT "%FRONTEND_PORT%"=="%BACKEND_PORT%" (
        echo Starting frontend on %HOST%:%FRONTEND_PORT%...
        start /b python -m http.server %FRONTEND_PORT% --bind %HOST% --directory static
    )
)

uvicorn app.main:app --host %HOST% --port %BACKEND_PORT% --reload

pause
