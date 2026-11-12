@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Cap nhat tu data/groups/*/all.csv. Hay sao luu du lieu truoc khi chay.
echo Instance BepDinhDuong can duoc Start trong Neo4j Desktop.
".venv\Scripts\python.exe" -X utf8 scripts/merge_groups.py
if errorlevel 1 goto loi
".venv\Scripts\python.exe" -X utf8 scripts/tach_tu.py
if errorlevel 1 goto loi
".venv\Scripts\python.exe" -X utf8 scripts/tach_doan.py --cach cau_truc
if errorlevel 1 goto loi
".venv\Scripts\python.exe" -X utf8 scripts/tao_kho_vector.py --cach cau_truc --tap tat_ca
if errorlevel 1 goto loi
".venv\Scripts\python.exe" -X utf8 scripts/nap_neo4j.py --kho kho_vector/cau_truc_tat_ca
if errorlevel 1 goto loi
".venv\Scripts\python.exe" -X utf8 scripts/kiem_tra_neo4j.py
if errorlevel 1 goto loi
echo Hoan tat. Hay tat va mo lai chatbot de nap kho moi.
pause
exit /b 0
:loi
echo Co loi. Quy trinh da dung, khong chay cac buoc tiep theo.
pause
exit /b 1
