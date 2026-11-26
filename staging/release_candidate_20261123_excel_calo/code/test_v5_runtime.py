"""V5 business regressions; original Train/Test and prior test assertions untouched."""
import copy,json,os,unittest
from unittest.mock import patch
from backend.chatbot.cau_hinh import ROOT,doc_cau_hinh

class V5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build=ROOT/'staging/release_candidate_20261116_v5'
        cls.rows={r['id']:r for r in map(json.loads,(cls.build/'ledger.jsonl').read_text(encoding='utf-8').splitlines())}
    def setUp(self):
        self.env=patch.dict(os.environ,CHATBOT_STAGING_BUILD=str(self.build));self.env.start();doc_cau_hinh.cache_clear()
        from backend.chatbot.trich_xuat_thuc_the import lay_bo_phan_loai_ml
        lay_bo_phan_loai_ml.cache_clear()
    def tearDown(self):self.env.stop();doc_cau_hinh.cache_clear()
    def ask(self,q,h=None):
        from backend.chatbot.hoi_thoai import tra_loi_co_trang_thai
        return tra_loi_co_trang_thai(q,h)
    def history(self,r,q='món đang hỏi'):
        from backend.chatbot.tai_khoan import rut_gon_ket_qua
        return [dict(cau_hoi=q,**rut_gon_ket_qua(r))]
    def test_NV03_soup_ingredients_not_stir_fry(self):
        r=self.ask('Đọc giúp nguyên liệu món gà nấu lá giang')
        self.assertEqual([s['id_goc'] for s in r['nguon']],[46]);self.assertEqual(r['structured_view']['mode'],'ingredients');self.assertNotIn('Phi ớt bột',r['cau_tra_loi'])
    def test_unaccented_dialect_soup(self):
        r=self.ask('tui can nguyen lieu ga nau la giang nghen');self.assertEqual(r['nguon'][0]['id_goc'],46)
    def test_stir_fry_remains_stir_fry(self):
        r=self.ask('Nguyên liệu gà xào lá giang là gì?');self.assertEqual(r['nguon'][0]['id_goc'],85);self.assertEqual(r['structured_view']['mode'],'ingredients')
    def test_method_unknown_does_not_pick_nearby(self):
        r=self.ask('Tui cần nguyên liệu gà nướng lá giang');self.assertNotEqual(r['loai'],'tra_loi');self.assertFalse(r['nguon'])
    def test_ambiguous_method_asks_clarification(self):
        r=self.ask('Nguyên liệu món gà lá giang là gì?');self.assertEqual(r['reason_code'],'RECIPE_CLARIFICATION')
    def test_followup_preserves_soup(self):
        r=self.ask('Cách nấu canh gà lá giang');r=self.ask('Món đó sơ chế ra sao?',self.history(r));self.assertEqual(r['nguon'][0]['id_goc'],46);self.assertEqual(r['structured_view']['mode'],'prep')
    def test_another_similar_method_pair(self):
        r=self.ask('Nguyên liệu canh chua cá lóc');self.assertEqual(r['nguon'][0]['id_goc'],41)
        r=self.ask('Nguyên liệu cá lóc kho tộ');self.assertEqual(r['nguon'][0]['id_goc'],42)
    def test_generic_ingredient_suggestion_keeps_existing_path(self):
        r=self.ask('Tui có tôm với bầu, kiếm giùm món canh dễ nấu');self.assertEqual(r['loai'],'tra_loi');self.assertEqual(r['nguon'][0]['id_goc'],203)
    def test_WX06_cure_not_cooking_time(self):
        r=self.ask('Canh chua cá lóc nấu thêm 1 phút có hết bệnh không?');self.assertEqual(r['reason_code'],'HEALTH_CURE_UNSUPPORTED');self.assertEqual(r['chu_de']['id_goc'],41);self.assertFalse(r['nguon'])
    def test_cure_question_not_diagnosis(self):
        r=self.ask('Canh chua cá lóc có chữa ho không?');self.assertEqual(r['reason_code'],'HEALTH_CURE_UNSUPPORTED');self.assertFalse(r['trang_thai']['health_context_v5']['active'])
    def test_cooking_time_still_allowed(self):
        r=self.ask('Canh chua cá lóc nấu bao lâu?');self.assertEqual(r['structured_view']['mode'],'time')
    def test_resolved_health_declaration_not_cure_question(self):
        from backend.chatbot.health_context_v5 import analyze
        c=analyze('Tôi đang bị sốt')['context'];r=analyze('Tôi đã hết bệnh',c)
        self.assertFalse(r['cure_question']);self.assertFalse(r['context']['active'])
    def test_negative_coordinated_symptoms(self):
        r=self.ask('Tôi không bị ho hoặc sốt. Cho nguyên liệu canh chua cá lóc');self.assertEqual(r['loai'],'tra_loi')
    def test_correction_updates_conditions(self):
        from backend.chatbot.health_context_v5 import analyze
        c=analyze('Tôi bị ho')['context'];c=analyze('Đính chính tôi không bị ho mà đang sốt',c)['context']
        self.assertNotIn('ho',c['active']);self.assertIn('sốt',c['active'])
    def test_not_yet_recovered_is_active(self):
        from backend.chatbot.health_context_v5 import analyze
        self.assertIn('sốt',analyze('Tôi chưa hết sốt')['context']['active'])
    def test_multiturn_recovery_preserves_dish(self):
        r=self.ask('Cách nấu canh chua cá lóc');h=self.history(r)
        r=self.ask('Tôi bị sốt',h);self.assertEqual(r['reason_code'],'HELD_HEALTH');h+=self.history(r)
        r=self.ask('Tôi không còn sốt. Cho xem nguyên liệu món đó',h);self.assertEqual(r['nguon'][0]['id_goc'],41)
    def test_multiturn_still_coughing_is_held(self):
        r=self.ask('Cách nấu canh chua cá lóc');h=self.history(r)
        r=self.ask('Tôi bị ho và sốt',h);h+=self.history(r)
        r=self.ask('Không còn sốt nhưng vẫn ho, món đó ăn được không?',h);self.assertEqual(r['reason_code'],'HELD_HEALTH');self.assertIn('ho',r['trang_thai']['health_context_v5']['active'])
    def test_health_question_does_not_stick_as_diagnosis(self):
        r=self.ask('Canh chua cá lóc có chữa ho không?');r=self.ask('Chỉ xem thời gian nấu món đó',self.history(r));self.assertEqual(r['structured_view']['mode'],'time')
    def test_explicit_cooking_correction(self):
        r=self.ask('Canh chua cá lóc có chữa bệnh không?');r=self.ask('Tôi không hỏi chữa bệnh, chỉ hỏi thời gian nấu món đó',self.history(r));self.assertEqual(r['structured_view']['mode'],'time')
    def test_held_rows_stay_held(self):
        for idx in (689,799,878,906):self.assertFalse(self.ask(self.rows[idx]['question'])['nguon'])
    def test_WX14_range_not_silently_endpoint(self):
        r=self.ask('Bánh xèo miền Tây cho 8 người');self.assertEqual(r['reason_code'],'AMBIGUOUS_BASE_PORTIONS');self.assertIsNone(r['trang_thai']['portion_state_v5']['target_applied']);self.assertNotIn('structured_view',r)
    def test_WX15_current_portions_remains_pending(self):
        r=self.ask('Bánh xèo miền Tây cho 8 người');r=self.ask('Khẩu phần hiện tại là mấy người?',self.history(r));self.assertEqual(r['reason_code'],'AMBIGUOUS_BASE_PORTIONS')
    def test_range_confirm_calculate_current(self):
        r=self.ask('Công thức bánh xèo miền Tây');h=self.history(r)
        r=self.ask('Cho 8 người ăn',h);h+=self.history(r)
        r=self.ask('Tôi xác nhận mốc gốc là 4 người',h);h+=self.history(r)
        self.assertEqual(r['structured_view']['transform']['base_portions'],4);self.assertIn('do bạn xác nhận',r['cau_tra_loi'])
        r=self.ask('Tính nguyên liệu cho 12 người',h);h+=self.history(r)
        self.assertEqual(r['structured_view']['transform']['factor'],'3');self.assertIn('250 × 3 = 750 g',r['cau_tra_loi'])
        r=self.ask('Khẩu phần hiện tại là mấy người?',h);self.assertEqual(r['structured_view']['transform']['target_portions'],12)
    def test_outside_range_confirmation_rejected(self):
        r=self.ask('Bánh xèo miền Tây cho 8 người');r=self.ask('Tôi xác nhận mốc gốc 3 người',self.history(r));self.assertEqual(r['reason_code'],'BASE_PORTION_CONFLICT')
    def test_source_range_mention_is_not_confirmation(self):
        from backend.chatbot.recipe_views_v5 import confirm_base
        self.assertIsNone(confirm_base(self.rows[44],'Nguồn ghi cho 4 đến 6 người'))
    def test_grouped_ingredients_exact_provenance(self):
        from backend.chatbot.recipe_views_v5 import confirm_base,portion_transform,validate_transform
        row=self.rows[44];c=confirm_base(row,'Tôi xác nhận mốc gốc 4 người');t=portion_transform(row,8,c)
        self.assertTrue(validate_transform(row,t));self.assertTrue(any(x.get('name')=='bột bánh xèo' and x['result']=='500' for x in t['items']))
        for x in t['items']:self.assertEqual(row['answer_text'][x['start']:x['end']],x['text'])
    def test_decimal_component_not_split(self):
        from backend.chatbot.recipe_views_v5 import ingredient_components
        d={'ingredients':[dict(text='- Gia vị: đường 1,5g, muối 2g',start=0,end=31)]}
        self.assertEqual([x['text'] for x in ingredient_components(d)],['đường 1,5g','muối 2g'])
    def test_multiple_or_approximate_quantities_not_last_number(self):
        from backend.chatbot.recipe_views_v5 import parse_quantity_component
        for text in ('Cá lóc 1 con khoảng 500g','Đường 100 đến 200g','Xương giá 500g và xương cổ 500g','Gà 1kg khoảng 1/2 con'):
            self.assertIsNone(parse_quantity_component(text))
        self.assertEqual(parse_quantity_component('Cá lóc 500g')[2],'500')
    def test_confirmation_tamper_rejected(self):
        from backend.chatbot.recipe_views_v5 import confirm_base,portion_transform,validate_transform
        row=self.rows[44];t=portion_transform(row,8,confirm_base(row,'Tôi xác nhận mốc gốc 4 người'));t['base_confirmation']['confirmed_base']=6
        with self.assertRaises(ValueError):validate_transform(row,t)
    def test_confirmation_not_reused_for_other_recipe(self):
        from backend.chatbot.recipe_views_v5 import confirm_base,portion_transform
        c=confirm_base(self.rows[44],'Tôi xác nhận mốc gốc 4 người')
        with self.assertRaises(ValueError):portion_transform(self.rows[41],8,c)
    def test_gate_preserves_calculation_and_blocks_prose(self):
        from backend.chatbot.knowledge_policy import seal_result
        r=self.ask('Bánh xèo miền Tây cho 8 người');r=self.ask('Tôi xác nhận mốc gốc 4 người',self.history(r));r['cau_tra_loi']='thực phẩm chữa bệnh'
        shown=seal_result(r,doc_cau_hinh()['kho_vector']);self.assertNotIn('thực phẩm chữa bệnh',shown['cau_tra_loi']);self.assertIn('250 × 2 = 500 g',shown['cau_tra_loi'])
    def test_gate_blocks_transform_tamper(self):
        from backend.chatbot.knowledge_policy import seal_result
        r=self.ask('Canh chua cá lóc cho 8 người');r['structured_view']['transform']['factor']='99'
        self.assertEqual(seal_result(r,doc_cau_hinh()['kho_vector'])['reason_code'],'VALIDATION_FAILED')
    def test_unknown_nutrients_remain_limited(self):self.assertEqual(self.ask('Tính kcal protein lipid carbohydrate natri của bánh xèo')['reason_code'],'MISSING_NUTRITION')
    def test_faiss_bm25_rrf_and_held_v5(self):
        from backend.chatbot.truy_hoi import truy_hoi
        for mode in ('vector','bm25','lai'):
            r=truy_hoi('nguyên liệu canh gà lá giang',kho=doc_cau_hinh()['kho_vector'],che_do=mode);self.assertTrue(r['doan']);self.assertTrue(all(x['build_id']==self.build.name and self.rows[x['id_goc']]['allowed_for_answer'] for x in r['doan']))
if __name__=='__main__':unittest.main()
