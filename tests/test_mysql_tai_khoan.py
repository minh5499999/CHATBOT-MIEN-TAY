"""RBAC tren MySQL that, chi chay khi CHAY_KIEM_THU_MYSQL=1; schema rieng duoc chi dinh."""
from concurrent.futures import ThreadPoolExecutor
import os
import unittest
from unittest.mock import patch
import test_database_tai_khoan as legacy
from backend.chatbot import co_so_du_lieu as db
from backend.chatbot import tai_khoan_sqlite as tk


@unittest.skipUnless(os.environ.get('CHAY_KIEM_THU_MYSQL')=='1','MySQL integration chay bang scripts/kiem_thu_mysql.py')
class MySQLTests(legacy.DatabaseTests):
    def setUp(self):
        if os.environ.get('MYSQL_DATABASE')!='bep_mien_tay_kiem_thu':
            raise RuntimeError('Cam chay kiem thu ghi tren schema production.')
        self.backend=patch.object(db,'BACKEND','mysql')
        self.backend.start()
        self.init=patch.object(db,'khoi_tao',return_value=None)
        self.init.start()
        self.clean()

    def clean(self):
        with db.ket_noi(ghi=True) as con:
            for name in ('tin_nhan','cuoc_tro_chuyen','phien','nhat_ky_quan_tri','nguoi_dung','cau_hinh_db'):
                con.execute('DELETE FROM '+name)

    def tearDown(self):
        try:
            self.clean()
        finally:
            self.init.stop()
            self.backend.stop()

    @unittest.skip('Chuyen JSON rieng cua SQLite da duoc kiem thu o DatabaseTests.')
    def test_chuyen_json_giu_hash_phien_lich_su_va_sao_luu(self):
        pass

    @unittest.skip('Rollback chuyen JSON SQLite da duoc kiem thu o DatabaseTests.')
    def test_migration_loi_rollback_khong_mat_json(self):
        pass

    def test_transaction_rollback_mysql(self):
        self.create()
        with self.assertRaises(RuntimeError):
            with db.ket_noi(ghi=True) as con:
                con.execute("UPDATE nguoi_dung SET ten_hien_thi=? WHERE ten_dang_nhap=?",('Không được commit','nguoidung'))
                raise RuntimeError('rollback fixture')
        self.assertEqual(tk.doc_ho_so('nguoidung')['ten_hien_thi'],'Kiểm thử')

    def test_hai_admin_cung_ha_quyen_van_con_mot_admin(self):
        first=self.admin()
        second=self.create('secondadmin')
        self.assertTrue(tk.admin_cap_nhat(first,second,'admin',True)[0])
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(lambda name:tk.admin_cap_nhat(name,name,'user',True),(first,second)))
        self.assertEqual(sum(ok for ok,_ in outcomes),1)
        with db.ket_noi() as con:
            self.assertEqual(con.execute("SELECT count(*) FROM nguoi_dung WHERE vai_tro='admin' AND kich_hoat=1").fetchone()[0],1)

    def test_unicode_literal_percent_va_sql_parameter(self):
        with db.ket_noi() as con:
            value="Đậu hũ 100% ? ' OR 1=1 --"
            row=con.execute("SELECT '100% rau?' AS literal, ? AS value",(value,)).fetchone()
            self.assertEqual(row['literal'],'100% rau?')
            self.assertEqual(row['value'],value)
