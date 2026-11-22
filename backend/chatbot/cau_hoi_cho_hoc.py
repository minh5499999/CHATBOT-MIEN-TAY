"""Read pending question statistics without importing the embedding stack."""
from __future__ import annotations
import json
import sqlite3
from typing import Any
from backend.chatbot.cau_hinh import ROOT

CHO_HOC_PATH = ROOT / "du_lieu_nguoi_dung/cau_hoi_cho_hoc.jsonl"
SQLITE_DB = ROOT / "du_lieu_nguoi_dung/chatbot.sqlite3"

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
                q = obj.get("cau_hoi", "").strip()
                if q and q.lower() not in da_gap:
                    da_gap.add(q.lower())
                    ds.append(obj)
            except Exception:
                pass

    # 2. Từ SQLite (nếu có các câu hỏi của user có câu trả lời ngoài phạm vi)
    if SQLITE_DB.exists():
        try:
            conn = sqlite3.connect(SQLITE_DB)
            cur = conn.cursor()
            cur.execute("""
                SELECT noi_dung, tao_luc
                FROM tin_nhan
                WHERE vai_tro = 'user'
                ORDER BY id DESC LIMIT 200
            """)
            for content, created_at in cur.fetchall():
                q = (content or "").strip()
                if q and len(q.split()) >= 3 and q.lower() not in da_gap:
                    # Kiểm tra xem câu này có chứa các từ hỏi món ăn miền Tây
                    if any(kw in q.lower() for kw in ("nấu", "làm", "món", "ăn", "nguyên liệu", "công thức")):
                        da_gap.add(q.lower())
                        ds.append({
                            "thoi_gian": str(created_at),
                            "cau_hoi": q,
                            "loai": "nhat_ky_chat",
                            "diem": 0.0,
                            "kho": "",
                        })
            conn.close()
        except Exception:
            pass

    return ds

