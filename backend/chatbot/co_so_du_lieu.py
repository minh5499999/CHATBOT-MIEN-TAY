"""SQLite cho tài khoản/phiên/lịch sử; chuyển JSON một lần trong transaction."""
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sqlite3
import threading
import uuid

from backend.chatbot.cau_hinh import ROOT, nap_env

nap_env()
BACKEND=os.environ.get('TAI_KHOAN_BACKEND','sqlite').lower()

FILE_DB = ROOT/'du_lieu_nguoi_dung/chatbot.sqlite3'
_KHOA = threading.RLock()
_SAN_SANG = set()

SCHEMA = """
CREATE TABLE IF NOT EXISTS cau_hinh_db (khoa TEXT PRIMARY KEY, gia_tri TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS nguoi_dung (
 ten_dang_nhap TEXT PRIMARY KEY COLLATE NOCASE,
 ten_hien_thi TEXT NOT NULL, email TEXT, google INTEGER NOT NULL DEFAULT 0,
 muoi TEXT, bam TEXT, so_vong_bam INTEGER NOT NULL DEFAULT 200000,
 vai_tro TEXT NOT NULL DEFAULT 'user' CHECK(vai_tro IN ('admin','user')),
 kich_hoat INTEGER NOT NULL DEFAULT 1 CHECK(kich_hoat IN (0,1)),
 ngay_tao TEXT NOT NULL, cap_nhat TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phien (
 bam_ma TEXT PRIMARY KEY,
 ten_dang_nhap TEXT NOT NULL REFERENCES nguoi_dung(ten_dang_nhap) ON DELETE CASCADE,
 het_han TEXT NOT NULL, tao_luc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS phien_nguoi_dung ON phien(ten_dang_nhap);
CREATE TABLE IF NOT EXISTS cuoc_tro_chuyen (
 ten_dang_nhap TEXT NOT NULL REFERENCES nguoi_dung(ten_dang_nhap) ON DELETE CASCADE,
 ma TEXT NOT NULL, tieu_de TEXT NOT NULL, tao_luc TEXT NOT NULL, cap_nhat TEXT NOT NULL,
 PRIMARY KEY(ten_dang_nhap,ma)
);
CREATE TABLE IF NOT EXISTS tin_nhan (
 id INTEGER PRIMARY KEY,
 ten_dang_nhap TEXT NOT NULL, ma_cuoc TEXT NOT NULL, thu_tu INTEGER NOT NULL,
 du_lieu_json TEXT NOT NULL,
 FOREIGN KEY(ten_dang_nhap,ma_cuoc) REFERENCES cuoc_tro_chuyen(ten_dang_nhap,ma) ON DELETE CASCADE,
 UNIQUE(ten_dang_nhap,ma_cuoc,thu_tu)
);
CREATE TABLE IF NOT EXISTS nhat_ky_quan_tri (
 id INTEGER PRIMARY KEY, nguoi_thuc_hien TEXT NOT NULL, doi_tuong TEXT NOT NULL,
 hanh_dong TEXT NOT NULL, chi_tiet TEXT NOT NULL, tao_luc TEXT NOT NULL
);
"""


def _doc(path, default):
    if not path.exists():
        return default
    # File hỏng phải dừng chuyển đổi, không âm thầm coi là danh sách rỗng.
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _mo():
    con=sqlite3.connect(str(FILE_DB),timeout=10)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=10000')
    return con


def _chuyen_json(con):
    folder=Path(FILE_DB).parent
    users=_doc(folder/'nguoi_dung.json',{})
    sessions=_doc(folder/'phien.json',{})
    histories={p.stem:_doc(p,[]) for p in sorted((folder/'lich_su').glob('*.json'))}
    if not isinstance(users,dict) or not isinstance(sessions,dict) or any(not isinstance(v,list) for v in histories.values()):
        raise ValueError('Dữ liệu JSON cũ sai cấu trúc; đã dừng chuyển đổi.')
    files=[p for p in (folder/'nguoi_dung.json',folder/'phien.json') if p.exists()]
    files += sorted((folder/'lich_su').glob('*.json'))
    backup=None
    if files:
        backup=folder/'sao_luu_json'/(datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8])
        for source in files:
            target=backup/source.relative_to(folder)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
    now=datetime.now().isoformat(timespec='seconds')
    for name,user in users.items():
        # JSON cũ chưa có phân quyền: mọi tài khoản được chuyển thành user.
        con.execute('''INSERT INTO nguoi_dung
            (ten_dang_nhap,ten_hien_thi,email,google,muoi,bam,so_vong_bam,ngay_tao,cap_nhat)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (name,user.get('ten_hien_thi',name),user.get('email'),int(bool(user.get('google'))),
             user.get('muoi'),user.get('bam'),200000,user.get('ngay_tao',now),now))
    for name,conversations in histories.items():
        owner=con.execute('SELECT ten_dang_nhap FROM nguoi_dung WHERE ten_dang_nhap=?',(name,)).fetchone()
        if not owner:
            # Giữ lịch sử mồ côi nhưng không tạo tài khoản có thể đăng nhập.
            con.execute('''INSERT INTO nguoi_dung
                (ten_dang_nhap,ten_hien_thi,kich_hoat,ngay_tao,cap_nhat) VALUES (?,?,0,?,?)''',(name,name,now,now))
        else:
            name=owner['ten_dang_nhap']
        for chat in conversations:
            con.execute('''INSERT INTO cuoc_tro_chuyen VALUES (?,?,?,?,?)''',
                        (name,chat['ma'],chat['tieu_de'],chat['tao_luc'],chat['cap_nhat']))
            con.executemany('INSERT INTO tin_nhan(ten_dang_nhap,ma_cuoc,thu_tu,du_lieu_json) VALUES (?,?,?,?)',
                            [(name,chat['ma'],i,json.dumps(m,ensure_ascii=False)) for i,m in enumerate(chat['tin_nhan'])])
    for token,session in sessions.items():
        owner=con.execute('SELECT ten_dang_nhap FROM nguoi_dung WHERE ten_dang_nhap=?',(session['ten_dang_nhap'],)).fetchone()
        if owner:
            con.execute('INSERT INTO phien VALUES (?,?,?,?)',(token,owner['ten_dang_nhap'],session['het_han'],now))
    details={'so_tai_khoan_json':len(users),'so_cuoc_tro_chuyen':sum(map(len,histories.values())),
             'so_tin_nhan':sum(len(c['tin_nhan']) for chats in histories.values() for c in chats),
             'so_phien_json':len(sessions),'thu_muc_sao_luu':str(backup) if backup else None}
    con.execute('INSERT INTO cau_hinh_db VALUES (?,?)',('chuyen_json_v1',json.dumps(details,ensure_ascii=False)))
    con.execute('INSERT INTO cau_hinh_db VALUES (?,?)',('phien_ban','1'))


def khoi_tao():
    path=Path(FILE_DB).resolve()
    with _KHOA:
        if path in _SAN_SANG and path.exists():
            return
        path.parent.mkdir(parents=True,exist_ok=True)
        con=_mo()
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA)
            con.execute('BEGIN IMMEDIATE')
            if not con.execute("SELECT 1 FROM cau_hinh_db WHERE khoa='chuyen_json_v1'").fetchone():
                _chuyen_json(con)
            con.commit()
            _SAN_SANG.add(path)
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


@contextmanager
def ket_noi(ghi=False):
    if BACKEND=='mysql':
        from backend.chatbot.co_so_du_lieu_mysql import ket_noi as ket_noi_mysql
        with ket_noi_mysql(ghi=ghi) as con:
            yield con
        return
    if BACKEND!='sqlite':
        raise ValueError('TAI_KHOAN_BACKEND phải là sqlite hoặc mysql.')
    khoi_tao()
    con=_mo()
    try:
        if ghi:
            con.execute('BEGIN IMMEDIATE')
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
