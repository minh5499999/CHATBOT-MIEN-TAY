"""Dịch vụ tài khoản/RBAC dùng SQLite hoặc MySQL qua tầng kết nối chung."""
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid

from backend.chatbot import co_so_du_lieu
from backend.chatbot.co_so_du_lieu import ket_noi

TEN_HOP_LE=re.compile(r'^[a-zA-Z0-9_.]{3,30}$')
_CONTROL_RE = re.compile(r'[\x00-\x1f\x7f]')
SO_VONG_BAM=600_000
HAN_PHIEN=timedelta(days=30)
_DUMMY_SALT = "00" * 16
MAX_LOGIN_ATTEMPTS = 5
MAX_SIGNUP_ATTEMPTS = 20
_SIGNUP_RATE_KEY = "__signup_rate__"
LOGIN_WINDOW_SECONDS = 900
LOGIN_LOCKOUT_SECONDS = 300
MAX_CHAT_MESSAGES = 200
MAX_MESSAGE_JSON_CHARS = 65_536
_LOGIN_LOCK = threading.Lock()


def _dam_bao_bang_gioi_han(con):
    if co_so_du_lieu.BACKEND != 'sqlite':
        return
    con.execute("""
        CREATE TABLE IF NOT EXISTS gioi_han_dang_nhap (
            khoa VARCHAR(120) PRIMARY KEY,
            so_lan INTEGER NOT NULL,
            cua_so_bat_dau DOUBLE NOT NULL,
            khoa_den DOUBLE NOT NULL
        )
    """)


def kiem_tra_khoa_dang_nhap(ten_dang_nhap):
    """Trả về số giây khóa còn lại từ DB (0 nếu chưa bị giới hạn đăng nhập)."""
    key = (ten_dang_nhap or "").strip().lower()[:120]
    if not key:
        return 0
    now = time.time()
    with _LOGIN_LOCK:
        with ket_noi(ghi=True) as con:
            _dam_bao_bang_gioi_han(con)
            row = con.execute(
                "SELECT khoa_den FROM gioi_han_dang_nhap WHERE khoa=?",
                (key,),
            ).fetchone()
            if not row:
                return 0
            until = float(row["khoa_den"] or 0.0)
            if until > now:
                return int(until - now) + 1
            if until > 0.0:
                con.execute("DELETE FROM gioi_han_dang_nhap WHERE khoa=?", (key,))
    return 0


def xoa_gioi_han_dang_nhap(ten_dang_nhap=None):
    """Xóa bộ đếm đăng nhập thất bại trong DB cho một tài khoản (hoặc toàn bộ nếu None)."""
    with _LOGIN_LOCK:
        with ket_noi(ghi=True) as con:
            _dam_bao_bang_gioi_han(con)
            if ten_dang_nhap is None:
                con.execute("DELETE FROM gioi_han_dang_nhap")
            else:
                key = ten_dang_nhap.strip().lower()[:120]
                con.execute("DELETE FROM gioi_han_dang_nhap WHERE khoa=?", (key,))


def _ghi_nhan_that_bai(key, max_attempts=MAX_LOGIN_ATTEMPTS):
    key = (key or "").strip().lower()[:120]
    if not key:
        return
    now = time.time()
    with _LOGIN_LOCK:
        with ket_noi(ghi=True) as con:
            _dam_bao_bang_gioi_han(con)
            row = con.execute(
                "SELECT so_lan, cua_so_bat_dau, khoa_den FROM gioi_han_dang_nhap WHERE khoa=?",
                (key,),
            ).fetchone()
            if not row or (now - float(row["cua_so_bat_dau"])) > LOGIN_WINDOW_SECONDS:
                count = 1
                window_start = now
                locked_until = 0.0
            else:
                count = int(row["so_lan"]) + 1
                window_start = float(row["cua_so_bat_dau"])
                locked_until = float(row["khoa_den"] or 0.0)
                if count >= max_attempts:
                    locked_until = now + LOGIN_LOCKOUT_SECONDS
            con.execute("DELETE FROM gioi_han_dang_nhap WHERE khoa=?", (key,))
            con.execute(
                "INSERT INTO gioi_han_dang_nhap (khoa, so_lan, cua_so_bat_dau, khoa_den) VALUES (?, ?, ?, ?)",
                (key, count, window_start, locked_until),
            )


def _now():
    return datetime.now().isoformat(timespec='seconds')


def _bam(mat_khau,muoi,so_vong=SO_VONG_BAM):
    return hashlib.pbkdf2_hmac('sha256',mat_khau.encode('utf-8'),bytes.fromhex(muoi),so_vong).hex()


def _ho_so(row):
    if not row or not row['kich_hoat']:
        return None
    result={k:row[k] for k in ('ten_dang_nhap','ten_hien_thi','vai_tro')}
    if row['google']:
        result['google']=True
    return result


def doc_ho_so(ten_dang_nhap):
    with ket_noi() as con:
        return _ho_so(con.execute('SELECT * FROM nguoi_dung WHERE ten_dang_nhap=?',(ten_dang_nhap,)).fetchone())


def la_admin(ten_dang_nhap):
    profile=doc_ho_so(ten_dang_nhap)
    return bool(profile and profile['vai_tro']=='admin')


def _yeu_cau_admin(con,actor):
    row=con.execute("SELECT 1 FROM nguoi_dung WHERE ten_dang_nhap=? AND vai_tro='admin' AND kich_hoat=1",(actor,)).fetchone()
    if not row:
        raise PermissionError('Chỉ quản trị viên đang hoạt động mới được thực hiện thao tác này.')


def _yeu_cau_user(con,name):
    row=con.execute('SELECT ten_dang_nhap FROM nguoi_dung WHERE ten_dang_nhap=? AND kich_hoat=1',(name,)).fetchone()
    if not row:
        raise PermissionError('Tài khoản không tồn tại hoặc đã bị khóa.')
    return row['ten_dang_nhap']


def _nhat_ky(con,actor,target,action,details=''):
    con.execute('INSERT INTO nhat_ky_quan_tri(nguoi_thuc_hien,doi_tuong,hanh_dong,chi_tiet,tao_luc) VALUES (?,?,?,?,?)',
                (actor,target,action,details,_now()))


def _chuan_hoa_ten_hien_thi(display):
    return _CONTROL_RE.sub(' ', str(display or '')).strip()


def _hop_le(ten,mat_khau,ten_hien_thi=None):
    if not TEN_HOP_LE.fullmatch(ten):
        return 'Tên đăng nhập 3–30 ký tự, chỉ gồm chữ không dấu, số, dấu chấm hoặc gạch dưới.'
    if ten_hien_thi is not None and len(_chuan_hoa_ten_hien_thi(ten_hien_thi)) > 100:
        return 'Tên hiển thị tối đa 100 ký tự.'
    if not 8<=len(mat_khau)<=64:
        return 'Mật khẩu mới cần từ 8 đến 64 ký tự.'
    return None


def _them(con,name,display,password,role='user'):
    salt=os.urandom(16).hex()
    now=_now()
    clean_display = _chuan_hoa_ten_hien_thi(display)
    if len(clean_display) > 100:
        raise ValueError('Tên hiển thị tối đa 100 ký tự.')
    con.execute('''INSERT INTO nguoi_dung
        (ten_dang_nhap,ten_hien_thi,muoi,bam,so_vong_bam,vai_tro,ngay_tao,cap_nhat)
        VALUES (?,?,?,?,?,?,?,?)''',(name,clean_display or name,salt,_bam(password,salt),SO_VONG_BAM,role,now,now))


def dang_ky(ten_dang_nhap,ten_hien_thi,mat_khau):
    wait = kiem_tra_khoa_dang_nhap(_SIGNUP_RATE_KEY)
    if wait > 0:
        return False, f'Thao tác đăng ký quá nhanh. Vui lòng thử lại sau {wait} giây.'
    ten=ten_dang_nhap.strip().lower()
    error=_hop_le(ten,mat_khau,ten_hien_thi)
    if error:
        return False,error
    _ghi_nhan_that_bai(_SIGNUP_RATE_KEY, max_attempts=MAX_SIGNUP_ATTEMPTS)
    try:
        with ket_noi(ghi=True) as con:
            _them(con,ten,ten_hien_thi,mat_khau)  # Đăng ký công khai luôn là user.
        return True,'Tạo tài khoản thành công.'
    except sqlite3.IntegrityError:
        return False,'Tên đăng nhập này đã có người dùng.'


def dang_nhap(ten_dang_nhap,mat_khau):
    key=(ten_dang_nhap or '').strip().lower()
    if kiem_tra_khoa_dang_nhap(key) > 0:
        return None
    with ket_noi() as con:
        row=con.execute('SELECT * FROM nguoi_dung WHERE ten_dang_nhap=?',(key,)).fetchone()
        if not row or not row['kich_hoat'] or not row['bam'] or not row['muoi']:
            # Chạy PBKDF2 giả để giảm khác biệt thời gian phản hồi khi rà tên tài khoản.
            _bam(mat_khau or '', _DUMMY_SALT, SO_VONG_BAM)
            _ghi_nhan_that_bai(key)
            return None
        try:
            valid=hmac.compare_digest(row['bam'],_bam(mat_khau,row['muoi'],row['so_vong_bam']))
        except ValueError:
            _ghi_nhan_that_bai(key)
            return None
        if not valid:
            _ghi_nhan_that_bai(key)
            return None
        xoa_gioi_han_dang_nhap(key)
        return _ho_so(row)


def dang_nhap_google(email,ten_hien_thi=None):
    """Chỉ gọi sau khi Google OAuth đã xác thực email trong app."""
    email=email.strip().lower()
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email):
        return None
    name='google-'+re.sub(r'[^a-z0-9_.]','_',email.replace('@','_at_'))
    with ket_noi(ghi=True) as con:
        row=con.execute('SELECT * FROM nguoi_dung WHERE ten_dang_nhap=?',(name,)).fetchone()
        if row and row['email']!=email:
            name += '_'+hashlib.sha256(email.encode()).hexdigest()[:12]
            row=con.execute('SELECT * FROM nguoi_dung WHERE ten_dang_nhap=?',(name,)).fetchone()
        if not row:
            now=_now()
            con.execute('''INSERT INTO nguoi_dung
                (ten_dang_nhap,ten_hien_thi,email,google,ngay_tao,cap_nhat) VALUES (?,?,?,1,?,?)''',
                        (name,ten_hien_thi or email.split('@')[0],email,now,now))
            row=con.execute('SELECT * FROM nguoi_dung WHERE ten_dang_nhap=?',(name,)).fetchone()
        return _ho_so(row)


def _bam_ma_phien(ma):
    return hashlib.sha256(ma.encode('utf-8')).hexdigest()


def tao_phien(ten_dang_nhap):
    ma=secrets.token_urlsafe(32)
    now=datetime.now()
    with ket_noi(ghi=True) as con:
        ten_dang_nhap=_yeu_cau_user(con,ten_dang_nhap)
        con.execute('DELETE FROM phien WHERE het_han<=?',(now.isoformat(timespec='seconds'),))
        con.execute('INSERT INTO phien VALUES (?,?,?,?)',(_bam_ma_phien(ma),ten_dang_nhap,
                    (now+HAN_PHIEN).isoformat(timespec='seconds'),now.isoformat(timespec='seconds')))
    return ma


def nguoi_dung_theo_phien(ma):
    if not isinstance(ma,str) or not ma:
        return None
    with ket_noi() as con:
        row=con.execute('''SELECT n.* FROM phien p JOIN nguoi_dung n USING(ten_dang_nhap)
            WHERE p.bam_ma=? AND p.het_han>?''',(_bam_ma_phien(ma),_now())).fetchone()
        return _ho_so(row)


def xoa_phien(ma):
    if isinstance(ma,str) and ma:
        with ket_noi(ghi=True) as con:
            con.execute('DELETE FROM phien WHERE bam_ma=?',(_bam_ma_phien(ma),))


def danh_sach_cuoc_tro_chuyen(ten_dang_nhap):
    with ket_noi() as con:
        ten_dang_nhap=_yeu_cau_user(con,ten_dang_nhap)
        chats=con.execute('SELECT ma,tieu_de,tao_luc,cap_nhat FROM cuoc_tro_chuyen WHERE ten_dang_nhap=? ORDER BY cap_nhat DESC',
                          (ten_dang_nhap,)).fetchall()
        result=[]
        for row in chats:
            messages=con.execute('SELECT du_lieu_json FROM tin_nhan WHERE ten_dang_nhap=? AND ma_cuoc=? ORDER BY thu_tu',
                                 (ten_dang_nhap,row['ma'])).fetchall()
            result.append({**dict(row),'tin_nhan':[json.loads(m['du_lieu_json']) for m in messages]})
        return result


def _chuan_hoa_tin_nhan_luu(msg):
    item = dict(msg)
    if isinstance(item.get('noi_dung'), str) and len(item['noi_dung']) > 8000:
        item['noi_dung'] = item['noi_dung'][:8000]
    if isinstance(item.get('ket_qua'), dict):
        item['ket_qua'] = rut_gon_ket_qua(item['ket_qua'])
    raw = json.dumps(item, ensure_ascii=False)
    if len(raw) > MAX_MESSAGE_JSON_CHARS and isinstance(item.get('ket_qua'), dict):
        kq = dict(item['ket_qua'])
        if isinstance(kq.get('cau_tra_loi'), str):
            kq['cau_tra_loi'] = kq['cau_tra_loi'][:16000]
        item['ket_qua'] = kq
        raw = json.dumps(item, ensure_ascii=False)
    if len(raw) > MAX_MESSAGE_JSON_CHARS:
        raise ValueError('Tin nhắn vượt quá kích thước cho phép.')
    return raw


def luu_cuoc_tro_chuyen(ten_dang_nhap,ma,tin_nhan):
    now=_now()
    tin_nhan = list(tin_nhan or [])[-MAX_CHAT_MESSAGES:]
    first=next((m['noi_dung'] for m in tin_nhan if m['vai']=='user'),'Cuộc trò chuyện')
    title=first if len(first)<=45 else first[:42].rstrip()+'...'
    serialized = [_chuan_hoa_tin_nhan_luu(m) for m in tin_nhan]
    with ket_noi(ghi=True) as con:
        ten_dang_nhap=_yeu_cau_user(con,ten_dang_nhap)
        old=con.execute('SELECT 1 FROM cuoc_tro_chuyen WHERE ten_dang_nhap=? AND ma=?',(ten_dang_nhap,ma)).fetchone() if ma else None
        if not old:
            ma=uuid.uuid4().hex[:12]
            con.execute('INSERT INTO cuoc_tro_chuyen VALUES (?,?,?,?,?)',(ten_dang_nhap,ma,title,now,now))
        else:
            con.execute('UPDATE cuoc_tro_chuyen SET tieu_de=?,cap_nhat=? WHERE ten_dang_nhap=? AND ma=?',(title,now,ten_dang_nhap,ma))
        con.execute('DELETE FROM tin_nhan WHERE ten_dang_nhap=? AND ma_cuoc=?',(ten_dang_nhap,ma))
        con.executemany('INSERT INTO tin_nhan(ten_dang_nhap,ma_cuoc,thu_tu,du_lieu_json) VALUES (?,?,?,?)',
                        [(ten_dang_nhap,ma,i,raw_json) for i,raw_json in enumerate(serialized)])
    return ma


def xoa_cuoc_tro_chuyen(ten_dang_nhap,ma):
    with ket_noi(ghi=True) as con:
        ten_dang_nhap=_yeu_cau_user(con,ten_dang_nhap)
        con.execute('DELETE FROM cuoc_tro_chuyen WHERE ten_dang_nhap=? AND ma=?',(ten_dang_nhap,ma))


def rut_gon_ket_qua(kq):
    fields=('cau_tra_loi','loai','nguon','goi_y','nhan_goi_y','chu_de','trang_thai','mau_phan_hoi','policy_build_id','policy_seal')
    return {key:kq[key] for key in fields if key in kq}


def danh_sach_nguoi_dung(actor):
    with ket_noi() as con:
        _yeu_cau_admin(con,actor)
        return [dict(r) for r in con.execute('''SELECT n.ten_dang_nhap,n.ten_hien_thi,n.email,n.google,
            n.vai_tro,n.kich_hoat,n.ngay_tao,
            (SELECT count(*) FROM cuoc_tro_chuyen c WHERE c.ten_dang_nhap=n.ten_dang_nhap) AS so_cuoc_tro_chuyen
            FROM nguoi_dung n ORDER BY n.ngay_tao,n.ten_dang_nhap''')]


def admin_tao_tai_khoan(actor,name,display,password,role='user'):
    name=name.strip().lower()
    with ket_noi(ghi=True) as con:
        _yeu_cau_admin(con,actor)
        error=_hop_le(name,password,display)
        if error or role not in ('user','admin'):
            return False,error or 'Vai trò không hợp lệ.'
        if con.execute('SELECT 1 FROM nguoi_dung WHERE ten_dang_nhap=?',(name,)).fetchone():
            return False,'Tên đăng nhập này đã có người dùng.'
        _them(con,name,display,password,role)
        _nhat_ky(con,actor,name,'tao_tai_khoan',role)
    return True,'Đã tạo tài khoản.'


def admin_cap_nhat(actor,target,role,active,ten_hien_thi=None):
    with ket_noi(ghi=True) as con:
        _yeu_cau_admin(con,actor)
        if role not in ('user','admin'):
            return False,'Vai trò không hợp lệ.'
        row=con.execute('SELECT * FROM nguoi_dung WHERE ten_dang_nhap=?',(target,)).fetchone()
        if not row:
            return False,'Không tìm thấy tài khoản.'
        if row['vai_tro']=='admin' and row['kich_hoat'] and (role!='admin' or not active):
            others=con.execute("SELECT count(*) FROM nguoi_dung WHERE vai_tro='admin' AND kich_hoat=1 AND ten_dang_nhap<>?",(target,)).fetchone()[0]
            if not others:
                return False,'Không thể khóa hoặc hạ quyền admin cuối cùng đang hoạt động.'
        con.execute('UPDATE nguoi_dung SET vai_tro=?,kich_hoat=?,cap_nhat=? WHERE ten_dang_nhap=?',(role,int(bool(active)),_now(),target))
        if ten_hien_thi is not None:
            display=ten_hien_thi.strip()
            if not display or len(display)>100:
                raise ValueError('Tên hiển thị cần từ 1 đến 100 ký tự.')
            con.execute('UPDATE nguoi_dung SET ten_hien_thi=? WHERE ten_dang_nhap=?',(display,target))
        if row['vai_tro']!=role or not active:
            con.execute('DELETE FROM phien WHERE ten_dang_nhap=?',(target,))
        _nhat_ky(con,actor,target,'cap_nhat_quyen',json.dumps({'vai_tro':role,'kich_hoat':bool(active)}))
    return True,'Đã cập nhật tài khoản.'


def admin_xoa_tai_khoan(actor,target):
    """Xóa sau khi giao diện đã xác nhận; kiểm tra quyền lại trong transaction."""
    with ket_noi(ghi=True) as con:
        _yeu_cau_admin(con,actor)
        row=con.execute('SELECT vai_tro,kich_hoat FROM nguoi_dung WHERE ten_dang_nhap=?',(target,)).fetchone()
        if not row:
            return False,'Không tìm thấy tài khoản.'
        if row['vai_tro']=='admin' and row['kich_hoat']:
            others=con.execute("SELECT count(*) FROM nguoi_dung WHERE vai_tro='admin' AND kich_hoat=1 AND ten_dang_nhap<>?",(target,)).fetchone()[0]
            if not others:
                return False,'Không thể xóa admin cuối cùng đang hoạt động.'
        if actor==target:
            return False,'Không thể xóa tài khoản đang đăng nhập.'
        # Xóa dữ liệu phụ trước để tương thích cả các schema MySQL cũ chưa có cascade.
        for table in ('tuy_chon_ho_so','tin_nhan','cuoc_tro_chuyen','phien'):
            con.execute('DELETE FROM '+table+' WHERE ten_dang_nhap=?',(target,))
        con.execute('DELETE FROM gioi_han_dang_nhap WHERE khoa=?',(target.strip().lower()[:120],))
        con.execute('DELETE FROM nguoi_dung WHERE ten_dang_nhap=?',(target,))
        _nhat_ky(con,actor,target,'xoa_tai_khoan','Đã xóa tài khoản, phiên và lịch sử trò chuyện')
    return True,'Đã xóa tài khoản và dữ liệu trò chuyện liên quan.'


def ghi_nhat_ky_quan_tri(actor,doi_tuong,hanh_dong,chi_tiet=''):
    with ket_noi(ghi=True) as con:
        _yeu_cau_admin(con,actor)
        _nhat_ky(con,actor,doi_tuong,hanh_dong,chi_tiet)


def admin_dat_lai_mat_khau(actor,target,password):
    with ket_noi(ghi=True) as con:
        _yeu_cau_admin(con,actor)
        row=con.execute('SELECT * FROM nguoi_dung WHERE ten_dang_nhap=?',(target,)).fetchone()
        if not row or row['google']:
            return False,'Chỉ đặt lại mật khẩu cho tài khoản đăng nhập bằng mật khẩu.'
        if not 8<=len(password)<=64:
            return False,'Mật khẩu mới cần từ 8 đến 64 ký tự.'
        salt=os.urandom(16).hex()
        con.execute('UPDATE nguoi_dung SET muoi=?,bam=?,so_vong_bam=?,cap_nhat=? WHERE ten_dang_nhap=?',
                    (salt,_bam(password,salt),SO_VONG_BAM,_now(),target))
        con.execute('DELETE FROM phien WHERE ten_dang_nhap=?',(target,))
        _nhat_ky(con,actor,target,'dat_lai_mat_khau')
    xoa_gioi_han_dang_nhap(target)
    return True,'Đã đặt lại mật khẩu và thu hồi các phiên đăng nhập của tài khoản.'


def nhat_ky_quan_tri(actor):
    with ket_noi() as con:
        _yeu_cau_admin(con,actor)
        return [dict(r) for r in con.execute('SELECT nguoi_thuc_hien,doi_tuong,hanh_dong,chi_tiet,tao_luc FROM nhat_ky_quan_tri ORDER BY id DESC LIMIT 100')]


def khoi_tao_admin_cuc_bo(name):
    """Chỉ dùng từ CLI của chủ máy, không gọi từ form đăng ký công khai."""
    name=name.strip().lower()
    with ket_noi(ghi=True) as con:
        if con.execute("SELECT 1 FROM nguoi_dung WHERE vai_tro='admin' AND kich_hoat=1").fetchone():
            row=con.execute('SELECT vai_tro,kich_hoat FROM nguoi_dung WHERE ten_dang_nhap=?',(name,)).fetchone()
            if row and row['vai_tro']=='admin' and row['kich_hoat']:
                return True,'Tài khoản đã là admin.'
            return False,'Đã có admin. Hãy dùng trang quản trị để cấp thêm quyền.'
        row=con.execute('SELECT kich_hoat FROM nguoi_dung WHERE ten_dang_nhap=?',(name,)).fetchone()
        if not row or not row['kich_hoat']:
            return False,'Cần một tài khoản đã có và đang hoạt động để khởi tạo admin.'
        con.execute("UPDATE nguoi_dung SET vai_tro='admin',cap_nhat=? WHERE ten_dang_nhap=?",(_now(),name))
        _nhat_ky(con,'thiet_lap_cuc_bo',name,'khoi_tao_admin')
    return True,'Đã cấp quyền admin cho tài khoản được chỉ định.'
