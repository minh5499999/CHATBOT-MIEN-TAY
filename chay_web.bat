@echo off
REM Chay chatbot voi MySQL cuc bo tai http://localhost:8501
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Khong tim thay Python trong .venv. Hay tao lai moi truong ao theo README.md.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -B -X utf8 ".\scripts\chay_web_mysql.py"
set "CHAY_WEB_EXIT=%ERRORLEVEL%"
if not "%CHAY_WEB_EXIT%"=="0" pause
exit /b %CHAY_WEB_EXIT%
