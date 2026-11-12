@echo off
chcp 65001 >nul
cd /d "%~dp0"
".venv\Scripts\python.exe" -X utf8 scripts/kiem_tra_neo4j.py
pause
