"""Nạp kho vector đã dựng (FAISS trên đĩa) vào Neo4j thành đồ thị tri thức có chỉ mục vector.

Cách chạy (từ thư mục gốc project, Neo4j đang bật và đã điền NEO4J_PASSWORD trong .env):
    .venv\\Scripts\\python.exe scripts/nap_neo4j.py                          # kho trong cấu hình
    .venv\\Scripts\\python.exe scripts/nap_neo4j.py --kho kho_vector/de_quy_tat_ca

Đồ thị: (:Nhom {ma, ten}) <-[:THUOC_NHOM]- (:CauHoi {id_goc, cau_hoi, tap, nguon}) <-[:THUOC_VE]- (:Doan {...})
        (:Kho {ten, so_doan, hash_sieu_du_lieu, ...thông tin kho})
Chạy lại nhiều lần được: xóa các đoạn cũ của đúng kho đó rồi nạp lại; vector lấy nguyên từ index.faiss, không sinh lại.
"""
import argparse
import json
import sys
from pathlib import Path

import faiss
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.chatbot.cau_hinh import ROOT, doc_cau_hinh  # noqa: E402
from backend.chatbot.kho_neo4j import CHI_MUC_VECTOR, bam_sieu_du_lieu, chay, tim_vector  # noqa: E402

LO = 200  # số đoạn mỗi lần ghi


def doc_kho_dia(thu_muc):
    index = faiss.deserialize_index(np.frombuffer((ROOT / thu_muc / "index.faiss").read_bytes(), dtype=np.uint8))
    sieu = [json.loads(d) for d in (ROOT / thu_muc / "sieu_du_lieu.jsonl").read_text(encoding="utf-8").splitlines()]
    thong_tin = json.loads((ROOT / thu_muc / "thong_tin.json").read_text(encoding="utf-8"))
    if index.ntotal != len(sieu):
        sys.exit(f"Kho {thu_muc} hỏng: {index.ntotal} vector nhưng {len(sieu)} dòng siêu dữ liệu")
    return index.reconstruct_n(0, index.ntotal), sieu, thong_tin


def tao_rang_buoc(so_chieu):
    chay("CREATE CONSTRAINT nhom_ma IF NOT EXISTS FOR (n:Nhom) REQUIRE n.ma IS UNIQUE")
    chay("CREATE CONSTRAINT cau_hoi_id IF NOT EXISTS FOR (c:CauHoi) REQUIRE c.id_goc IS UNIQUE")
    chay("CREATE CONSTRAINT kho_ten IF NOT EXISTS FOR (k:Kho) REQUIRE k.ten IS UNIQUE")
    chay("CREATE CONSTRAINT doan_kho_chunk IF NOT EXISTS FOR (d:Doan) REQUIRE (d.kho, d.chunk_id) IS UNIQUE")
    chay("CREATE INDEX doan_kho IF NOT EXISTS FOR (d:Doan) ON (d.kho)")
    chay(f"CREATE VECTOR INDEX {CHI_MUC_VECTOR} IF NOT EXISTS FOR (d:Doan) ON d.embedding "
         f"OPTIONS {{indexConfig: {{`vector.dimensions`: {int(so_chieu)}, `vector.similarity_function`: 'cosine'}}}}")


def nap(thu_muc):
    vec, sieu, thong_tin = doc_kho_dia(thu_muc)
    print(f"Kho {thu_muc}: {len(sieu)} đoạn, vector {vec.shape[1]} chiều")
    tao_rang_buoc(vec.shape[1])

    # xóa bản cũ của đúng kho này (theo lô để không tràn bộ nhớ giao dịch)
    while chay("MATCH (d:Doan {kho: $kho}) WITH d LIMIT 1000 DETACH DELETE d RETURN count(*) AS n",
               kho=thu_muc)[0]["n"]:
        pass

    for dau in range(0, len(sieu), LO):
        lo = [{**d, "kho": thu_muc, "vi_tri": dau + j, "embedding": vec[dau + j].astype(float).tolist()}
              for j, d in enumerate(sieu[dau:dau + LO])]
        chay("UNWIND $lo AS d "
             "MERGE (n:Nhom {ma: d.nhom_folder}) SET n.ten = d.nhom "
             "MERGE (c:CauHoi {id_goc: d.id_goc}) SET c.cau_hoi = d.cau_hoi, c.tap = d.tap, c.nguon = d.nguon "
             "MERGE (c)-[:THUOC_NHOM]->(n) "
             "CREATE (x:Doan) SET x = d "
             "CREATE (x)-[:THUOC_VE]->(c)", lo=lo)
        print(f"  đã ghi {min(dau + LO, len(sieu))}/{len(sieu)}")

    # thông tin kho: chỉ giữ giá trị đơn (Neo4j không lưu được dict lồng như phien_ban)
    phang = {k: v for k, v in thong_tin.items() if not isinstance(v, dict)}
    phang.update({f"phien_ban_{k}": v for k, v in thong_tin.get("phien_ban", {}).items()})
    chay("MERGE (k:Kho {ten: $ten}) SET k = $tt, k.ten = $ten, k.so_doan = $so_doan, k.hash_sieu_du_lieu = $bam",
         ten=thu_muc, tt=phang, so_doan=len(sieu), bam=bam_sieu_du_lieu(thu_muc))
    chay("CALL db.awaitIndexes(300)")

    # kiểm tra: đủ số đoạn, và tìm bằng vector của chính đoạn đầu phải ra đúng đoạn đó
    so = chay("MATCH (d:Doan {kho: $kho})-[:THUOC_VE]->(:CauHoi)-[:THUOC_NHOM]->(:Nhom) RETURN count(d) AS n",
              kho=thu_muc)[0]["n"]
    tim = chay(tim_vector("d.vi_tri AS i, score") + " LIMIT 1", k=5, v=vec[0].astype(float).tolist(), kho=thu_muc)
    print(f"Kiểm tra: {so}/{len(sieu)} đoạn nối đủ Câu hỏi → Nhóm · tự tìm đoạn 0 → vi_tri {tim[0]['i']}, "
          f"cos {2 * tim[0]['score'] - 1:.4f}")
    if so != len(sieu):
        sys.exit("Nạp thiếu đoạn.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Nạp kho vector vào Neo4j")
    ap.add_argument("--kho", default=doc_cau_hinh()["kho_vector"], help="thư mục kho, ví dụ kho_vector/cau_truc_tat_ca")
    nap(Path(ap.parse_args().kho).as_posix())
    tong = chay("MATCH (n:Nhom) WITH count(n) AS nhom MATCH (c:CauHoi) WITH nhom, count(c) AS cau "
                "MATCH (d:Doan) RETURN nhom, cau, count(d) AS doan")[0]
    print(f"Neo4j hiện có: {tong['nhom']} nhóm · {tong['cau']} câu hỏi gốc · {tong['doan']} đoạn")


if __name__ == "__main__":
    main()
