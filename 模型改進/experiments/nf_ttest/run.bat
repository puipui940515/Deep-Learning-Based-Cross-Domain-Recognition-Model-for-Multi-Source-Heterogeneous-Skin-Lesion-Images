@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONNOUSERSITE=
echo NoiseFilter inference test - R0 checkpoint, GPU if available
"C:\anaconda3\python.exe" -X utf8 -u run.py %*
echo.
echo Finished. Results are in the out folder.
pause
