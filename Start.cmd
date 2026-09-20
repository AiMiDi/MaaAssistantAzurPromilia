@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto setup
if not exist "install\MFAAvalonia.exe" goto setup
".venv\Scripts\python.exe" -X utf8 tools\package_local.py
if errorlevel 1 goto failed
start "" /d "%~dp0install" "%~dp0install\MFAAvalonia.exe"
exit /b 0
:setup
echo Please run setup.ps1 once before starting the assistant.
:failed
pause
exit /b 1
