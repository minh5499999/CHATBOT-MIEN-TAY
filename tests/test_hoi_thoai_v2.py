"""Regression qua FAISS/embedding thật, chặn mạng; đây là bộ phát triển, không phải Test kín."""
import ast
import copy
import json
from pathlib import Path
import unittest
try:
    import test_chatbot as baseline
except ImportError:
    from tests import test_chatbot as baseline
from backend.chatbot.intent import phan_tich
from backend.chatbot.trang_thai import lay_trang_thai, cap_nhat, chon_theo_so
from backend.chatbot.che_do_du_lieu import chon_kho


def history(q, r):
    return {'cau_hoi':q, 'cau_tra_loi':r['cau_tra_loi'], 'chu_de':r['chu_de'], 'trang_thai':r['trang_thai']}


class CauTrucTests(unittest.TestCase):
    def test_nhieu_intent(self):
        p = phan_tich('Cho tôi nguyên liệu và cách nấu canh chua cá lóc')
        self.assertTrue({'nguyen_lieu','che_bien','cong_thuc'} <= set(p['intents']))

    def test_ingredient_dedup_and_egg(self):
        p = phan_tich('Tôi có trứng vịt, gợi ý món ăn', ['trứng vịt','trung vit','vịt'])
        self.assertEqual(p['nguyen_lieu_co'], ['trung vit'])

    def test_time_and_portions(self):
        p=phan_tich('Gợi ý món nấu cho 3 người trong 1 giờ')
        self.assertEqual((p['khau_phan'],p['thoi_gian_toi_da']),(3,60))

    def test_di_ung_khong_bi_xoa_nhu_so_thich(self):
        s=cap_nhat(lay_trang_thai([]),phan_tich('Tôi dị ứng tôm và đậu phộng'))
        self.assertEqual(s['di_ung'],['tôm','đậu phộng'])
        later=cap_nhat(s,phan_tich('Bỏ hết điều kiện'))
        self.assertEqual(later['dieu_kien']['loai_tru'],['tôm','đậu phộng'])
        self.assertIn('tôm',cap_nhat(s,phan_tich('ăn lại tôm'))['dieu_kien']['loai_tru'])
        self.assertNotIn('tôm',cap_nhat(s,phan_tich('Tôi không dị ứng tôm'))['di_ung'])

    def test_cho_phep_lai_so_thich(self):
        s=cap_nhat(lay_trang_thai([]),phan_tich('Không dùng ớt nha'))
        self.assertEqual(s['dieu_kien']['loai_tru'],['ớt'])
        self.assertFalse(cap_nhat(s,phan_tich('Dùng lại ớt'))['dieu_kien']['loai_tru'])

    def test_di_ung_chua_ro_khong_bi_quen(self):
        s=cap_nhat(lay_trang_thai([]),phan_tich('Tôi dị ứng nấm'))
        later=cap_nhat(s,phan_tich('Món đó nấu sao'))
        self.assertIn('nam',later['di_ung_chua_ro'])
        self.assertIn('nam',later['dieu_kien']['chua_ro'])
        corrected=cap_nhat(later,phan_tich('Tôi không còn dị ứng nấm'))
        self.assertFalse(corrected['dieu_kien']['chua_ro'])

    def test_state_copy_and_no_cross_session(self):
        original=lay_trang_thai([])
        s=cap_nhat(original,phan_tich('Tôi dị ứng tôm'))
        s['nguyen_lieu_co'].append('test')
        self.assertFalse(original['dieu_kien']['loai_tru'])
        self.assertFalse(lay_trang_thai([])['nguyen_lieu_co'])

    def test_calories_remain_until_cleared(self):
        s=cap_nhat(lay_trang_thai([]),phan_tich('Gợi ý món dưới 400 kcal'))
        self.assertTrue(cap_nhat(s,phan_tich('món đó nấu sao'))['dieu_kien']['can_dinh_luong'])
        self.assertFalse(cap_nhat(s,phan_tich('bỏ yêu cầu dinh dưỡng'))['dieu_kien']['can_dinh_luong'])

    def test_evaluation_rejects_production(self):
        with self.assertRaises(ValueError):
            chon_kho({'che_do_du_lieu':'evaluation','kho':'kho_vector/cau_truc_tat_ca'})
        self.assertEqual(chon_kho({'che_do_du_lieu':'evaluation'})[0],'kho_vector/cau_truc_Train')

    def test_ordinal_without_list(self):
        self.assertIsNotNone(chon_theo_so('Món thứ hai nấu sao',lay_trang_thai([]))[1])

    def test_no_generative_runtime(self):
        root=Path(__file__).resolve().parents[1]
        self.assertFalse((root/'chatbot/mo_hinh_sinh.py').exists())
        for folder in ('chatbot','scripts'):
            for path in (root/folder).glob('*.py'):
                tree=ast.parse(path.read_text(encoding='utf-8-sig'))
                for node in ast.walk(tree):
                    if isinstance(node,(ast.Import,ast.ImportFrom)):
                        imports=[a.name for a in node.names]+([node.module or ''] if isinstance(node,ast.ImportFrom) else [])
                        self.assertFalse(any('mo_hinh_sinh' in x or x in ('openai','ollama','anthropic') for x in imports),path)
                self.assertNotIn('AutoModelForCausalLM',path.read_text(encoding='utf-8-sig'),path)


class HoiThoaiOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        baseline.TichHopOfflineTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        baseline.TichHopOfflineTests.tearDownClass.__func__(cls)

    def test_nam_cach_dien_dat_trung_vit(self):
        for q in ['Chỉ tui nấu thịt kho hột vịt.', 'Chi tui nau thit kho hot vit.',
                  'Cách làm thịt kho trứng vịt?', 'Nấu thịt kho hột vịt sao cho ngon?',
                  'Mình muốn làm thịt kho có trứng vịt.']:
            with self.subTest(q=q):
                r=self.ask(q)
                self.assertEqual(r['loai'],'tra_loi')
                self.assertEqual([n['id_goc'] for n in r['nguon']],[59])
                self.assertIn('Trứng vịt 10 quả',r['cau_tra_loi'])

    def test_hai_phan_duoc_tra_du(self):
        r=self.ask('Cho tôi nguyên liệu và cách nấu canh chua cá lóc')
        self.assertEqual(r['nguon'][0]['id_goc'],41)
        self.assertIn('Nguyên liệu',r['cau_tra_loi'])
        self.assertIn('Sơ chế',r['cau_tra_loi'])
        self.assertIn('Cách chế biến',r['cau_tra_loi'])

    def test_fuzzy_cho_xac_nhan(self):
        r=self.ask('canh chua ca locc')
        self.assertEqual(r['loai'],'khong_chac')
        self.assertFalse(r['nguon'])
        self.assertTrue(r['goi_y'])

    def test_goi_y_va_chon_dung_thu_tu(self):
        q='Gợi ý món ăn từ cá lóc'
        first=self.ask(q)
        self.assertGreaterEqual(len(first['trang_thai']['de_xuat']),2)
        expected=first['trang_thai']['de_xuat'][1]['id_goc']
        r=self.ask('Món thứ hai nấu sao?',[history(q,first)])
        self.assertEqual(r['loai'],'tra_loi')
        self.assertEqual(r['nguon'][0]['id_goc'],expected)
        json.dumps(r['trang_thai'])

    def test_dieu_kien_moi_khong_doi_mon(self):
        q='Gợi ý món ăn từ cá lóc'
        first=self.ask(q)
        h=[history(q,first)]
        r=self.ask('Món thứ hai nấu sao?',h)
        selected=r['nguon'][0]['id_goc']
        h.append(history('Món thứ hai nấu sao?',r))
        r=self.ask('Không dùng ớt nha.',h)
        self.assertEqual(r['trang_thai']['mon_hien_tai']['id_goc'],selected)
        self.assertIn('ớt',r['trang_thai']['dieu_kien']['loai_tru'])
        self.assertFalse(r['nguon'])  # nguồn này có ớt, không tự bỏ nguyên liệu
        h.append(history('Không dùng ớt nha.',r))
        r=self.ask('Nấu cho 3 người thì sao?',h)
        self.assertEqual(r['trang_thai']['khau_phan'],3)
        self.assertEqual(r['trang_thai']['mon_hien_tai']['id_goc'],selected)

    def test_loc_thoi_gian_va_chien(self):
        from backend.chatbot.cong_thuc import danh_muc
        from backend.chatbot.ngon_ngu import chuan_hoa
        r=self.ask('Gợi ý món không chiên trong 30 phút')
        recipes={x.id_goc:x for x in danh_muc(r['giai_thich']['kho'])}
        self.assertTrue(r['nguon'])
        for source in r['nguon']:
            recipe=recipes[source['id_goc']]
            self.assertLessEqual(recipe.tong_phut,30)
            self.assertNotIn('chien',chuan_hoa(recipe.noi_dung))

    def test_kcal_khong_tu_tinh(self):
        r=self.ask('Gợi ý món dưới 400 kcal')
        self.assertFalse(r['nguon'])
        self.assertIn('chưa có bảng dưỡng chất',r['cau_tra_loi'])

    def test_bao_quan_noi_tiep_khong_tra_lai_cong_thuc(self):
        q='cách nấu canh chua cá lóc'
        first=self.ask(q)
        for followup in ('Món đó bảo quản thế nào?', 'Món đó thay thế nguyên liệu ra sao?'):
            r=self.ask(followup,[history(q,first)])
            self.assertNotEqual(r['loai'],'tra_loi')
            self.assertFalse(r['nguon'])
            self.assertEqual(r['trang_thai']['mon_hien_tai']['id_goc'],41)

    def test_chi_co_khong_dau_ngam_them_nguyen_lieu(self):
        r=self.ask('Tôi chỉ có cá lóc, gợi ý món ăn')
        self.assertFalse(r['nguon'])

    def test_quy_doi_bao_toan_khoang(self):
        from backend.chatbot.cong_thuc import CongThuc, quy_doi_khau_phan
        recipe=CongThuc(0,'fixture','',('- Cá 400g','- Ớt 1 đến 2 trái','- Muối vừa đủ','- Muối 15g (khoảng 2/3 muỗng canh)'),2,20,{})
        scaled=quy_doi_khau_phan(recipe,3)
        self.assertEqual(scaled['dong'],['- Cá 600 g'])
        self.assertEqual(len(scaled['chua_quy_doi']),3)

    def test_cache_khong_sua_state(self):
        a=self.ask('Gợi ý món ăn từ cá lóc')
        b=copy.deepcopy(a)
        a['trang_thai']['de_xuat'][0]['id_goc']=-999
        c=self.ask('Gợi ý món ăn từ cá lóc')
        self.assertEqual(c['trang_thai']['de_xuat'],b['trang_thai']['de_xuat'])

    def test_evaluation_khong_co_Test(self):
        from backend.chatbot.sinh_cau_tra_loi import tra_loi
        r=tra_loi('cách nấu canh chua cá lóc',tuy_chon={'che_do_du_lieu':'evaluation'})
        self.assertEqual(r['giai_thich']['che_do_du_lieu'],'evaluation')
        self.assertTrue(all(d['tap']=='Train' for d in r['doan_truy_hoi']))


if __name__=='__main__':
    unittest.main()
