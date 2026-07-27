@echo off
REM ==========================================================
REM  TH-Programming - installer for Windows
REM  Double-click this file, or run it from cmd.
REM
REM  ASCII-only on purpose: cmd.exe parses .bat files with the
REM  system codepage, so Thai text inside a .bat breaks parsing.
REM ==========================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

echo.
echo === TH-Programming : installing ===
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [FAIL] Python not found on this machine.
    echo        Install it from https://www.python.org/downloads/
    echo        Remember to tick "Add Python to PATH".
    pause
    exit /b 1
)

for /f "delims=" %%v in ('python --version') do echo [ OK ] found %%v

echo.
echo Installing the "thpro" command ...
python -m pip install --disable-pip-version-check -e . >nul 2>&1
if errorlevel 1 (
    echo [FAIL] install failed. Run this yourself to see details:
    echo        python -m pip install -e .
    pause
    exit /b 1
)

echo.
python -m thpro doctor
if errorlevel 1 (
    echo.
    echo Note: if the "thpro" command is not found, close and reopen cmd.
    pause
    exit /b 1
)

echo.
echo Done. Try this next:
echo.
echo     thpro examples\demo.th
echo     thpro help
echo.
pause
