"""SQLite/RBAC thật trong thư mục tạm; không dùng tài khoản hay mật khẩu thật."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from backend.chatbot import co_so_du_lieu as db
from backend.chatbot import tai_khoan_sqlite as tk
from backend.chatbot.cau_hinh import ROOT

PASSWORD='MatKhauKiemThu123!'


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'scratch').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'scratch',prefix='test_sqlite_')
        self.folder=Path(self.temp.name)
        self.patcher=patch.object(db,'FILE_DB',self.folder/'chatbot.sqlite3')
        self.patcher.start()
        self.backend=patch.object(db,'BACKEND','sqlite')
        self.backend.start()

    def tearDown(self):
        self.backend.stop()
        self.patcher.stop()
        self.temp.cleanup()

    def create(self,name='nguoidung'):
        self.assertTrue(tk.dang_ky(name,'Kiểm thử',PASSWORD)[0])
        return name

    def admin(self):
        name=self.create('quantri')
        self.assertTrue(tk.khoi_tao_admin_cuc_bo(name)[0])
        return name

    def test_sua_ho_so_va_quyen_trong_cung_transaction(self):
        actor=self.admin(); target=self.create('suadoi')
        self.assertTrue(tk.admin_cap_nhat(actor,target,'user',True,'Tên mới tiếng Việt')[0])
        self.assertEqual(tk.doc_ho_so(target)['ten_hien_thi'],'Tên mới tiếng Việt')
        with self.assertRaises(ValueError):
            tk.admin_cap_nhat(actor,target,'admin',False,' ')
        self.assertEqual(tk.doc_ho_so(target)['vai_tro'],'user')
        self.assertIsNotNone(tk.dang_nhap(target,PASSWORD))

    def test_xoa_tai_khoan_thu_hoi_phien_va_xoa_lich_su(self):
        actor=self.admin(); target=self.create('canxoa')
        token=tk.tao_phien(target)
        tk.luu_cuoc_tro_chuyen(target,None,[{'vai':'user','noi_dung':'Dữ liệu fixture'}])
        self.assertTrue(tk.admin_xoa_tai_khoan(actor,target)[0])
        self.assertIsNone(tk.doc_ho_so(target))
        self.assertIsNone(tk.nguoi_dung_theo_phien(token))
        with db.ket_noi() as con:
            for table in ('tin_nhan','cuoc_tro_chuyen','phien'):
                self.assertEqual(con.execute('SELECT count(*) FROM '+table+' WHERE ten_dang_nhap=?',(target,)).fetchone()[0],0)
        self.assertEqual(tk.nhat_ky_quan_tri(actor)[0]['hanh_dong'],'xoa_tai_khoan')

    def test_xoa_chan_user_admin_cuoi_va_tu_xoa(self):
        actor=self.admin(); user=self.create('userxoa')
        with self.assertRaises(PermissionError): tk.admin_xoa_tai_khoan(user,actor)
        self.assertFalse(tk.admin_xoa_tai_khoan(actor,actor)[0])
        self.assertTrue(tk.admin_tao_tai_khoan(actor,'adminhai','Admin hai',PASSWORD,'admin')[0])
        self.assertFalse(tk.admin_xoa_tai_khoan(actor,actor)[0])
        self.assertTrue(tk.admin_xoa_tai_khoan(actor,'adminhai')[0])

    def test_dang_ky_mac_dinh_user_hash_va_muoi_rieng(self):
        self.create('alpha')
        self.create('beta')
        self.assertEqual(tk.dang_nhap('ALPHA',PASSWORD)['vai_tro'],'user')
        self.assertIsNone(tk.dang_nhap('alpha','sai mat khau'))
        with db.ket_noi() as con:
            rows=con.execute('SELECT bam,muoi,so_vong_bam FROM nguoi_dung').fetchall()
        self.assertNotEqual(rows[0]['muoi'],rows[1]['muoi'])
        self.assertTrue(all(r['bam']!=PASSWORD and r['so_vong_bam']==600000 for r in rows))
        self.assertFalse(tk.dang_ky('alpha','Trùng',PASSWORD)[0])
        self.assertNotIn('bam',tk.doc_ho_so('alpha'))

    def test_validate_va_sql_injection(self):
        self.create()
        self.assertFalse(tk.dang_ky("x' OR 1=1 --",'x',PASSWORD)[0])
        self.assertFalse(tk.dang_ky('adminx','x','123')[0])
        self.assertIsNone(tk.dang_nhap("' OR 1=1 --",PASSWORD))

    def test_user_khong_duoc_goi_quan_tri(self):
        user=self.create()
        for action in (lambda:tk.danh_sach_nguoi_dung(user),lambda:tk.nhat_ky_quan_tri(user),
                       lambda:tk.admin_cap_nhat(user,user,'admin',True),
                       lambda:tk.admin_tao_tai_khoan(user,'xuser','X',PASSWORD,'admin'),
                       lambda:tk.admin_dat_lai_mat_khau(user,user,PASSWORD)):
            with self.assertRaises(PermissionError):
                action()

    def test_admin_cuoi_khong_duoc_tu_khoa_ha_quyen(self):
        admin=self.admin()
        self.assertFalse(tk.admin_cap_nhat(admin,admin,'user',True)[0])
        self.assertFalse(tk.admin_cap_nhat(admin,admin,'admin',False)[0])
        self.assertTrue(tk.la_admin(admin))

    def test_admin_them_khoa_mo_va_thu_hoi_phien(self):
        admin=self.admin()
        self.assertTrue(tk.admin_tao_tai_khoan(admin,'userx','User X',PASSWORD)[0])
        token=tk.tao_phien('userx')
        self.assertIsNotNone(tk.nguoi_dung_theo_phien(token))
        self.assertTrue(tk.admin_cap_nhat(admin,'userx','user',False)[0])
        self.assertIsNone(tk.dang_nhap('userx',PASSWORD))
        self.assertIsNone(tk.nguoi_dung_theo_phien(token))
        with self.assertRaises(PermissionError):
            tk.tao_phien('userx')
        self.assertTrue(tk.admin_cap_nhat(admin,'userx','user',True)[0])
        self.assertIsNotNone(tk.dang_nhap('userx',PASSWORD))

    def test_quyen_lay_lai_tu_db_khong_tin_phien_cu(self):
        admin=self.admin()
        other=self.create('otheradmin')
        token=tk.tao_phien(admin)
        self.assertTrue(tk.admin_cap_nhat(admin,other,'admin',True)[0])
        self.assertTrue(tk.admin_cap_nhat(other,admin,'user',True)[0])
        self.assertFalse(tk.la_admin(admin))
        self.assertIsNone(tk.nguoi_dung_theo_phien(token))
        with self.assertRaises(PermissionError):
            tk.danh_sach_nguoi_dung(admin)

    def test_khoi_tao_admin_khong_the_cap_them_bang_bootstrap(self):
        admin=self.admin()
        self.create('khach')
        self.assertTrue(tk.khoi_tao_admin_cuc_bo(admin)[0])
        self.assertFalse(tk.khoi_tao_admin_cuc_bo('khach')[0])
        self.assertEqual(tk.doc_ho_so('khach')['vai_tro'],'user')

    def test_phien_chi_luu_hash_het_han_va_dang_xuat(self):
        self.create()
        token=tk.tao_phien('nguoidung')
        with db.ket_noi(ghi=True) as con:
            row=con.execute('SELECT bam_ma FROM phien').fetchone()
            self.assertEqual(row['bam_ma'],hashlib.sha256(token.encode()).hexdigest())
            self.assertNotEqual(row['bam_ma'],token)
            con.execute("UPDATE phien SET het_han='2000-01-01T00:00:00'")
        self.assertIsNone(tk.nguoi_dung_theo_phien(token))
        token=tk.tao_phien('nguoidung')
        tk.xoa_phien(token)
        self.assertIsNone(tk.nguoi_dung_theo_phien(token))

    def test_dat_lai_mat_khau_khong_lo_bam_va_audit(self):
        admin=self.admin()
        self.create()
        token=tk.tao_phien('nguoidung')
        new=PASSWORD+'moi'
        self.assertTrue(tk.admin_dat_lai_mat_khau(admin,'nguoidung',new)[0])
        self.assertIsNone(tk.dang_nhap('nguoidung',PASSWORD))
        self.assertIsNotNone(tk.dang_nhap('nguoidung',new))
        self.assertIsNone(tk.nguoi_dung_theo_phien(token))
        text=json.dumps(tk.danh_sach_nguoi_dung(admin)+tk.nhat_ky_quan_tri(admin))
        self.assertNotIn(new,text)
        self.assertNotIn('"bam"',text)
        self.assertNotIn('"muoi"',text)

    def test_google_khong_trung_email_khong_dang_nhap_bang_password(self):
        a=tk.dang_nhap_google('a+b@example.com')
        b=tk.dang_nhap_google('a_b@example.com')
        self.assertNotEqual(a['ten_dang_nhap'],b['ten_dang_nhap'])
        self.assertIsNone(tk.dang_nhap(a['ten_dang_nhap'],PASSWORD))
        self.assertEqual(tk.dang_nhap_google('a+b@example.com')['ten_dang_nhap'],a['ten_dang_nhap'])

    def test_lich_su_cach_ly_va_xoa_cascade(self):
        self.create('alpha')
        self.create('beta')
        messages=[{'vai':'user','noi_dung':'Câu riêng alpha'},
                  {'vai':'assistant','cau_hoi':'Câu riêng alpha','ket_qua':{'trang_thai':{'di_ung':['tôm']}}}]
        chat=tk.luu_cuoc_tro_chuyen('alpha',None,messages)
        other=tk.luu_cuoc_tro_chuyen('beta',chat,[{'vai':'user','noi_dung':'Câu beta'}])
        self.assertNotEqual(chat,other)
        tk.xoa_cuoc_tro_chuyen('beta',chat)
        self.assertEqual(tk.danh_sach_cuoc_tro_chuyen('alpha')[0]['tin_nhan'],messages)
        self.assertEqual(len(tk.danh_sach_cuoc_tro_chuyen('beta')),1)
        tk.xoa_cuoc_tro_chuyen('alpha',chat)
        with db.ket_noi() as con:
            self.assertEqual(con.execute("SELECT count(*) FROM tin_nhan WHERE ten_dang_nhap='alpha'").fetchone()[0],0)

    def test_dang_ky_trung_dong_thoi_chi_mot_thanh_cong(self):
        db.khoi_tao()
        with ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(lambda _:tk.dang_ky('trungten','User',PASSWORD),range(3)))
        self.assertEqual(sum(ok for ok,_ in results),1)

    def legacy(self):
        salt='ab'*16
        hashed=hashlib.pbkdf2_hmac('sha256',PASSWORD.encode(),bytes.fromhex(salt),200000).hex()
        users={'cu':{'ten_hien_thi':'Tài khoản cũ','muoi':salt,'bam':hashed,'ngay_tao':'2025-01-01T00:00:00'}}
        self.folder.joinpath('nguoi_dung.json').write_text(json.dumps(users),encoding='utf-8')
        token='phien_cu_gia_lap'
        sessions={hashlib.sha256(token.encode()).hexdigest():{'ten_dang_nhap':'cu','het_han':'2099-01-01T00:00:00'}}
        self.folder.joinpath('phien.json').write_text(json.dumps(sessions),encoding='utf-8')
        history=[{'ma':'macu','tieu_de':'Tiêu đề cũ','tao_luc':'2025-01-01T00:00:00','cap_nhat':'2025-01-02T00:00:00',
                  'tin_nhan':[{'vai':'user','noi_dung':'Câu cũ'},{'vai':'assistant','ket_qua':{'trang_thai':{'khau_phan':3}}}]}]
        (self.folder/'lich_su').mkdir()
        (self.folder/'lich_su/cu.json').write_text(json.dumps(history),encoding='utf-8')
        return users,token,history

    def test_chuyen_json_giu_hash_phien_lich_su_va_sao_luu(self):
        users,token,history=self.legacy()
        before=(self.folder/'nguoi_dung.json').read_bytes()
        db.khoi_tao()
        self.assertEqual(tk.dang_nhap('cu',PASSWORD)['vai_tro'],'user')
        self.assertIsNotNone(tk.nguoi_dung_theo_phien(token))
        self.assertEqual(tk.danh_sach_cuoc_tro_chuyen('cu'),history)
        with db.ket_noi() as con:
            self.assertEqual(con.execute('SELECT bam FROM nguoi_dung').fetchone()[0],users['cu']['bam'])
            self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertFalse(con.execute('PRAGMA foreign_key_check').fetchall())
        self.assertEqual((self.folder/'nguoi_dung.json').read_bytes(),before)
        backups=list((self.folder/'sao_luu_json').glob('*/nguoi_dung.json'))
        self.assertEqual(len(backups),1)
        db._SAN_SANG.discard((self.folder/'chatbot.sqlite3').resolve())
        db.khoi_tao()
        self.assertEqual(len(tk.danh_sach_cuoc_tro_chuyen('cu')),1)
        self.assertEqual(len(list((self.folder/'sao_luu_json').glob('*/nguoi_dung.json'))),1)

    def test_migration_loi_rollback_khong_mat_json(self):
        self.legacy()
        (self.folder/'lich_su/cu.json').write_text('[{"ma":"thieu_truong"}]',encoding='utf-8')
        with self.assertRaises(KeyError):
            db.khoi_tao()
        con=sqlite3.connect(self.folder/'chatbot.sqlite3')
        self.assertEqual(con.execute('SELECT count(*) FROM nguoi_dung').fetchone()[0],0)
        self.assertEqual(con.execute("SELECT count(*) FROM cau_hinh_db WHERE khoa='chuyen_json_v1'").fetchone()[0],0)
        con.close()
        self.assertTrue((self.folder/'nguoi_dung.json').exists())


if __name__=='__main__':
    unittest.main()
