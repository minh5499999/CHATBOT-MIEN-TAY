"""Smoke test Streamlit AppTest; tài khoản/lưu lịch sử giả lập trong bộ nhớ, không ghi hồ sơ thật."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import torch
    torch.set_num_threads(4)
    from streamlit.testing.v1 import AppTest
    from backend.chatbot.cau_hinh import doc_cau_hinh
    doc_cau_hinh().update(kho_tim_kiem='faiss',ghi_nhat_ky=False)
    native_connect=socket.socket.connect
    def local_connect(sock,address):
        if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','localhost','::1'):
            raise AssertionError('Không gọi mạng bên ngoài')
        return native_connect(sock,address)
    with patch.object(socket.socket,'connect',new=local_connect), \
         patch('backend.chatbot.tai_khoan.doc_ho_so',return_value={'ten_dang_nhap':'fixture_khong_ton_tai','ten_hien_thi':'Kiểm thử','vai_tro':'user'}), \
         patch('backend.chatbot.tai_khoan.la_admin',return_value=False), \
         patch('backend.chatbot.tai_khoan.danh_sach_cuoc_tro_chuyen',return_value=[]), \
         patch('backend.chatbot.tai_khoan.luu_cuoc_tro_chuyen',return_value='kiem_thu_trong_bo_nho') as save:
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60).run()
        assert len(at.exception)==0, str(at.exception)
        login_rendered=len(at.text_input)>0
        assert login_rendered
        at.session_state['nguoi_dung']={'ten_dang_nhap':'fixture_khong_ton_tai','ten_hien_thi':'Kiểm thử'}
        at.query_params['giai_thich']='1'
        at.run()
        assert len(at.exception)==0, str(at.exception)
        at.chat_input[0].set_value('Gợi ý món ăn từ cá lóc').run()
        assert len(at.exception)==0, str(at.exception)
        first=at.session_state['tin_nhan'][-1]['ket_qua']
        selected=first['trang_thai']['de_xuat'][1]['id_goc']
        assert any(b.label.startswith('2. ') for b in at.button)
        at.chat_input[0].set_value('Món thứ hai nấu sao?').run()
        assert len(at.exception)==0, str(at.exception)
        second=at.session_state['tin_nhan'][-1]['ket_qua']
        assert second['nguon'][0]['id_goc']==selected
        saved_messages=save.call_args.args[2]
        assert saved_messages[-1]['ket_qua']['trang_thai']['mon_hien_tai']['id_goc']==selected
        for question in ('bị tiểu đường thì nấu được món gì', 'mình bị tiểu đường thì nấu ăn món nào được'):
            at.chat_input[0].set_value(question).run()
            assert len(at.exception)==0, str(at.exception)
            result=at.session_state['tin_nhan'][-1]['ket_qua']
            assert not result['goi_y'] and not result['nguon']
            assert 'tiểu đường' in result['cau_tra_loi']
            assert not any(str(b.key).startswith('lq_') for b in at.button)
        output={'dang_nhap_hien_thi':login_rendered,'chat_sau_dang_nhap_gia_lap':True,
                'cau_hoi_tieu_duong_khong_goi_y_lac_chu_de':True,
                'goi_y_co_so_thu_tu':True,'chon_dung_mon_thu_hai':True,
                'luu_trang_thai_trong_lich_su':True,'debug_khong_loi':True,
                'ghi_tai_khoan_that':False,'kiem_thu_oauth_that':False}
    (ROOT/'reports/giao_dien_v2.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
