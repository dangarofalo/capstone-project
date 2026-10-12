@echo off
rem Double-click to start SentinelView, then open http://127.0.0.1:8000
rem Keep this window open while you use the dashboard. Close it to stop the server.
cd /d "%~dp0backend"
if not exist "..\frontend\dist\index.html" (
  echo The dashboard hasn't been built yet. In the frontend folder run: npm install, then npm run build
  pause
  exit /b 1
)
echo Starting SentinelView at http://127.0.0.1:8000  (keep this window open)
rem Open the browser after a few seconds, once the server is ready.
start "" /min cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8000"
"..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
