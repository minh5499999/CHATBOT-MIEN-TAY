"""Không đề xuất bài/món không liên quan khi thiếu tri thức cho bệnh lý."""
import unittest
import test_chatbot as baseline
from backend.chatbot.suc_khoe import nhan_dien, cap_nhat, dung_chu_de
from backend.chatbot.intent import phan_tich


class ThucTheSucKhoeTests(unittest.TestCase):
    def test_cac_cach_hoi_khong_dong_nhat_voi_it_duong(self):
        for q in ('bị tiểu đường thì nấu được món gì', 'minh bi dai thao duong thi nau mon nao'):
            p=phan_tich(q)
            self.assertEqual(p['tinh_trang_suc_khoe'],['tiểu đường'])
            self.assertIn('goi_y_mon',p['intents'])
            self.assertNotIn('ít đường',p['dieu_kien']['nhu_cau'])

    def test_phu_dinh_va_dinh_chinh(self):
        self.assertFalse(nhan_dien('Tôi không bị tiểu đường, muốn nấu canh chua'))
        self.assertFalse(cap_nhat(['tiểu đường'],'Tôi không bị đái tháo đường'))
        self.assertEqual(cap_nhat(['tiểu đường'],'vậy nấu món gì'),['tiểu đường'])

    def test_bang_chung_khong_chi_la_it_duong_hoac_an_chay(self):
        self.assertFalse(dung_chu_de('Món ít đường, ăn chay giàu đạm',['tiểu đường']))
        self.assertFalse(dung_chu_de('Không dành cho người tiểu đường',['tiểu đường']))
        self.assertTrue(dung_chu_de('Thông tin dành cho người đái tháo đường',['tiểu đường']))
        self.assertFalse(dung_chu_de('Người tiểu đường',['tiểu đường','bệnh thận']))


class SucKhoeOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        baseline.TichHopOfflineTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        baseline.TichHopOfflineTests.tearDownClass.__func__(cls)

    def test_hai_cau_trong_anh_va_dien_dat_lai(self):
        for q in ('bị tiểu đường thì nấu được món gì',
                  'mình bị tiểu đường thì nấu ăn món nào được',
                  'bi tieu duong thi nau duoc mon gi',
                  'Gợi ý món ăn cho người đái tháo đường',
                  'Tôi bị tiểu đường, có cá lóc thì nấu món nào?'):
            with self.subTest(q=q):
                r=self.ask(q)
                self.assertEqual(r['loai'],'khong_chac')
                self.assertFalse(r['nguon'])
                self.assertFalse(r['goi_y'])
                self.assertIn('tiểu đường',r['cau_tra_loi'])
                self.assertIn('chưa có tài liệu chuyên biệt',r['cau_tra_loi'])

    def test_giu_qua_luot_sau_va_khong_sua_lich_su(self):
        first=self.ask('mình bị tiểu đường thì nấu món nào')
        h=[{'cau_hoi':'mình bị tiểu đường thì nấu món nào','chu_de':first['chu_de'],
            'cau_tra_loi':first['cau_tra_loi'],'trang_thai':first['trang_thai']}]
        r=self.ask('vậy gợi ý món từ cá lóc',h)
        self.assertFalse(r['nguon'])
        self.assertFalse(r['goi_y'])
        self.assertEqual(r['trang_thai']['tinh_trang_suc_khoe'],['tiểu đường'])
        self.assertEqual(self.ask('cảm ơn',h)['loai'],'chao_hoi')

    def test_lich_su_cu_chua_co_truong_suc_khoe(self):
        from backend.chatbot.trang_thai import lay_trang_thai
        h=[{'cau_hoi':'Tôi bị đái tháo đường, nấu gì được?', 'chu_de':None,
            'cau_tra_loi':'phản hồi cũ', 'trang_thai':lay_trang_thai([])}]
        r=self.ask('Gợi ý món ăn từ cá lóc',h)
        self.assertFalse(r['goi_y'])
        self.assertIn('tiểu đường',r['trang_thai']['tinh_trang_suc_khoe'])

    def test_phu_dinh_khong_chan_mon_thong_thuong(self):
        r=self.ask('Tôi không bị tiểu đường, cách nấu canh chua cá lóc')
        self.assertFalse(r['trang_thai']['tinh_trang_suc_khoe'])
        self.assertNotIn('chưa có tài liệu chuyên biệt',r['cau_tra_loi'])
