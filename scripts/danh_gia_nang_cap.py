"""Đánh giá hồi quy truy hồi trên bộ diễn đạt lại, cấm kết nối mạng."""
import csv
import json
import socket
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from backend.chatbot.cau_hinh import doc_cau_hinh
    from backend.chatbot.truy_hoi import truy_hoi
    from backend.chatbot.chuoi_langchain import truy_hoi_langchain
    ch = doc_cau_hinh()
    ch.update(kho_tim_kiem="faiss", chi_chay_cuc_bo=True)
    with (ROOT / "data/kiem_thu/dien_dat_lai.tsv").open(encoding="utf-8") as stream:
        questions = list(csv.DictReader((line for line in stream if not line.startswith("#")), delimiter="\t"))
    results = []
    started = time.perf_counter()
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Kết nối mạng bị chặn")):
        for row in questions:
            expected = int(row["id_goc"])
            result = {"cau_hoi": row["cau_hoi"], "id_dung": expected}
            for label, retrieve in [("cu_khong_mo_rong", truy_hoi), ("langchain_keyword", truy_hoi_langchain)]:
                found = retrieve(row["cau_hoi"])["doan"]
                ids = [d["id_goc"] for d in found]
                result[label] = {"top_ids": ids, "hang_dung": ids.index(expected) + 1 if expected in ids else None}
            results.append(result)
    summary = {}
    for label in ("cu_khong_mo_rong", "langchain_keyword"):
        ranks = [r[label]["hang_dung"] for r in results]
        summary[label] = {"n": len(ranks), "hit1": sum(r == 1 for r in ranks) / len(ranks),
                          "hit5": sum(r is not None for r in ranks) / len(ranks),
                          "mrr5": sum(1/r for r in ranks if r) / len(ranks)}
    output = {"tom_tat": summary, "giay": round(time.perf_counter()-started, 2), "chi_tiet": results,
              "luu_y": "44 câu diễn đạt lại; kiểm tra truy hồi, không phải đánh giá y khoa hoặc độ tự nhiên của mô hình sinh."}
    (ROOT / "reports/danh_gia_nang_cap.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
