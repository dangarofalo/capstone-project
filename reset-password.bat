@echo off
rem Double-click to set a new password for a SentinelView dashboard user.
cd /d "%~dp0backend"
echo.
echo  Reset a SentinelView password
echo  -----------------------------
echo  Existing users:
"..\.venv\Scripts\python.exe" -m app.manage list-users
echo.
echo  Type the username, then the new password twice.
echo  Password: at least 10 characters, mixing letters with numbers or symbols.
echo  (Nothing appears on screen while you type the password. That's normal.)
echo.
"..\.venv\Scripts\python.exe" -m app.manage reset-password
echo.
pause
