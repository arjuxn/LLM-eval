@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "src\dashboard.py"
) else (
    python "src\dashboard.py"
)
if errorlevel 1 (
    echo.
    echo Dashboard could not start. Check that Python and the project dependencies are installed.
    pause
)
endlocal
