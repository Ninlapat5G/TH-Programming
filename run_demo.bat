@echo off
REM ==========================================================
REM  TH-Programming - demo runner
REM  Double-click this file to see the language in action.
REM  Works even if you have NOT installed thpro yet.
REM
REM  This file is intentionally ASCII-only: cmd.exe parses .bat
REM  files with the system codepage, so Thai text inside a .bat
REM  breaks parsing. All Thai output comes from Python instead.
REM ==========================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
set "PYTHONIOENCODING=utf-8"

where python >nul 2>nul
if errorlevel 1 (
    echo Python not found. Install it from https://www.python.org/downloads/
    echo Remember to tick "Add Python to PATH".
    pause
    exit /b 1
)

python -m thpro demo
echo.
pause
