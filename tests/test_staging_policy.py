"""Development tests: immutable staged artifacts, no sealed-Test optimization."""
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.run_isolated_tests import ROOT, snapshot


class StagingPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        torch.set_num_threads(4)
        builds = [p for p in (ROOT/'staging').glob('release_candidate_*') if (p/'manifest.json').is_file()]
        if not builds:
            raise RuntimeError('Build staging before running this test suite')
        cls.build = sorted(builds)[-1]
        cls.manifest = json.loads((cls.build/'manifest.json').read_text(encoding='utf-8'))
        cls.ledger = {r['id']:r for r in map(json.loads,(cls.build/'ledger.jsonl').read_text(encoding='utf-8').splitlines())}

    def setUp(self):
        self.before = snapshot(ROOT)
        self.env = patch.dict(os.environ, CHATBOT_STAGING_BUILD=str(self.build))
        self.env.start()
        self.reset_caches()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.env.stop()
        self.reset_caches()
        self.assertEqual(self.before, snapshot(ROOT))

    @staticmethod
    def reset_caches():
        from backend.chatbot.cau_hinh import doc_cau_hinh
        doc_cau_hinh.cache_clear()
        from backend.chatbot.trich_xuat_thuc_the import lay_bo_phan_loai_ml
        lay_bo_phan_loai_ml.cache_clear()

    def store(self):
        return (self.build/'kho_vector/answer_all').relative_to(ROOT).as_posix()

    def test_id2_and_fixture_archive(self):
        active=list(map(json.loads,(self.build/'merged/dataset.jsonl').read_text(encoding='utf-8').splitlines()))
        self.assertEqual(len(active),832)
        self.assertEqual([r['question'] for r in active if r['id']==2],['Chào bot'])
        archive=list(map(json.loads,(self.build/'archive/fixtures.jsonl').read_text(encoding='utf-8').splitlines()))
        self.assertEqual(len(archive),4)
        for r in archive:self.assertEqual(hashlib.sha256(r['raw'].encode()).hexdigest(),r['raw_sha256'])

    def test_original_test_is_byte_identical(self):
        paths=list((ROOT/'data/groups').glob('*/test.csv'))
        for p in paths:
            copy_path=self.build/'archive/original_groups'/p.parent.name/'test.csv'
            self.assertEqual(p.read_bytes(),copy_path.read_bytes())
        with (ROOT/'data/groups/06_thay_the_nguyen_lieu/test.csv').open(encoding='utf-8-sig',newline='') as f:
            self.assertTrue(any(r['ID']=='441' and r['Tập']=='Test' for r in csv.DictReader(f,delimiter=';')))

    def test_conflicts_have_no_selected_version(self):
        master={r['id']:r for r in map(json.loads,(self.build/'master/records.jsonl').read_text(encoding='utf-8').splitlines())}
        for idx in (689,799,878,906):
            self.assertIsNone(master[idx]['selected_answer_version'])
            self.assertGreaterEqual(len(master[idx]['versions']),3)
            self.assertEqual(self.ledger[idx]['decision'],'HOLD_CONFLICT')
            self.assertFalse(self.ledger[idx]['allowed_for_answer'])
            self.assertEqual(self.ledger[idx]['answer_text'],'')

    def test_culinary_spans_preserved_without_keyword_ban(self):
        for idx in (214,277):
            row=self.ledger[idx]
            self.assertTrue(row['allowed_for_answer'])
            self.assertEqual(row['source_verification'],'UNVERIFIED')
            self.assertIn('Nguyên liệu',row['answer_text'])
            self.assertIn('Hoàn thành món ăn',row['answer_text'])
            self.assertNotIn('trẻ nhỏ',row['answer_text'])
        self.assertEqual(sum(r['group_folder']=='03_huong_dan_nau_mon_mien_tay' and r['allowed_for_answer'] for r in self.ledger.values()),150)

    def test_faiss_bm25_rrf_faq_catalog_and_fuzzy_share_build(self):
        from backend.chatbot.truy_hoi import nap_kho, nap_bm25, truy_hoi
        from backend.chatbot.doi_chieu import chi_muc_cau_hoi,chi_muc_ten_mon
        from backend.chatbot.cong_thuc import danh_muc
        from backend.chatbot.fuzzy import de_nghi_ten_mon
        store=self.store();idx,rows,info=nap_kho(store)
        self.assertEqual(info['build_id'],self.manifest['build_id'])
        self.assertEqual(idx.ntotal,len(rows))
        self.assertEqual(len(nap_bm25(store).tf),len(rows))
        for mode in ('vector','bm25','lai'):
            result=truy_hoi('cách nấu canh chua cá lóc',kho=store,che_do=mode)
            self.assertTrue(result['doan'])
            self.assertTrue(all(self.ledger[d['id_goc']]['allowed_for_answer'] and d['build_id']==self.manifest['build_id'] for d in result['doan']))
        for table in (chi_muc_cau_hoi(store),chi_muc_ten_mon(store)):
            self.assertTrue(all(self.ledger[idx]['allowed_for_answer'] for group in table.values() for idx in group))
        recipes=danh_muc(store)
        self.assertEqual(len(recipes),250)
        self.assertTrue(all(self.ledger[r.id_goc]['allowed_for_answer'] for r in recipes))
        for q in de_nghi_ten_mon('cach nau canh chua ca lo',store):
            self.assertIn(q,{r['question'] for r in self.ledger.values() if r['allowed_for_answer']})

    def test_held_ids_never_enter_any_answer_path(self):
        from backend.chatbot.truy_hoi import nap_kho
        from backend.chatbot.doi_chieu import chi_muc_cau_hoi
        from backend.chatbot.ngon_ngu import khoa_cau_hoi
        from backend.chatbot.sinh_cau_tra_loi import tra_loi
        held={idx for idx,r in self.ledger.items() if not r['allowed_for_answer']}
        self.assertEqual(len(held),161)
        _,rows,_=nap_kho(self.store())
        self.assertFalse(held & {r['id_goc'] for r in rows})
        table=chi_muc_cau_hoi(self.store())
        for idx in held:
            self.assertNotIn(idx,table.get(khoa_cau_hoi(self.ledger[idx]['question']),{}))
        for idx in (803,799,878,906):
            result=tra_loi(self.ledger[idx]['question'])
            self.assertEqual(result['loai'],'khong_chac')
            self.assertFalse(result['nguon'])
            self.assertNotIn('thuốc hạ sốt',result['cau_tra_loi'])

    def test_final_gate_uses_source_span_not_branch_free_text(self):
        from backend.chatbot.knowledge_policy import seal_result,render_result
        result=dict(loai='tra_loi',cau_tra_loi='LỜI KHUYÊN Y TẾ CHƯA DUYỆT',nguon=[{'id_goc':214}],goi_y=[self.ledger[803]['question']],chu_de=None,doan_truy_hoi=[])
        sealed=seal_result(result,self.store())
        shown=render_result(sealed,self.store())
        self.assertNotIn('LỜI KHUYÊN Y TẾ',shown['cau_tra_loi'])
        self.assertIn(self.ledger[214]['answer_text'],shown['cau_tra_loi'])
        self.assertFalse(shown['goi_y'])

    def test_history_cannot_replay_held_or_tampered_text(self):
        from backend.chatbot.knowledge_policy import render_result,seal_result,sanitize_history,LIMIT
        from backend.chatbot.tai_khoan_dich_vu import rut_gon_ket_qua
        old=dict(loai='tra_loi',cau_tra_loi='thuốc hạ sốt',nguon=[{'id_goc':803}],goi_y=[],chu_de={'id_goc':803})
        self.assertEqual(render_result(old,self.store())['cau_tra_loi'],LIMIT)
        history=[dict(cau_hoi='sốt',cau_tra_loi='thuốc hạ sốt',chu_de={'id_goc':803},trang_thai={'mon_hien_tai':{'id_goc':803},'de_xuat':[{'id_goc':803}]})]
        clean=sanitize_history(history,self.store())
        self.assertEqual(clean[0]['cau_tra_loi'],'');self.assertIsNone(clean[0]['chu_de'])
        self.assertIsNone(clean[0]['trang_thai']['mon_hien_tai']);self.assertFalse(clean[0]['trang_thai']['de_xuat'])
        good=seal_result(dict(loai='tra_loi',nguon=[{'id_goc':214}],goi_y=[],chu_de=None),self.store())
        self.assertNotEqual(render_result(rut_gon_ket_qua(good),self.store())['cau_tra_loi'],LIMIT)
        bad=copy.deepcopy(good);bad['cau_tra_loi']='thuốc hạ sốt'
        self.assertEqual(render_result(bad,self.store())['cau_tra_loi'],LIMIT)

    def test_same_build_retrieval_and_source_visibility(self):
        from backend.chatbot.sinh_cau_tra_loi import tra_loi
        from backend.chatbot.knowledge_policy import render_result
        result=tra_loi('cách nấu canh chua cá lóc')
        self.assertEqual(result['loai'],'tra_loi')
        self.assertEqual(result['policy_build_id'],self.manifest['build_id'])
        self.assertIn('chưa được xác minh',render_result(result,self.store())['cau_tra_loi'])

    def test_stage_cannot_write_legacy_or_mix_stores(self):
        from backend.chatbot.truy_hoi import nap_kho,nap_bm25,nap_bm25_khong_dau
        from backend.chatbot.doi_chieu import chi_muc_cau_hoi,chi_muc_ten_mon
        from backend.chatbot.cong_thuc import danh_muc
        from backend.chatbot.tu_hoc import them_cau_hoi_moi
        # Populate legacy caches first: cache hits must not bypass authorization.
        with patch.dict(os.environ, CHATBOT_STAGING_BUILD=''):
            for reader in (nap_bm25,nap_bm25_khong_dau,chi_muc_cau_hoi,chi_muc_ten_mon,danh_muc):
                reader('kho_vector/cau_truc_tat_ca')
        with self.assertRaises(ValueError):nap_kho('kho_vector/cau_truc_tat_ca')
        for reader in (nap_bm25,nap_bm25_khong_dau,chi_muc_cau_hoi,chi_muc_ten_mon,danh_muc):
            with self.assertRaises(ValueError):reader('kho_vector/cau_truc_tat_ca')
        with self.assertRaises(ValueError):them_cau_hoi_moi('q','a')

    def test_modified_artifact_is_blocked_even_after_policy_cache_warm(self):
        import shutil
        from backend.chatbot import knowledge_policy as module
        with tempfile.TemporaryDirectory(prefix='tamper_test_') as temp:
            fixture=Path(temp).resolve()
            clone=fixture/'staging'/self.build.name
            shutil.copytree(self.build,clone)
            with patch.object(module,'ROOT',fixture),patch.dict(os.environ,CHATBOT_STAGING_BUILD=str(clone)):
                module.policy('staging/'+clone.name+'/kho_vector/answer_all')
                path=clone/'kho_vector/answer_all/index.faiss'
                raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
                with self.assertRaises(ValueError):module.policy('staging/'+clone.name+'/kho_vector/answer_all')

    def test_build_failure_has_no_promotion_or_production_mutation(self):
        import shutil
        from scripts import build_staging_knowledge as builder
        # Build-input fixtures also live in temp, independently of the outer runner.
        with tempfile.TemporaryDirectory(prefix='failed_build_') as temp:
            fixture=Path(temp).resolve()
            shutil.copytree(ROOT/'data',fixture/'data')
            (fixture/'audit').mkdir()
            with (fixture/'audit/question_scope_review.csv').open('w',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=['id','record_role','classification'])
                writer.writeheader()
                writer.writerows(dict(id=i,record_role='ORIGINAL_QA',classification=r['scope']) for i,r in self.ledger.items())
            with patch.object(builder,'ROOT',fixture):
                before=builder.protected_hashes()
                with self.assertRaises(RuntimeError):builder.build('injected_failure',fail_at='after_export')
                folder=fixture/'staging/injected_failure'
                self.assertTrue((folder/'FAILED.json').is_file())
                self.assertFalse((folder/'manifest.json').exists())
                self.assertEqual(before,builder.protected_hashes())

    def test_manifest_order_tokens_and_evaluation_not_ingested(self):
        import faiss,numpy as np
        from backend.chatbot.mo_hinh_vector import nap_mo_hinh
        model=nap_mo_hinh()
        for name in ('answer_all','answer_Train'):
            folder=self.build/'kho_vector'/name
            rows=list(map(json.loads,(folder/'sieu_du_lieu.jsonl').read_text(encoding='utf-8').splitlines()))
            ids=json.loads((folder/'ordered_chunks.json').read_text(encoding='utf-8'))
            idx=faiss.deserialize_index(np.frombuffer((folder/'index.faiss').read_bytes(),dtype=np.uint8))
            self.assertEqual([r['chunk_id'] for r in rows],[r['chunk_id'] for r in ids]);self.assertEqual(idx.ntotal,len(rows))
            self.assertTrue(all(model.tokenizer.encode(r['noi_dung_kem_tieu_de_tach_tu'],truncation=False).__len__()<=256 for r in rows))
            self.assertTrue(all(r['id_goc'] in self.ledger and self.ledger[r['id_goc']]['allowed_for_answer'] for r in rows))
            if name=='answer_Train':self.assertTrue(all(r['tap']=='Train' for r in rows))
