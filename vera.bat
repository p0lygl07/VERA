@echo off
title VERA — Verified Execution Reasoning Agent
color 0A
cls

echo ============================================================
echo   VERA — Verified Execution Reasoning Agent
echo   It doesn't say done until it's done.
echo ============================================================
echo.

cd /d "%~dp0"

REM Step 1: Run proactive watch check
echo [VERA] Running project awareness check...
"C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe" src\vera_watch.py
echo.

REM Step 2: Start the agent
echo [VERA] Starting agent...
echo.
"C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe" src\vera_agent.py

pause
