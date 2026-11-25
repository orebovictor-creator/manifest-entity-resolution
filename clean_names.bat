@echo off
REM Drag Excel files onto this icon (or double-click it to pick files).
REM A cleaned copy is saved next to each file as <name>_clean.xlsx
cd /d "%~dp0"
python -m manifest_er clean %*
echo.
pause
