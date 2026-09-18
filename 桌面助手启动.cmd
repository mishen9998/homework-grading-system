@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
where python >nul 2>nul
if not errorlevel 1 (
    python -X utf8 desktop_assistant\bootstrap.py %*
    if not errorlevel 1 exit /b 0
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -X utf8 desktop_assistant\bootstrap.py %*
    if not errorlevel 1 exit /b 0
)
echo Desktop assistant could not start.
echo Please install Python 3.10+ with Tcl/Tk and add Python to PATH.
echo See the desktop assistant guide in this project folder.
pause
exit /b 1
