"""Persistent profile preferences for the configured account database."""
import json
from datetime import date

from backend.chatbot.co_so_du_lieu import ket_noi


def khoi_tao_tuy_chon(con):
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
    birthday = settings.get("birthday")
    payload = json.dumps({**settings, "birthday": birthday.isoformat() if birthday else None},
                         ensure_ascii=False)
    with ket_noi(ghi=True) as con:
        account = con.execute(
            "SELECT ten_dang_nhap FROM nguoi_dung WHERE ten_dang_nhap=? AND kich_hoat=1",
            (ten_dang_nhap,),
        ).fetchone()
        if account is None:
            return False
        con.execute(
            "UPDATE nguoi_dung SET ten_hien_thi=? WHERE ten_dang_nhap=? AND kich_hoat=1",
            (ten_hien_thi, ten_dang_nhap),
        )
        con.execute("DELETE FROM tuy_chon_ho_so WHERE ten_dang_nhap=?", (ten_dang_nhap,))
        con.execute(
            "INSERT INTO tuy_chon_ho_so (ten_dang_nhap,tuy_chon) VALUES (?,?)",
            (ten_dang_nhap, payload),
        )
    return True
