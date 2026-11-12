"""Trích xuất từ khóa đồ thị (TextRank), cụm cú pháp (Chunking) và phân loại ý định ML cổ điển.

Không sử dụng bất kỳ mô hình ngôn ngữ lớn (LLM) nào.
Toàn bộ sử dụng thuật toán đồ thị PageRank (networkx), luật cú pháp và máy học scikit-learn (TF-IDF + LogisticRegression).
"""
from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import networkx as nx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from backend.chatbot.ngon_ngu import (
    chuan_hoa,
    chuan_hoa_dia_phuong,
    tach_phu_dinh,
)
from scripts.tach_tu import TachTu, doc_tu_dien

ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_CSV = ROOT / "data" / "merged" / "dataset.csv"

# Từ dừng tiếng Việt và các từ đệm hội thoại
STOPWORDS_VN = {
    "là", "và", "của", "có", "thì", "ở", "cho", "với", "trong", "những", "các",
    "được", "này", "đó", "gì", "sao", "nào", "thế", "như", "nhé", "nha", "ạ",
    "ơi", "bạn", "mình", "tôi", "em", "anh", "chị", "giúp", "hộ", "với",
    "nhỉ", "hả", "ha", "vậy", "ngon", "hay", "chuẩn", "vị", "tại", "nhà",
    "cách", "làm", "hướng", "dẫn", "hỏi", "xin", "làm_ơn", "vui_lòng",
    "một", "hai", "ba", "bốn", "năm", "khoảng", "tầm", "chút", "ít", "nhiều",
}

# -----------------------------------------------------------------------------
# 1. TRÍCH XUẤT TỪ KHÓA ĐỒ THỊ (TEXTRANK / PAGERANK)
# -----------------------------------------------------------------------------

@lru_cache(maxsize=1)
def lay_bo_tach_tu() -> TachTu:
    return TachTu(doc_tu_dien())


def trich_xuat_textrank(
    cau_hoi: str,
    top_k: int = 5,
    cua_so: int = 2,
    damping: float = 0.85,
) -> list[tuple[str, float]]:
    """Trích xuất từ khóa quan trọng bằng thuật toán PageRank trên đồ thị đồng xuất hiện từ (TextRank).

    Mỗi từ (hoặc từ ghép ẩm thực đã được BiMM tách thành token nối _) là một nút trên đồ thị.
    Cạnh nối giữa 2 từ xuất hiện cùng nhau trong cửa sổ `cua_so`.
    """
    if not cau_hoi or not cau_hoi.strip():
        return []

    tach = lay_bo_tach_tu()
    cau_chuan = chuan_hoa_dia_phuong(cau_hoi)
    cau_tach = tach.tach_cau_hoi(cau_chuan).lower()

    # Tách token, loại bỏ dấu câu và từ dừng
    tokens_raw = [
        t.strip(".,!?;:()[]\"'-")
        for t in cau_tach.split()
        if re.search(r"\w", t)
    ]
    tokens = [
        t for t in tokens_raw
        if len(t) > 1 and t not in STOPWORDS_VN and not t.isdigit()
    ]

    if not tokens:
        return []

    # Xây dựng đồ thị vô hướng đồng xuất hiện
    G = nx.Graph()
    for tok in tokens:
        G.add_node(tok)

    n = len(tokens)
    for i in range(n):
        for j in range(i + 1, min(i + 1 + cua_so, n)):
            u, v = tokens[i], tokens[j]
            if u != v:
                if G.has_edge(u, v):
                    G[u][v]["weight"] += 1.0
                else:
                    G.add_edge(u, v, weight=1.0)

    if G.number_of_nodes() == 0:
        return []

    try:
        if G.number_of_edges() > 0:
            scores = nx.pagerank(G, alpha=damping, weight="weight", max_iter=200)
        else:
            scores = {node: 1.0 / len(tokens) for node in G.nodes()}
    except Exception:
        scores = {node: float(G.degree(node, weight="weight") + 1) for node in G.nodes()}

    # Sắp xếp theo trọng số giảm dần
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(k.replace("_", " "), round(v, 4)) for k, v in ranked[:top_k]]


# -----------------------------------------------------------------------------
# 2. TRÍCH XUẤT CÚ PHÁP (GRAMMAR CHUNKING)
# -----------------------------------------------------------------------------

PAT_MON_AN = re.compile(
    r"\b(?:(nấu|kho|xào|chiên|rán|hấp|luộc|nướng|hầm|nêm|làm|chế biến|chưng|rang)\s+)?"
    r"(canh|cá|thịt|sườn|vịt|gà|tôm|tép|cua|ghẹ|ếch|lươn|ốc|bánh|lẩu|gỏi|cháo|chè|bún|hủ tiếu|mắm|rau|củ|đọt|bắp|bông|khoai)"
    r"(?:\s+([^\W\d_]+(?:\s+[^\W\d_]+){0,3}))?\b",
    flags=re.IGNORECASE,
)

PAT_DINH_DUONG = re.compile(
    r"\b(ít|nhiều|giàu|giảm|hạn chế|thừa|thiếu|kiểm soát|thanh)\s+"
    r"(đạm|protein|béo|chất béo|mỡ|dầu|dầu mỡ|đường|calo|kcal|calories|muối|natri|chất xơ|xơ|tinh bột|carb|năng lượng|đạm protein)\b",
    flags=re.IGNORECASE,
)

PAT_DI_UNG_KIENG = re.compile(
    r"\b(dị ứng(?: với)?|kiêng(?: ăn)?|không ăn(?: được)?|không dùng|không nêm|tránh(?: ăn)?|ghét ăn)\s+"
    r"([^,;.!?]+)",
    flags=re.IGNORECASE,
)


def trich_xuat_cum_cu_phap(cau_hoi: str) -> dict[str, list[str]]:
    """Gom cụm thực thể dựa trên luật ngữ pháp (Grammar Chunker):

    - cum_mon_an: <V_chế_biến>? + <N_thực_phẩm> + <Modifier>
    - rang_buoc_dinh_duong: <Modifier_định_lượng> + <N_dinh_dưỡng>
    - di_ung_kieng: <V_phủ_định/kiêng> + <N_thực_thể>
    """
    chuan = chuan_hoa_dia_phuong(cau_hoi or "").strip()
    ket_qua: dict[str, list[str]] = {
        "cum_mon_an": [],
        "rang_buoc_dinh_duong": [],
        "di_ung_kieng": [],
    }

    # 1. Ràng buộc dinh dưỡng
    for m in PAT_DINH_DUONG.finditer(chuan):
        cum = f"{m.group(1)} {m.group(2)}".strip().lower()
        if cum not in ket_qua["rang_buoc_dinh_duong"]:
            ket_qua["rang_buoc_dinh_duong"].append(cum)

    # 2. Dị ứng & kiêng khem
    for m in PAT_DI_UNG_KIENG.finditer(chuan):
        verb = m.group(1).strip().lower()
        vung = m.group(2).strip()
        vung = re.split(r"\b(?:nhưng|còn|muốn|cần|hãy|gợi ý|nấu|thích|thì|để|nên|là gì)\b", vung, flags=re.I)[0].strip()
        if vung:
            cum = f"{verb}: {vung}".lower()
            if cum not in ket_qua["di_ung_kieng"]:
                ket_qua["di_ung_kieng"].append(cum)

    # 3. Cụm món ăn
    for m in PAT_MON_AN.finditer(chuan):
        verb = (m.group(1) or "").strip().lower()
        noun = m.group(2).strip().lower()
        mod = (m.group(3) or "").strip().lower()
        # Loại trừ nếu mod dính sang mệnh đề khác
        mod = re.split(r"\b(?:ở|tại|cho|như thế nào|thế nào|sao cho|bao nhiêu|mấy|gì|nào|được không)\b", mod)[0].strip()
        cum_parts = [p for p in (verb, noun, mod) if p]
        cum = " ".join(cum_parts)
        if len(cum.split()) >= 2 and cum not in ket_qua["cum_mon_an"]:
            ket_qua["cum_mon_an"].append(cum)

    return ket_qua


# -----------------------------------------------------------------------------
# 3. PHÂN LOẠI Ý ĐỊNH BẰNG MÁY HỌC CỔ ĐIỂN (CLASSICAL ML INTENT CLASSIFIER)
# -----------------------------------------------------------------------------

class PhanLoaiIntentML:
    """Mô hình máy học phân loại 12 nhóm ý định dựa trên TF-IDF n-gram và Logistic Regression."""

    def __init__(self) -> None:
        self.pipeline: Pipeline | None = None
        self.nhom_danh_sach: list[str] = []
        self._huan_luyen()

    def _huan_luyen(self) -> None:
        if not DATASET_CSV.exists():
            return
        X, y = [], []
        with DATASET_CSV.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                q = (row.get("Câu hỏi") or "").strip()
                grp = (row.get("Nhóm") or "").strip()
                if q and grp:
                    X.append(chuan_hoa_dia_phuong(q))
                    y.append(grp)
        if not X:
            return

        union = FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2)),
        ])
        clf = LogisticRegression(max_iter=300, random_state=42, C=1.5)
        self.pipeline = Pipeline([
            ("feats", union),
            ("clf", clf),
        ])
        self.pipeline.fit(X, y)
        self.nhom_danh_sach = list(self.pipeline.classes_)

    def du_doan(self, cau_hoi: str, top_k: int = 3) -> dict[str, Any]:
        if not self.pipeline or not cau_hoi or not cau_hoi.strip():
            return {"nhom": "02_huong_dan_nau_an", "diem": 0.0, "top_nhom": []}
        chuan = chuan_hoa_dia_phuong(cau_hoi)
        probs = self.pipeline.predict_proba([chuan])[0]
        indexed = sorted(enumerate(probs), key=lambda x: x[1], reverse=True)
        top = [(self.nhom_danh_sach[i], round(float(p), 4)) for i, p in indexed[:top_k]]
        best_grp, best_prob = top[0]
        return {
            "nhom": best_grp,
            "diem": best_prob,
            "top_nhom": top,
        }


@lru_cache(maxsize=1)
def lay_bo_phan_loai_ml() -> PhanLoaiIntentML:
    return PhanLoaiIntentML()


# -----------------------------------------------------------------------------
# 4. TỔNG HỢP PHÂN TÍCH CHUYÊN SÂU
# -----------------------------------------------------------------------------

def phan_tich_chuyen_sau(cau_hoi: str) -> dict[str, Any]:
    """Kết hợp phân tích toàn diện: TextRank, Cú pháp, Phủ định, và ML Intent."""
    chuan = chuan_hoa_dia_phuong(cau_hoi)
    tu_khoa = trich_xuat_textrank(cau_hoi, top_k=5)
    cum_cu_phap = trich_xuat_cum_cu_phap(cau_hoi)
    pham_vi = tach_phu_dinh(cau_hoi)
    bo_ml = lay_bo_phan_loai_ml()
    du_doan_ml = bo_ml.du_doan(cau_hoi)

    return {
        "cau_goc": cau_hoi,
        "cau_chuan": chuan,
        "tu_khoa_textrank": tu_khoa,
        "cum_cu_phap": cum_cu_phap,
        "positive_keywords": pham_vi["positive_keywords"],
        "negative_keywords": pham_vi["negative_keywords"],
        "phan_loai_ml": du_doan_ml,
    }

