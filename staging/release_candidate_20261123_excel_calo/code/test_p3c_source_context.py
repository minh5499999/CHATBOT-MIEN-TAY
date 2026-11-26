import os,unittest
from backend.chatbot.cau_hinh import doc_cau_hinh
class SourceContextTests(unittest.TestCase):
    def setUp(self):doc_cau_hinh.cache_clear()
    def ask(self,q,h=None):
        from backend.chatbot.hoi_thoai import tra_loi_co_trang_thai
        return tra_loi_co_trang_thai(q,h)
    def test_source_question_variants_keep_recipe_and_version(self):
        from backend.chatbot.tai_khoan import rut_gon_ket_qua
        history=[];version=None
        for q in ('Canh chua cá lóc bao nhiêu calo?','Một phần bao nhiêu protein?','Nấu cho 8 người thì sao?','Số liệu lấy từ đâu?','Lấy từ tài liệu nào vậy?','Căn cứ nào cho các số liệu đó?'):
            r=self.ask(q,history);history.append(dict(cau_hoi=q,**rut_gon_ket_qua(r)))
            self.assertEqual(r['chu_de']['id_goc'],41);self.assertEqual(r['reason_code'],'NUTRITION_BLOCKED');self.assertIsNone(r['nutrition_result']['totals'])
            current=r['nutrition_request']['recipe_version'];version=version or current;self.assertEqual(current,version)
        self.assertEqual(r['nutrition_request']['target_servings'],8)
    def test_same_source_rule_applies_to_another_dish(self):
        from backend.chatbot.tai_khoan import rut_gon_ket_qua
        q='Cá lóc kho tộ bao nhiêu calo?';r=self.ask(q)
        r=self.ask('so lieu lay tu dau vay?',[dict(cau_hoi=q,**rut_gon_ket_qua(r))])
        self.assertEqual(r['chu_de']['id_goc'],42);self.assertEqual(r['reason_code'],'NUTRITION_BLOCKED')
