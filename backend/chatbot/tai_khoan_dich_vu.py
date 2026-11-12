"""Dịch vụ tài khoản/RBAC dùng SQLite hoặc MySQL qua tầng kết nối chung."""
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import uuid

from backend.chatbot.co_so_du_lieu import ket_noi

TEN_HOP_LE=re.compile(r'^[a-zA-Z0-9_.]{3,30}$')
SO_VONG_BAM=600_000
HAN_PHIEN=timedelta(days=30)


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


def _hop_le(ten,mat_khau):
    if not TEN_HOP_LE.fullmatch(ten):
        return 'Tên đăng nhập 3–30 ký tự, chỉ gồm chữ không dấu, số, dấu chấm hoặc gạch dưới.'
    if not 8<=len(mat_khau)<=128:
        return 'Mật khẩu mới cần từ 8 đến 128 ký tự.'
    return None


def _them(con,name,display,password,role='user'):
    salt=os.urandom(16).hex()
    now=_now()
    con.execute('''INSERT INTO nguoi_dung
        (ten_dang_nhap,ten_hien_thi,muoi,bam,so_vong_bam,vai_tro,ngay_tao,cap_nhat)
        VALUES (?,?,?,?,?,?,?,?)''',(name,display.strip() or name,salt,_bam(password,salt),SO_VONG_BAM,role,now,now))


def dang_ky(ten_dang_nhap,ten_hien_thi,mat_khau):
    ten=ten_dang_nhap.strip().lower()
    error=_hop_le(ten,mat_khau)
    if error:
        return False,error
    try:
        with ket_noi(ghi=True) as con:
            _them(con,ten,ten_hien_thi,mat_khau)  # Đăng ký công khai luôn là user.
        return True,'Tạo tài khoản thành công.'
    except sqlite3.IntegrityError:
        return False,'Tên đăng nhập này đã có người dùng.'


def dang_nhap(ten_dang_nhap,mat_khau):
    with ket_noi() as con:
        row=con.execute('SELECT * FROM nguoi_dung WHERE ten_dang_nhap=?',(ten_dang_nhap.strip().lower(),)).fetchone()
        if not row or not row['kich_hoat'] or not row['bam'] or not row['muoi']:
            return None
        try:
            valid=hmac.compare_digest(row['bam'],_bam(mat_khau,row['muoi'],row['so_vong_bam']))
        except ValueError:
            return None
        return _ho_so(row) if valid else None


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


def luu_cuoc_tro_chuyen(ten_dang_nhap,ma,tin_nhan):
    now=_now()
    first=next((m['noi_dung'] for m in tin_nhan if m['vai']=='user'),'Cuộc trò chuyện')
    title=first if len(first)<=45 else first[:42].rstrip()+'...'
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
                        [(ten_dang_nhap,ma,i,json.dumps(m,ensure_ascii=False)) for i,m in enumerate(tin_nhan)])
    return ma


def xoa_cuoc_tro_chuyen(ten_dang_nhap,ma):
    with ket_noi(ghi=True) as con:
        ten_dang_nhap=_yeu_cau_user(con,ten_dang_nhap)
        con.execute('DELETE FROM cuoc_tro_chuyen WHERE ten_dang_nhap=? AND ma=?',(ten_dang_nhap,ma))


def rut_gon_ket_qua(kq):
    fields=('cau_tra_loi','loai','nguon','goi_y','nhan_goi_y','chu_de','trang_thai','mau_phan_hoi')
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
        error=_hop_le(name,password)
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
        for table in ('tin_nhan','cuoc_tro_chuyen','phien'):
            con.execute('DELETE FROM '+table+' WHERE ten_dang_nhap=?',(target,))
        con.execute('DELETE FROM nguoi_dung WHERE ten_dang_nhap=?',(target,))
        _nhat_ky(con,actor,target,'xoa_tai_khoan','Đã xóa tài khoản, phiên và lịch sử trò chuyện')
    return True,'Đã xóa tài khoản và dữ liệu trò chuyện liên quan.'


def admin_dat_lai_mat_khau(actor,target,password):
    with ket_noi(ghi=True) as con:
        _yeu_cau_admin(con,actor)
        row=con.execute('SELECT * FROM nguoi_dung WHERE ten_dang_nhap=?',(target,)).fetchone()
        if not row or row['google']:
            return False,'Chỉ đặt lại mật khẩu cho tài khoản đăng nhập bằng mật khẩu.'
        if not 8<=len(password)<=128:
            return False,'Mật khẩu mới cần từ 8 đến 128 ký tự.'
        salt=os.urandom(16).hex()
        con.execute('UPDATE nguoi_dung SET muoi=?,bam=?,so_vong_bam=?,cap_nhat=? WHERE ten_dang_nhap=?',
                    (salt,_bam(password,salt),SO_VONG_BAM,_now(),target))
        con.execute('DELETE FROM phien WHERE ten_dang_nhap=?',(target,))
        _nhat_ky(con,actor,target,'dat_lai_mat_khau')
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
