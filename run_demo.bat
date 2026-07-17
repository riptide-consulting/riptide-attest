@echo off
rem Riptide Attest -- double-click launcher for the self-verifying demo.
rem The demo (run_demo.py) asserts every determinism claim itself; its
rem exit code is the proof. This wrapper only bootstraps a venv on first
rem use and keeps the console window open afterward.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No .venv found -- creating one. This happens once.
    python -m venv .venv
    if errorlevel 1 (
        echo Could not create .venv -- install Python 3.11+ and retry.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install pytest
)

".venv\Scripts\python.exe" run_demo.py
set DEMO_EXIT=%errorlevel%

echo.
echo Demo exit code: %DEMO_EXIT%  [0 = every determinism assertion held]
pause
exit /b %DEMO_EXIT%
