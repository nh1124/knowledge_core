@echo off
REM Reset Antigravity Cortex (Knowledge Core) Environment

echo Resetting Antigravity Cortex environment...
echo.

REM Stop and remove containers and volumes
echo Stopping Docker containers and removing volumes...
docker-compose down -v

REM Remove log files
echo Cleaning up logs...
if exist logs\ (
    del /q logs\*.log
)

REM Optionally, remove __pycache__
echo Cleaning up Python cache...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

echo.
echo Initialization complete. To start the service, run:
echo start_service.bat
echo.

pause
