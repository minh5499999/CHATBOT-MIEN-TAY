"""Chạy Streamlit với MySQL cục bộ (nếu đã cấu hình .env) hoặc tự chuyển SQLite an toàn."""

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def chon_mysql():
    from dotenv import dotenv_values

    os.chdir(ROOT)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    values = dotenv_values(ROOT / ".env") if (ROOT / ".env").is_file() else {}
    for name in ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE"):
        if values.get(name) is not None:
            os.environ.setdefault(name, values[name])

    from backend.chatbot import co_so_du_lieu
    from backend.chatbot.co_so_du_lieu_mysql import cau_hinh

    if not os.environ.get("MYSQL_PASSWORD"):
        print("Chưa cấu hình MYSQL_PASSWORD trong .env; sử dụng kho tài khoản SQLite cục bộ.")
        co_so_du_lieu.BACKEND = "sqlite"
        os.environ["TAI_KHOAN_BACKEND"] = "sqlite"
        return

    if cau_hinh()["host"].lower() not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Chế độ này yêu cầu MySQL chạy trên máy cục bộ.")

    co_so_du_lieu.BACKEND = "mysql"
    os.environ["TAI_KHOAN_BACKEND"] = "mysql"
    # Kiểm tra schema sẵn có trước khi mở giao diện đăng nhập.
    with co_so_du_lieu.ket_noi() as con:
        for table in ("nguoi_dung", "phien", "cuoc_tro_chuyen", "tin_nhan", "gioi_han_dang_nhap", "tuy_chon_ho_so"):
            con.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()


def main():
    chon_mysql()
    from streamlit.web.cli import main as streamlit

    sys.argv = [
        "streamlit", "run", str(ROOT / "app.py"),
        "--server.address", "localhost", "--server.port", "8501",
        "--server.fileWatcherType", "none", "--browser.gatherUsageStats", "false",
    ]
    streamlit()


if __name__ == "__main__":
    main()
