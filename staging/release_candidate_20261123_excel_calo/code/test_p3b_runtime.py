import copy,json,os,unittest
from unittest.mock import patch
from backend.chatbot.cau_hinh import ROOT,doc_cau_hinh

class NutritionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.build=ROOT/'staging/release_candidate_20261116_p3b_v1'
        self.env=patch.dict(os.environ,CHATBOT_STAGING_BUILD=str(self.build));self.env.start();self.addCleanup(self.env.stop);doc_cau_hinh.cache_clear();self.addCleanup(doc_cau_hinh.cache_clear)
    def ask(self,q,h=None):
        from backend.chatbot.hoi_thoai import tra_loi_co_trang_thai
        return tra_loi_co_trang_thai(q,h)
    def h(self,q,r):
        from backend.chatbot.tai_khoan import rut_gon_ket_qua
        return dict(cau_hoi=q,**rut_gon_ket_qua(r))
    def assert_blocked(self,r,rid):
        self.assertEqual(r['reason_code'],'NUTRITION_BLOCKED');self.assertEqual(r['chu_de']['id_goc'],rid)
        self.assertIsNone(r['nutrition_result']['totals']);self.assertIn('Thiếu:',r['cau_tra_loi'])
    def test_kcal_right_recipe(self):self.assert_blocked(self.ask('Canh chua cá lóc bao nhiêu calo?'),41)
    def test_protein(self):self.assert_blocked(self.ask('Một phần cá lóc kho tộ có bao nhiêu đạm?'),42)
    def test_five_nutrients(self):self.assert_blocked(self.ask('Bảng kcal protein lipid carbohydrate natri canh chua cá lóc'),41)
    def test_fat_followup(self):
        q='Hướng dẫn nấu cá lóc kho tộ';r=self.ask(q)
        self.assert_blocked(self.ask('Món này bao nhiêu chất béo?',[self.h(q,r)]),42)
    def test_no_accent_dialect(self):self.assert_blocked(self.ask('tui hoi canh chua ca loc bao nhieu calo nghen'),41)
    def test_5_turn_memory_and_absolute_scaling(self):
        history=[]
        questions=['Hướng dẫn nấu cá lóc kho tộ','Món này bao nhiêu calo?','Nếu nấu cho tám người thì sao?','Đổi sang 2 người thì tổng calo bao nhiêu?','Những con số này lấy từ nguồn nào?']
        for q in questions:
            r=self.ask(q,history);history.append(self.h(q,r))
        self.assert_blocked(r,42);self.assertEqual(r['nutrition_request']['target_servings'],2)
        self.assertEqual(history[2]['nutrition_request']['target_servings'],8)
        self.assertEqual(r['nutrition_request']['recipe_version'],history[1]['nutrition_request']['recipe_version'])
    def test_range_stays_blocked(self):
        r=self.ask('Bánh xèo miền Tây bao nhiêu calo cho 8 người?');self.assert_blocked(r,44);self.assertIn('dạng khoảng',r['cau_tra_loi'])
    def test_user_confirmation_does_not_approve(self):
        q='Bánh xèo miền Tây cho 8 người';r=self.ask(q);h=[self.h(q,r)]
        q='Tôi xác nhận mốc gốc 4 người';r=self.ask(q,h);h.append(self.h(q,r))
        self.assert_blocked(self.ask('Tính natri món này',h),44)
    def test_missing_sodium_explained(self):self.assertIn('gia vị',self.ask('Tại sao canh chua cá lóc chưa tính được natri?')['cau_tra_loi'])
    def test_source_after_nutrition(self):
        q='Canh chua cá lóc bao nhiêu calo?';r=self.ask(q)
        self.assert_blocked(self.ask('Những con số này lấy từ nguồn nào?',[self.h(q,r)]),41)
    def test_unknown_named_dish_does_not_reuse_old(self):
        q='Cách nấu canh chua cá lóc';r=self.ask(q)
        r=self.ask('Canh thiên thạch bao nhiêu calo?',[self.h(q,r)])
        self.assertEqual(r['reason_code'],'RECIPE_CLARIFICATION');self.assertNotIn('nutrition_result',r)
    def test_health_gate_first(self):self.assertEqual(self.ask('Canh chua cá lóc thêm calo có chữa ho không?')['reason_code'],'HEALTH_CURE_UNSUPPORTED')
    def test_held_stays_held(self):
        rows={r['id']:r for r in map(json.loads,(self.build/'ledger.jsonl').read_text(encoding='utf-8').splitlines())}
        for rid in (689,799,878,906):self.assertFalse(self.ask(rows[rid]['question'])['nguon'])
    def test_partial_214_277_no_health_prose(self):
        for q,rid in [('Tôm chiên bột mì bao nhiêu calo?',214),('Cá basa chiên xù bao nhiêu natri?',277)]:self.assert_blocked(self.ask(q),rid)
    def test_nv03(self):self.assertEqual(self.ask('Nguyên liệu gà nấu lá giang')['chu_de']['id_goc'],46)
    def test_x02_general_prep_priority(self):
        for q,rid in [('Sơ chế nguyên liệu gà xào lá giang ra sao?',85),('Lam sach nguyen lieu canh chua ca loc the nao?',41)]:
            r=self.ask(q);self.assertEqual(r['structured_view']['mode'],'prep');self.assertEqual(r['chu_de']['id_goc'],rid)
    def test_ingredients_remain(self):self.assertEqual(self.ask('Nguyên liệu gà xào lá giang')['structured_view']['mode'],'ingredients')
    def test_steps_remain(self):self.assertEqual(self.ask('Các bước nấu canh chua cá lóc')['structured_view']['mode'],'steps')
    def test_outside(self):self.assertEqual(self.ask('Viết mã Python ngân hàng')['reason_code'],'OUT_OF_SCOPE')
    def test_final_gate_recomputes_tampered_numbers(self):
        from backend.chatbot.knowledge_policy import enforce_result
        r=self.ask('Canh chua cá lóc bao nhiêu calo?');r['cau_tra_loi']='999 kcal';r['nutrition_result']['totals']={'kcal':999}
        r=enforce_result(r,doc_cau_hinh()['kho_vector']);self.assertNotIn('999 kcal',r['cau_tra_loi']);self.assertIsNone(r['nutrition_result']['totals'])
    def test_nutrition_fields_sealed(self):
        from backend.chatbot.knowledge_policy import render_result
        r=self.ask('Canh chua cá lóc bao nhiêu calo?');r['nutrition_result']['totals']={'kcal':999}
        self.assertEqual(render_result(r,doc_cau_hinh()['kho_vector'])['reason_code'],'HISTORY_UNSEALED')
    def test_restart_rejects_old_seal(self):
        from backend.chatbot.knowledge_policy import render_result,_seal_key
        r=self.ask('Canh chua cá lóc bao nhiêu calo?');before=copy.deepcopy(r);_seal_key.cache_clear()
        self.assertEqual(render_result(r,doc_cau_hinh()['kho_vector'])['reason_code'],'HISTORY_UNSEALED');self.assertEqual(r,before)
    def test_original_plan_not_used_after_modification(self):
        q='Cách nấu canh chua cá lóc';r=self.ask(q);h=[self.h(q,r)]
        q='Bỏ nước mắm món đó';r=self.ask(q,h);h.append(self.h(q,r))
        result=self.ask('Món này bao nhiêu calo?',h)
        self.assertIn(result['reason_code'],('MODIFICATION_UNSUPPORTED','EDIT_NUTRITION_BLOCKED'))
        self.assertIsNone((result.get('nutrition_result') or {}).get('totals'))
    def test_langchain_chain_is_real(self):
        from backend.chatbot.hoi_thoai import chuoi_hoi_thoai
        from langchain_core.runnables import RunnableSequence
        self.assertIsInstance(chuoi_hoi_thoai(),RunnableSequence)
    def test_whole_batch_is_not_ingredient_omission(self):self.assert_blocked(self.ask('Tính calo toàn bộ món canh chua cá lóc'),41)
    def test_omission_with_nutrition_is_not_original_plan(self):
        result=self.ask('Bỏ nước mắm canh chua cá lóc rồi tính calo')
        self.assertIn(result['reason_code'],('MODIFICATION_UNSUPPORTED','EDIT_APPLIED'))
        self.assertIsNone((result.get('nutrition_result') or {}).get('totals'))
        if result['reason_code']=='EDIT_APPLIED':
            self.assertEqual(result['structured_view']['mode'],'recipe_edit')
            self.assertIn('cần hồ sơ riêng đã duyệt',result['cau_tra_loi'])
