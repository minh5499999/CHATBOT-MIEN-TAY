"""Hệ truy hồi (Bài 4 – Phần III): tìm các đoạn liên quan tới câu hỏi trong kho vector FAISS.

Các bước: chuẩn hóa câu hỏi bằng đúng hàm đã dùng khi dựng kho → sinh vector → lọc theo siêu dữ liệu
→ lấy candidate_k ứng viên (vector, hoặc vector + BM25 kết hợp bằng RRF) → gộp đoạn cùng id_goc
→ giữ k → đánh dấu ngoài phạm vi nếu điểm cao nhất dưới ngưỡng.

Thử nhanh: python -m backend.chatbot.truy_hoi "món canh chua cá lóc"
"""
import json
import logging
import math
import re
import sys
import unicodedata
from collections import Counter
from functools import lru_cache

import numpy as np

from backend.chatbot.cau_hinh import ROOT, doc_cau_hinh
from backend.chatbot.mo_hinh_vector import chuan_bi_cau_hoi, sinh_vector

DAU_CAU = re.compile(r"^[^\w]+$")
AM_TIET = re.compile(r"\w+")
SO_TIM_VECTOR = 100  # số đoạn lấy từ chỉ mục vector khi không lọc (≥ candidate_k = 20, dư cho bước gộp id_goc)


# ------------------------------------------------------------------ nạp kho

def thu_muc_kho(cach_cat=None, tap="tat_ca"):
    """Không chỉ định cách cắt → dùng kho trong cấu hình; có → kho_vector/<cach>_<tap>."""
    if cach_cat is None:
        return ROOT / doc_cau_hinh()["kho_vector"]
    return ROOT / doc_cau_hinh()["thu_muc_kho"] / f"{cach_cat}_{tap}"


@lru_cache(maxsize=8)
def nap_kho(thu_muc):
    """Nạp kho một lần (không dựng lại mỗi lần chạy). Trả về (index, siêu dữ liệu, thông tin).

    Cấu hình kho_tim_kiem = "neo4j" → đọc kho trong Neo4j; Neo4j chưa bật / chưa nạp kho này → đọc FAISS trên đĩa.
    """
    if doc_cau_hinh().get("kho_tim_kiem") == "neo4j":
        try:
            from backend.chatbot import kho_neo4j
            kq = kho_neo4j.nap_kho(thu_muc)
            if kq:
                return kq
            logging.getLogger(__name__).warning("Neo4j chưa có kho %s (chạy scripts/nap_neo4j.py), dùng FAISS",
                                                thu_muc)
        except Exception as e:
            logging.getLogger(__name__).warning("Không dùng được Neo4j (%s), dùng FAISS trên đĩa", e)
    import faiss
    thu_muc = ROOT / thu_muc
    if not (thu_muc / "index.faiss").exists():
        raise FileNotFoundError(f"Chưa có kho vector ở {thu_muc}. Chạy: python scripts/tao_kho_vector.py")
    index = faiss.deserialize_index(np.frombuffer((thu_muc / "index.faiss").read_bytes(), dtype=np.uint8))
    sieu = [json.loads(dong) for dong in (thu_muc / "sieu_du_lieu.jsonl").read_text(encoding="utf-8").splitlines()]
    thong_tin = json.loads((thu_muc / "thong_tin.json").read_text(encoding="utf-8")) | {"may_tim": "faiss"}
    if index.ntotal != len(sieu):
        raise ValueError(f"Kho {thu_muc.name} hỏng: {index.ntotal} vector nhưng {len(sieu)} dòng siêu dữ liệu")
    return index, sieu, thong_tin


# ------------------------------------------------------------------ BM25 viết tay

def tu_bm25(van_ban_tach_tu):
    """Bản đã tách từ → danh sách từ viết thường, bỏ token chỉ gồm dấu câu. Giữ nguyên số như 2,8."""
    return [t for t in van_ban_tach_tu.lower().split() if not DAU_CAU.match(t)]


def bo_dau(van_ban):
    """Bỏ dấu tiếng Việt: "Cá lóc kho" → "Ca loc kho"."""
    khong = "".join(c for c in unicodedata.normalize("NFD", van_ban) if unicodedata.category(c) != "Mn")
    return khong.replace("đ", "d").replace("Đ", "D")


def la_khong_dau(van_ban):
    """Câu có chữ nhưng không có ký tự nào mang dấu tiếng Việt (người dùng gõ không dấu)."""
    return bool(AM_TIET.search(van_ban)) and bo_dau(van_ban) == van_ban and len(van_ban.split()) >= 2


def tu_khong_dau(van_ban):
    """Âm tiết không dấu viết thường + cặp âm tiết liền nhau (thay cho tách từ, vốn hỏng khi mất dấu)."""
    am = AM_TIET.findall(bo_dau(van_ban).lower().replace("_", " "))
    return am + [f"{a}_{b}" for a, b in zip(am, am[1:])]


class BM25:
    """Okapi BM25 trên các đoạn đã tách từ (k1, b lấy từ cấu hình)."""

    def __init__(self, tai_lieu, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in tai_lieu]
        self.do_dai = np.array([len(d) for d in tai_lieu], dtype=np.float32)
        self.tb_do_dai = float(self.do_dai.mean()) if len(tai_lieu) else 0.0
        df = Counter(t for d in self.tf for t in d)
        n = len(tai_lieu)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def diem(self, tu_hoi):
        kq = np.zeros(len(self.tf), dtype=np.float32)
        chuan = self.k1 * (1 - self.b + self.b * self.do_dai / max(self.tb_do_dai, 1e-9))
        for t in set(tu_hoi):
            if t not in self.idf:
                continue
            f = np.array([d.get(t, 0) for d in self.tf], dtype=np.float32)
            kq += self.idf[t] * f * (self.k1 + 1) / (f + chuan)
        return kq

    def diem_chuan_hoa(self, tu_hoi):
        """Điểm BM25 chia cho cận trên (tổng idf·(k1+1) của các từ hỏi) → nằm trong [0, 1),
        để dùng chung kiểu ngưỡng với cosine. Không từ nào có trong kho → toàn 0."""
        tran = sum(self.idf[t] * (self.k1 + 1) for t in set(tu_hoi) if t in self.idf)
        return self.diem(tu_hoi) / tran if tran else np.zeros(len(self.tf), dtype=np.float32)


@lru_cache(maxsize=8)
def nap_bm25(thu_muc):
    ch = doc_cau_hinh()
    _, sieu, _ = nap_kho(thu_muc)
    return BM25([tu_bm25(d["noi_dung_kem_tieu_de_tach_tu"]) for d in sieu],
                ch.get("bm25_k1", 1.5), ch.get("bm25_b", 0.75))


@lru_cache(maxsize=8)
def nap_bm25_khong_dau(thu_muc):
    """Chỉ mục phụ không dấu (Bài 5) cho câu hỏi gõ không dấu."""
    ch = doc_cau_hinh()
    _, sieu, _ = nap_kho(thu_muc)
    return BM25([tu_khong_dau(d["noi_dung_kem_tieu_de"]) for d in sieu],
                ch.get("bm25_k1", 1.5), ch.get("bm25_b", 0.75))


# ------------------------------------------------------------------ truy hồi

def _xep_hang(diem, mask, n):
    """Chỉ số của n điểm cao nhất trong các đoạn qua bộ lọc (sắp giảm dần, hòa thì theo thứ tự kho)."""
    ung_vien = np.flatnonzero(mask)
    thu_tu = ung_vien[np.argsort(-diem[ung_vien], kind="stable")]
    return thu_tu[:n].tolist()


def _gop_theo_id_goc(ket_qua):
    """Gộp các đoạn cùng câu hỏi gốc thành một mục, nối nội dung theo thu_tu_doan, điểm = điểm cao nhất."""
    nhom, thu_tu = {}, []
    for d in ket_qua:
        if d["id_goc"] not in nhom:
            nhom[d["id_goc"]] = []
            thu_tu.append(d["id_goc"])
        nhom[d["id_goc"]].append(d)
    gop = []
    for id_goc in thu_tu:
        cac_doan = sorted(nhom[id_goc], key=lambda d: d["thu_tu_doan"])
        dau = dict(max(cac_doan, key=lambda d: d["diem"]))
        if len(cac_doan) > 1:
            dau["noi_dung"] = "\n".join(d["noi_dung"] for d in cac_doan)
            dau["ten_muc"] = " + ".join(d["ten_muc"] for d in cac_doan if d["ten_muc"])
        dau["chunk_ids"] = [d["chunk_id"] for d in cac_doan]
        gop.append(dau)
    return gop


def truy_hoi(cau_hoi, k=None, loc_nhom=None, loc_tap=None, nguong_diem=None,
             che_do=None, gop_theo_id_goc=None, kho=None):
    """Tìm các đoạn liên quan. Tham số để None thì lấy từ cau_hinh/chatbot.json.

    che_do: "vector" (cosine), "lai" (vector + BM25 kết hợp RRF, điểm hiển thị vẫn là cosine)
            hoặc "bm25" (chỉ BM25 chuẩn hóa, KHÔNG dùng mô hình vector).
            Câu hỏi gõ không dấu luôn tự chuyển sang "khong_dau" (BM25 trên chỉ mục phụ không dấu).
    loc_nhom: danh sách nhom_folder (ví dụ ["03_huong_dan_nau_mon_mien_tay"]); loc_tap: ["Train"] / ["Test"].
    Trả về dict: doan (list đoạn kèm diem, xep_hang, siêu dữ liệu), ngoai_pham_vi, diem_cao_nhat,
    nguong / nguong_tin_cay (theo chế độ), cau_hoi_sach (sau tiền xử lý), cau_hoi_vao_mo_hinh (sau tách từ).
    """
    ch = doc_cau_hinh()
    k = k or ch["k"]
    che_do = che_do or ch["che_do_truy_hoi"]
    if la_khong_dau(cau_hoi):
        che_do = "khong_dau"
    bo_nguong = ch["nguong"][che_do if che_do in ("bm25", "khong_dau") else "vector"]
    nguong = bo_nguong["ngoai_pham_vi"] if nguong_diem is None else nguong_diem
    gop = ch["gop_theo_id_goc"] if gop_theo_id_goc is None else gop_theo_id_goc
    # khóa bộ đệm nap_kho luôn dùng "/" (str(Path) trên Windows ra "\" → nạp kho hai lần)
    thu_muc = kho if isinstance(kho, str) else (kho or thu_muc_kho()).relative_to(ROOT).as_posix()

    index, sieu, thong_tin = nap_kho(thu_muc)
    sach, vao = chuan_bi_cau_hoi(cau_hoi)
    tu_hoi = tu_bm25(vao)

    # chấm điểm MỌI đoạn (tìm vét cạn, kho chỉ ~1–3 nghìn đoạn) rồi lọc theo siêu dữ liệu
    if che_do == "bm25":
        diem = nap_bm25(thu_muc).diem_chuan_hoa(tu_hoi)
    elif che_do == "khong_dau":
        diem = nap_bm25_khong_dau(thu_muc).diem_chuan_hoa(tu_khong_dau(cau_hoi))
    else:
        # chế độ vector không lọc chỉ cần top candidate_k → lấy 100 đoạn đầu là đủ (Neo4j nhanh gấp ~4 lần);
        # có lọc hoặc chế độ lai (điểm hiển thị cosine của cả ứng viên BM25) thì vẫn chấm mọi đoạn
        so_tim = index.ntotal if (loc_nhom or loc_tap or che_do == "lai") else min(index.ntotal, SO_TIM_VECTOR)
        d, i = index.search(sinh_vector([vao]), so_tim)
        diem = np.full(index.ntotal, -1.0, dtype=np.float32)  # đoạn ngoài top so_tim: cosine thấp nhất
        diem[i[0]] = d[0]
    mask = np.array([(not loc_nhom or s["nhom_folder"] in loc_nhom) and (not loc_tap or s["tap"] in loc_tap)
                     for s in sieu])

    if che_do == "khong_dau":
        # câu chào rất ngắn nên BM25 không dấu ưu tiên quá mức; lời chào đã có quy tắc nhận diện riêng
        mask &= np.array([s["nhom_folder"] != "01_chao_hoi" for s in sieu])

    candidate_k = max(ch["candidate_k"], k)
    hang_vector = _xep_hang(diem, mask, candidate_k)
    if che_do == "lai":
        hang_bm25 = _xep_hang(nap_bm25(thu_muc).diem(tu_hoi), mask, candidate_k)
        rrf, w_v, w_b = Counter(), ch.get("trong_so_vector", 1.0), ch.get("trong_so_bm25", 1.0)
        for w, hang in ((w_v, hang_vector), (w_b, hang_bm25)):
            for r, idx in enumerate(hang, 1):
                rrf[idx] += w / (ch["rrf_k"] + r)
        thu_tu = sorted(rrf, key=lambda idx: (-rrf[idx], idx))[:candidate_k]
    else:
        rrf, thu_tu = {}, hang_vector

    ket_qua = [dict(sieu[idx], diem=round(float(diem[idx]), 4),
                    **({"diem_rrf": round(rrf[idx], 5)} if rrf else {})) for idx in thu_tu]
    if gop:
        ket_qua = _gop_theo_id_goc(ket_qua)
    ket_qua = ket_qua[:k]
    for r, doan in enumerate(ket_qua, 1):
        doan["xep_hang"] = r

    diem_cao_nhat = max((x["diem"] for x in ket_qua), default=0.0)
    return {
        "doan": ket_qua,
        "ngoai_pham_vi": diem_cao_nhat < nguong,
        "diem_cao_nhat": diem_cao_nhat,
        "nguong": nguong,
        "nguong_tin_cay": bo_nguong["tin_cay"],
        "cau_hoi_sach": sach,
        "cau_hoi_vao_mo_hinh": vao,
        "che_do_truy_hoi": che_do,
        "kho": thu_muc,
        "may_tim": getattr(index, "may_tim", thong_tin["may_tim"]),  # "neo4j" hoặc "faiss": nơi thật sự đã tìm
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    import argparse
    p = argparse.ArgumentParser(description="Thử truy hồi một câu hỏi")
    p.add_argument("cau_hoi")
    p.add_argument("--k", type=int)
    p.add_argument("--che_do", choices=["vector", "lai", "bm25"])
    p.add_argument("--cach", choices=["cau_truc", "co_dinh", "de_quy"])
    a = p.parse_args()
    kq = truy_hoi(a.cau_hoi, k=a.k, che_do=a.che_do, kho=thu_muc_kho(a.cach) if a.cach else None)
    print(f"Câu hỏi đưa vào mô hình: {kq['cau_hoi_vao_mo_hinh']}")
    print(f"Kho: {kq['kho']} | chế độ: {kq['che_do_truy_hoi']} | ngoài phạm vi: {kq['ngoai_pham_vi']}")
    for d in kq["doan"]:
        print(f"{d['xep_hang']}. [{d['diem']:.4f}] ID {d['id_goc']} · {d['nhom_folder']} · {d['cau_hoi']}"
              f"{' · ' + d['ten_muc'] if d['ten_muc'] else ''}")


if __name__ == "__main__":
    main()
