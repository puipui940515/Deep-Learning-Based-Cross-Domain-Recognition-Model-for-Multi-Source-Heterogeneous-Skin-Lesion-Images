@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONNOUSERSITE=
title NoiseFilter training comparison (max 2 hours)
echo NoiseFilter training comparison: off vs NoiseFilter, 2 seeds, max 115 minutes
echo Do not close this window until it says Finished.
"C:\anaconda3\python.exe" -X utf8 -u run.py %*
echo.
echo Finished. Results are in the out folder.
pause
