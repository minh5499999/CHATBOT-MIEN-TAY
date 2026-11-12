"""Sinh vector cho đoạn và dựng kho vector FAISS (Bài 4 – Phần II).

Cách chạy (từ thư mục gốc project):
    .venv\\Scripts\\python.exe scripts/tao_kho_vector.py                              # cau_truc, tat_ca
    .venv\\Scripts\\python.exe scripts/tao_kho_vector.py --cach tat_ca --tap tat_ca
    .venv\\Scripts\\python.exe scripts/tao_kho_vector.py --cach de_quy --tap Train

Đầu vào : data/doan/doan_<cach>.jsonl (chỉ đọc), cau_hinh/chatbot.json, cau_hinh/tach_doan.json
Đầu ra  : kho_vector/<cach>_<tap>/index.faiss, sieu_du_lieu.jsonl, thong_tin.json
          kho_vector/_bo_dem/<hash>.npy (bộ đệm vector theo hash nội dung)
          reports/kiem_tra_kho_vector.md
Hai loại kho tách bạch: <cach>_Train chỉ có đoạn Train (đánh giá câu trả lời, không rò đáp án Test);
<cach>_tat_ca có Train + Test (chatbot chạy thật, đánh giá truy hồi).
Tìm vét cạn (IndexFlatIP) trên vector chuẩn hóa L2, tức là cosine.
"""
import argparse
import hashlib
import json
import random
import sys
import time
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

import faiss
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.chatbot.cau_hinh import ROOT, doc_cau_hinh, doc_cau_hinh_cat_doan, duong_dan  # noqa: E402
from backend.chatbot.mo_hinh_vector import sinh_vector, van_ban_doan, vector_cau_hoi  # noqa: E402

CAC_CACH = ["cau_truc", "co_dinh", "de_quy"]
CAC_TAP = ["Train", "tat_ca"]
REPORTS = ROOT / "reports"
SO_MAU_TU_TRUY_HOI = 20

CH = doc_cau_hinh()
THU_MUC_KHO = duong_dan("thu_muc_kho")
BO_DEM = THU_MUC_KHO / "_bo_dem"


def doc_doan(cach):
    path = duong_dan("thu_muc_doan") / f"doan_{cach}.jsonl"
    if not path.exists():
        sys.exit(f"Không thấy {path}. Chạy scripts/tach_doan.py trước.")
    raw = path.read_bytes()
    doan = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    return doan, hashlib.sha256(raw).hexdigest(), path


def vector_co_bo_dem(van_ban):
    """Sinh vector, lưu .npy theo hash (mô hình + tiền tố + nội dung). Lần sau trùng hash thì chỉ nạp."""
    h = hashlib.sha256()
    h.update(doc_cau_hinh_cat_doan()["ten_mo_hinh"].encode("utf-8"))
    for t in van_ban:
        h.update(b"\x00" + t.encode("utf-8"))
    path = BO_DEM / f"{h.hexdigest()[:32]}.npy"
    if path.exists():
        v = np.load(path)
        if v.shape[0] == len(van_ban):
            return v, True, 0.0
    t0 = time.perf_counter()
    v = sinh_vector(van_ban, hien_tien_trinh=True)
    giay = time.perf_counter() - t0
    BO_DEM.mkdir(parents=True, exist_ok=True)
    np.save(path, v)
    return v, False, giay


def ghi_kho(thu_muc, vec, doan, thong_tin):
    """Ghi index + siêu dữ liệu cùng thứ tự. Ghi qua bytes vì faiss.write_index lỗi với đường dẫn có dấu."""
    thu_muc.mkdir(parents=True, exist_ok=True)
    index = faiss.IndexFlatIP(vec.shape[1])
    index.add(vec)
    (thu_muc / "index.faiss").write_bytes(faiss.serialize_index(index).tobytes())
    with (thu_muc / "sieu_du_lieu.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for d in doan:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    (thu_muc / "thong_tin.json").write_text(json.dumps(thong_tin, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8", newline="\n")


def nap_kho(thu_muc):
    """Nạp lại kho TỪ ĐĨA (để kiểm bước lưu thật sự hoạt động)."""
    index = faiss.deserialize_index(np.frombuffer((thu_muc / "index.faiss").read_bytes(), dtype=np.uint8))
    sieu = [json.loads(line) for line in (thu_muc / "sieu_du_lieu.jsonl").read_text(encoding="utf-8").splitlines()]
    return index, sieu


def kiem_tra(thu_muc, so_dau_vao, cau_mau):
    """Bốn phép kiểm sau khi tạo kho, chạy trên kho đã nạp lại từ đĩa."""
    index, sieu = nap_kho(thu_muc)
    vec = index.reconstruct_n(0, index.ntotal)
    kq = {"so_vector": index.ntotal, "so_sieu_du_lieu": len(sieu), "so_dau_vao": so_dau_vao}
    kq["khop_so_luong"] = index.ntotal == len(sieu) == so_dau_vao

    chuan = np.linalg.norm(vec, axis=1)
    kq["chuan_min"], kq["chuan_max"] = float(chuan.min()), float(chuan.max())
    kq["chuan_dat"] = bool(np.all(np.abs(chuan - 1) < 1e-3))

    # tự truy hồi: đoạn có vector trùng hệt đoạn khác thì top-1 có thể là bản trùng, ghi riêng
    rng = random.Random(CH["seed"])
    mau = rng.sample(range(index.ntotal), min(SO_MAU_TU_TRUY_HOI, index.ntotal))
    D, I = index.search(vec[mau], 2)
    dung, trung = 0, []
    for j, i in enumerate(mau):
        if I[j, 0] == i:
            dung += 1
        elif abs(D[j, 0] - D[j, 1]) < 1e-6 and i in I[j]:
            dung += 1
            trung.append(sieu[i]["chunk_id"])
    kq["tu_truy_hoi"] = (dung, len(mau))
    kq["tu_truy_hoi_trung_vector"] = trung

    kq["cau_mau"] = []
    for q in cau_mau:
        qv, sach, vao = vector_cau_hoi(q)
        D, I = index.search(qv, 5)
        kq["cau_mau"].append({"cau_hoi": q, "dua_vao_mo_hinh": vao, "top": [
            {"xep_hang": r + 1, "diem": float(D[0, r]), "chunk_id": sieu[I[0, r]]["chunk_id"],
             "id_goc": sieu[I[0, r]]["id_goc"], "nhom": sieu[I[0, r]]["nhom_folder"],
             "tap": sieu[I[0, r]]["tap"], "cau_hoi_goc": sieu[I[0, r]]["cau_hoi"],
             "ten_muc": sieu[I[0, r]]["ten_muc"]} for r in range(min(5, index.ntotal))]})
    return kq


def viet_bao_cao(path, ket_qua):
    ch_cd = doc_cau_hinh_cat_doan()
    L = ["# Kiểm tra kho vector (Bài 4 – Phần II)", "",
         f"- Ngày chạy: {datetime.now():%Y-%m-%d %H:%M}",
         f"- Mô hình: `{ch_cd['ten_mo_hinh']}`, tách từ trước khi sinh vector: `{ch_cd['can_tach_tu']}`, "
         f"tiền tố đoạn: `{CH['tien_to_doan'] or '(không)'}`, tiền tố câu hỏi: `{CH['tien_to_cau_hoi'] or '(không)'}`.",
         "- Kho: FAISS `IndexFlatIP` (tìm vét cạn) trên vector chuẩn hóa L2, tức là điểm = cosine.",
         "- Mọi phép kiểm chạy trên kho **nạp lại từ đĩa**, không dùng vector còn trong bộ nhớ.", "",
         "## 1. Bảng kiểm", "",
         "| Kho | Số đoạn vào | Số vector | Số dòng siêu dữ liệu | Khớp | Chuẩn min–max | Tự truy hồi top-1 | Số chiều | Sinh vector |",
         "|---|---|---|---|---|---|---|---|---|"]
    for ten, k in ket_qua.items():
        d, n = k["kiem"]["tu_truy_hoi"]
        L.append(f"| `{ten}` | {k['kiem']['so_dau_vao']} | {k['kiem']['so_vector']} | {k['kiem']['so_sieu_du_lieu']} | "
                 f"{'đạt' if k['kiem']['khop_so_luong'] else '**KHÔNG**'} | "
                 f"{k['kiem']['chuan_min']:.6f}–{k['kiem']['chuan_max']:.6f} | {d}/{n} | {k['so_chieu']} | {k['sinh']} |")
    trung = {t for k in ket_qua.values() for t in k["kiem"]["tu_truy_hoi_trung_vector"]}
    if trung:
        L += ["", "Đoạn có vector trùng hệt đoạn khác (top-1 có thể là bản trùng, vẫn tính đạt): "
                  + ", ".join(f"`{t}`" for t in sorted(trung))]
    L += ["", "## 2. Ba câu hỏi mẫu (top-5)", ""]
    for ten, k in ket_qua.items():
        L += [f"### Kho `{ten}`", ""]
        for c in k["kiem"]["cau_mau"]:
            L += [f"**{c['cau_hoi']}** → đưa vào mô hình: `{c['dua_vao_mo_hinh']}`", "",
                  "| # | Điểm | ID gốc | Nhóm | Tập | Câu hỏi gốc | Tên mục |", "|---|---|---|---|---|---|---|"]
            for t in c["top"]:
                L.append(f"| {t['xep_hang']} | {t['diem']:.4f} | {t['id_goc']} | {t['nhom']} | {t['tap']} | "
                         f"{t['cau_hoi_goc']} | {t['ten_muc'] or '—'} |")
            L.append("")
    path.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Sinh vector và dựng kho vector FAISS")
    ap.add_argument("--cach", choices=CAC_CACH + ["tat_ca"], default=CH["cach_cat"])
    ap.add_argument("--tap", choices=CAC_TAP, default="tat_ca",
                    help="Train: chỉ đoạn Train; tat_ca: Train + Test")
    args = ap.parse_args()
    cac_cach = CAC_CACH if args.cach == "tat_ca" else [args.cach]

    ket_qua = {}
    for cach in cac_cach:
        doan, hash_dau_vao, path = doc_doan(cach)
        # luôn sinh vector cho cả file rồi mới lọc theo tập: kho Train dùng lại đúng vector của kho tat_ca
        vec_all, tu_bo_dem, giay = vector_co_bo_dem([van_ban_doan(d) for d in doan])
        sinh = "bộ đệm" if tu_bo_dem else f"{giay:.0f} s"
        print(f"{cach}: {len(doan)} đoạn, vector {vec_all.shape} ({sinh})")
        chon = [i for i, d in enumerate(doan) if args.tap == "tat_ca" or d["tap"] == args.tap]
        vec, doan_kho = vec_all[chon], [doan[i] for i in chon]

        ten = f"{cach}_{args.tap}"
        thong_tin = {
            "ten_mo_hinh": doc_cau_hinh_cat_doan()["ten_mo_hinh"],
            "so_chieu": int(vec.shape[1]), "so_doan": len(doan_kho),
            "ngay_tao": datetime.now().isoformat(timespec="seconds"),
            "cach_cat": cach, "tap": args.tap,
            "dau_vao": str(path.relative_to(ROOT)).replace("\\", "/"), "hash_dau_vao_sha256": hash_dau_vao,
            "truong_dua_vao_mo_hinh": ("noi_dung_kem_tieu_de_tach_tu" if doc_cau_hinh_cat_doan()["can_tach_tu"]
                                       else "noi_dung_kem_tieu_de"),
            "tien_to_doan": CH["tien_to_doan"], "tien_to_cau_hoi": CH["tien_to_cau_hoi"],
            "chuan_hoa": "L2", "do_do": "cosine (tích vô hướng trên vector chuẩn hóa)",
            "loai_index": "faiss.IndexFlatIP",
            "phien_ban": {p: version(p) for p in ("faiss-cpu", "sentence-transformers", "torch", "numpy")},
        }
        ghi_kho(THU_MUC_KHO / ten, vec, doan_kho, thong_tin)
        kiem = kiem_tra(THU_MUC_KHO / ten, len(doan_kho), CH["so_cau_mau_kiem_tra"])
        ket_qua[ten] = {"kiem": kiem, "so_chieu": vec.shape[1], "sinh": sinh}
        d, n = kiem["tu_truy_hoi"]
        print(f"  → kho_vector/{ten}: {kiem['so_vector']} vector, khớp số lượng: "
              f"{'đạt' if kiem['khop_so_luong'] else 'KHÔNG'}, chuẩn {kiem['chuan_min']:.4f}–{kiem['chuan_max']:.4f}, "
              f"tự truy hồi {d}/{n}")
        for c in kiem["cau_mau"]:
            print(f"     «{c['cau_hoi']}»")
            for t in c["top"]:
                print(f"       {t['xep_hang']}. {t['diem']:.4f}  ID {t['id_goc']:<4} {t['nhom']:<30} "
                      f"{t['cau_hoi_goc'][:45]}{' · ' + t['ten_muc'] if t['ten_muc'] else ''}")

    duoi = "" if args.cach == "tat_ca" and args.tap == "tat_ca" else f"_{args.cach}_{args.tap}"
    REPORTS.mkdir(exist_ok=True)
    viet_bao_cao(REPORTS / f"kiem_tra_kho_vector{duoi}.md", ket_qua)
    print(f"\nBáo cáo: reports/kiem_tra_kho_vector{duoi}.md")
    if not all(k["kiem"]["khop_so_luong"] and k["kiem"]["chuan_dat"]
               and k["kiem"]["tu_truy_hoi"][0] == k["kiem"]["tu_truy_hoi"][1] for k in ket_qua.values()):
        sys.exit("CÓ PHÉP KIỂM KHÔNG ĐẠT — xem báo cáo.")


if __name__ == "__main__":
    main()
