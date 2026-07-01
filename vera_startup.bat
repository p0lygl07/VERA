@echo off
cd /d "C:\Users\p0ly\Desktop\AI\VERA"

REM Start dashboard server in background
start "VERA Dashboard Server" /min vera_server.bat

REM Wait 3 seconds for server to initialize
timeout /t 3 /nobreak > nul

REM Start VERA agent in new window
start "VERA Agent" vera.bat
