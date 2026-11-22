"""Danh sách món yêu thích của từng tài khoản, lưu trong một tệp JSON trên máy.

Chỉ lưu câu hỏi (để hỏi lại) và thời điểm lưu, không lưu nội dung câu trả lời.
"""
import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / 'du_lieu_nguoi_dung/mon_yeu_thich.json'
TOI_DA = 100
_khoa = threading.Lock()


def _doc():
    try:
        data = json.loads(FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _ghi(data):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tam = tempfile.mkstemp(dir=FILE.parent, prefix='.mon_yeu_thich_', suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tam, FILE)
    except BaseException:
        Path(tam).unlink(missing_ok=True)
        raise


def danh_sach(ten_dang_nhap):
    items = _doc().get(ten_dang_nhap, [])
    return [m for m in items if isinstance(m, dict) and isinstance(m.get('cau_hoi'), str)]


def da_luu(ten_dang_nhap, cau_hoi):
    return any(m['cau_hoi'] == cau_hoi for m in danh_sach(ten_dang_nhap))


def them(ten_dang_nhap, cau_hoi):
    cau_hoi = str(cau_hoi).strip()[:200]
    if not cau_hoi:
        return
    with _khoa:
        data = _doc()
        items = [m for m in data.get(ten_dang_nhap, []) if isinstance(m, dict) and m.get('cau_hoi') != cau_hoi]
        items.insert(0, {'cau_hoi': cau_hoi, 'luc': datetime.now().isoformat(timespec='seconds')})
        data[ten_dang_nhap] = items[:TOI_DA]
        _ghi(data)


def xoa(ten_dang_nhap, cau_hoi):
    with _khoa:
        data = _doc()
        data[ten_dang_nhap] = [m for m in data.get(ten_dang_nhap, [])
                               if isinstance(m, dict) and m.get('cau_hoi') != cau_hoi]
        _ghi(data)


def doi(ten_dang_nhap, cau_hoi):
    (xoa if da_luu(ten_dang_nhap, cau_hoi) else them)(ten_dang_nhap, cau_hoi)
