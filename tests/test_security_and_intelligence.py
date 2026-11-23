"""Regression tests for security hardening, dataset integrity, NLP smoothness, and intelligence."""
from __future__ import annotations

import json
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.chatbot import cau_hoi_cho_hoc
from backend.chatbot import co_so_du_lieu as db
from backend.chatbot import tai_khoan_dich_vu as tk
from backend.chatbot.cau_hinh import ROOT
from backend.chatbot.intent import phan_tich
from backend.chatbot.ngon_ngu import dieu_kien, mo_rong_keyword, vi_pham
from backend.chatbot.suc_khoe import cap_nhat as cap_nhat_suc_khoe
from backend.chatbot.suc_khoe import la_cau_hoi_chua_benh
from frontend import luu_tuy_chon_ho_so as profile_store

PASSWORD = "MatKhauKiemThu123!"


class SecurityAndDatabaseRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="test_sec_")
        self.folder = Path(self.temp.name)
        self.p_db = patch.object(db, "FILE_DB", self.folder / "chatbot.sqlite3")
        self.p_backend = patch.object(db, "BACKEND", "sqlite")
        self.p_db.start()
        self.p_backend.start()
        tk.xoa_gioi_han_dang_nhap()

    def tearDown(self):
        tk.xoa_gioi_han_dang_nhap()
        self.p_backend.stop()
        self.p_db.stop()
        self.temp.cleanup()

    def test_login_rate_limiting_and_admin_reset_unlock(self):
        self.assertTrue(tk.dang_ky("adminuser", "Admin", PASSWORD)[0])
        self.assertTrue(tk.khoi_tao_admin_cuc_bo("adminuser")[0])
        self.assertTrue(tk.dang_ky("victim", "Victim", PASSWORD)[0])

        for _ in range(tk.MAX_LOGIN_ATTEMPTS):
            self.assertIsNone(tk.dang_nhap("victim", "SaiMatKhau1!"))

        with db.ket_noi() as con:
            row = con.execute("SELECT so_lan, khoa_den FROM gioi_han_dang_nhap WHERE khoa=?", ("victim",)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["so_lan"], tk.MAX_LOGIN_ATTEMPTS)
        self.assertGreater(tk.kiem_tra_khoa_dang_nhap("victim"), 0)
        # Even the correct password must be rejected while locked out.
        self.assertIsNone(tk.dang_nhap("victim", PASSWORD))

        new_pw = PASSWORD + "Moi"
        self.assertTrue(tk.admin_dat_lai_mat_khau("adminuser", "victim", new_pw)[0])
        self.assertEqual(tk.kiem_tra_khoa_dang_nhap("victim"), 0)
        self.assertIsNotNone(tk.dang_nhap("victim", new_pw))

    def test_csv_formula_injection_and_admin_guards_and_config(self):
        dummy_st = types.ModuleType("streamlit")
        dummy_st.cache_data = lambda **_: (lambda f: f)
        dummy_st.cache_resource = lambda **_: (lambda f: f)
        dummy_st.fragment = lambda **_: (lambda f: f)
        dummy_st.dialog = lambda *a, **k: (lambda f: f)
        with patch.dict(sys.modules, {"streamlit": dummy_st}):
            from frontend import bang_quan_tri
            csv_bytes = bang_quan_tri._csv([{"question": "=CMD|' /C calc'!A0", "answer": "+1+1", "source": "@evil"}])
            csv_text = csv_bytes.decode("utf-8-sig")
            self.assertIn("'=CMD|", csv_text)
            self.assertIn("'+1+1", csv_text)
            self.assertIn("'@evil", csv_text)

        for mod_name in (
            "mon_an_admin.py", "dinh_duong_admin.py", "quy_tac_admin.py",
            "chatbot_admin.py", "tu_khoa_admin.py", "y_dinh_admin.py",
            "kiem_thu_admin.py", "cai_dat_admin.py",
        ):
            src = (ROOT / "frontend" / mod_name).read_text(encoding="utf-8")
            self.assertIn("tai_khoan.la_admin(actor)", src, f"Missing RBAC guard in {mod_name}")

        cfg = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
        self.assertIn("enableXsrfProtection = true", cfg)
        self.assertIn('showErrorDetails = "none"', cfg)

    def test_unknown_user_dummy_pbkdf2_rejects_and_rate_limits(self):
        for _ in range(tk.MAX_LOGIN_ATTEMPTS):
            self.assertIsNone(tk.dang_nhap("khong_ton_tai_xyz", "BatKyMatKhau1!"))
        self.assertGreater(tk.kiem_tra_khoa_dang_nhap("khong_ton_tai_xyz"), 0)

    def test_profile_preferences_validation_and_persistence(self):
        self.assertTrue(tk.dang_ky("profile_u", "User Old", PASSWORD)[0])
        with self.assertRaises(ValueError):
            profile_store.luu_tuy_chon("profile_u", "   ", {})
        with self.assertRaises(ValueError):
            profile_store.luu_tuy_chon("profile_u", "User", {"email": "khong-phai-email"})
        with self.assertRaises(ValueError):
            profile_store.luu_tuy_chon("profile_u", "User", {"phone": "<script>alert(1)</script>"})

        ok = profile_store.luu_tuy_chon(
            "profile_u",
            "  Nguyễn\x00Văn A  ",
            {
                "email": "a@example.com",
                "phone": "0909 123 456",
                "goal": "Không hợp lệ",
                "servings": 999,
                "avoid": "ớt",
                "allergies": "tôm, cua\n",
                "health": ["Ho", "FakeCondition"],
                "notes": "Ghi chú\x07",
            },
        )
        self.assertTrue(ok)
        loaded = profile_store.doc_tuy_chon("profile_u")
        self.assertEqual(loaded["goal"], "Ăn uống cân bằng")
        self.assertEqual(loaded["servings"], 30)
        self.assertEqual(loaded["health"], ["Ho"])
        self.assertEqual(loaded["allergies"], "tôm, cua")
        self.assertNotIn("\x00", tk.doc_ho_so("profile_u")["ten_hien_thi"])

    def test_cau_hoi_cho_hoc_reads_real_tin_nhan_schema(self):
        self.assertTrue(tk.dang_ky("learner", "Learner", PASSWORD)[0])
        tk.luu_cuoc_tro_chuyen(
            "learner",
            None,
            [
                {"vai": "user", "noi_dung": "Cách làm bánh tét nhân chuối sáp ngon"},
                {"vai": "assistant", "cau_hoi": "Cách làm bánh tét nhân chuối sáp ngon", "ket_qua": {"loai": "khong_chac"}},
                {"vai": "user", "noi_dung": "Cách nấu canh chua cá lóc"},
                {"vai": "assistant", "cau_hoi": "Cách nấu canh chua cá lóc", "ket_qua": {"loai": "tra_loi"}},
            ],
        )
        with patch.object(cau_hoi_cho_hoc, "SQLITE_DB", self.folder / "chatbot.sqlite3"), \
             patch.object(cau_hoi_cho_hoc, "CHO_HOC_PATH", self.folder / "missing.jsonl"):
            pending = cau_hoi_cho_hoc.lay_danh_sach_cau_hoi_chua_biet()
        questions = [item["cau_hoi"] for item in pending]
        self.assertIn("Cách làm bánh tét nhân chuối sáp ngon", questions)
        self.assertNotIn("Cách nấu canh chua cá lóc", questions)

    def test_app_session_token_not_written_to_query_params_and_cookie_hardened(self):
        app_src = (ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
        self.assertNotIn('st.query_params["phien"] =', app_src)
        self.assertNotIn("importlib.reload(giao_dien_tro_chuyen)", app_src)
        self.assertIn("SameSite=Lax", app_src)
        self.assertIn("Secure", app_src)
        self.assertIn("tai_khoan.la_admin(TEN)", app_src)

    def test_bang_quan_tri_source_link_blocks_javascript_scheme(self):
        dummy_st = types.ModuleType("streamlit")
        dummy_st.cache_data = lambda **_: (lambda f: f)
        dummy_st.cache_resource = lambda **_: (lambda f: f)
        dummy_st.fragment = lambda **_: (lambda f: f)
        dummy_st.dialog = lambda *a, **k: (lambda f: f)
        with patch.dict(sys.modules, {"streamlit": dummy_st}):
            from frontend import bang_quan_tri
            safe_html = bang_quan_tri._o_nguon("javascript:alert(1)")
            self.assertNotIn("href=", safe_html)
            http_html = bang_quan_tri._o_nguon("Bài viết https://example.com/cong-thuc.")
            self.assertIn('href="https://example.com/cong-thuc"', http_html)

    def test_tu_hoc_rbac_enforcement_for_production_store(self):
        self.assertTrue(tk.dang_ky("normaluser", "User", PASSWORD)[0])
        self.assertTrue(tk.dang_ky("admin_ok", "Admin", PASSWORD)[0])
        self.assertTrue(tk.khoi_tao_admin_cuc_bo("admin_ok")[0])

        dummy_tu_hoc = types.ModuleType("backend.chatbot.tu_hoc")
        # Import the real function cleanly without requiring sentence_transformers/faiss if absent
        import ast
        src = (ROOT / "backend" / "chatbot" / "tu_hoc.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn_names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.assertIn("them_cau_hoi_moi", fn_names)
        self.assertIn("tai_khoan.la_admin(actor)", src)
        self.assertIn("PermissionError", src)
        # If faiss & sklearn are installed, execute the actual RBAC check live.
        try:
            from backend.chatbot import tu_hoc
            with patch.dict("os.environ", {"CHATBOT_STAGING_BUILD": ""}):
                with self.assertRaises(PermissionError):
                    tu_hoc.them_cau_hoi_moi("Câu hỏi test", "Câu trả lời test", actor="normaluser", kiem_tra_quyen=True)
        except ImportError:
            pass


class DatasetAndIntelligenceTests(unittest.TestCase):
    def test_dataset_jsonl_schema_and_medical_sync(self):
        ds_path = ROOT / "data" / "merged" / "dataset.jsonl"
        sieu_path = ROOT / "kho_vector" / "cau_truc_tat_ca" / "sieu_du_lieu.jsonl"
        rows = [json.loads(line) for line in ds_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 993)
        self.assertEqual(len({str(r["id"]) for r in rows}), 993)
        expected_keys = {"id", "group", "group_folder", "split", "question", "answer", "source"}
        self.assertTrue(all(set(r.keys()) == expected_keys for r in rows))

        sieu_map = {}
        for line in sieu_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                sieu_map.setdefault(str(d["id_goc"]), []).append(d)

        for idx in ("689", "799", "878", "906"):
            row = next(r for r in rows if str(r["id"]) == idx)
            sieu_text = "\n".join(c["noi_dung"] for c in sorted(sieu_map[idx], key=lambda x: x["thu_tu_doan"]))
            self.assertEqual(row["answer"], sieu_text)

    def test_intent_hot_path_smoothness_and_features(self):
        vocab = ("cá lóc", "cà chua", "bạc hà", "thịt heo")
        # Verify hot path avoids importing/running trich_xuat_thuc_the by default.
        with patch.dict(sys.modules, {"backend.chatbot.trich_xuat_thuc_the": MagicMock(side_effect=AssertionError("Must stay lazy"))}):
            t0 = time.perf_counter()
            for _ in range(50):
                p = phan_tich("Nhà có cá lóc và cà chua thì nấu món gì?", vocab)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0 / 50.0
        self.assertEqual(p["nguyen_lieu_co"], ["ca loc", "ca chua"])
        self.assertEqual(p["tu_khoa_chinh"], [])
        self.assertLess(elapsed_ms, 50.0)

        omit = phan_tich("Bỏ bạc hà khỏi món này rồi viết lại cách nấu", vocab)
        self.assertTrue(omit["bo_nguyen_lieu"])

    def test_nutrition_quant_and_bac_ha_allergy(self):
        dk_bac_ha = dieu_kien("Tôi dị ứng dọc mùng")
        self.assertIn("bạc hà", dk_bac_ha["loai_tru"])
        self.assertTrue(vi_pham("Canh chua gồm bạc hà 100g", dk_bac_ha))

        dk_quant = dieu_kien("Món này bao nhiêu kcal và đạm?")
        self.assertTrue(dk_quant["can_dinh_luong"])
        self.assertNotIn("giàu đạm", dk_quant["nhu_cau"])
        self.assertNotIn("giàu đạm", mo_rong_keyword("Món này bao nhiêu đạm?"))

    def test_health_recovery_and_cure_claim_guard(self):
        self.assertEqual(cap_nhat_suc_khoe(["bệnh dạ dày", "tiểu đường"], "Tôi hết đau dạ dày rồi"), ["tiểu đường"])
        self.assertTrue(la_cau_hoi_chua_benh("Ăn canh gà lá giang có chữa khỏi ho không?"))
        self.assertFalse(la_cau_hoi_chua_benh("Bị cảm cúm nên ăn gì cho mau khỏi"))

    def test_fix1_comma_and_semicolon_allergy_lists_not_truncated(self):
        dk_comma = dieu_kien("Tôi dị ứng tôm, đậu phộng")
        self.assertEqual(dk_comma["loai_tru"], ["tôm", "đậu phộng"])
        self.assertEqual(dk_comma["chua_ro"], [])

        p_comma = phan_tich("Tôi dị ứng tôm, đậu phộng")
        self.assertEqual(p_comma["di_ung"], ["tôm", "đậu phộng"])

        dk_semi = dieu_kien("Tôi dị ứng tôm; cua; sữa")
        self.assertEqual(dk_semi["loai_tru"], ["cua", "sữa", "tôm"])
        self.assertEqual(dk_semi["chua_ro"], [])

        dk_switch = dieu_kien("Tôi không ăn tôm, cách nấu canh chua cá lóc")
        self.assertEqual(dk_switch["loai_tru"], ["tôm"])
        self.assertEqual(dk_switch["chua_ro"], [])

    def test_fix2_mysql_schema_and_deletion_cleanup_and_no_runtime_ddl(self):
        ddl = (ROOT / "sql" / "bep_mien_tay.sql").read_text(encoding="utf-8")
        for tbl in ("gioi_han_dang_nhap", "tuy_chon_ho_so", "noi_dung_quan_tri"):
            self.assertIn(tbl, ddl)

        temp_db = tempfile.TemporaryDirectory(prefix="test_fix2_")
        self.addCleanup(temp_db.cleanup)
        db_file = Path(temp_db.name) / "chatbot.sqlite3"
        with patch.object(db, "FILE_DB", db_file), patch.object(db, "BACKEND", "sqlite"):
            self.assertTrue(tk.dang_ky("adm2", "Admin", PASSWORD)[0])
            self.assertTrue(tk.khoi_tao_admin_cuc_bo("adm2")[0])
            self.assertTrue(tk.dang_ky("deluser", "Del User", PASSWORD)[0])
            self.assertTrue(profile_store.luu_tuy_chon("deluser", "Del User", {"allergies": "tôm"}))
            tk.dang_nhap("deluser", "WrongPass1!")
            self.assertTrue(tk.admin_xoa_tai_khoan("adm2", "deluser")[0])
            with db.ket_noi() as con:
                self.assertIsNone(con.execute("SELECT 1 FROM tuy_chon_ho_so WHERE ten_dang_nhap=?", ("deluser",)).fetchone())
                self.assertIsNone(con.execute("SELECT 1 FROM gioi_han_dang_nhap WHERE khoa=?", ("deluser",)).fetchone())

        mock_con = MagicMock()
        with patch.object(db, "BACKEND", "mysql"):
            tk._dam_bao_bang_gioi_han(mock_con)
            profile_store.khoi_tao_tuy_chon(mock_con)
        mock_con.execute.assert_not_called()

    def test_fix3_chay_web_mysql_no_hardcoded_missing_staging_shadow(self):
        src = (ROOT / "scripts" / "chay_web_mysql.py").read_text(encoding="utf-8")
        self.assertNotIn("release_candidate_20261118_m5_v9", src)
        self.assertNotIn("CHATBOT_STAGING_BUILD", src)

    def test_fix4_tu_hoc_blocks_external_path_rbac_bypass(self):
        from backend.chatbot import tu_hoc
        temp_dir = tempfile.TemporaryDirectory(prefix="test_fix4_db_")
        ext_store = tempfile.TemporaryDirectory(prefix="test_fix4_ext_")
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(ext_store.cleanup)
        with patch.object(db, "FILE_DB", Path(temp_dir.name) / "chatbot.sqlite3"), \
             patch.object(db, "BACKEND", "sqlite"), \
             patch.dict("os.environ", {"CHATBOT_STAGING_BUILD": ""}):
            self.assertTrue(tk.dang_ky("user4", "User", PASSWORD)[0])
            self.assertTrue(tk.dang_ky("adm4", "Admin", PASSWORD)[0])
            self.assertTrue(tk.khoi_tao_admin_cuc_bo("adm4")[0])
            with self.assertRaises(PermissionError):
                tu_hoc.them_cau_hoi_moi("Câu hỏi", "Câu trả lời", actor="user4", kho_rel=ext_store.name)
            with self.assertRaises(ValueError):
                tu_hoc.them_cau_hoi_moi("Câu hỏi", "Câu trả lời", actor="adm4", kho_rel=ext_store.name)

    def test_fix5_cau_hoi_cho_hoc_uses_shared_db_connector(self):
        temp_db = tempfile.TemporaryDirectory(prefix="test_fix5_")
        self.addCleanup(temp_db.cleanup)
        db_file = Path(temp_db.name) / "chatbot.sqlite3"
        with patch.object(db, "FILE_DB", db_file), \
             patch.object(db, "BACKEND", "sqlite"), \
             patch.object(cau_hoi_cho_hoc, "CHO_HOC_PATH", Path(temp_db.name) / "missing.jsonl"):
            self.assertTrue(tk.dang_ky("user5", "User 5", PASSWORD)[0])
            tk.luu_cuoc_tro_chuyen(
                "user5",
                None,
                [
                    {"vai": "user", "noi_dung": "Cách nấu chè bắp nếp miền Tây"},
                    {"vai": "assistant", "cau_hoi": "Cách nấu chè bắp nếp miền Tây", "ket_qua": {"loai": "khong_chac"}},
                ],
            )
            pending = cau_hoi_cho_hoc.lay_danh_sach_cau_hoi_chua_biet()
            self.assertTrue(any(p["cau_hoi"] == "Cách nấu chè bắp nếp miền Tây" for p in pending))

    def test_fix6_input_length_signup_limits_and_chat_cap(self):
        from backend.chatbot.hoi_thoai import MAX_QUESTION_CHARS, tra_loi_co_trang_thai
        res = tra_loi_co_trang_thai("x " * (MAX_QUESTION_CHARS + 50))
        self.assertEqual(res["loai"], "khong_chac")
        self.assertIn("quá dài", res["cau_tra_loi"])

        temp_db = tempfile.TemporaryDirectory(prefix="test_fix6_")
        self.addCleanup(temp_db.cleanup)
        db_file = Path(temp_db.name) / "chatbot.sqlite3"
        with patch.object(db, "FILE_DB", db_file), \
             patch.object(db, "BACKEND", "sqlite"), \
             patch.object(tk, "MAX_SIGNUP_ATTEMPTS", 2):
            self.assertFalse(tk.dang_ky("longdisp", "A" * 101, PASSWORD)[0])
            self.assertTrue(tk.dang_ky("sig1", "User 1", PASSWORD)[0])
            self.assertTrue(tk.dang_ky("sig2", "User 2", PASSWORD)[0])
            ok3, msg3 = tk.dang_ky("sig3", "User 3", PASSWORD)
            self.assertFalse(ok3)
            self.assertIn("quá nhanh", msg3)

            long_msgs = [{"vai": "user", "noi_dung": f"Tin nhắn {i}"} for i in range(210)]
            cid = tk.luu_cuoc_tro_chuyen("sig1", None, long_msgs)
            saved = tk.danh_sach_cuoc_tro_chuyen("sig1")[0]
            self.assertEqual(saved["ma"], cid)
            self.assertEqual(len(saved["tin_nhan"]), tk.MAX_CHAT_MESSAGES)
            self.assertEqual(saved["tin_nhan"][0]["noi_dung"], "Tin nhắn 10")

    def test_fix7_mysql_cursor_closed_and_retrieval_mode_allowlist(self):
        from backend.chatbot.co_so_du_lieu_mysql import KetNoi

        fake_cursor = MagicMock()
        fake_cursor.description = [("ten",)]
        fake_cursor.fetchall.return_value = [{"ten": "Admin"}]
        fake_con = MagicMock()
        fake_con.cursor.return_value = fake_cursor

        kq = KetNoi(fake_con).execute("SELECT ? AS ten", ("Admin",))
        fake_cursor.close.assert_called_once()
        self.assertEqual(kq.fetchone()["ten"], "Admin")
        self.assertIsNone(kq.fetchone())

        dl_src = (ROOT / "frontend" / "du_lieu_tim_kiem_admin.py").read_text(encoding="utf-8")
        self.assertIn("if mode not in MODES:", dl_src)
        self.assertIn("ghi_nhat_ky_quan_tri", dl_src)
        self.assertIn("if not tai_khoan.la_admin(actor):", dl_src)


if __name__ == "__main__":
    unittest.main()
