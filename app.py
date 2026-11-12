"""Điểm chạy tương thích: mã giao diện nằm trong frontend/app.py."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parent / "frontend/app.py"), run_name="__main__")
