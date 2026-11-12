"""Kho tri thức trên Neo4j: đồ thị (:Doan)-[:THUOC_VE]->(:CauHoi)-[:THUOC_NHOM]->(:Nhom), tìm bằng chỉ mục vector.

Nạp dữ liệu vào Neo4j: python scripts/nap_neo4j.py (đọc kho FAISS đã dựng trên đĩa, chép vector + siêu dữ liệu sang).
Kết nối đọc từ .env: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE.

Mỗi :Doan giữ đủ trường như sieu_du_lieu.jsonl, thêm `kho` (ví dụ "kho_vector/cau_truc_tat_ca"), `vi_tri` (thứ tự
trong kho) và `embedding` (vector 768 chiều đã chuẩn hóa L2). Chỉ mục vector dùng cosine; Neo4j trả điểm
(1 + cos) / 2 nên đổi lại thành cos để dùng chung các ngưỡng đã chọn cho FAISS.
"""
import hashlib
import math
import os
from functools import lru_cache

import numpy as np

from backend.chatbot.cau_hinh import ROOT, nap_env

CHI_MUC_VECTOR = "doan_vector"
TRUONG_THEM = ("kho", "vi_tri", "embedding")  # trường chỉ có trong Neo4j, không thuộc siêu dữ liệu gốc


@lru_cache(maxsize=1)
def ket_noi():
    """Driver Neo4j dùng chung (lỗi thì không lưu vào bộ đệm, lần sau thử lại)."""
    from neo4j import GraphDatabase
    nap_env()
    mat_khau = os.environ.get("NEO4J_PASSWORD")
    if not mat_khau:
        raise RuntimeError("Chưa điền NEO4J_PASSWORD trong .env")
    driver = GraphDatabase.driver(os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
                                  auth=(os.environ.get("NEO4J_USER", "neo4j"), mat_khau), connection_timeout=5)
    try:
        driver.verify_connectivity()
    except Exception:
        driver.close()
        raise
    return driver


def chay(cypher, **tham_so):
    """Chạy một câu Cypher, trả về danh sách bản ghi."""
    ban_ghi, _, _ = ket_noi().execute_query(cypher, tham_so, database_=os.environ.get("NEO4J_DATABASE", "neo4j"))
    return ban_ghi


def tim_vector(tra_ve):
    """Câu Cypher tìm theo chỉ mục vector (mệnh đề SEARCH của Cypher 25, thay db.index.vector.queryNodes đã cũ).

    Tham số: $v (vector câu hỏi), $k (số đoạn lấy), $kho (chỉ giữ đoạn của kho này).
    """
    return (f"CYPHER 25 MATCH (d:Doan) SEARCH d IN (VECTOR INDEX {CHI_MUC_VECTOR} FOR $v LIMIT $k) SCORE AS score "
            f"WHERE d.kho = $kho RETURN {tra_ve} ORDER BY score DESC")


def bam_sieu_du_lieu(thu_muc):
    """Mã băm file siêu dữ liệu của kho trên đĩa, để biết bản trong Neo4j còn khớp không."""
    path = ROOT / thu_muc / "sieu_du_lieu.jsonl"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


class ChiMucNeo4j:
    """Có ntotal và search(vec, k) như faiss.Index, để truy_hoi dùng chung một đường, chỉ đổi nơi tìm.

    Neo4j mất kết nối giữa chừng → tự tìm trên kho FAISS cùng tên trên đĩa (cùng thứ tự vi_tri).
    """

    def __init__(self, kho, ntotal, tong_doan):
        self.kho, self.ntotal = kho, ntotal
        # chỉ mục vector chứa đoạn của mọi kho đã nạp → xin nhiều hơn theo tỉ lệ rồi lọc lại theo kho
        self.ti_le = max(tong_doan / ntotal, 1.0) if ntotal else 1.0
        self.may_tim = "neo4j"  # nơi lần tìm gần nhất thật sự chạy
        self._faiss = None

    def search(self, vec, k):
        try:
            kq = self._tim_neo4j(vec, k)
            self.may_tim = "neo4j"
            return kq
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Neo4j lỗi khi tìm (%s), chuyển sang FAISS trên đĩa", e)
            self.may_tim = "faiss"
            if self._faiss is None:
                import faiss
                self._faiss = faiss.deserialize_index(
                    np.frombuffer((ROOT / self.kho / "index.faiss").read_bytes(), dtype=np.uint8))
            return self._faiss.search(vec, k)

    def _tim_neo4j(self, vec, k):
        xin = min(math.ceil(k * self.ti_le), round(self.ntotal * self.ti_le))
        ban_ghi = chay(tim_vector("d.vi_tri AS i, score"), k=xin, v=vec[0].astype(float).tolist(), kho=self.kho)
        diem = dict((r["i"], 2 * r["score"] - 1) for r in ban_ghi)
        # đoạn không được trả về (ngoài k, hoặc chỉ mục xấp xỉ bỏ sót) nhận điểm thấp nhất
        thu_tu = sorted(range(self.ntotal), key=lambda i: -diem.get(i, -1.0))[:k]
        return (np.array([[diem.get(i, -1.0) for i in thu_tu]], dtype=np.float32),
                np.array([thu_tu], dtype=np.int64))


def nap_kho(thu_muc):
    """Kho trong Neo4j → (ChiMucNeo4j, siêu dữ liệu, thông tin) như truy_hoi.nap_kho; chưa nạp kho này thì None.

    Kho trên đĩa đã dựng lại sau lần nạp Neo4j (mã băm khác) → báo lỗi để không trả nhầm thứ tự đoạn.
    """
    kho = chay("MATCH (k:Kho {ten: $ten}) RETURN k", ten=thu_muc)
    if not kho:
        return None
    kho = dict(kho[0]["k"])
    bam_dia = bam_sieu_du_lieu(thu_muc)
    if bam_dia and bam_dia != kho["hash_sieu_du_lieu"]:
        raise ValueError(f"Kho {thu_muc} trong Neo4j cũ hơn bản trên đĩa. Chạy lại: python scripts/nap_neo4j.py")
    ban_ghi = chay("MATCH (d:Doan {kho: $kho}) RETURN d ORDER BY d.vi_tri", kho=thu_muc)
    sieu = [{k: v for k, v in dict(r["d"]).items() if k not in TRUONG_THEM} for r in ban_ghi]
    if len(sieu) != kho["so_doan"]:
        raise ValueError(f"Kho {thu_muc} trong Neo4j thiếu đoạn: {len(sieu)}/{kho['so_doan']}")
    thong_tin = {k: v for k, v in kho.items() if k not in ("ten", "hash_sieu_du_lieu")}
    thong_tin["may_tim"] = "neo4j"
    tong_doan = chay("MATCH (d:Doan) RETURN count(d) AS n")[0]["n"]
    return ChiMucNeo4j(thu_muc, len(sieu), tong_doan), sieu, thong_tin
