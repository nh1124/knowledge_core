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

REM Start docker-compose (only postgres for local development)
docker-compose up -d postgres

REM Start uvicorn with settings from environment
if not defined HOST set HOST=0.0.0.0
if defined KC_HOST_PORT (
    set PORT=%KC_HOST_PORT%
) else (
    if not defined PORT set PORT=8200
)

echo.
echo TIP: Ensure your database is running (e.g., docker-compose up -d)
echo.

echo Starting Antigravity Cortex on %HOST%:%PORT%...
echo UI will be available at http://localhost:%PORT%/ui
echo.

uvicorn app.main:app --host %HOST% --port %PORT% --reload

pause
