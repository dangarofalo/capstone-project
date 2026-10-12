@echo off
rem Double-click to create a SentinelView dashboard administrator account.
cd /d "%~dp0backend"
echo.
echo  Create a SentinelView administrator
echo  -----------------------------------
echo  Choose a username (letters, numbers, dots, dashes), then a password.
echo  Password: at least 10 characters, mixing letters with numbers or symbols.
echo  (Nothing appears on screen while you type the password. That's normal.)
echo.
"..\.venv\Scripts\python.exe" -m app.manage create-user --role admin
echo.
pause
