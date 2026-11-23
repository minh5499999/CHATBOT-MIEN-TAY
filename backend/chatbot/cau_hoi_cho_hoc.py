"""Read pending question statistics without importing the embedding stack."""
from __future__ import annotations
import json
import logging
import sqlite3
from typing import Any
from backend.chatbot import co_so_du_lieu
from backend.chatbot.cau_hinh import ROOT

LOGGER = logging.getLogger(__name__)
CHO_HOC_PATH = ROOT / "du_lieu_nguoi_dung/cau_hoi_cho_hoc.jsonl"
_DEFAULT_SQLITE_DB = ROOT / "du_lieu_nguoi_dung/chatbot.sqlite3"
SQLITE_DB = _DEFAULT_SQLITE_DB
_TU_KHOA_AM_THUC = ("nấu", "làm", "món", "ăn", "nguyên liệu", "công thức", "dinh dưỡng", "thay thế", "bảo quản")

_SQL_TIN_NHAN = """
    SELECT t.ten_dang_nhap, t.ma_cuoc, t.thu_tu, t.du_lieu_json, c.cap_nhat
    FROM tin_nhan t
    JOIN cuoc_tro_chuyen c
      ON t.ten_dang_nhap = c.ten_dang_nhap AND t.ma_cuoc = c.ma
    ORDER BY c.cap_nhat DESC, t.thu_tu ASC
    LIMIT 400
"""


def lay_danh_sach_cau_hoi_chua_biet() -> list[dict[str, Any]]:
    """Tổng hợp danh sách các câu hỏi người dùng hỏi nhưng bot chưa đáp ứng được."""
    ds: list[dict[str, Any]] = []
    da_gap = set()

    # 1. Từ file cau_hoi_cho_hoc.jsonl
    if CHO_HOC_PATH.exists():
        for line in CHO_HOC_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                q = str(obj.get("cau_hoi") or "").strip()
                if q and q.lower() not in da_gap:
                    da_gap.add(q.lower())
                    ds.append(obj)
            except Exception as exc:
                LOGGER.warning("Bỏ qua dòng chờ học lỗi JSON: %s", exc)

    # 2. Từ CSDL tài khoản chung (MySQL hoặc SQLite)
    rows: list[Any] = []
    use_shared_db = co_so_du_lieu.BACKEND == "mysql" or (
        SQLITE_DB == _DEFAULT_SQLITE_DB and co_so_du_lieu.FILE_DB.exists()
    )
    if use_shared_db:
        try:
            with co_so_du_lieu.ket_noi() as con:
                rows = [tuple(r[k] for k in ("ten_dang_nhap", "ma_cuoc", "thu_tu", "du_lieu_json", "cap_nhat"))
                        for r in con.execute(_SQL_TIN_NHAN).fetchall()]
        except Exception as exc:
            LOGGER.warning("Không đọc được câu hỏi chờ học từ DB (%s): %s", co_so_du_lieu.BACKEND, exc)
    elif SQLITE_DB.exists():
        conn = None
        try:
            conn = sqlite3.connect(SQLITE_DB)
            rows = conn.execute(_SQL_TIN_NHAN).fetchall()
        except Exception as exc:
            LOGGER.warning("Không đọc được câu hỏi chờ học từ SQLite: %s", exc)
        finally:
            if conn is not None:
                conn.close()

    if rows:
        convs: dict[tuple[str, str], list[tuple[dict[str, Any], str]]] = {}
        for user, chat_id, _, raw_json, updated_at in rows:
            try:
                msg = json.loads(raw_json)
            except Exception:
                continue
            if isinstance(msg, dict):
                convs.setdefault((user, chat_id), []).append((msg, str(updated_at or "")))

        for items in convs.values():
            for idx, (msg, updated_at) in enumerate(items):
                if msg.get("vai") != "user":
                    continue
                q = str(msg.get("noi_dung") or "").strip()
                if not q or len(q.split()) < 3 or q.lower() in da_gap:
                    continue
                paired = items[idx + 1][0] if idx + 1 < len(items) else None
                loai = None
                if paired and paired.get("vai") == "assistant":
                    loai = (paired.get("ket_qua") or {}).get("loai")
                unresolved = loai in ("khong_chac", "ngoai_pham_vi")
                if unresolved or (paired is None and any(kw in q.lower() for kw in _TU_KHOA_AM_THUC)):
                    da_gap.add(q.lower())
                    ds.append({
                        "thoi_gian": updated_at,
                        "cau_hoi": q,
                        "loai": loai or "nhat_ky_chat",
                        "diem": 0.0,
                        "kho": "",
                    })

    return ds

