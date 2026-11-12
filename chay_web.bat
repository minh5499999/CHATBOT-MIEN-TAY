@echo off
REM Chạy giao diện web của chatbot: mở http://localhost:8501
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Khong tim thay Python trong .venv. Hay tao lai moi truong ao theo README.md.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m streamlit run app.py --server.address localhost
pause
