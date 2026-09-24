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
"C:\Users\P01yG107\AppData\Local\Programs\Python\Python311\python.exe" src\vera_watch.py
echo.

echo [VERA] Starting services...
echo.

echo [1/5] Dashboard server (port 8765)...
start "VERA-Dashboard" /min "C:\Users\P01yG107\AppData\Local\Programs\Python\Python311\python.exe" -m http.server 8765

echo [2/5] Conductor (port 8766)...
start "VERA-Conductor" /min "C:\Users\P01yG107\AppData\Local\Programs\Python\Python311\python.exe" core\agent_conductor.py

echo [3/5] Bridge (port 8767)...
start "VERA-Bridge" /min "C:\Users\P01yG107\AppData\Local\Programs\Python\Python311\python.exe" src\vera_bridge.py

echo [4/5] Perception engine (mic + screen + camera)...
start "VERA-Perception" /min "C:\Users\P01yG107\AppData\Local\Programs\Python\Python311\python.exe" src\vera_perception.py --all

echo [5/5] Waiting for services to initialize...
timeout /t 4 /nobreak > nul

echo.
echo [VERA] All services running. Opening dashboard...
start "" http://localhost:8765/vera_dashboard.html

echo.
echo [VERA] Starting agent...
echo.

"C:\Users\P01yG107\AppData\Local\Programs\Python\Python311\python.exe" src\vera_agent.py

echo.
echo [VERA] Agent stopped. Services still running in background.
echo [VERA] Close minimized windows to stop all services.
pause
