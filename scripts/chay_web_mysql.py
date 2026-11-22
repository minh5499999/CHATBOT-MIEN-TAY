"""Chạy Streamlit staging bằng kho tài khoản MySQL cục bộ hiện có."""

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "staging/release_candidate_20261118_m5_v9"


def chon_mysql():
    from dotenv import dotenv_values

    os.chdir(ROOT)
    os.environ["CHATBOT_STAGING_BUILD"] = str(BUILD)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"
    # Giữ mã staging ở đầu và cho bộ tách từ nạp package scripts của dự án.
    sys.path[:0] = [str(BUILD / "code"), str(ROOT)]

    values = dotenv_values(ROOT / ".env")
    for name in ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE"):
        if values.get(name) is not None:
            os.environ.setdefault(name, values[name])

    from backend.chatbot import co_so_du_lieu
    from backend.chatbot.co_so_du_lieu_mysql import cau_hinh

    if cau_hinh()["host"].lower() not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Chế độ này yêu cầu MySQL chạy trên máy cục bộ.")

    co_so_du_lieu.BACKEND = "mysql"
    # Kiểm tra schema sẵn có trước khi mở giao diện đăng nhập.
    with co_so_du_lieu.ket_noi() as con:
        for table in ("nguoi_dung", "phien", "cuoc_tro_chuyen", "tin_nhan"):
            con.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()


def main():
    chon_mysql()
    # The backend package is already loaded from the validated build.
    # Serve the editable frontend and its static assets from the project root.
    sys.path.insert(0, str(ROOT))
    # Pin the UI package before Streamlit or any plugin can resolve a staging copy.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "frontend", ROOT / "frontend/__init__.py",
        submodule_search_locations=[str(ROOT / "frontend")],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules["frontend"] = package
    spec.loader.exec_module(package)
    from streamlit.web.cli import main as streamlit

    sys.argv = [
        "streamlit", "run", str(ROOT / "app.py"),
        "--server.address", "localhost", "--server.port", "8501",
        "--server.fileWatcherType", "none", "--browser.gatherUsageStats", "false",
    ]
    streamlit()


if __name__ == "__main__":
    main()
