"""AppTest với SQLite thật tạm thời; không thay đổi tài khoản trên máy người dùng."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def pick(elements,label):
    return next(e for e in elements if e.label==label)


@contextmanager
def database_fixture(backend):
    from backend.chatbot import co_so_du_lieu as db
    if backend=='sqlite':
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch',prefix='ui_admin_') as folder, \
             patch.object(db,'FILE_DB',Path(folder)/'chatbot.sqlite3'), patch.object(db,'BACKEND','sqlite'):
            yield
    else:
        from dotenv import dotenv_values
        config=dict(dotenv_values(ROOT/'du_lieu_nguoi_dung/mysql_ket_noi.env'))
        config['MYSQL_DATABASE']='bep_mien_tay_kiem_thu'
        def clear():
            if os.environ.get('MYSQL_DATABASE')!='bep_mien_tay_kiem_thu':
                raise RuntimeError('Cam kiem thu ghi vao production.')
            with db.ket_noi(ghi=True) as con:
                for table in ('tin_nhan','cuoc_tro_chuyen','phien','nhat_ky_quan_tri','nguoi_dung','cau_hinh_db'):
                    con.execute('DELETE FROM '+table)
        with patch.dict(os.environ,config),patch.object(db,'BACKEND','mysql'):
            clear()
            try:
                yield
            finally:
                clear()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend',choices=['sqlite','mysql'],default='sqlite')
    args=parser.parse_args()
    import torch
    torch.set_num_threads(4)
    from streamlit.testing.v1 import AppTest
    from backend.chatbot import co_so_du_lieu as db, tai_khoan as tk
    from backend.chatbot.tai_khoan_sqlite import khoi_tao_admin_cuc_bo
    from backend.chatbot.cau_hinh import doc_cau_hinh
    from frontend.bang_quan_tri import trang_thai_neo4j
    doc_cau_hinh().update(kho_tim_kiem='faiss',ghi_nhat_ky=False)
    native_connect=socket.socket.connect
    def local_only(sock,address):
        if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','localhost','::1'):
            raise AssertionError('Không gọi mạng bên ngoài')
        return native_connect(sock,address)
    password='MatKhauFixture123!'
    with database_fixture(args.backend), \
         patch('frontend.bang_quan_tri.trang_thai_neo4j', return_value=False), \
         patch.object(socket.socket,'connect',new=local_only):
        assert tk.dang_ky('admin_test','Admin Test',password)[0]
        assert tk.dang_ky('normal_user','User Test',password)[0]
        assert khoi_tao_admin_cuc_bo('admin_test')[0]
        tk.luu_cuoc_tro_chuyen('normal_user',None,[{'vai':'user','noi_dung':'Lịch sử riêng của user fixture'}])
        admin=AppTest.from_file(str(ROOT/'app.py'),default_timeout=90)
        admin.session_state['trang_hien_tai']='Quản trị'
        admin.run()
        admin.text_input[0].set_value('admin_test')
        admin.text_input[1].set_value(password)
        pick(admin.button,'Đăng nhập').click().run()
        assert not admin.exception, str(admin.exception)
        assert admin.session_state['nguoi_dung']['vai_tro']=='admin'
        assert any('Tổng quan hệ thống' in str(m.value) for m in admin.markdown)
        assert admin.session_state['admin_muc']=='Tổng quan'
        next(b for b in admin.button if b.key=='edit_overview_normal_user').click().run()
        pick(admin.text_input,'Tên hiển thị').set_value('User đã sửa')
        pick(admin.button,'Lưu thay đổi').click().run()
        assert not admin.exception, str(admin.exception)
        assert tk.doc_ho_so('normal_user')['ten_hien_thi']=='User đã sửa'
        pick(admin.button,'Tài khoản').click().run()
        assert any(t.value=='Quản trị tài khoản' for t in admin.title)
        assert not any('Lịch sử riêng của user fixture' in str(m.value) for m in admin.markdown)
        pick(admin.text_input,'Tên đăng nhập mới').set_value('created_by_admin')
        pick(admin.text_input,'Tên hiển thị mới').set_value('Được admin tạo')
        pick(admin.text_input,'Mật khẩu ban đầu').set_value(password)
        pick(admin.text_input,'Nhập lại mật khẩu ban đầu').set_value(password)
        pick(admin.button,'Tạo tài khoản mới').click().run()
        assert not admin.exception, str(admin.exception)
        assert tk.doc_ho_so('created_by_admin')['vai_tro']=='user'
        next(b for b in admin.button if b.key=='delete_accounts_created_by_admin').click().run()
        pick(admin.text_input,'Nhập đúng tên đăng nhập để xác nhận').set_value('sai_ten')
        pick(admin.button,'Xác nhận xóa vĩnh viễn').click().run()
        assert tk.doc_ho_so('created_by_admin') is not None
        pick(admin.text_input,'Nhập đúng tên đăng nhập để xác nhận').set_value('created_by_admin')
        pick(admin.button,'Xác nhận xóa vĩnh viễn').click().run()
        assert not admin.exception, str(admin.exception)
        assert tk.doc_ho_so('created_by_admin') is None
        user=AppTest.from_file(str(ROOT/'app.py'),default_timeout=90).run()
        user.text_input[0].set_value('normal_user')
        user.text_input[1].set_value(password)
        pick(user.button,'Đăng nhập').click().run()
        assert not user.exception, str(user.exception)
        assert user.session_state['nguoi_dung']['vai_tro']=='user'
        assert not any(t.value=='Quản trị tài khoản' for t in user.title)
        assert not any(r.label=='Chức năng' for r in user.radio)
        user.session_state['trang_hien_tai']='Quản trị'
        user.run()
        assert not any(t.value=='Quản trị tài khoản' for t in user.title)
        token=user.session_state['ma_phien']
        pick(admin.selectbox,'Tài khoản cần cập nhật').select('normal_user').run()
        pick(admin.checkbox,'Cho phép đăng nhập').set_value(False)
        pick(admin.button,'Lưu quyền và trạng thái').click().run()
        assert not admin.exception, str(admin.exception)
        assert tk.nguoi_dung_theo_phien(token) is None
        user.run()
        assert not user.exception, str(user.exception)
        assert user.session_state['nguoi_dung'] is None
        assert len(user.chat_input)==0
        pick(admin.selectbox,'Tài khoản cần cập nhật').select('admin_test').run()
        pick(admin.selectbox,'Vai trò').select('user')
        pick(admin.button,'Lưu quyền và trạng thái').click().run()
        assert tk.la_admin('admin_test')
        assert any('admin cuối cùng' in e.value for e in admin.error)
        output={'backend':args.backend,'khong_ghi_tai_khoan_that':True,'dang_nhap_admin':True,
                'trang_quan_tri_hien_dung_quyen':True,'admin_tao_user':True,
                'user_khong_mo_duoc_quan_tri':True,'khoa_user_thu_hoi_phien_dang_mo':True,
                'chan_ha_quyen_admin_cuoi':True,'khong_hien_noi_dung_lich_su_user_cho_admin':True}
    filename='kiem_thu_admin_user_mysql.json' if args.backend=='mysql' else 'kiem_thu_admin_user.json'
    (ROOT/'reports'/filename).write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
