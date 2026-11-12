"""Kiểm thử toàn diện 4 khả năng nâng cấp NLP & Tự học không dùng LLM:

1. Tách từ Bi-directional Maximum Matching (BiMM) & Chuẩn hóa phương ngữ/teencode.
2. Trích xuất từ khóa đồ thị (TextRank/PageRank), Cụm cú pháp (Chunking) & Phân loại ML Intent.
3. Phân tách phạm vi phủ định (Positive vs Negative Scope) & Ràng buộc thực thể.
4. Tự học chủ động (Active Learning clustering) & Thêm vector gia tăng (Incremental FAISS Indexing).
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import faiss
import numpy as np

from backend.chatbot.ngon_ngu import (
    chuan_hoa_dia_phuong,
    tach_phu_dinh,
)
from backend.chatbot.nhan_dien_mon import dac_trung_mon
from backend.chatbot.trich_xuat_thuc_the import (
    lay_bo_phan_loai_ml,
    trich_xuat_cum_cu_phap,
    trich_xuat_textrank,
)
from backend.chatbot.tu_hoc import (
    gom_cum_cau_hoi,
    them_cau_hoi_moi,
)
from scripts.tach_tu import TachTu


class TestNangCapNLP(unittest.TestCase):
    def setUp(self):
        self.tu_dien = [
            "canh chua", "cá lóc", "thịt kho", "hột vịt", "nước mắm",
            "lạp xưởng", "dừa sáp", "bông điên điển", "rau đắng", "miền Tây",
            "chất đạm", "giàu đạm", "ít đường",
        ]
        self.tokenizer = TachTu(self.tu_dien)

    # -------------------------------------------------------------------------
    # 1. KIỂM THỬ TÁCH TỪ BiMM & CHUẨN HÓA PHƯƠNG NGỮ
    # -------------------------------------------------------------------------
    def test_bimm_tokenizer_prioritizes_compounds(self):
        text = "Hướng dẫn nấu canh chua cá lóc miền Tây tại nhà"
        tokens = self.tokenizer.tach_cau_hoi(text)
        self.assertIn("canh_chua", tokens)
        self.assertIn("cá_lóc", tokens)
        self.assertIn("miền_Tây", tokens)

    def test_bimm_directional_matching_tie_break(self):
        fmm = self.tokenizer._tim_khop_fmm(["canh", "chua", "cá", "lóc"])
        bmm = self.tokenizer._tim_khop_bmm(["canh", "chua", "cá", "lóc"])
        self.assertEqual(fmm, [(0, 2), (2, 4)])
        self.assertEqual(bmm, [(0, 2), (2, 4)])

    def test_chuan_hoa_dia_phuong_va_teencode(self):
        raw = "mik muon biet ca chuoi nau canh chua đc ko"
        normalized = chuan_hoa_dia_phuong(raw)
        self.assertIn("mình", normalized)
        self.assertIn("cá lóc", normalized)
        self.assertIn("được", normalized)
        self.assertIn("không", normalized)

    # -------------------------------------------------------------------------
    # 2. KIỂM THỬ TEXTRANK, CÚ PHÁP & PHÂN LOẠI ML
    # -------------------------------------------------------------------------
    def test_textrank_keyword_extraction(self):
        cau_hoi = "Cách nấu canh chua cá lóc miền Tây chuẩn vị ngon nhất"
        keywords = trich_xuat_textrank(cau_hoi, top_k=5)
        self.assertTrue(len(keywords) > 0)
        kw_names = [k for k, _ in keywords]
        # TextRank phải nhận diện thực thể món ăn hoặc nguyên liệu chính
        self.assertTrue(any(term in kw_names for term in ("cá lóc", "canh chua", "miền tây")))
        for _, score in keywords:
            self.assertGreater(score, 0.0)

    def test_grammar_chunking_entities(self):
        cau_hoi = "Cách nấu canh chua cá lóc không dùng me, tôi cần nhiều đạm"
        chunks = trich_xuat_cum_cu_phap(cau_hoi)
        self.assertTrue(len(chunks["cum_mon_an"]) > 0)
        self.assertTrue(any("canh" in c and "cá" in c for c in chunks["cum_mon_an"]))
        self.assertIn("nhiều đạm", chunks["rang_buoc_dinh_duong"])
        self.assertTrue(any("me" in c for c in chunks["di_ung_kieng"]))

    def test_classical_ml_intent_classifier(self):
        clf = lay_bo_phan_loai_ml()
        res = clf.du_doan("Cách nấu canh chua cá lóc chuẩn vị miền Tây")
        self.assertIn("nhom", res)
        self.assertGreater(res["diem"], 0.0)
        self.assertTrue(len(res["top_nhom"]) > 0)

    # -------------------------------------------------------------------------
    # 3. KIỂM THỬ PHÂN TÁCH PHỦ ĐỊNH & RÀNG BUỘC THỰC THỂ
    # -------------------------------------------------------------------------
    def test_tach_phu_dinh_scope(self):
        cau_hoi = "Tôi muốn ăn canh chua không dùng me, cần nhiều đạm"
        scope = tach_phu_dinh(cau_hoi)
        self.assertIn("me", scope["negative_keywords"])
        self.assertIn("giàu đạm", scope["positive_keywords"])
        self.assertNotIn("me", scope["positive_keywords"])

    def test_dac_trung_mon_mo_rong(self):
        dt = dac_trung_mon("cách làm cá tai tượng chiên xù")
        self.assertIn("cá tai tượng", dt)

    # -------------------------------------------------------------------------
    # 4. KIỂM THỬ ACTIVE LEARNING & INCREMENTAL FAISS INDEXING
    # -------------------------------------------------------------------------
    def test_gom_cum_cau_hoi_clustering(self):
        danh_sach = [
            "Cách làm lạp xưởng tươi Mai Quế Lộ",
            "Hướng dẫn ướp lạp xưởng tươi miền Tây",
            "Công thức làm lạp xưởng tôm",
            "Cách nấu canh kiểm chay nước cốt dừa",
            "Nấu canh kiểm Nam Bộ thế nào",
        ]
        clusters = gom_cum_cau_hoi(danh_sach, eps=0.5, min_samples=1)
        self.assertTrue(len(clusters) >= 2)
        tong_cau = sum(c["so_cau_hoi"] for c in clusters)
        self.assertEqual(tong_cau, len(danh_sach))

    def test_incremental_faiss_indexing_in_isolated_dir(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Tạo index FAISS giả lập 768 chiều
            d = 768
            index = faiss.IndexFlatIP(d)
            v0 = np.random.randn(1, d).astype(np.float32)
            v0 /= np.linalg.norm(v0)
            index.add(v0)

            index_path = temp_dir / "index.faiss"
            sieu_path = temp_dir / "sieu_du_lieu.jsonl"
            info_path = temp_dir / "thong_tin.json"

            index_path.write_bytes(faiss.serialize_index(index).tobytes())
            sieu_path.write_text(
                json.dumps({"id_goc": 1, "cau_hoi": "câu gốc", "noi_dung": "nội dung gốc"}) + "\n",
                encoding="utf-8",
            )
            info_path.write_text(json.dumps({"so_doan": 1}), encoding="utf-8")

            # Gọi hàm thêm câu hỏi mới
            res = them_cau_hoi_moi(
                cau_hoi="Cách nấu canh kiểm miền Tây",
                cau_tra_loi="Canh kiểm nấu với khoai lang, bí đỏ, nước cốt dừa.",
                kho_rel=str(temp_dir),
            )

            self.assertEqual(res["tong_so_vector"], 2)
            idx_sau = faiss.deserialize_index(np.frombuffer(index_path.read_bytes(), dtype=np.uint8))
            self.assertEqual(idx_sau.ntotal, 2)

            sieu_lines = [json.loads(line) for line in sieu_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(sieu_lines), 2)
            self.assertEqual(sieu_lines[-1]["cau_hoi"], "Cách nấu canh kiểm miền Tây")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

