r"""Chạy: .venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v

Kiểm thử có cả kho FAISS/model embedding thật; cấm kết nối mạng trong integration.
"""
import socket
import unittest
from unittest.mock import patch

from backend.chatbot.ngon_ngu import (mo_rong_keyword, dieu_kien, vi_pham, du_bang_chung)
from backend.chatbot.phan_hoi import kiem_tra_bam_nguon


class NgonNguTests(unittest.TestCase):
    def test_phan_biet_goi_y_mon_va_hoi_thuc_pham(self):
        from backend.chatbot.y_dinh_an_uong import nhan_dien_cau_hoi_chung
        self.assertEqual(nhan_dien_cau_hoi_chung('tôi bị cảm thì ăn món gì được'), ('cam','an_gi'))
        self.assertEqual(nhan_dien_cau_hoi_chung('tôi bị cảm nên uống gì'), ('cam','uong_gi'))
        for q in ['bị cảm có nên ăn hải sản không', 'bị cảm kiêng ăn gì', 'tôi không bị cảm',
                  'bị cảm kèm đau họng nên ăn gì', 'trẻ nhỏ bị cảm ăn gì', 'cảm thấy kiệt sức ăn gì']:
            self.assertIsNone(nhan_dien_cau_hoi_chung(q))
    def test_dia_phuong_khong_nham_thit_vit(self):
        from backend.chatbot.ngon_ngu import chuan_hoa_dia_phuong
        from backend.chatbot.nhan_dien_mon import dac_trung_mon
        self.assertEqual(chuan_hoa_dia_phuong('thịt kho hột vịt'), 'thịt kho trứng vịt')
        self.assertEqual(dac_trung_mon('thit kho hot vit'), ['trứng vịt'])
        self.assertEqual(chuan_hoa_dia_phuong('hột é'), 'hột é')

    def test_kieng_la_cau_hoi_khong_phai_nguyen_lieu(self):
        for q in ['Ho kiêng ăn gì cho mau hết', 'Làm sao tránh ngộ độc thực phẩm',
                  'Dị ứng thực phẩm là gì', 'Gợi ý món ăn cho người ăn kiêng']:
            dk = dieu_kien(q)
            self.assertFalse(dk['chua_ro'])
            self.assertFalse(dk['loai_tru'])
        self.assertEqual(dieu_kien('không ăn được cay thì nấu gì')['loai_tru'], ['cay'])

    def test_tai_nha_khong_mat_chu_nha(self):
        from backend.chatbot.doi_chieu import ten_mon_tu_cau_hoi
        self.assertEqual(ten_mon_tu_cau_hoi('Cách nấu hủ tiếu Mỹ Tho tại nhà'), 'hu tieu my tho')

    def test_nhan_dien_thit_kho(self):
        from backend.chatbot.nhan_dien_mon import nhan_dien_mon, dung_ten_mon
        mon = nhan_dien_mon('hướng dẫn tôi làm món thịt kho đi')
        self.assertTrue(mon['hoi_chung'])
        self.assertFalse(dung_ten_mon('Cá bông lau kho tộ', mon))
        self.assertFalse(dung_ten_mon('Cá lóc kho thịt ba rọi', mon))
        self.assertTrue(dung_ten_mon('Thịt kho trứng nước dừa', mon))
        self.assertFalse(nhan_dien_mon('cách làm thịt kho trứng')['hoi_chung'])

    def test_phu_dinh_sot(self):
        self.assertEqual(mo_rong_keyword("Tôi không bị sốt, muốn ăn nhiều đạm"),
                         "Tôi không bị sốt, muốn ăn nhiều đạm giàu đạm protein")

    def test_phu_dinh_ho(self):
        self.assertNotIn("thức ăn mềm", mo_rong_keyword("Tôi không bị ho, cần món ít đường"))

    def test_dong_nghia(self):
        self.assertIn("giàu đạm", mo_rong_keyword("món giàu protein"))
        self.assertIn("đậu phụ", mo_rong_keyword("nau dau hu"))
        self.assertIn("dưỡng sức", mo_rong_keyword("nguoi met nen an gi"))

    def test_chuyen_y_sau_phu_dinh(self):
        self.assertIn("giàu đạm", mo_rong_keyword("không bị sốt nhưng muốn ăn nhiều đạm"))

    def test_di_ung_nhieu_thu(self):
        self.assertEqual(dieu_kien("dị ứng tôm và đậu phộng")['loai_tru'], ['tôm', 'đậu phộng'])

    def test_khong_di_ung(self):
        self.assertFalse(dieu_kien("tôi không dị ứng tôm")['loai_tru'])

    def test_phan_biet_nguyen_lieu_muon_an(self):
        dk = dieu_kien("không ăn tôm nhưng muốn nấu cá")
        self.assertEqual(dk['loai_tru'], ['tôm'])

    def test_khong_dau(self):
        self.assertEqual(dieu_kien("toi di ung tom")['loai_tru'], ['tôm'])

    def test_gia_vi_va_bien_tu(self):
        dk = dieu_kien("dị ứng tôm")
        self.assertTrue(vi_pham("Canh rau, gia vị: mắm ruốc", dk))
        self.assertTrue(vi_pham("Tép rang", dk))
        self.assertFalse(vi_pham("Cháo đậu xanh", dk))

    def test_nho_loai_tru(self):
        self.assertIn('tôm', dieu_kien("món đó nấu sao", [{'cau_hoi': 'dị ứng tôm'}])['loai_tru'])
        self.assertIn('giàu đạm', dieu_kien("món đó nấu sao", [{'cau_hoi': 'món giàu đạm'}])['nhu_cau'])

    def test_chay(self):
        dk = dieu_kien("gợi ý món ăn chay")
        self.assertTrue(dk['an_chay'])
        self.assertTrue(vi_pham("Đậu hũ sốt nước mắm", dk))
        self.assertFalse(vi_pham("Đậu hũ hấp nấm", dk))
        self.assertFalse(vi_pham("Bỏ phần vỏ, nấu cho cả nhà", dk))
        self.assertFalse(dieu_kien("không ăn chay")['an_chay'])

    def test_nhu_cau_khong_suy_dien(self):
        dk = dieu_kien("món giàu protein")
        self.assertFalse(du_bang_chung("Thịt gà luộc", dk))
        self.assertTrue(du_bang_chung("Món giàu đạm cho bữa ăn", dk))
        self.assertFalse(du_bang_chung("Món này không giàu đạm", dk))

    def test_dieu_kien_chua_ho_tro(self):
        self.assertTrue(dieu_kien("dị ứng kiwi")['chua_ro'])
        self.assertTrue(dieu_kien("dị ứng tôm và kiwi")['chua_ro'])

    def test_dinh_luong(self):
        self.assertTrue(dieu_kien("món ăn dưới 500 kcal")['can_dinh_luong'])

    def test_sinh_phai_bam_nguon(self):
        source = "Đậu xanh rửa sạch. Nấu khoảng 20 phút."
        self.assertTrue(kiem_tra_bam_nguon("Đậu xanh rửa sạch.", source))
        self.assertFalse(kiem_tra_bam_nguon("Nấu khoảng 40 phút.", source))
        self.assertFalse(kiem_tra_bam_nguon("Món này chữa được tiểu đường.", source))
        self.assertFalse(kiem_tra_bam_nguon("Món này giàu đạm.", "Không đúng khi nói món này giàu đạm."))


class TichHopOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        torch.set_num_threads(4)
        cls.network_guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('Không được gọi mạng'))
        cls.network_guard.start()
        from backend.chatbot.cau_hinh import doc_cau_hinh
        cls.ch = doc_cau_hinh()
        cls.original = dict(cls.ch)
        cls.ch.update(ghi_nhat_ky=False, kho_tim_kiem='faiss', chi_chay_cuc_bo=True)
        from backend.chatbot.sinh_cau_tra_loi import tra_loi
        cls.ask = staticmethod(lambda q, history=None: tra_loi(q, history))

    @classmethod
    def tearDownClass(cls):
        cls.ch.clear()
        cls.ch.update(cls.original)
        cls.network_guard.stop()

    def test_cong_thuc_day_du(self):
        r = self.ask("cách nấu canh chua cá lóc")
        self.assertEqual(r['loai'], 'tra_loi')
        self.assertIn('Nguyên liệu', r['cau_tra_loi'])
        self.assertTrue(r['nguon'][0]['nguon'].startswith('http'))
        self.assertEqual(r['giai_thich']['framework'], 'langchain')

    def test_thit_kho_khong_doi_sang_ca(self):
        from backend.chatbot.nhan_dien_mon import nhan_dien_mon, dung_ten_mon
        for q in ['hướng dẫn tôi làm món thịt kho đi', 'huong dan toi lam mon thit kho di', 'thịt kho']:
            r = self.ask(q)
            self.assertEqual(r['loai'], 'khong_chac')
            self.assertTrue(r['goi_y'])
            self.assertTrue(all(dung_ten_mon(title, nhan_dien_mon(q)) for title in r['goi_y']))
            self.assertNotIn('Cá bông lau', r['cau_tra_loi'])
            self.assertIsNone(r['chu_de'])

    def test_thit_kho_trung_co_the_xem_cong_thuc(self):
        r = self.ask('Thịt kho trứng nước dừa làm sao cho mềm')
        self.assertEqual(r['loai'], 'tra_loi')
        self.assertIn('Thịt kho', r['nguon'][0]['cau_hoi'])
        self.assertIn('Nguyên liệu', r['cau_tra_loi'])

    def test_trung_vit_khong_tra_cong_thuc_thit_vit(self):
        for q in ['thịt kho hột vịt', 'thit kho hot vit']:
            r = self.ask(q)
            self.assertEqual(r['loai'], 'tra_loi')
            self.assertEqual(r['nguon'][0]['id_goc'], 59)
            self.assertIn('Trứng vịt 10 quả', r['cau_tra_loi'])
            self.assertNotIn('Vịt kho nước dừa là', r['cau_tra_loi'])

    def test_ten_mon_ngan_khong_nham_bai_an_kem(self):
        for q, expected in [('mắm chưng miền Tây', 58), ('mắm kho miền Tây', 52)]:
            a = self.ask(q)
            self.assertEqual(a['loai'], 'tra_loi')
            self.assertEqual(a['nguon'][0]['id_goc'], expected)
            self.assertIn('Nguyên liệu', a['cau_tra_loi'])

    def test_faq_nguyen_van_khong_chon_bai_gan_nghia(self):
        cases = [('Hướng dẫn mình nấu lẩu mắm miền Tây', 43),
                 ('Rau đắng miền Tây ăn kèm món gì', 561),
                 ('Bạn ơi, cho mình hỏi: Ho kiêng ăn gì cho mau hết nhé', 776)]
        for q, expected in cases:
            r = self.ask(q)
            self.assertEqual(r['loai'], 'tra_loi')
            self.assertEqual(r['nguon'][0]['id_goc'], expected)

    def test_goi_y_mon_khi_cam_khong_tra_bai_hai_san(self):
        cases = [('tôi bị cảm thì ăn món gì được',771), ('toi bi cam thi an mon gi duoc',771),
                 ('nên ăn gì khi bị cảm',771), ('bị cảm cúm ăn gì',771),
                 ('bị cảm nên ăn gì nhỉ',771), ('tôi bị cảm nên nấu món gì dễ ăn',771),
                 ('tôi đang ho thì ăn gì',775), ('tôi bị sốt nên ăn gì',778),
                 ('tôi bị cảm nên uống gì',774), ('bị cảm có nên ăn hải sản không',823)]
        for q, expected in cases:
            r = self.ask(q)
            self.assertEqual(r['loai'], 'tra_loi', q)
            self.assertEqual(r['nguon'][0]['id_goc'], expected, q)
            if expected == 771:
                self.assertNotIn('tránh tôm cua', r['cau_tra_loi'])
                self.assertIn('cháo', r['cau_tra_loi'].lower())

    def test_ten_mon_ngan_va_hoi_du_cong_thuc(self):
        r = self.ask('Mình muốn nấu ga hap hanh thì cần nguyên liệu và các bước?')
        self.assertEqual(r['loai'], 'tra_loi')
        self.assertEqual(r['nguon'][0]['id_goc'], 244)
        self.assertIn('Nguyên liệu', r['cau_tra_loi'])
        self.assertIn('Cách chế biến', r['cau_tra_loi'])

    def test_chao(self):
        self.assertEqual(self.ask('xin chào')['loai'], 'chao_hoi')

    def test_ngoai_pham_vi(self):
        self.assertNotEqual(self.ask('Lập trình thuật toán sắp xếp bằng Java')['loai'], 'tra_loi')

    def test_noi_tiep(self):
        q = 'cách nấu canh chua cá lóc'
        a = self.ask(q)
        b = self.ask('món đó cần nguyên liệu gì', [{'cau_hoi': q, 'chu_de': a['chu_de']}])
        self.assertEqual(a['chu_de']['id_goc'], b['chu_de']['id_goc'])
        self.assertIn('Nguyên liệu', b['cau_tra_loi'])

    def test_loc_toan_bo_cong_thuc_va_goi_y(self):
        from backend.chatbot.sinh_cau_tra_loi import noi_dung_day_du
        dk = dieu_kien('dị ứng tôm')
        r = self.ask('dị ứng tôm, gợi ý món canh')
        for d in r['doan_truy_hoi']:
            self.assertFalse(vi_pham(d['cau_hoi'] + noi_dung_day_du(r['giai_thich']['kho'], d['id_goc']), dk))
        allowed = {d['cau_hoi'] for d in r['doan_truy_hoi']}
        self.assertTrue(set(r['goi_y']) <= allowed)

    def test_chua_ro_khong_goi_y_bua(self):
        for q in ['dị ứng kiwi nấu gì', 'món ăn 500 kcal']:
            r = self.ask(q)
            self.assertEqual(r['loai'], 'khong_chac')
            self.assertFalse(r['goi_y'])

    def test_langchain_documents(self):
        from backend.chatbot.chuoi_langchain import truy_hoi_langchain
        from langchain_core.documents import Document
        result = truy_hoi_langchain('nau dau hu', che_do='bm25')
        self.assertIsInstance(result['documents'][0], Document)

    def test_faq_khong_can_embedding_va_cache_khong_bi_sua(self):
        from backend.chatbot.chuoi_langchain import truy_hoi_langchain, _ket_qua_truy_hoi
        _ket_qua_truy_hoi.cache_clear()
        with patch('backend.chatbot.mo_hinh_vector.nap_mo_hinh', side_effect=AssertionError('FAQ không cần embedding')):
            a = truy_hoi_langchain('Hướng dẫn mình nấu lẩu mắm miền Tây')
            self.assertEqual(a['doan'][0]['id_goc'], 43)
        a['doan'].clear()
        b = truy_hoi_langchain('Hướng dẫn mình nấu lẩu mắm miền Tây')
        self.assertEqual(b['doan'][0]['id_goc'], 43)


if __name__ == '__main__':
    unittest.main()
