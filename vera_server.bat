@echo off
cd /d "%~dp0"
echo Starting VERA Dashboard server at http://localhost:8765
echo Open http://localhost:8765/vera_dashboard.html in your browser
"C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe" -m http.server 8765
