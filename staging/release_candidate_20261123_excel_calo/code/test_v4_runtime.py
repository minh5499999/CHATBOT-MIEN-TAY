"""Version-specific regression and validation of provenance boundaries, offline."""
import copy,json,os,unittest
from pathlib import Path
from unittest.mock import patch
from backend.chatbot.cau_hinh import ROOT,doc_cau_hinh

class V4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build=ROOT/'staging/release_candidate_20261116_v4'
        cls.rows={r['id']:r for r in map(json.loads,(cls.build/'ledger.jsonl').read_text(encoding='utf-8').splitlines())}
    def setUp(self):
        self.env=patch.dict(os.environ,CHATBOT_STAGING_BUILD=str(self.build));self.env.start()
        doc_cau_hinh.cache_clear()
        from backend.chatbot.trich_xuat_thuc_the import lay_bo_phan_loai_ml
        lay_bo_phan_loai_ml.cache_clear()
    def tearDown(self):self.env.stop();doc_cau_hinh.cache_clear()
    def ask(self,q,h=None):
        from backend.chatbot.hoi_thoai import tra_loi_co_trang_thai
        return tra_loi_co_trang_thai(q,h)
    def history(self,r,q='Cách nấu canh chua cá lóc'):
        from backend.chatbot.tai_khoan import rut_gon_ket_qua
        return [dict(cau_hoi=q,**rut_gon_ket_qua(r))]
    def store(self):return doc_cau_hinh()['kho_vector']
    def test_R03_full_recipe_not_greens(self):
        r=self.ask('Tôi muốn tự nấu lẩu mắm miền Tây, hướng dẫn trọn món')
        self.assertEqual([n['id_goc'] for n in r['nguon']],[43]);self.assertIn('Nấu nước lẩu',r['cau_tra_loi'])
    def test_V02_unaccented_recipe(self):self.assertEqual(self.ask('bay tui nau canh chua ca loc kieu mien tay')['nguon'][0]['id_goc'],41)
    def test_V03_unaccented_kho_to(self):self.assertEqual(self.ask('cach lam ca loc kho to cho bua com chieu')['nguon'][0]['id_goc'],42)
    def test_V04_dialect_lau_mam(self):self.assertEqual(self.ask('Bữa nay tui muốn đãi cả nhà lẩu mắm, nấu sao cho ngon vậy')['nguon'][0]['id_goc'],43)
    def test_ingredients_aspect_only(self):
        r=self.ask('Canh chua cá lóc cần nguyên liệu gì?');self.assertEqual(r['structured_view']['mode'],'ingredients');self.assertNotIn('Đun sôi',r['cau_tra_loi'])
    def test_prep_aspect_only(self):
        r=self.ask('Canh chua cá lóc sơ chế ra sao?');self.assertIn('Ướp cá',r['cau_tra_loi']);self.assertNotIn('Đun sôi',r['cau_tra_loi'])
    def test_named_step_exact_span(self):
        r=self.ask('Lẩu mắm miền Tây nấu nước lẩu ra sao?');self.assertEqual(r['structured_view']['mode'],'step');self.assertIn('Nấu nước lẩu',r['cau_tra_loi']);self.assertNotIn('Luộc hải sản',r['cau_tra_loi'])
    def test_unknown_step_not_invented(self):self.assertEqual(self.ask('Canh chua cá lóc bước 99 là gì?')['reason_code'],'MISSING_STEP')
    def test_time_no_sum_invented(self):self.assertIn('chưa có tổng thời gian',self.ask('Canh chua cá lóc nấu bao lâu?')['cau_tra_loi'])
    def test_D02_portions_survive_final_gate(self):
        r=self.ask('Cách nấu canh chua cá lóc');r=self.ask('Cho 8 người ăn',self.history(r))
        self.assertIn('500 × 2 = 1000 g',r['cau_tra_loi']);self.assertEqual(r['structured_view']['transform']['target_portions'],8)
    def test_portion_four_eight_two_current(self):
        r=self.ask('Cách nấu canh chua cá lóc');h=self.history(r)
        for q,target in [('Đổi thành 8 người',8),('Đổi còn 2 người',2),('Khẩu phần hiện tại là mấy người?',2)]:
            r=self.ask(q,h);self.assertEqual(r['trang_thai']['khau_phan'],target);self.assertEqual(r['structured_view']['transform']['target_portions'],target);h+=self.history(r,q)
        self.assertIn('500 × 1/2 = 250 g',r['cau_tra_loi'])
    def test_remaining_servings_without_verb(self):
        r=self.ask('Cách nấu canh chua cá lóc');h=self.history(r)
        r=self.ask('Cho 8 người ăn',h);h+=self.history(r)
        r=self.ask('Giờ chỉ còn 2 người',h);self.assertEqual(r['structured_view']['transform']['target_portions'],2)
    def test_omission_persists_as_not_applied(self):
        r=self.ask('Cách nấu canh chua cá lóc');r=self.ask('Món đó bỏ nước mắm',self.history(r))
        self.assertEqual(r['trang_thai']['pending_ingredient_change']['status'],'NOT_APPLIED')
        r=self.ask('Xem lại phần sơ chế món đó',self.history(r));self.assertEqual(r['reason_code'],'MODIFICATION_UNSUPPORTED')
    def test_nonadjacent_substitution_is_not_original_recipe(self):
        self.assertEqual(self.ask('Canh chua cá lóc thay cá lóc bằng cá quả được không')['reason_code'],'MODIFICATION_UNSUPPORTED')
    def test_recipe_title_descriptive_suffixes(self):
        for q,idx in [('Chỉ tui đổ bánh xèo miền Tây',44),('ca loc nuong trui kieu mien tay lam sao',45)]:self.assertEqual(self.ask(q)['nguon'][0]['id_goc'],idx)
    def test_ambiguous_units_not_converted(self):
        from backend.chatbot.recipe_views import portion_transform
        t=portion_transform(self.rows[41],8)
        self.assertTrue(any(x['status']=='UNRESOLVED' and 'Nước mắm' in x['text'] for x in t['items']))
    def test_transform_provenance_every_line(self):
        from backend.chatbot.recipe_views import portion_transform,validate_transform
        t=portion_transform(self.rows[41],8);self.assertTrue(validate_transform(self.rows[41],t))
        self.assertTrue(all(x['source_version']==self.rows[41]['answer_sha256'] and x['source'] for x in t['items']))
    def test_transform_arithmetic_tamper_rejected(self):
        from backend.chatbot.recipe_views import portion_transform,validate_transform
        t=portion_transform(self.rows[41],8);t['items'][0]['result']='9999'
        with self.assertRaises(ValueError):validate_transform(self.rows[41],t)
    def test_transform_version_tamper_rejected(self):
        from backend.chatbot.recipe_views import portion_transform,validate_transform
        t=portion_transform(self.rows[41],8);t['recipe_version']='wrong'
        with self.assertRaises(ValueError):validate_transform(self.rows[41],t)
    def test_invalid_servings_not_silently_four(self):
        for count in (0,101):self.assertEqual(self.ask(f'Canh chua cá lóc cho {count} người')['reason_code'],'MODIFICATION_UNSUPPORTED')
    def test_final_gate_discards_injected_prose(self):
        from backend.chatbot.knowledge_policy import seal_result
        r=self.ask('Canh chua cá lóc cho 8 người');r['cau_tra_loi']='MÓN ĂN CHỮA BỆNH'
        self.assertNotIn('CHỮA BỆNH',seal_result(r,self.store())['cau_tra_loi'])
    def test_gate_invalid_transform_not_rendered(self):
        from backend.chatbot.knowledge_policy import seal_result
        r=self.ask('Canh chua cá lóc cho 8 người');r['structured_view']['transform']['items'][0]['result']='9999'
        self.assertEqual(seal_result(r,self.store())['reason_code'],'VALIDATION_FAILED')
    def test_D04_omission_not_claimed_done(self):
        r=self.ask('Bỏ nước mắm khỏi canh chua cá lóc rồi viết lại công thức')
        self.assertEqual(r['reason_code'],'MODIFICATION_UNSUPPORTED');self.assertNotEqual(r['loai'],'tra_loi');self.assertNotIn('Ướp cá',r['cau_tra_loi'])
    def test_omission_multiturn_stays_same_dish(self):
        r=self.ask('Cách nấu canh chua cá lóc');r=self.ask('Món đó bỏ nước mắm',self.history(r))
        self.assertEqual(r['chu_de']['id_goc'],41);self.assertEqual(r['adjustment_request']['requested_target'],'nuoc mam')
    def test_ingredient_occurrences_include_steps(self):
        from backend.chatbot.recipe_views import adjustment_request
        a=adjustment_request(self.rows[41],'Bỏ nước mắm');self.assertGreaterEqual(len(a['source_occurrences']),2)
    def test_synonym_and_compound_uncertainty(self):
        from backend.chatbot.recipe_views import adjustment_request
        a=adjustment_request(self.rows[41],'Bỏ fish sauce');self.assertEqual(a['requested_target'],'nuoc mam');self.assertTrue(a['unresolved_compound_ingredients'])
    def test_negated_omission_not_accepted_as_remove(self):
        r=self.ask('Canh chua cá lóc không bỏ nước mắm');self.assertEqual(r.get('structured_view',{}).get('mode'),'full')
    def test_reduction_and_substitution_limited(self):
        for q in ('Cá lóc kho tộ giảm một nửa đường','Canh chua cá lóc không có me thì thay bằng gì?'):
            self.assertEqual(self.ask(q)['reason_code'],'MODIFICATION_UNSUPPORTED')
    def test_nutrition_reason_not_recipe(self):
        r=self.ask('Canh chua cá lóc có bao nhiêu kcal protein lipid carbohydrate natri?');self.assertEqual(r['reason_code'],'MISSING_NUTRITION');self.assertFalse(r['nguon'])
    def test_health_scoped_but_held(self):
        for condition in ('cảm','ho','sốt','kinh nguyệt'):
            r=self.ask('Tôi đang '+condition+', nên ăn món gì?');self.assertEqual(r['reason_code'],'HELD_HEALTH');self.assertNotEqual(r['loai'],'ngoai_pham_vi')
    def test_held_exact_question_never_answered(self):
        for idx in (689,799,878,906):
            r=self.ask(self.rows[idx]['question']);self.assertEqual(r['reason_code'],'HELD_HEALTH');self.assertFalse(r['nguon'])
    def test_outside_reason(self):self.assertEqual(self.ask('Kể lịch sử chiến tranh La Mã')['reason_code'],'OUT_OF_SCOPE')
    def test_unknown_recipe_reason(self):self.assertEqual(self.ask('Công thức bánh sao Kim chưa có trong kho')['reason_code'],'MISSING_DISH')
    def test_source_not_promoted_verified(self):
        r=self.ask('Nguồn công thức canh chua cá lóc ở đâu?');self.assertEqual(r['reason_code'],'SOURCE_UNVERIFIED');self.assertIn('chưa có bản nguồn gốc',r['cau_tra_loi'])
    def test_seal_covers_transform_state_and_reason(self):
        from backend.chatbot.knowledge_policy import render_result
        r=self.ask('Canh chua cá lóc cho 8 người');bad=copy.deepcopy(r);bad['trang_thai']['khau_phan']=2
        self.assertEqual(render_result(bad,self.store())['reason_code'],'HISTORY_UNSEALED')
    def test_rut_gon_preserves_sealed_typed_view(self):
        from backend.chatbot.tai_khoan import rut_gon_ket_qua
        from backend.chatbot.knowledge_policy import render_result
        r=self.ask('Canh chua cá lóc cho 8 người');self.assertEqual(render_result(rut_gon_ket_qua(r),self.store())['cau_tra_loi'],r['cau_tra_loi'])
    def test_unsigned_held_history_remains_blocked(self):
        from backend.chatbot.knowledge_policy import render_result
        r=render_result(dict(loai='tra_loi',nguon=[{'id_goc':799}],cau_tra_loi='thuốc',chu_de=None),self.store())
        self.assertEqual(r['reason_code'],'HISTORY_UNSEALED');self.assertNotIn('thuốc',r['cau_tra_loi'])
    def test_faiss_bm25_rrf_real_v4(self):
        from backend.chatbot.truy_hoi import truy_hoi
        for mode in ('vector','bm25','lai'):
            result=truy_hoi('hướng dẫn nấu lẩu mắm',kho=self.store(),che_do=mode)
            self.assertTrue(result['doan']);self.assertTrue(all(r['build_id']==self.build.name for r in result['doan']))
    def test_counts_held_split_and_vector_copy(self):
        import hashlib
        self.assertEqual(len(self.rows),993);self.assertEqual(sum(not r['allowed_for_answer'] for r in self.rows.values()),161)
        self.assertEqual(sum(r['split']=='Train' for r in self.rows.values()),795)
        self.assertEqual(sum(r['split']=='Test' for r in self.rows.values()),198)
        for name in ('answer_all','answer_Train'):
            p=self.build/'kho_vector'/name/'index.faiss';v3=ROOT/'staging/release_candidate_20261116_v3/kho_vector'/name/'index.faiss'
            self.assertEqual(hashlib.sha256(p.read_bytes()).digest(),hashlib.sha256(v3.read_bytes()).digest())

if __name__=='__main__':unittest.main()
