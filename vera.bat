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

echo [VERA] Starting ambient stack (listener, observer, scanner, recon)...
"C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe" src\vera_ambient_stack.py
echo.

echo [VERA] Starting agent...
echo.
"C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe" src\vera_agent.py

pause
