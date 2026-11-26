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
from backend.chatbot.knowledge_policy import store_cache

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
def _nap_kho_cached(thu_muc):
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
    from backend.chatbot.knowledge_policy import check_rows
    check_rows(thu_muc.relative_to(ROOT).as_posix(), sieu)
    return index, sieu, thong_tin


def nap_kho(thu_muc):
    from backend.chatbot.knowledge_policy import policy
    policy(thu_muc)  # validate even when cached index/catalog already exists
    return _nap_kho_cached(thu_muc)

nap_kho.cache_clear = _nap_kho_cached.cache_clear


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


@store_cache(maxsize=8)
def nap_bm25(thu_muc):
    ch = doc_cau_hinh()
    _, sieu, _ = nap_kho(thu_muc)
    return BM25([tu_bm25(d["noi_dung_kem_tieu_de_tach_tu"]) for d in sieu],
                ch.get("bm25_k1", 1.5), ch.get("bm25_b", 0.75))


@store_cache(maxsize=8)
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


def _recipe_mask(sieu, eligible, question, positive, store):
    from backend.chatbot.knowledge_policy import policy
    from backend.chatbot.ngon_ngu import co_cum, dieu_kien
    from backend.chatbot.nhan_dien_mon import CACH_NAU, dac_trung_mon, dung_dac_trung, dung_ten_mon, nhan_dien_mon
    from backend.chatbot.recipe_views_v5 import _check_recipe, _surface_score

    from backend.chatbot.fuzzy import _spellings

    explicit = any(forms-{key} for key,forms in _spellings(question).items())
    conditions = dieu_kien(question)
    restricted = any(conditions[field] for field in ('loai_tru','chua_ro','an_chay','nhu_cau','can_dinh_luong'))
    features = dac_trung_mon(positive)
    dish = nhan_dien_mon(positive)
    methods = [method for method in CACH_NAU if co_cum(positive,method)]
    # Only enforce identity for a clear request. Lists and alternatives
    # still go through the existing recipe and dialogue validators.
    compare = re.search(r'\b(?:hoac|hay la|so sanh|khac nhau|thay the|thay bang)\b',bo_dau(positive).lower())
    name_filter = not compare and (dish or (len(features)==1 and len(methods)==1))
    knowledge = policy(store) if restricted or name_filter else None
    ledger = knowledge[1] if knowledge else {}
    recipe_groups = {'02_huong_dan_nau_an','03_huong_dan_nau_mon_mien_tay'}
    decisions = {}
    mask = np.ones(len(sieu),dtype=bool)
    for i in np.flatnonzero(eligible):
        row = sieu[i]
        if row['nhom_folder'] not in recipe_groups:
            continue
        rid = row['id_goc']
        if rid not in decisions:
            title = row['cau_hoi']
            accepted = not explicit or _surface_score(question,title)>=0
            if accepted and name_filter:
                source = ledger.get(rid,{}).get('answer_text',row['noi_dung_kem_tieu_de'])
                accepted = (dung_ten_mon(title,dish)
                            and dung_dac_trung(title,source,features)
                            and (len(methods)!=1 or co_cum(title,methods[0])))
            if accepted and restricted and rid in ledger:
                accepted = not conditions['can_dinh_luong'] and not _check_recipe(
                    ledger[rid],{'dieu_kien':conditions}
                )[0]
            decisions[rid] = accepted
        mask[i] = decisions[rid]
    return mask


def _rrf_order(channels, metadata, group, candidate_k, rank_constant, lexical_priority=None):
    fused = Counter()
    chunks = {}
    for weight, ranking in channels:
        seen = set()
        for idx in ranking:
            item = metadata[idx]['id_goc'] if group else idx
            chunks.setdefault(item,{})[idx] = None
            if item not in seen:
                seen.add(item)
                fused[item] += weight/(rank_constant+len(seen))
    def order(item):
        lexical = max(lexical_priority[idx] for idx in chunks[item]) if lexical_priority is not None else 0
        return -lexical,-fused[item],next(iter(chunks[item]))
    ranked = sorted(fused,key=order)[:candidate_k]
    order = [idx for item in ranked for idx in chunks[item]]
    return {idx:fused[item] for item in ranked for idx in chunks[item]},order


def truy_hoi(cau_hoi, k=None, loc_nhom=None, loc_tap=None, nguong_diem=None,
             che_do=None, gop_theo_id_goc=None, kho=None):
    """Tìm các đoạn liên quan. Tham số để None thì lấy từ cau_hinh/chatbot.json.

    che_do: "vector" (cosine), "lai" (vector + BM25 kết hợp RRF, điểm hiển thị vẫn là cosine)
            hoặc "bm25" (chỉ BM25 chuẩn hóa, KHÔNG dùng mô hình vector).
            Hybrid giữ BM25 làm thứ tự chính cho câu không dấu và dùng vector khi các điểm đầu hòa.
    loc_nhom: danh sách nhom_folder (ví dụ ["03_huong_dan_nau_mon_mien_tay"]); loc_tap: ["Train"] / ["Test"].
    Trả về dict: doan (list đoạn kèm diem, xep_hang, siêu dữ liệu), ngoai_pham_vi, diem_cao_nhat,
    nguong / nguong_tin_cay (theo chế độ), cau_hoi_sach (sau tiền xử lý), cau_hoi_vao_mo_hinh (sau tách từ).
    """
    ch = doc_cau_hinh()
    k = k or ch["k"]
    che_do = che_do or ch["che_do_truy_hoi"]
    khong_dau = la_khong_dau(cau_hoi)
    if khong_dau and che_do == "bm25":
        che_do = "khong_dau"
    gop = ch["gop_theo_id_goc"] if gop_theo_id_goc is None else gop_theo_id_goc
    thu_muc = kho if isinstance(kho, str) else (kho or thu_muc_kho()).relative_to(ROOT).as_posix()
    index, sieu, thong_tin = nap_kho(thu_muc)

    from backend.chatbot.ngon_ngu import _positive_surface
    ranking_question = re.sub(r'\bđừng(?=\s+(?:ăn|dùng|thêm|cho)\b)','không',cau_hoi,flags=re.I)
    positive = ' '.join(_positive_surface(ranking_question,omit_allergy=True).split())
    has_query = bool(AM_TIET.search(positive))
    sach, vao = chuan_bi_cau_hoi(positive)
    tu_hoi = tu_bm25(vao)
    mask = np.array([(not loc_nhom or row["nhom_folder"] in loc_nhom)
                     and (not loc_tap or row["tap"] in loc_tap) for row in sieu],dtype=bool)
    mask &= has_query
    if khong_dau:
        mask &= np.array([row["nhom_folder"]!="01_chao_hoi" for row in sieu],dtype=bool)
    if mask.any():
        mask &= _recipe_mask(sieu,mask,ranking_question,positive,thu_muc)

    lexical = None
    if che_do=="lai" and khong_dau and mask.any():
        lexical = nap_bm25_khong_dau(thu_muc).diem(tu_khong_dau(positive))
        leaders = {}
        for idx in _xep_hang(lexical,mask & (lexical>0),len(sieu)):
            item = sieu[idx]['id_goc'] if gop else idx
            leaders.setdefault(item,lexical[idx])
            if len(leaders)>=k+1:
                break
        scores = list(leaders.values())
        # The encoder is trained on accented Vietnamese. Use it to break
        # lexical ties, while keeping distinct unaccented BM25 scores ordered.
        if not any(left==right for left,right in zip(scores,scores[1:])):
            che_do = "khong_dau"

    bo_nguong = ch["nguong"][che_do if che_do in ("bm25","khong_dau") else "vector"]
    nguong = bo_nguong["ngoai_pham_vi"] if nguong_diem is None else nguong_diem
    if not mask.any():
        diem = np.zeros(index.ntotal,dtype=np.float32)
    elif che_do=="bm25":
        diem = nap_bm25(thu_muc).diem_chuan_hoa(tu_hoi)
    elif che_do=="khong_dau":
        diem = nap_bm25_khong_dau(thu_muc).diem_chuan_hoa(tu_khong_dau(positive))
    else:
        so_tim = index.ntotal if (loc_nhom or loc_tap or che_do=="lai" or not mask.all()) else min(index.ntotal,SO_TIM_VECTOR)
        d,i = index.search(sinh_vector([vao]),so_tim)
        diem = np.full(index.ntotal,-1.0,dtype=np.float32)
        valid = (i[0]>=0) & (i[0]<index.ntotal)
        diem[i[0][valid]] = d[0][valid]
    if che_do in ("bm25","khong_dau"):
        mask &= diem>0

    candidate_k = max(ch["candidate_k"], k)
    hang_vector = _xep_hang(diem, mask, candidate_k)
    if che_do == "lai":
        if lexical is None:
            lexical = nap_bm25(thu_muc).diem(tu_hoi) if mask.any() else np.zeros(len(sieu),dtype=np.float32)
        hang_bm25 = _xep_hang(lexical,mask & (lexical>0),candidate_k)
        rrf,thu_tu = _rrf_order(
            ((ch.get('trong_so_vector',1.0),hang_vector),(ch.get('trong_so_bm25',1.0),hang_bm25)),
            sieu,gop,candidate_k,ch['rrf_k'],lexical if khong_dau else None,
        )
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
