"""Persistent profile preferences for the configured account database."""
import json
import re
from datetime import date, datetime

from backend.chatbot import co_so_du_lieu
from backend.chatbot.co_so_du_lieu import ket_noi

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[0-9+\-\s().]{6,25}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_GOALS = ("", "Ăn uống cân bằng", "Ăn chay", "Ăn ít muối", "Ăn ít dầu")
_HEALTH_ALLOWED = {"Cảm", "Ho", "Sốt", "Đang hành kinh"}


def _sach_chuoi(value, max_len):
    cleaned = _CONTROL_RE.sub(" ", str(value or "")).strip()
    return cleaned[:max_len]


def _chuan_hoa_tuy_chon(ten_hien_thi, settings):
    display = _sach_chuoi(ten_hien_thi, 100)
    if not display:
        raise ValueError("Tên hiển thị cần từ 1 đến 100 ký tự.")
    raw = dict(settings or {})
    email = _sach_chuoi(raw.get("email"), 120)
    if email and not _EMAIL_RE.fullmatch(email):
        raise ValueError("Địa chỉ email không đúng định dạng.")
    phone = _sach_chuoi(raw.get("phone"), 25)
    if phone and not _PHONE_RE.fullmatch(phone):
        raise ValueError("Số điện thoại chỉ gồm số và ký tự +, -, khoảng trắng (6–25 ký tự).")
    goal = str(raw.get("goal") or "").strip()
    if goal not in _GOALS:
        goal = _GOALS[1]
    try:
        servings = max(1, min(30, int(raw.get("servings", 2))))
    except (TypeError, ValueError):
        servings = 2
    birthday = raw.get("birthday")
    if isinstance(birthday, date):
        birthday_iso = birthday.isoformat()
    elif isinstance(birthday, str) and birthday.strip():
        birthday_iso = date.fromisoformat(birthday.strip()).isoformat()
    else:
        birthday_iso = None
    health = [str(item).strip() for item in (raw.get("health") or []) if str(item).strip() in _HEALTH_ALLOWED]
    alerts_raw = raw.get("alerts") if isinstance(raw.get("alerts"), dict) else {}
    alerts = {str(k)[:80]: bool(v) for k, v in alerts_raw.items()}
    return display, {
        "email": email,
        "phone": phone,
        "birthday": birthday_iso,
        "goal": goal,
        "servings": servings,
        "avoid": _sach_chuoi(raw.get("avoid"), 300),
        "allergies": _sach_chuoi(raw.get("allergies"), 300),
        "health": health,
        "notes": _sach_chuoi(raw.get("notes"), 500),
        "alerts": alerts,
    }


def khoi_tao_tuy_chon(con):
    if co_so_du_lieu.BACKEND != "sqlite":
        return
    con.execute("""
        CREATE TABLE IF NOT EXISTS tuy_chon_ho_so (
            ten_dang_nhap VARCHAR(384) PRIMARY KEY,
            tuy_chon TEXT NOT NULL,
            FOREIGN KEY (ten_dang_nhap) REFERENCES nguoi_dung(ten_dang_nhap) ON DELETE CASCADE
        )
    """)


def doc_tuy_chon(ten_dang_nhap):
    with ket_noi() as con:
        khoi_tao_tuy_chon(con)
        row = con.execute(
            "SELECT tuy_chon FROM tuy_chon_ho_so WHERE ten_dang_nhap=?",
            (ten_dang_nhap,),
        ).fetchone()
    if row is None:
        return {}
    settings = json.loads(row["tuy_chon"])
    if settings.get("birthday"):
        settings["birthday"] = date.fromisoformat(settings["birthday"])
    return settings


def luu_tuy_chon(ten_dang_nhap, ten_hien_thi, settings):
    display, sanitized = _chuan_hoa_tuy_chon(ten_hien_thi, settings)
    payload = json.dumps(sanitized, ensure_ascii=False)
    now = datetime.now().isoformat(timespec="seconds")
    with ket_noi(ghi=True) as con:
        khoi_tao_tuy_chon(con)
        account = con.execute(
            "SELECT ten_dang_nhap FROM nguoi_dung WHERE ten_dang_nhap=? AND kich_hoat=1",
            (ten_dang_nhap,),
        ).fetchone()
        if account is None:
            return False
        con.execute(
            "UPDATE nguoi_dung SET ten_hien_thi=?, cap_nhat=? WHERE ten_dang_nhap=? AND kich_hoat=1",
            (display, now, ten_dang_nhap),
        )
        con.execute("DELETE FROM tuy_chon_ho_so WHERE ten_dang_nhap=?", (ten_dang_nhap,))
        con.execute(
            "INSERT INTO tuy_chon_ho_so (ten_dang_nhap,tuy_chon) VALUES (?,?)",
            (ten_dang_nhap, payload),
        )
    return True
