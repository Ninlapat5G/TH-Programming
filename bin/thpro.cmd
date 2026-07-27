@echo off
REM TH-Programming launcher for Windows (works without pip install)
REM Comments kept ASCII-only: cmd.exe reads this file in the OEM codepage.
setlocal
set "PYTHONPATH=%~dp0..;%PYTHONPATH%"
python -m thpro %*
endlocal
