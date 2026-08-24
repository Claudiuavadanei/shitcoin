@echo off
title SHITCOIN SNIPER PRO [24/7 RUNNER]
chcp 65001 > nul
color 0b

echo =====================================================================
echo           SHITCOIN SNIPER PRO - 24/7 PERSISTENT RUNNER
echo =====================================================================
echo.
echo [INFO] Starting Autonomous Sniper Engine...
echo [INFO] Dashboard URL: http://localhost:8080
echo [INFO] Auto-Restart Protection is ACTIVE (24/7 365 Days)
echo.

:loop
echo [%date% %time%] Launching Bot Process...
.venv\Scripts\python.exe main.py

echo.
echo [WARNING] Bot process stopped unexpectedly or was closed.
echo [INFO] Restarting automatically in 3 seconds to ensure 24/7 uptime...
echo.
timeout /t 3 /nobreak > nul
goto loop
