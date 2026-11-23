"""Hệ thống Tự học chủ động (Active Learning) và Cập nhật Vector tức thì (Incremental FAISS Indexing).

Hoàn toàn không sử dụng mô hình sinh (LLM).
- Tự động ghi nhận câu hỏi ngoài phạm vi / độ tin cậy thấp từ hội thoại.
- Gom cụm tự động bằng vector embedding + DBSCAN / K-Means để phát hiện chủ đề mới cần bổ sung.
- Thêm trực tiếp câu hỏi & công thức mới vào chỉ mục FAISS (index.add) trong mili-giây mà không cần dựng lại từ đầu.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import shutil
import sqlite3
import threading
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sklearn.cluster import DBSCAN

from backend.chatbot.cau_hinh import ROOT, doc_cau_hinh
from backend.chatbot.mo_hinh_vector import sinh_vector
from backend.chatbot.trich_xuat_thuc_the import trich_xuat_textrank
from scripts.tach_tu import TachTu, doc_tu_dien, tien_xu_ly

LOGGER = logging.getLogger(__name__)
_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WRITE_LOCK = threading.Lock()
_MAX_CHO_HOC_LINES = 5000
CHO_HOC_PATH = ROOT / "du_lieu_nguoi_dung" / "cau_hoi_cho_hoc.jsonl"
SQLITE_DB = ROOT / "du_lieu_nguoi_dung" / "chatbot.sqlite3"
DATASET_CSV = ROOT / "data" / "merged" / "dataset.csv"
DATASET_JSONL = ROOT / "data" / "merged" / "dataset.jsonl"


def _thoi_gian_hien_tai() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _backup_file(path: Path) -> Path:
    """Tự động sao lưu file trước khi chỉnh sửa hoặc ghi đè."""
    if not path.exists():
        return path
    backup_dir = ROOT / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = backup_dir / f"{path.stem}_BACKUP_{ts}{path.suffix}"
    shutil.copy2(path, dst)
    return dst


# -----------------------------------------------------------------------------
# 1. GHI NHẬN CÂU HỎI NGOÀI PHẠM VI / ĐIỂM THẤP
# -----------------------------------------------------------------------------

def ghi_nhan_cau_hoi_cho_hoc(cau_hoi: str, loai: str, diem: float, kho: str = "") -> None:
    """Ghi nhận câu hỏi người dùng cần học thêm vào cau_hoi_cho_hoc.jsonl."""
    cau = (cau_hoi or "").strip()[:300]
    if not cau or len(cau.split()) < 2:
        return

    dong = {
        "thoi_gian": _thoi_gian_hien_tai(),
        "cau_hoi": cau,
        "loai": loai,
        "diem": round(float(diem), 4),
        "kho": str(kho)[:120],
    }
    line = json.dumps(dong, ensure_ascii=False)
    with _WRITE_LOCK:
        CHO_HOC_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CHO_HOC_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        try:
            lines = CHO_HOC_PATH.read_text(encoding="utf-8").splitlines()
            if len(lines) > _MAX_CHO_HOC_LINES:
                tmp = CHO_HOC_PATH.with_suffix(".jsonl.tmp")
                tmp.write_text("\n".join(lines[-_MAX_CHO_HOC_LINES:]) + "\n", encoding="utf-8")
                os.replace(tmp, CHO_HOC_PATH)
        except Exception as exc:
            LOGGER.warning("Không thể cắt gọn %s: %s", CHO_HOC_PATH, exc)


# -----------------------------------------------------------------------------
# 2. KHAI PHÁ & GOM CỤM CÂU HỎI MỚI (CLUSTERING)
# -----------------------------------------------------------------------------

from backend.chatbot.cau_hoi_cho_hoc import lay_danh_sach_cau_hoi_chua_biet


def gom_cum_cau_hoi(danh_sach_cau_hoi: list[str] | None = None, eps: float = 0.35, min_samples: int = 1) -> list[dict[str, Any]]:
    """Gom cụm các câu hỏi chưa biết theo chủ đề bằng vector embedding + DBSCAN."""
    if danh_sach_cau_hoi is None:
        raw_list = lay_danh_sach_cau_hoi_chua_biet()
        cau_hoi_list = [item["cau_hoi"] for item in raw_list]
    else:
        cau_hoi_list = [q.strip() for q in danh_sach_cau_hoi if q.strip()]

    if not cau_hoi_list:
        return []

    # Loại bỏ trùng lặp giữ thứ tự
    unique_q = list(dict.fromkeys(cau_hoi_list))
    if not unique_q:
        return []

    # Vectorize bằng mô hình vietnamese-bi-encoder (CPU)
    vectors = sinh_vector(unique_q)  # shape (N, 768), đã L2 normalized

    # Chạy DBSCAN với metric cosine (khoảng cách cosine = 1 - dot product trên vector chuẩn hóa)
    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
    labels = clustering.fit_predict(vectors)

    # Gom nhóm theo nhãn
    nhom_cum: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        nhom_cum.setdefault(label, []).append(idx)

    ket_qua: list[dict[str, Any]] = []
    for cluster_id, indices in nhom_cum.items():
        if cluster_id == -1 and len(indices) > 3:
            # Nhiễu (noise)
            continue
        members = [unique_q[i] for i in indices]
        cluster_vecs = vectors[indices]
        centroid = np.mean(cluster_vecs, axis=0)
        centroid /= np.linalg.norm(centroid) or 1.0

        # Tìm câu hỏi đại diện (gần tâm centroid nhất)
        sims = np.dot(cluster_vecs, centroid)
        rep_idx = int(np.argmax(sims))
        dai_dien = members[rep_idx]

        # Trích xuất từ khóa chủ đề đại diện bằng TextRank
        chuoi_gop = " . ".join(members)
        rank_kw = trich_xuat_textrank(chuoi_gop, top_k=2)
        chu_de = " / ".join(k for k, _ in rank_kw) if rank_kw else dai_dien

        ket_qua.append({
            "cum_id": int(cluster_id),
            "chu_de": chu_de,
            "cau_hoi_dai_dien": dai_dien,
            "so_cau_hoi": len(members),
            "danh_sach_cau_hoi": members,
        })

    # Sắp xếp theo số lượng câu hỏi trong cụm giảm dần
    ket_qua.sort(key=lambda x: x["so_cau_hoi"], reverse=True)
    return ket_qua


# -----------------------------------------------------------------------------
# 3. CẬP NHẬT VECTOR TỨC THÌ (INCREMENTAL FAISS INDEXING)
# -----------------------------------------------------------------------------

def them_cau_hoi_moi(
    cau_hoi: str,
    cau_tra_loi: str,
    nhom: str = "Hướng dẫn nấu món ăn miền Tây",
    nhom_folder: str = "03_huong_dan_nau_mon_mien_tay",
    nguon: str = "Học chủ động (Active Learning)",
    actor: str = "admin",
    kho_rel: str = "kho_vector/cau_truc_tat_ca",
    kiem_tra_quyen: bool | None = None,
) -> dict[str, Any]:
    """Thêm trực tiếp câu hỏi & câu trả lời vào chỉ mục FAISS và siêu dữ liệu trong vài mili-giây.

    Tự động:
    1. Sao lưu dự phòng các file quan trọng (index.faiss, sieu_du_lieu.jsonl, dataset.csv).
    2. Tách từ bằng BiMM Tokenizer.
    3. Sinh vector 768 chiều L2-normalized.
    4. index.add(vector) và faiss.write_index().
    5. Cập nhật sieu_du_lieu.jsonl, dataset.csv, dataset.jsonl, thong_tin.json.
    6. Xóa toàn bộ bộ nhớ đệm (LRU cache) để hệ thống nhận ngay tri thức mới mà không cần khởi động lại.
    """
    from backend.chatbot.knowledge_policy import active_build
    if active_build():
        raise ValueError("Staging knowledge build is immutable; rebuild in a new version")
    kho_dir = (Path(kho_rel) if Path(kho_rel).is_absolute() else ROOT / kho_rel).resolve()
    is_real_runtime = ROOT.resolve() == _REAL_PROJECT_ROOT
    need_rbac = True if is_real_runtime else bool(kiem_tra_quyen)
    if need_rbac:
        from backend.chatbot import tai_khoan
        if not actor or not tai_khoan.la_admin(actor):
            raise PermissionError("Chỉ quản trị viên đang hoạt động mới được cập nhật kho tri thức.")
    if is_real_runtime and not kho_dir.is_relative_to(ROOT.resolve()):
        raise ValueError("Đường dẫn kho tri thức phải nằm trong thư mục dự án.")
    cau_hoi = cau_hoi.strip()
    cau_tra_loi = cau_tra_loi.strip()
    if not cau_hoi or not cau_tra_loi:
        raise ValueError("Câu hỏi và câu trả lời không được để trống.")

    index_path = kho_dir / "index.faiss"
    sieu_path = kho_dir / "sieu_du_lieu.jsonl"
    info_path = kho_dir / "thong_tin.json"

    if not index_path.exists() or not sieu_path.exists():
        raise FileNotFoundError(f"Không tìm thấy kho vector tại {kho_dir}")

    # 2. Chuẩn bị tách từ & sinh vector trước khi khóa file
    tach = TachTu(doc_tu_dien())
    hoi_tx = tien_xu_ly(cau_hoi, {"doi_kieu_dau": 0, "them_cach_sau_dau": 0})
    tl_tx = tien_xu_ly(cau_tra_loi, {"doi_kieu_dau": 0, "them_cach_sau_dau": 0})
    hoi_tach = tach.tach_cau_hoi(hoi_tx)
    tl_tach, _ = tach.tach_cau_tra_loi(tl_tx)

    noi_dung_kem_tieu_de = f"{nhom} · {cau_hoi}\n{cau_tra_loi}"
    noi_dung_kem_tieu_de_tach_tu = f"{tach.tach_cau_hoi(nhom)} · {hoi_tach} {tl_tach}"
    vector_moi = sinh_vector([noi_dung_kem_tieu_de_tach_tu])  # shape (1, 768), float32

    with _WRITE_LOCK:
        bak_index = _backup_file(index_path)
        bak_sieu = _backup_file(sieu_path)
        bak_info = _backup_file(info_path) if info_path.exists() else None
        if DATASET_CSV.exists():
            _backup_file(DATASET_CSV)

        index = faiss.deserialize_index(np.frombuffer(index_path.read_bytes(), dtype=np.uint8))
        index.add(vector_moi)

        sieu_raw = sieu_path.read_text(encoding="utf-8")
        sieu_cu = [json.loads(line) for line in sieu_raw.splitlines() if line.strip()]
        max_id_goc = max((d.get("id_goc", 0) for d in sieu_cu), default=0) + 1
        new_chunk_id = f"cau_truc_{max_id_goc:04d}_01"

        new_doc = {
            "chunk_id": new_chunk_id,
            "cach_cat": "cau_truc",
            "id_goc": max_id_goc,
            "nhom": nhom,
            "nhom_folder": nhom_folder,
            "tap": "Train",
            "cau_hoi": cau_hoi,
            "ten_muc": "",
            "muc_truoc": "",
            "thu_tu_doan": 1,
            "tong_so_doan_cua_cau": 1,
            "nguon": nguon,
            "noi_dung": cau_tra_loi,
            "noi_dung_kem_tieu_de": noi_dung_kem_tieu_de,
            "noi_dung_kem_tieu_de_tach_tu": noi_dung_kem_tieu_de_tach_tu,
            "so_token": len(noi_dung_kem_tieu_de_tach_tu.split()),
            "so_ky_tu": len(noi_dung_kem_tieu_de),
            "vi_tri_ky_tu": [0, len(noi_dung_kem_tieu_de)],
            "so_ky_tu_chong_lan": 0,
            "chia_theo_cau": False,
            "canh_bao": [],
            "nguoi_tao": actor,
            "ngay_tao": _thoi_gian_hien_tai(),
        }

        idx_tmp = kho_dir / ".index.faiss.tmp"
        sieu_tmp = kho_dir / ".sieu_du_lieu.jsonl.tmp"
        info_tmp = kho_dir / ".thong_tin.json.tmp"
        try:
            idx_tmp.write_bytes(faiss.serialize_index(index).tobytes())
            prefix = sieu_raw if (not sieu_raw or sieu_raw.endswith("\n")) else sieu_raw + "\n"
            sieu_tmp.write_text(prefix + json.dumps(new_doc, ensure_ascii=False) + "\n", encoding="utf-8")
            if info_path.exists():
                info = json.loads(info_path.read_text(encoding="utf-8"))
                info["so_doan"] = index.ntotal
                info["ngay_cap_nhat_cuoi"] = _thoi_gian_hien_tai()
                info_tmp.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

            os.replace(idx_tmp, index_path)
            os.replace(sieu_tmp, sieu_path)
            if info_tmp.exists():
                os.replace(info_tmp, info_path)
        except Exception:
            for tmp_p in (idx_tmp, sieu_tmp, info_tmp):
                tmp_p.unlink(missing_ok=True)
            if bak_index.exists():
                shutil.copy2(bak_index, index_path)
            if bak_sieu.exists():
                shutil.copy2(bak_sieu, sieu_path)
            if bak_info and bak_info.exists():
                shutil.copy2(bak_info, info_path)
            raise

        # 7. Đồng bộ vào data/merged/dataset.csv và dataset.jsonl
        if DATASET_CSV.exists():
            with DATASET_CSV.open("a", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow([max_id_goc, nhom, "Train", cau_hoi, cau_tra_loi, nguon])

        if DATASET_JSONL.exists():
            with DATASET_JSONL.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "id": str(max_id_goc),
                    "group": nhom,
                    "group_folder": nhom_folder,
                    "split": "Train",
                    "question": cau_hoi,
                    "answer": cau_tra_loi,
                    "source": nguon,
                }, ensure_ascii=False) + "\n")

        if need_rbac:
            try:
                from backend.chatbot import tai_khoan
                tai_khoan.ghi_nhat_ky_quan_tri(actor, f"id_{max_id_goc}", "them_tri_thuc", cau_hoi[:200])
            except Exception as exc:
                LOGGER.warning("Không ghi được nhật ký quản trị thêm tri thức: %s", exc)

        # 8. Xóa LRU Caches để nhận ngay lập tức
        _xoa_tat_ca_cache()

        # 9. Dọn dẹp câu hỏi khỏi danh sách chờ học (nếu có)
        _loai_bo_cau_hoi_da_hoc(cau_hoi)

    return {
        "id_goc": max_id_goc,
        "chunk_id": new_chunk_id,
        "cau_hoi": cau_hoi,
        "tong_so_vector": index.ntotal,
        "thoi_gian": _thoi_gian_hien_tai(),
    }


def _xoa_tat_ca_cache() -> None:
    """Xóa tất cả các tầng cache để hệ thống nhận dữ liệu mới ngay lập tức."""
    try:
        from backend.chatbot.truy_hoi import nap_kho, nap_bm25, nap_bm25_khong_dau
        nap_kho.cache_clear()
        nap_bm25.cache_clear()
        nap_bm25_khong_dau.cache_clear()
    except Exception as exc:
        LOGGER.debug("Không xóa được cache truy_hoi: %s", exc)

    try:
        from backend.chatbot.doi_chieu import chi_muc_cau_hoi, chi_muc_ten_mon
        chi_muc_cau_hoi.cache_clear()
        chi_muc_ten_mon.cache_clear()
    except Exception as exc:
        LOGGER.debug("Không xóa được cache doi_chieu: %s", exc)

    try:
        from backend.chatbot.cong_thuc import danh_muc, tu_vung_nguyen_lieu
        danh_muc.cache_clear()
        if hasattr(tu_vung_nguyen_lieu, "cache_clear"):
            tu_vung_nguyen_lieu.cache_clear()
    except Exception as exc:
        LOGGER.debug("Không xóa được cache cong_thuc: %s", exc)

    try:
        from backend.chatbot.chuoi_langchain import _ket_qua_truy_hoi
        _ket_qua_truy_hoi.cache_clear()
    except Exception as exc:
        LOGGER.debug("Không xóa được cache chuoi_langchain: %s", exc)

    try:
        from backend.chatbot.trich_xuat_thuc_the import lay_bo_phan_loai_ml
        lay_bo_phan_loai_ml.cache_clear()
    except Exception as exc:
        LOGGER.debug("Không xóa được cache phan_loai_ml: %s", exc)

    try:
        from frontend.bang_quan_tri import tai_tai_lieu
        tai_tai_lieu.cache_clear()
    except Exception as exc:
        LOGGER.debug("Không xóa được cache bang_quan_tri: %s", exc)


def _loai_bo_cau_hoi_da_hoc(cau_hoi: str) -> None:
    """Xóa các câu hỏi tương tự khỏi file chờ học khi đã được admin giải đáp."""
    if not CHO_HOC_PATH.exists():
        return
    q_chuan = cau_hoi.strip().lower()
    con_lai = []
    for line in CHO_HOC_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get("cau_hoi", "").strip().lower() != q_chuan:
                con_lai.append(line)
        except Exception:
            con_lai.append(line)
    CHO_HOC_PATH.write_text("\n".join(con_lai) + ("\n" if con_lai else ""), encoding="utf-8")

