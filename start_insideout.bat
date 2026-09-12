@echo off
if not exist "%~dp0.venv-desktop\Scripts\python.exe" (
    echo Desktop environment missing. Run setup_insideout.ps1 first.
    pause
    exit /b 1
)
"%~dp0.venv-desktop\Scripts\python.exe" "%~dp0insideout.py" %*
if errorlevel 1 (
    echo InsideOut stopped with an error. See data\logs\insideout.log.
    pause
    exit /b 1
)
