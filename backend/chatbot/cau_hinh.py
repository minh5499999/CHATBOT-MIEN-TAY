"""Đọc cấu hình chatbot (cau_hinh/chatbot.json), cấu hình cắt đoạn và khóa bí mật trong .env."""
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAU_HINH_PATH = ROOT / "cau_hinh" / "chatbot.json"


@lru_cache(maxsize=1)
def doc_cau_hinh():
    """Cấu hình backend.chatbot. Đường dẫn trong file là tương đối so với thư mục gốc project."""
    return json.loads(CAU_HINH_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def doc_cau_hinh_cat_doan():
    """Cấu hình của bước cắt đoạn: tên mô hình sinh vector, giới hạn token, có cần tách từ không."""
    return json.loads((ROOT / doc_cau_hinh()["cau_hinh_cat_doan"]).read_text(encoding="utf-8"))


def duong_dan(khoa):
    """Đổi một khóa đường dẫn trong cấu hình thành Path tuyệt đối."""
    return ROOT / doc_cau_hinh()[khoa]


@lru_cache(maxsize=1)
def nap_env():
    """Nạp .env một lần (nếu có), ví dụ HF_TOKEN để tải mô hình. Không ghi khóa vào cấu hình hay nhật ký."""
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    return True
