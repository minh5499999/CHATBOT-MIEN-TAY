"""Đánh giá chatbot (Bài 4 – Phần V, Bài 7). Chatbot không dùng mô hình sinh: câu trả lời = nguyên văn
câu trả lời gốc của câu hỏi khớp nhất, nên đánh giá tập trung vào truy hồi và ngưỡng từ chối.

Bộ câu (data/kiem_thu/, đáp án viết trước khi chạy):
  - 198 câu Test (nằm nguyên văn trong kho → cận trên);
  - dien_dat_lai.tsv: câu hỏi viết lại theo cách người dùng thật hỏi (+ bản không dấu sinh tự động);
  - noi_tiep.tsv: hội thoại 2 lượt;  ngoai_pham_vi.txt;  khong_co_du_lieu.txt.

  1. Truy hồi: Hit@1/3/5, MRR@5, Nhóm đúng@1, độ trễ P50/P90/P95 cho 3 cách cắt × 3 cách tìm.
  2. Chọn ngưỡng (Youden J) và đo từ chối hai chiều.
  3. Hội thoại nối tiếp.
  4. Câu trả lời cuối trên kho <cach>_Train (đáp án Test không có trong kho): ROUGE-L, cosine.
  Xuất: reports/danh_gia_chatbot.md, reports/danh_gia_chi_tiet.csv, reports/cham_tay.csv

Chạy:  python scripts/danh_gia.py                 (đủ bộ câu)
       python scripts/danh_gia.py --gioi_han 30   (chạy thử 30 câu Test)
       python scripts/danh_gia.py --ghi_cau_hinh  (ghi cấu hình đề xuất vào cau_hinh/chatbot.json)
"""
import argparse
import csv
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.chatbot.cau_hinh import CAU_HINH_PATH, doc_cau_hinh, doc_cau_hinh_cat_doan  # noqa: E402
from backend.chatbot.mo_hinh_vector import _bo_tach_tu, sinh_vector  # noqa: E402
from backend.chatbot.sinh_cau_tra_loi import noi_dung_day_du, tra_loi  # noqa: E402
from backend.chatbot.truy_hoi import bo_dau, thu_muc_kho, truy_hoi  # noqa: E402

CACH_CAT = ["cau_truc", "co_dinh", "de_quy"]
CACH_TIM = ["vector", "lai", "bm25"]
KIEM_THU = ROOT / "data" / "kiem_thu"
REPORTS = ROOT / "reports"
SEED = 42


# ------------------------------------------------------------------ dữ liệu

def doc_cau_test(gioi_han=None):
    """Câu hỏi Test (mỗi id_goc một câu) kèm nhóm và đáp án gốc đầy đủ."""
    dong = [json.loads(x) for x in (ROOT / "data/doan/doan_cau_truc.jsonl").read_text(encoding="utf-8").splitlines()]
    theo_id, nhom_cua = {}, {}
    for d in dong:
        nhom_cua[d["id_goc"]] = d["nhom_folder"]
        if d["tap"] == "Test":
            theo_id.setdefault(d["id_goc"], []).append(d)
    cau = [{"id_goc": i, "cau_hoi": ds[0]["cau_hoi"], "nhom": ds[0]["nhom_folder"],
            "dap_an": "\n".join(x["noi_dung"] for x in sorted(ds, key=lambda x: x["thu_tu_doan"]))}
           for i, ds in sorted(theo_id.items())]
    if gioi_han:
        cau = random.Random(SEED).sample(cau, min(gioi_han, len(cau)))
    return cau, nhom_cua


def doc_tsv(ten):
    dong = [x for x in (KIEM_THU / ten).read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
    cot = dong[0].split("\t")
    return [dict(zip(cot, x.split("\t"))) for x in dong[1:]]


def doc_danh_sach(ten):
    return [x.strip() for x in (KIEM_THU / ten).read_text(encoding="utf-8").splitlines()
            if x.strip() and not x.startswith("#")]


# ------------------------------------------------------------------ chỉ số

def phan_vi(gia_tri, p):
    return float(np.percentile(gia_tri, p)) if gia_tri else 0.0


def chi_so_truy_hoi(ket_qua):
    n = len(ket_qua)
    hang = [r["hang_dung"] for r in ket_qua]
    tg = [r["thoi_gian_ms"] for r in ket_qua]
    return {
        "n": n,
        "hit1": sum(h == 1 for h in hang) / n,
        "hit3": sum(h is not None and h <= 3 for h in hang) / n,
        "hit5": sum(h is not None and h <= 5 for h in hang) / n,
        "mrr5": sum(1 / h for h in hang if h is not None and h <= 5) / n,
        "nhom1": sum(r["nhom_top1"] == r["nhom"] for r in ket_qua) / n,
        "p50": phan_vi(tg, 50), "p90": phan_vi(tg, 90), "p95": phan_vi(tg, 95),
    }


def rouge_l(du_doan, dap_an):
    """ROUGE-L F1 trên từ (viết thường), LCS quy hoạch động."""
    a, b = du_doan.lower().split(), dap_an.lower().split()
    if not a or not b:
        return 0.0
    truoc = [0] * (len(b) + 1)
    for x in a:
        hien = [0]
        for j, y in enumerate(b, 1):
            hien.append(truoc[j - 1] + 1 if x == y else max(truoc[j], hien[j - 1]))
        truoc = hien
    lcs = truoc[-1]
    if lcs == 0:
        return 0.0
    p, r = lcs / len(a), lcs / len(b)
    return 2 * p * r / (p + r)


def chon_nguong(chap_nhan, tu_choi):
    """Ngưỡng t tối đa hóa J = tỉ lệ chap_nhan ≥ t + tỉ lệ tu_choi < t − 1 (Youden). Hòa → t nhỏ hơn."""
    if not chap_nhan or not tu_choi:
        return (min(chap_nhan) if chap_nhan else 0.0), 0.0
    tot, t_tot = -2, 0.0
    for t in sorted(set(round(x, 3) for x in chap_nhan + tu_choi)):
        j = np.mean([x >= t for x in chap_nhan]) + np.mean([x < t for x in tu_choi]) - 1
        if j > tot + 1e-9:
            tot, t_tot = j, t
    return t_tot, float(tot)


# ------------------------------------------------------------------ chạy

def chay_truy_hoi(cau, kho, che_do):
    """cau: [{id_goc, cau_hoi, nhom}] → kết quả từng câu (hạng của đáp án đúng trong top-5, điểm top-1...)."""
    ket_qua = []
    for c in cau:
        t0 = time.perf_counter()
        tr = truy_hoi(c["cau_hoi"], k=5, kho=kho, che_do=che_do, gop_theo_id_goc=True)
        ms = (time.perf_counter() - t0) * 1000
        ids = [d["id_goc"] for d in tr["doan"]]
        ket_qua.append({
            **{k: c[k] for k in ("id_goc", "cau_hoi", "nhom")},
            "hang_dung": ids.index(c["id_goc"]) + 1 if c["id_goc"] in ids else None,
            "top3": [(d["id_goc"], d["cau_hoi"], d["diem"]) for d in tr["doan"][:3]],
            "nhom_top1": tr["doan"][0]["nhom_folder"] if tr["doan"] else None,
            "diem_top1": tr["diem_cao_nhat"], "thoi_gian_ms": ms,
        })
    return ket_qua


def diem_top1(cau_hoi_list, kho, che_do):
    return [truy_hoi(q, k=1, kho=kho, che_do=che_do)["diem_cao_nhat"] for q in cau_hoi_list]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Đánh giá chatbot")
    ap.add_argument("--gioi_han", type=int, help="chỉ chạy N câu Test ngẫu nhiên (seed 42)")
    ap.add_argument("--ghi_cau_hinh", action="store_true", help="đã khóa: không ghi tham số từ benchmark production")
    a = ap.parse_args()
    if a.ghi_cau_hinh:
        ap.error('Không ghi ngưỡng từ benchmark production/Test. Cần tập validation Train riêng đã phê duyệt.')
    print('Benchmark production lịch sử; không phải đánh giá Test kín hoặc hiệu chuẩn evaluation.')

    test, nhom_cua = doc_cau_test(a.gioi_han)
    dien_dat = [{"id_goc": int(r["id_goc"]), "cau_hoi": r["cau_hoi"], "nhom": nhom_cua[int(r["id_goc"])]}
                for r in doc_tsv("dien_dat_lai.tsv")]
    khong_dau = [{**c, "cau_hoi": bo_dau(c["cau_hoi"])} for c in dien_dat]
    noi_tiep = doc_tsv("noi_tiep.tsv")
    ngoai = doc_danh_sach("ngoai_pham_vi.txt")
    khong_co = doc_danh_sach("khong_co_du_lieu.txt")
    bo = {"test": test, "dien_dat": dien_dat, "khong_dau": khong_dau}
    cac_cach = [c for c in CACH_CAT if (thu_muc_kho(c, "tat_ca") / "index.faiss").exists()]
    print(f"{len(test)} câu Test · {len(dien_dat)} câu diễn đạt lại (+ bản không dấu) · {len(noi_tiep)} hội thoại "
          f"nối tiếp · {len(ngoai)} ngoài phạm vi · {len(khong_co)} không có dữ liệu · cách cắt: {', '.join(cac_cach)}")

    # ---------- 1. truy hồi
    bang, chi_tiet = {}, {}
    for cach in cac_cach:
        kho = thu_muc_kho(cach, "tat_ca")
        for tim in CACH_TIM:
            for ten, cau in bo.items():
                kq = chay_truy_hoi(cau, kho, tim)
                bang[(cach, tim, ten)], chi_tiet[(cach, tim, ten)] = chi_so_truy_hoi(kq), kq
            m, t = bang[(cach, tim, "dien_dat")], bang[(cach, tim, "test")]
            print(f"  {cach:9} {tim:6} Test Hit@1 {t['hit1']:.3f} | diễn đạt lại Hit@1 {m['hit1']:.3f} "
                  f"MRR@5 {m['mrr5']:.3f}")
    # Chỉ xếp theo bộ phát triển, không dùng Test để phá hòa.
    tot_nhat = max(((c, t) for c in cac_cach for t in CACH_TIM),
                   key=lambda x: tuple(bang[(*x, b)][m] for b in ("dien_dat", "khong_dau") for m in ("mrr5", "hit1")))
    cach_tot, tim_tot = tot_nhat
    print(f"Cấu hình truy hồi tốt nhất: {cach_tot} + {tim_tot}")

    # ---------- 2. ngưỡng, trên cách cắt tốt nhất, cho từng họ điểm (cosine; BM25 chuẩn hóa)
    kho_tot = thu_muc_kho(cach_tot, "tat_ca")
    nguong, du_lieu_nguong = {}, {}
    # họ "khong_dau": câu gõ không dấu luôn đi BM25 không dấu, nên đo trên bản không dấu của mọi bộ câu
    for ho, tim, bo_cau, doi in (("vector", tim_tot if tim_tot != "bm25" else "vector", "dien_dat", str),
                                 ("bm25", "bm25", "dien_dat", str),
                                 ("khong_dau", tim_tot, "khong_dau", bo_dau)):
        kq = chi_tiet[(cach_tot, tim, bo_cau)]
        dung = [r["diem_top1"] for r in kq if r["hang_dung"] == 1]
        sai = [r["diem_top1"] for r in kq if r["hang_dung"] != 1]
        d_ngoai = diem_top1([doi(x) for x in ngoai], kho_tot, tim)
        d_khong = diem_top1([doi(x) for x in khong_co], kho_tot, tim)
        trong_linh_vuc = [r["diem_top1"] for r in kq] + d_khong
        t_ngoai, j_ngoai = chon_nguong(trong_linh_vuc, d_ngoai)
        if ho == "khong_dau":
            # điểm không dấu tách kém; câu không dấu được trả lời bằng 3 gợi ý nên ưu tiên KHÔNG từ chối nhầm:
            # hạ ngưỡng xuống phân vị 5 của câu trong lĩnh vực (từ chối nhầm ≤ 5%)
            t_ngoai = min(t_ngoai, round(phan_vi(trong_linh_vuc, 5), 3))
        t_tin, j_tin = chon_nguong(dung, [x for x in sai + d_khong if x >= t_ngoai])
        if ho == "khong_dau":
            # chỉ trả lời thẳng khi điểm vượt phân vị 95 của các trường hợp tìm sai / không có dữ liệu
            t_tin = max(t_tin, round(phan_vi(sai + d_khong, 95), 3))
        nguong[ho] = {"ngoai_pham_vi": t_ngoai, "tin_cay": max(t_tin, t_ngoai)}
        du_lieu_nguong[ho] = {"tim": tim, "bo_cau": bo_cau, "dung": dung, "sai": sai, "ngoai": d_ngoai, "khong": d_khong,
                              "j_ngoai": j_ngoai, "j_tin": j_tin}
        print(f"  ngưỡng {ho}: ngoài phạm vi {nguong[ho]['ngoai_pham_vi']} (J={j_ngoai:.2f}), "
              f"tin cậy {nguong[ho]['tin_cay']} (J={j_tin:.2f})")

    # các bước sau chạy đúng luồng chatbot với cấu hình đề xuất (sửa trong bộ nhớ, không ghi nhật ký)
    ch = doc_cau_hinh()
    ch.update({"che_do_truy_hoi": tim_tot, "kho_vector": str(kho_tot.relative_to(ROOT)), "nguong": nguong,
               "ghi_nhat_ky": False})

    # ---------- 3. hội thoại nối tiếp
    ket_qua_noi_tiep = []
    for h in noi_tiep:
        l1 = tra_loi(h["cau_truoc"])
        lich_su = [{"cau_hoi": h["cau_truoc"], "cau_tra_loi": l1["cau_tra_loi"], "chu_de": l1["chu_de"]}]
        khong_ls = tra_loi(h["cau_noi_tiep"])
        co_ls = tra_loi(h["cau_noi_tiep"], lich_su)
        id_cua = lambda kq: kq["nguon"][0]["id_goc"] if kq["nguon"] else None
        ket_qua_noi_tiep.append({**h, "viet_lai": co_ls["giai_thich"]["cau_hoi_viet_lai"],
                                 "dung_khong_ls": id_cua(khong_ls) == int(h["id_goc"]),
                                 "dung_co_ls": id_cua(co_ls) == int(h["id_goc"])})

    # ---------- 4. câu trả lời cuối trên kho Train (đáp án Test không có trong kho)
    ho_tot = "bm25" if tim_tot == "bm25" else "vector"
    kho_train = thu_muc_kho(cach_tot, "Train")
    tra_loi_cuoi = []
    for c in test:
        tr = truy_hoi(c["cau_hoi"], k=5, kho=kho_train, che_do=tim_tot)
        dau = tr["doan"][0]
        tl = noi_dung_day_du(tr["kho"], dau["id_goc"])
        tra_loi_cuoi.append({**c, "loai": phan_loai(tr["diem_cao_nhat"], nguong[ho_tot]), "diem_top1": tr["diem_cao_nhat"],
                             "id_tra_loi": dau["id_goc"], "cau_hoi_khop": dau["cau_hoi"], "tra_loi": tl,
                             "rouge_l": rouge_l(tl, c["dap_an"]), "nhom_dung": dau["nhom_folder"] == c["nhom"]})
    tach = _bo_tach_tu()
    v_tl = sinh_vector([tach.tach_cau_hoi(r["tra_loi"]) for r in tra_loi_cuoi])
    v_da = sinh_vector([tach.tach_cau_hoi(r["dap_an"]) for r in tra_loi_cuoi])
    for r, cos in zip(tra_loi_cuoi, (v_tl * v_da).sum(axis=1)):
        r["cosine"] = float(cos)

    viet_bao_cao(bo, ngoai, khong_co, bang, chi_tiet, tot_nhat, nguong, du_lieu_nguong, ket_qua_noi_tiep,
                 tra_loi_cuoi, kho_tot)

    if a.ghi_cau_hinh:
        goc = json.loads(CAU_HINH_PATH.read_text(encoding="utf-8"))
        goc.update({"cach_cat": cach_tot, "kho_vector": f"{goc['thu_muc_kho']}/{cach_tot}_tat_ca",
                    "che_do_truy_hoi": tim_tot, "nguong": nguong})
        CAU_HINH_PATH.write_text(json.dumps(goc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"Đã ghi cấu hình đề xuất vào {CAU_HINH_PATH.relative_to(ROOT)}")


def phan_loai(diem, n):
    return "ngoai_pham_vi" if diem < n["ngoai_pham_vi"] else ("khong_chac" if diem < n["tin_cay"] else "tra_loi")


# ------------------------------------------------------------------ báo cáo

TEN_BO = {"test": "Test (nguyên văn)", "dien_dat": "Diễn đạt lại", "khong_dau": "Không dấu"}


def viet_bao_cao(bo, ngoai, khong_co, bang, chi_tiet, tot_nhat, nguong, du_lieu_nguong, noi_tiep, tra_loi_cuoi,
                 kho_tot):
    REPORTS.mkdir(exist_ok=True)
    cach_tot, tim_tot = tot_nhat
    n_test, n_dd = len(bo["test"]), len(bo["dien_dat"])
    L = ["# Đánh giá chatbot (Bài 4 – Phần V)\n",
         f"- Ngày chạy: {datetime.now():%Y-%m-%d %H:%M}",
         "- Chatbot **không dùng mô hình sinh câu trả lời**: câu trả lời là nguyên văn câu trả lời gốc của câu hỏi khớp "
         "nhất, nên chất lượng phụ thuộc hoàn toàn vào truy hồi và ngưỡng từ chối.",
         f"- Mô hình sinh vector (chỉ dùng để tìm kiếm): `{doc_cau_hinh_cat_doan()['ten_mo_hinh']}`. Truy hồi tất định: "
         "chạy lại cho cùng kết quả.",
         f"- Bộ câu (đáp án viết trước khi chạy, trong `data/kiem_thu/`): {n_test} câu Test · {n_dd} câu diễn đạt lại · "
         f"{n_dd} bản không dấu của chúng · {len(noi_tiep)} hội thoại nối tiếp · {len(ngoai)} câu ngoài phạm vi · "
         f"{len(khong_co)} câu nấu ăn mà dữ liệu không có.\n",
         "## 1. Truy hồi (kho `<cach>_tat_ca`)\n",
         "> Câu Test nằm **nguyên văn** trong kho nên cột Test chỉ là cận trên. Bộ **diễn đạt lại** (cùng ý, khác chữ) "
         "gần với người dùng thật hơn và là căn cứ chọn cấu hình.\n",
         "| Cách cắt | Cách tìm | Bộ câu | n | Hit@1 | Hit@3 | Hit@5 | MRR@5 | Nhóm đúng@1 | Trễ P50 (ms) | P90 | P95 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (cach, tim, ten), m in bang.items():
        dam = "**" if (cach, tim) == tot_nhat else ""
        L.append(f"| {dam}{cach}{dam} | {dam}{tim}{dam} | {TEN_BO[ten]} | {m['n']} | {m['hit1']:.3f} | {m['hit3']:.3f} | "
                 f"{m['hit5']:.3f} | {m['mrr5']:.3f} | {m['nhom1']:.3f} | {m['p50']:.0f} | {m['p90']:.0f} | {m['p95']:.0f} |")
    L.append(f"\nTốt nhất (MRR@5 rồi Hit@1 trên bộ diễn đạt lại): **{cach_tot} + {tim_tot}**.\n")

    kq_dd = chi_tiet[(cach_tot, tim_tot, "dien_dat")]
    L += [f"### Theo nhóm – bộ diễn đạt lại ({cach_tot} + {tim_tot})\n",
          "| Nhóm | n | Hit@1 | Hit@5 | MRR@5 |", "|---|---|---|---|---|"]
    for nhom in sorted({r["nhom"] for r in kq_dd}):
        m = chi_so_truy_hoi([r for r in kq_dd if r["nhom"] == nhom])
        L.append(f"| {nhom} | {m['n']} | {m['hit1']:.3f} | {m['hit5']:.3f} | {m['mrr5']:.3f} |")

    sai = sorted([r for r in kq_dd + chi_tiet[(cach_tot, tim_tot, "test")] if r["hang_dung"] != 1],
                 key=lambda r: (r["hang_dung"] is not None, r["hang_dung"] or 0, -r["diem_top1"]))[:10]
    L += [f"\n### Các câu truy hồi sai tệ nhất ({cach_tot} + {tim_tot}, tối đa 10)\n",
          "| ID đúng | Câu hỏi | Hạng đúng | Top-3 thực tế (ID · câu hỏi · điểm) |", "|---|---|---|---|"]
    for r in sai:
        top = "<br>".join(f"{i} · {q} · {s:.3f}" for i, q, s in r["top3"])
        L.append(f"| {r['id_goc']} | {r['cau_hoi']} | {r['hang_dung'] or '> 5'} | {top} |")
    if not sai:
        L.append("| — | Không có câu sai | | |")

    L += [f"\n## 2. Ngưỡng từ chối (Youden J, kho `{Path(kho_tot).name}`)\n",
          "- **Ngưỡng ngoài phạm vi**: tách câu trong lĩnh vực (diễn đạt lại + không có dữ liệu) khỏi câu ngoài phạm vi.",
          "- **Ngưỡng tin cậy**: tách câu diễn đạt lại tìm đúng top-1 khỏi câu tìm sai / không có dữ liệu. "
          "Dưới ngưỡng này chatbot không trả lời mà đưa 3 câu hỏi gần nhất để người dùng chọn.",
          "- Họ `khong_dau`: câu gõ không dấu tự chuyển sang BM25 trên chỉ mục phụ không dấu; ngưỡng đo trên bản "
          "không dấu của các bộ câu. Điểm họ này tách kém (J thấp) nên ngưỡng ngoài phạm vi được hạ xuống phân vị 5 "
          "của câu trong lĩnh vực; ngưỡng tin cậy nâng lên phân vị 95 của câu tìm sai, nên hầu hết câu không dấu nhận 3 câu gợi ý (Hit@3 cao) kèm lời nhắc gõ có dấu thay vì trả lời thẳng.\n",
          "| Họ điểm | Ngưỡng ngoài phạm vi | J | Ngưỡng tin cậy | J | Điểm top-1 TB: tìm đúng | tìm sai | ngoài phạm vi | không có dữ liệu |",
          "|---|---|---|---|---|---|---|---|---|"]
    tb = lambda x: f"{np.mean(x):.3f} (n={len(x)})" if x else "—"
    for ho, d in du_lieu_nguong.items():
        L.append(f"| {ho} | {nguong[ho]['ngoai_pham_vi']} | {d['j_ngoai']:.2f} | {nguong[ho]['tin_cay']} | {d['j_tin']:.2f} | "
                 f"{tb(d['dung'])} | {tb(d['sai'])} | {tb(d['ngoai'])} | {tb(d['khong'])} |")

    L += ["\n### Từ chối đo hai chiều (với ngưỡng trên)\n",
          "| Họ điểm | Ngoài phạm vi bị từ chối ✓ | Không có dữ liệu không bị trả lời ✓ | "
          "Diễn đạt lại (tìm đúng) được trả lời ✓ | Diễn đạt lại bị từ chối nhầm ✗ |", "|---|---|---|---|---|"]
    for ho, d in du_lieu_nguong.items():
        dem = lambda xs, loai: f"{sum(phan_loai(x, nguong[ho]) in loai for x in xs)}/{len(xs)}"
        dd = [r["diem_top1"] for r in chi_tiet[(cach_tot, d["tim"], d["bo_cau"])]]
        L.append(f"| {ho} | {dem(d['ngoai'], ('ngoai_pham_vi',))} | {dem(d['khong'], ('ngoai_pham_vi', 'khong_chac'))} | "
                 f"{dem(d['dung'], ('tra_loi',))} | {dem(dd, ('ngoai_pham_vi',))} |")

    L += ["\n## 3. Hội thoại nối tiếp (luồng chatbot đầy đủ, cấu hình đề xuất)\n",
          "| Lượt 1 | Lượt 2 | Câu viết lại | Đúng khi KHÔNG nhớ lượt trước | Đúng khi có nhớ |", "|---|---|---|---|---|"]
    for h in noi_tiep:
        L.append(f"| {h['cau_truoc']} | {h['cau_noi_tiep']} | {h['viet_lai'] or '—'} | "
                 f"{'✓' if h['dung_khong_ls'] else '✗'} | {'✓' if h['dung_co_ls'] else '✗'} |")
    L.append(f"\nĐúng: {sum(h['dung_khong_ls'] for h in noi_tiep)}/{len(noi_tiep)} khi không nhớ → "
             f"{sum(h['dung_co_ls'] for h in noi_tiep)}/{len(noi_tiep)} khi có nhớ hội thoại.")

    n = len(tra_loi_cuoi)
    tra = [r for r in tra_loi_cuoi if r["loai"] == "tra_loi"]
    L += [f"\n## 4. Câu trả lời cuối (kho `{cach_tot}_Train`, đáp án Test KHÔNG có trong kho)\n",
          "Câu trả lời = nguyên văn câu trả lời gốc của câu hỏi Train khớp nhất, so với đáp án gốc của câu Test. "
          "Mốc so sánh: đáp án so với chính nó cho ROUGE-L = cosine = 1.\n",
          "| Chỉ số | Giá trị |", "|---|---|",
          f"| ROUGE-L F1 trung bình | {np.mean([r['rouge_l'] for r in tra_loi_cuoi]):.3f} (n={n}) |",
          f"| Cosine trung bình với đáp án gốc | {np.mean([r['cosine'] for r in tra_loi_cuoi]):.3f} (n={n}) |",
          f"| Câu khớp nhất cùng nhóm với câu Test | {np.mean([r['nhom_dung'] for r in tra_loi_cuoi]):.3f} (n={n}) |",
          f"| Trả lời / chỉ gợi ý / từ chối | {len(tra)} / {sum(r['loai'] == 'khong_chac' for r in tra_loi_cuoi)} / "
          f"{sum(r['loai'] == 'ngoai_pham_vi' for r in tra_loi_cuoi)} (n={n}) |"]
    if tra:
        L.append(f"| ROUGE-L / cosine chỉ trên câu được trả lời | {np.mean([r['rouge_l'] for r in tra]):.3f} / "
                 f"{np.mean([r['cosine'] for r in tra]):.3f} (n={len(tra)}) |")
    L.append("\nPhần lớn câu Test là món / ý hỏi không có trong Train, nên chatbot đúng ra phải **chỉ gợi ý** thay vì "
             "trả lời; điểm ROUGE-L thấp ở đây phản ánh dữ liệu thiếu, không phải câu trả lời bị bịa. "
             "Chấm tay 20 câu ngẫu nhiên trong `reports/cham_tay.csv`.")

    m_dd = bang[(cach_tot, tim_tot, "dien_dat")]
    L += ["\n## 5. Kết luận\n",
          f"- Cấu hình đề xuất: kho **{cach_tot}**, cách tìm **{tim_tot}** (diễn đạt lại: Hit@1 {m_dd['hit1']:.3f}, "
          f"MRR@5 {m_dd['mrr5']:.3f}, n={m_dd['n']}); ngưỡng vector {nguong['vector']}, BM25 {nguong['bm25']}.",
          "- Chatbot trả nguyên văn dữ liệu nên không bịa nguyên liệu, định lượng; rủi ro chính là **chọn nhầm câu hỏi "
          "gốc** (câu cần ghép nhiều cặp hỏi–đáp, món không có trong dữ liệu nhưng tên gần giống, câu gõ không dấu).",
          "- Hạn chế: bộ diễn đạt lại, ngoài phạm vi và không có dữ liệu là bộ nhỏ tự soạn nên ngưỡng còn dao động; "
          "câu Test nằm trong kho nên số trên bộ Test là cận trên.",
          "- Đây là benchmark production lịch sử, không phải Test kín; chế độ ghi ngưỡng đã bị khóa."]
    (REPORTS / "danh_gia_chatbot.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")

    with open(REPORTS / "danh_gia_chi_tiet.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cach_cat", "cach_tim", "bo_cau", "id_goc", "nhom", "cau_hoi", "hang_dung", "id_top1", "diem_top1",
                    "nhom_top1", "thoi_gian_ms"])
        for (cach, tim, ten), kq in chi_tiet.items():
            for r in kq:
                w.writerow([cach, tim, ten, r["id_goc"], r["nhom"], r["cau_hoi"], r["hang_dung"] or "",
                            r["top3"][0][0] if r["top3"] else "", f"{r['diem_top1']:.4f}", r["nhom_top1"],
                            f"{r['thoi_gian_ms']:.1f}"])

    with open(REPORTS / "cham_tay.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id_goc", "cau_hoi", "dap_an_goc", "loai", "cau_hoi_khop", "tra_loi_chatbot",
                    "Đúng ý (1/0)", "Chọn nhầm món (1/0)", "Dẫn nguồn đúng (1/0)", "Ghi chú"])
        for r in random.Random(SEED).sample(tra_loi_cuoi, min(20, n)):
            w.writerow([r["id_goc"], r["cau_hoi"], r["dap_an"], r["loai"], r["cau_hoi_khop"], r["tra_loi"], "", "", "", ""])
    print("Đã ghi reports/danh_gia_chatbot.md, reports/danh_gia_chi_tiet.csv, reports/cham_tay.csv")


if __name__ == "__main__":
    main()
