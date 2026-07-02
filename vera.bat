@echo off
title VERA -- Verified Execution Reasoning Agent
color 0A
cls

echo ============================================================
echo   VERA -- Verified Execution Reasoning Agent
echo   It doesn't say done until it's done.
echo ============================================================
echo.

cd /d "%~dp0"

echo [VERA] Running project awareness check...
"C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe" src\vera_watch.py
echo.

echo [VERA] Starting dashboard server (port 8765)...
start "VERA Dashboard" /min "C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe" -m http.server 8765

echo [VERA] Starting conductor (port 8766)...
start "VERA Conductor" /min "C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe" core\agent_conductor.py

echo [VERA] Starting bridge (port 8767)...
start "VERA Bridge" /min "C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe" src\vera_bridge.py

timeout /t 3 /nobreak > nul

echo [VERA] Starting agent...
echo.
"C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe" src\vera_agent.py

pause
