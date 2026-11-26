"""Điểm chạy tương thích: mã giao diện nằm trong frontend/app.py."""
from pathlib import Path
import runpy
import os
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
os.environ['CHATBOT_STAGING_BUILD']='staging/'+Path(__file__).resolve().parent.parent.name

runpy.run_path(str(Path(__file__).resolve().parent / "frontend/app.py"), run_name="__main__")
