"""Tải mô hình sinh vector và sinh vector cho đoạn / câu hỏi.

Model card bkai-foundation-models/vietnamese-bi-encoder: đầu vào PHẢI tách từ trước, mean pooling,
768 chiều, không tiền tố query:/passage:, không có lớp Normalize → ta tự chuẩn hóa L2 để dùng cosine.
"""
import os
import sys
from functools import lru_cache

import numpy as np

from backend.chatbot.cau_hinh import ROOT, doc_cau_hinh, doc_cau_hinh_cat_doan, nap_env

os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# dùng lại đúng hàm tiền xử lý và tách từ đã dùng khi cắt đoạn (không viết lại)
sys.path.insert(0, str(ROOT / "scripts"))
from tach_tu import TachTu, doc_tu_dien, tien_xu_ly  # noqa: E402


@lru_cache(maxsize=1)
def nap_mo_hinh():
    """Ưu tiên bản đã tải về máy, không có thì tải từ Hugging Face. Chạy trên CPU."""
    from sentence_transformers import SentenceTransformer
    nap_env()  # HF_TOKEN trong .env (nếu có) để tải mô hình
    ten =doc_cau_hinh_cat_doan()["ten_mo_hinh"]
    offline = doc_cau_hinh().get("chi_chay_cuc_bo", True)
    try:
        m = SentenceTransformer(ten, device="cpu", local_files_only=True)
    except Exception:
        if offline:
            raise RuntimeError("Thiếu mô hình embedding cục bộ. Chạy scripts/chuan_bi_mo_hinh.py khi có mạng trước.")
        m = SentenceTransformer(ten, device="cpu")
    m.max_seq_length = doc_cau_hinh_cat_doan()["gioi_han_token_mo_hinh"]
    return m


@lru_cache(maxsize=1)
def _bo_tach_tu():
    return TachTu(doc_tu_dien())


def chuan_bi_cau_hoi(cau_hoi):
    """Câu hỏi → chuỗi đưa vào mô hình: tiền xử lý, tách từ nếu mô hình cần, thêm tiền tố nếu có.

    Trả về (đã tiền xử lý, đưa vào mô hình) để chế độ giải thích in được cả hai.
    """
    sach = " ".join(tien_xu_ly(cau_hoi, {"doi_kieu_dau": 0, "them_cach_sau_dau": 0}).split())
    vao = _bo_tach_tu().tach_cau_hoi(sach) if doc_cau_hinh_cat_doan()["can_tach_tu"] else sach
    return sach, doc_cau_hinh()["tien_to_cau_hoi"] + vao


def van_ban_doan(doan):
    """Trường của đoạn đưa vào mô hình (bản tách từ nếu mô hình cần), kèm tiền tố đoạn nếu có."""
    truong = "noi_dung_kem_tieu_de_tach_tu" if doc_cau_hinh_cat_doan()["can_tach_tu"] else "noi_dung_kem_tieu_de"
    return doc_cau_hinh()["tien_to_doan"] + doan[truong]


def sinh_vector(van_ban, hien_tien_trinh=False):
    """Danh sách chuỗi → ma trận float32 (n, d) đã chuẩn hóa L2, sinh theo lô batch_size."""
    v = nap_mo_hinh().encode(list(van_ban), batch_size=doc_cau_hinh()["batch_size"],
                             show_progress_bar=hien_tien_trinh, convert_to_numpy=True,
                             normalize_embeddings=True)
    return np.ascontiguousarray(v, dtype=np.float32)


def vector_cau_hoi(cau_hoi):
    """Một câu hỏi thô → (vector 1 x d, đã tiền xử lý, chuỗi đưa vào mô hình)."""
    sach, vao = chuan_bi_cau_hoi(cau_hoi)
    return sinh_vector([vao]), sach, vao
