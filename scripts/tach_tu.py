"""Tách từ tiếng Việt cho cột Câu hỏi và Câu trả lời (theo Bài 3).

Cách chạy (từ thư mục gốc project):
    .venv\\Scripts\\python.exe scripts/tach_tu.py                              # tất cả nhóm
    .venv\\Scripts\\python.exe scripts/tach_tu.py --nhom 06_thay_the_nguyen_lieu

Đầu vào : data/groups/*/all.csv (nếu không có thì Dataset_1000.csv).
Đầu ra  : data/tach_tu/tach_tu_cau_hoi.csv     (ID;Nhóm;Tập;Câu hỏi;Câu hỏi tách từ)
          data/tach_tu/tach_tu_cau_tra_loi.csv  (ID;Nhóm;Tập;Câu trả lời;Câu trả lời tách từ;Số câu trả lời;Nguồn)
          data/tach_tu/tat_ca.jsonl, reports/kiem_tra_tach_tu.md
          Chạy một nhóm thì thêm đuôi _<nhom> vào tên 2 file CSV và báo cáo, không ghi đè tat_ca.jsonl.
Không sửa file gốc, không sửa 6 cột gốc.
"""
import argparse
import csv
import json
import random
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from underthesea import sent_tokenize, word_tokenize

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
GROUPS = DATA / "groups"
OUT_DIR = DATA / "tach_tu"
REPORTS = ROOT / "reports"
TU_DIEN_PATH = ROOT / "cau_hinh" / "tu_dien_rieng.txt"
FALLBACK_INPUTS = [ROOT / "Dataset_1000.csv", DATA / "raw" / "Dataset_1000.csv"]

HEADER = ["ID", "Nhóm", "Tập", "Câu hỏi", "Câu trả lời", "Nguồn"]
SEED = 42
KIEU_DAU = "kiểu cũ: dấu đặt trên nguyên âm thứ nhất khi vần không có phụ âm cuối (hòa, thủy, khỏe, lóa)"

# ---------------------------------------------------------------- tiền xử lý

DAU_THANH = "[̣̀́̃̉]"  # huyền, sắc, ngã, hỏi, nặng (dạng tổ hợp NFD)
# oà/oé/uỷ ... ở cuối âm tiết → òa/óe/ủy. Bỏ qua "qu" (quý, quỷ) và vần có phụ âm cuối (hoàn, thuyền).
# Sau dấu thanh không được còn dấu phụ (ă â ê): ở dạng NFD, "ặ" = a + dấu nặng + dấu trăng nên "hoặc" không phải vần oa.
OA_OE = re.compile(r"(?<![qQ])([oO])([aAeE])(" + DAU_THANH + r")(?![^\W\d_]|[̀-ͯ])")
UY = re.compile(r"(?<![qQ])([uU])([yY])(" + DAU_THANH + r")(?![^\W\d_]|[̀-ͯ])")

KHOANG_TRANG_LA = re.compile(r"[ ​   　﻿\t]")
NHAY_CONG = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "‚": "'",
                           "–": "-", "—": "-", "―": "-", "−": "-"})
URL_RE = re.compile(r"(?:https?://|www\.)\S+?(?=[.,;:!?)\]]*(?:\s|$))")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# dấu câu dính chữ phía sau: "nha.Mình" → "nha. Mình" (số như 1,5 / 7:30 không bị ảnh hưởng)
DINH_DAU = re.compile(r"(?<=\S)([.,!?;:])(?=[^\W\d_])")
NHIEU_CACH = re.compile(r" {2,}")


def chuan_hoa_dau(text):
    """Đưa kiểu đặt dấu mới (hoà, thuỷ) về kiểu cũ (hòa, thủy). Trả về (text, số chỗ đã sửa)."""
    nfd = unicodedata.normalize("NFD", text)
    nfd, n1 = OA_OE.subn(r"\1\3\2", nfd)
    nfd, n2 = UY.subn(r"\1\3\2", nfd)
    return unicodedata.normalize("NFC", nfd), n1 + n2


def _them_cach_sau_dau(text):
    """Thêm dấu cách sau . , ! ? ; : khi dính chữ, giữ nguyên URL và email."""
    out, last = [], 0
    for m in re.finditer(f"{URL_RE.pattern}|{EMAIL_RE.pattern}", text):
        out.append(DINH_DAU.sub(r"\1 ", text[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(DINH_DAU.sub(r"\1 ", text[last:]))
    return "".join(out)


def tien_xu_ly(text, thong_ke):
    """Các bước 1→4 của mục 2 theo đúng thứ tự. Giữ xuống dòng, không sửa chính tả."""
    text = unicodedata.normalize("NFC", text)                       # 1. NFC
    text, n = chuan_hoa_dau(text)                                   # 2. một kiểu đặt dấu
    thong_ke["doi_kieu_dau"] += n
    text = KHOANG_TRANG_LA.sub(" ", text).translate(NHAY_CONG)      # 3. khoảng trắng lạ, nháy, gạch
    moi = _them_cach_sau_dau(text)                                  # 4. dấu câu dính chữ
    if moi != text:
        thong_ke["them_cach_sau_dau"] += 1
    lines = [NHIEU_CACH.sub(" ", line).strip() for line in moi.split("\n")]
    return "\n".join(lines).strip()


# ------------------------------------------------------- bảo vệ token đặc biệt

DON_VI = sorted(["độ C", "°C", "°", "kcal", "calo", "lít", "phút", "giờ", "giây", "ngày", "tuần",
                 "tháng", "kg", "mg", "ml", "gr", "g", "l", "cm", "mm", "cc", "%"], key=len, reverse=True)
SO = r"\d+(?:[.,:/]\d+)*"
SO_DON_VI = re.compile(r"(?<![\w.,])" + SO + r"(?:\s?(?:" + "|".join(map(re.escape, DON_VI)) + r"))?(?![^\W_])")
BUOC = re.compile(r"\b[Bb]ước\s+\d+\b")
DAU_DONG = re.compile(r"^(\d+[.)]|[a-zA-Zđ]\))(?=\s)")
PH_RE = re.compile(r"zzph[a-j]+z")


def _ma_placeholder(i):
    """Placeholder chỉ gồm chữ thường để thư viện coi như một âm tiết: 12 → zzphbcz."""
    return "zzph" + "".join("abcdefghij"[int(c)] for c in str(i)) + "z"


def bao_ve(text, kho):
    """Thay URL, email, Bước n, số + đơn vị, đầu mục 1. / a) bằng placeholder."""
    def thay(m):
        ma = _ma_placeholder(len(kho))
        kho[ma] = m.group(0)
        return ma
    text = URL_RE.sub(thay, text)
    text = EMAIL_RE.sub(thay, text)
    text = BUOC.sub(thay, text)
    text = DAU_DONG.sub(thay, text)
    return SO_DON_VI.sub(thay, text)


def _tach_placeholder(tokens):
    """Thư viện có thể nối placeholder với từ bên cạnh (zzphaz_zzphbz) → tách ra lại."""
    out = []
    for tok in tokens:
        if not PH_RE.search(tok):
            out.append(tok)
            continue
        cum = []
        for phan in tok.split("_"):
            if PH_RE.search(phan):  # cả khoảng số zzphaz-zzphbz cũng phải đứng riêng
                if cum:
                    out.append("_".join(cum))
                    cum = []
                out.append(phan)
            else:
                cum.append(phan)
        if cum:
            out.append("_".join(cum))
    return out


# --------------------------------------------------------------- tách từ

def doc_tu_dien():
    """Đọc từ điển riêng, chuẩn hóa giống văn bản, bỏ dòng trống/trùng."""
    tu = []
    for line in TU_DIEN_PATH.read_text(encoding="utf-8-sig").splitlines():
        line = " ".join(chuan_hoa_dau(unicodedata.normalize("NFC", line))[0].split())
        if line and not line.startswith("#") and line not in tu:
            tu.append(line)
    return tu


class TachTu:
    def __init__(self, tu_dien, trong_so_cum=None):
        self.tu_dien = tu_dien
        self.cum = {tuple(t.lower().split()) for t in tu_dien if len(t.split()) > 1}
        self.max_len = max((len(c) for c in self.cum), default=0)
        # Trọng số ưu tiên cho giải thuật Bi-directional Maximum Matching (FMM + BMM)
        self.trong_so_cum = {
            c: (trong_so_cum.get(" ".join(c), 1.0) if trong_so_cum else 1.0) * (len(c) ** 1.5)
            for c in self.cum
        }
        self.dem_thu_vien_sai = Counter()  # cụm từ điển mà thư viện tách sai (trước khi ép)

    def _tim_khop_fmm(self, thap):
        """Forward Maximum Matching (FMM): quét từ trái sang phải."""
        spans = []
        i, n = 0, len(thap)
        while i < n:
            for L in range(min(self.max_len, n - i), 1, -1):
                if tuple(thap[i:i + L]) in self.cum:
                    spans.append((i, i + L))
                    i += L
                    break
            else:
                i += 1
        return spans

    def _tim_khop_bmm(self, thap):
        """Backward Maximum Matching (BMM): quét từ phải sang trái."""
        spans = []
        j = len(thap)
        while j > 0:
            for L in range(min(self.max_len, j), 1, -1):
                if tuple(thap[j - L:j]) in self.cum:
                    spans.append((j - L, j))
                    j -= L
                    break
            else:
                j -= 1
        spans.reverse()
        return spans

    def _diem_phu_ongan(self, spans, thap):
        """Chấm điểm phương án khớp từ điển: ưu tiên độ phủ âm tiết cao, ít mảnh lẻ, trọng số cụm lớn."""
        so_am_phu = sum(e - s for s, e in spans)
        trong_so = sum(self.trong_so_cum.get(tuple(thap[s:e]), float(e - s)) for s, e in spans)
        # Số cụm khớp càng ít (tức cụm càng dài) càng tốt khi cùng độ phủ
        return (so_am_phu, trong_so, -len(spans))

    def _chon_khop_hai_chieu(self, thap):
        """Bi-directional Maximum Matching (BiMM): kết hợp FMM và BMM có trọng số."""
        fmm = self._tim_khop_fmm(thap)
        bmm = self._tim_khop_bmm(thap)
        if fmm == bmm:
            return fmm
        if self._diem_phu_ongan(bmm, thap) >= self._diem_phu_ongan(fmm, thap):
            return bmm
        return fmm

    def _ep_tu_dien(self, tokens):
        """Ép ranh giới đúng theo từ điển bằng Bi-directional Maximum Matching (FMM/BMM):
        cụm trong từ điển thành đúng một token, ưu tiên thực thể ẩm thực dài và trọng số cao.

        fixed_words của underthesea 9.5 hay nối các cụm đứng cạnh nhau (canh_chua_cá_lóc)
        hoặc nối cụm với từ trước (Nêm_nước_mắm), nên phải sửa lại ranh giới ở đây.
        """
        am_tiet, noi = [], []  # noi[i] = True nếu âm tiết i nối với âm tiết i+1
        for tok in tokens:
            parts = tok.split("_") if tok != "_" else ["_"]
            for j, p in enumerate(parts):
                am_tiet.append(p)
                noi.append(j < len(parts) - 1)
        thap = [a.lower() for a in am_tiet]
        spans = self._chon_khop_hai_chieu(thap)
        for s, e in spans:
            dung = all(noi[s:e - 1]) and not noi[e - 1] and (s == 0 or not noi[s - 1])
            if not dung:
                self.dem_thu_vien_sai[" ".join(thap[s:e])] += 1
            if s > 0:
                noi[s - 1] = False
            for k in range(s, e - 1):
                noi[k] = True
            noi[e - 1] = False
        out, cur = [], []
        for a, n in zip(am_tiet, noi):
            cur.append(a)
            if not n:
                out.append("_".join(cur))
                cur = []
        return out

    def tach_doan(self, text_bao_ve, kho):
        """Tách từ một đoạn đã thay placeholder, trả về chuỗi đã trả lại giá trị gốc."""
        kq = word_tokenize(text_bao_ve, format="text", fixed_words=self.tu_dien, use_token_normalize=False)
        tokens = _tach_placeholder(kq.split())
        tokens = self._ep_tu_dien(tokens)
        # placeholder có thể nằm giữa token (khoảng số "3-4" → zzphaz-zzphbz) nên thay bằng regex
        return " ".join(PH_RE.sub(lambda m: kho[m.group(0)], t) for t in tokens)

    def tach_cau_hoi(self, text):
        kho = {}
        return self.tach_doan(bao_ve(" ".join(text.split("\n")), kho), kho)

    def tach_cau_tra_loi(self, text):
        """Tách câu (theo từng dòng) → gộp câu < 3 từ vào câu sau → tách từ từng câu."""
        kho, cau = {}, []
        for line in text.split("\n"):
            if line.strip():
                cau.extend(s.strip() for s in sent_tokenize(bao_ve(line, kho)) if s.strip())
        gop, dem = [], ""
        for s in cau:
            dem = f"{dem} {s}" if dem else s
            if so_tu(PH_RE.sub(lambda m: kho[m.group(0)], dem)) >= 3:
                gop.append(dem)
                dem = ""
        if dem:
            if gop:
                gop[-1] = f"{gop[-1]} {dem}"
            else:
                gop.append(dem)
        return " ".join(self.tach_doan(s, kho) for s in gop), len(gop)


def so_tu(text):
    """Số từ = số token có chữ hoặc số (không tính dấu câu)."""
    return sum(1 for t in text.split() if re.search(r"\w", t))


def tu_ghep(text):
    """Token có _ nối các âm tiết (bỏ qua URL/email vốn có _ sẵn)."""
    return [t for t in text.split() if "_" in t.strip("_") and re.search(r"[^\W\d_]", t)
            and "://" not in t and "@" not in t and not t.startswith("www.")]


def bo_khoang_trang(text):
    return re.sub(r"\s+", "", text.replace("_", " "))


# ------------------------------------------------------------- đọc / ghi

def doc_csv(path):
    """Đọc CSV ;, utf-8-sig, bỏ dòng trống hoàn toàn. Giữ nguyên giá trị gốc."""
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    rows, trong = [], 0
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        header = [h.strip() for h in next(reader)]
        if header != HEADER:
            sys.exit(f"Header không khớp ở {path}: {header}")
        for r in reader:
            if not any(c.strip() for c in r):
                trong += 1
                continue
            r = (r + [""] * len(HEADER))[:len(HEADER)]
            rows.append(dict(zip(HEADER, r)))
    return rows, trong, newline


def tim_dau_vao(nhom):
    """Danh sách (tên, path): ưu tiên data/groups/*/all.csv, nếu không có thì Dataset_1000.csv."""
    if GROUPS.exists() and any(GROUPS.glob("*/all.csv")):
        ds = [(p.parent.name, p) for p in sorted(GROUPS.glob("*/all.csv"))]
        if nhom:
            ds = [x for x in ds if x[0] == nhom]
            if not ds:
                ten = ", ".join(p.parent.name for p in sorted(GROUPS.glob("*/all.csv")))
                sys.exit(f"Không có nhóm '{nhom}'. Các nhóm: {ten}")
        return ds
    for p in FALLBACK_INPUTS:
        if p.exists():
            return [("dataset_tach_tu", p)]
    sys.exit("Không tìm thấy data/groups/*/all.csv hoặc Dataset_1000.csv")


COT_FILE_HOI = ["ID", "Nhóm", "Tập", "Câu hỏi", "Câu hỏi tách từ"]
COT_FILE_TL = ["ID", "Nhóm", "Tập", "Câu trả lời", "Câu trả lời tách từ", "Số câu trả lời", "Nguồn"]


def ghi_csv(path, rows, cot, newline):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator=newline)
        w.writerow(cot)
        for r in rows:
            w.writerow([r[c] for c in cot])


# ------------------------------------------------------------------ báo cáo

def kiem_thu_chuan_hoa():
    """Kiểm thử slide 33: cùng chữ 'cá lóc' ở dạng NFD và NFC."""
    goc = "Cách nấu cá lóc"
    nfd, nfc = unicodedata.normalize("NFD", goc), unicodedata.normalize("NFC", goc)
    t_nfd = word_tokenize(nfd, format="text", use_token_normalize=False)
    t_nfc = word_tokenize(nfc, format="text", use_token_normalize=False)
    t_sau = word_tokenize(unicodedata.normalize("NFC", nfd), format="text", use_token_normalize=False)
    # ví dụ thứ hai: hai kiểu đặt dấu
    moi, cu = "Khuấy cho đường hoà tan", "Khuấy cho đường hòa tan"
    t_moi = word_tokenize(moi, format="text", use_token_normalize=False)
    t_cu = word_tokenize(cu, format="text", use_token_normalize=False)
    t_moi_sau = word_tokenize(chuan_hoa_dau(moi)[0], format="text", use_token_normalize=False)
    L = ["## 2. Kiểm thử chuẩn hóa (slide 33)", "",
         "**a) NFD và NFC**", "",
         "| | NFD (dấu tổ hợp) | NFC (dựng sẵn) |", "|---|---|---|",
         f"| Số ký tự của `{goc}` | {len(nfd)} | {len(nfc)} |",
         f"| So sánh chuỗi `nfd == nfc` | `{nfd == nfc}` | |",
         f"| Có tìm thấy `\"cá lóc\"` (NFC) trong chuỗi? | `{'cá lóc' in nfd}` | `{'cá lóc' in nfc}` |",
         f"| Tách từ trước chuẩn hóa | `{t_nfd}` ({len(t_nfd)} ký tự) | `{t_nfc}` ({len(t_nfc)} ký tự) |",
         f"| Tách từ sau `normalize('NFC')` | `{t_sau}` | `{t_nfc}` |", "",
         f"- Trước chuẩn hóa hai chuỗi **khác nhau** ({len(nfd)} và {len(nfc)} ký tự), nên tra từ điển và đếm từ cho kết quả khác.",
         f"- Kết quả tách từ trước chuẩn hóa giống nhau: `{t_nfd == t_nfc}`. Lưu ý: underthesea 9.5 tự đổi đầu vào NFD về NFC"
         " bên trong hàm tách từ, nên riêng bước tách từ không thấy khác biệt. Các bước khác của pipeline"
         " (từ điển riêng, regex bảo vệ số, so khớp chuỗi) vẫn bị ảnh hưởng, nên NFC vẫn phải làm đầu tiên.",
         f"- Sau chuẩn hóa: `{t_sau == t_nfc}` (giống nhau).", "",
         "**b) Hai kiểu đặt dấu (bước 2), thư viện không tự sửa**", "",
         "| Câu | Tách từ |", "|---|---|",
         f"| `{moi}` (kiểu mới) | `{t_moi}` |",
         f"| `{cu}` (kiểu cũ) | `{t_cu}` |",
         f"| `{moi}` sau khi thống nhất dấu | `{t_moi_sau}` |", "",
         f"- Trước chuẩn hóa dấu, hai câu cho kết quả giống nhau? `{t_moi == t_cu}`: cùng một từ bị tách thành hai kiểu khác nhau.",
         f"- Sau chuẩn hóa dấu, giống nhau? `{t_moi_sau == t_cu}`.", ""]
    return L


def viet_bao_cao(path, ket_qua, tach, thong_ke, chay_mot_nhom):
    tat_ca = [r for _, rows in ket_qua for r in rows]
    L = ["# Kiểm tra tách từ", "",
         f"- Kiểu đặt dấu đã chọn: **{KIEU_DAU}**.",
         "- Thư viện: underthesea 9.5.0, `word_tokenize(..., format=\"text\", fixed_words=TU_DIEN_RIENG, use_token_normalize=False)`.",
         f"- Từ điển riêng: `cau_hinh/tu_dien_rieng.txt` ({len(tach.tu_dien)} cụm).",
         f"- Số dòng: {len(tat_ca)}. Dòng trống đã bỏ: {thong_ke['dong_trong']}.",
         f"- Tiền xử lý: {thong_ke['doi_kieu_dau']} chỗ đổi kiểu đặt dấu, {thong_ke['them_cach_sau_dau']} ô được thêm dấu cách sau dấu câu.",
         f"- Seed ngẫu nhiên: {SEED}.", ""]
    if chay_mot_nhom:
        L += [f"> Chỉ chạy nhóm `{ket_qua[0][0]}`.", ""]

    # 1. không mất chữ
    loi = [(r["ID"], cot) for r in tat_ca for cot, a, b in
           (("Câu hỏi", r["_hoi_tx"], r["Câu hỏi tách từ"]), ("Câu trả lời", r["_tl_tx"], r["Câu trả lời tách từ"]))
           if bo_khoang_trang(a) != bo_khoang_trang(b)]
    L += ["## 1. Không mất chữ", "",
          "So sánh văn bản đã tiền xử lý và bản tách từ, sau khi đổi `_` thành dấu cách và bỏ toàn bộ khoảng trắng.", "",
          f"- Lỗi ở Câu hỏi: **{sum(1 for _, c in loi if c == 'Câu hỏi')}**",
          f"- Lỗi ở Câu trả lời: **{sum(1 for _, c in loi if c == 'Câu trả lời')}**", ""]
    if loi:
        L += ["| ID | Cột |", "|---|---|"] + [f"| {i} | {c} |" for i, c in loi] + [""]

    L += kiem_thu_chuan_hoa()

    # 3. top 50 từ ghép
    dem = Counter(t.lower() for r in tat_ca for col in ("Câu hỏi tách từ", "Câu trả lời tách từ")
                  for t in tu_ghep(r[col]))
    L += ["## 3. Top 50 từ ghép", "", "| # | Từ ghép | Số lần |", "|---|---|---|"]
    L += [f"| {i} | {t} | {n} |" for i, (t, n) in enumerate(dem.most_common(50), 1)] + [""]

    # 4. nghi tách sai
    con_tach = Counter()
    for r in tat_ca:
        for col in ("Câu hỏi tách từ", "Câu trả lời tách từ"):
            txt = r[col].lower()
            for cum in tach.cum:
                pat = r"(?<![\w])" + r"[ _]".join(map(re.escape, cum)) + r"(?![\w])"
                for m in re.finditer(pat, txt):
                    if " " in m.group(0):
                        con_tach[" ".join(cum)] += 1
    dai = Counter(t for t in dem if t.count("_") >= 4)
    L += ["## 4. Nghi tách sai", "",
          "**a) Cụm trong từ điển riêng vẫn bị tách rời trong kết quả cuối**", "",
          "Bước ép từ điển luôn ghép đủ cụm, nên mục này phải bằng 0. Nếu khác 0 tức là bước ép bị lỗi.", ""]
    L += ([f"- `{c}`: {n} lần" for c, n in con_tach.most_common()] or ["- Không có (0 trường hợp)."]) + [""]
    L += ["**b) Cụm từ điển mà underthesea tách sai, đã được bước ép từ điển sửa lại**", "",
          "Thư viện tách rời cụm hoặc nối cụm với từ bên cạnh (ví dụ `Nêm_nước_mắm`, `canh_chua_cá_lóc`).", "",
          "| Cụm | Số lần đã sửa |", "|---|---|"]
    L += [f"| {c} | {n} |" for c, n in tach.dem_thu_vien_sai.most_common()] + [""]
    L += ["**c) Từ ghép dài hơn 4 âm tiết**", ""]
    L += ([f"- `{t}`: {dem[t]} lần" for t in sorted(dai, key=lambda x: (-dem[x], x))] or ["- Không có."]) + [""]

    # 5. trước và sau
    L += ["## 5. So sánh trước và sau (3 dòng ngẫu nhiên mỗi nhóm, seed = 42)", ""]
    for ten, rows in ket_qua:
        L += [f"### {ten}", ""]
        for r in random.Random(SEED).sample(rows, min(3, len(rows))):
            L += [f"**ID {r['ID']}**", "",
                  f"- Câu hỏi gốc: {r['Câu hỏi']}",
                  f"- Câu hỏi tách từ: `{r['Câu hỏi tách từ']}`", "",
                  "Câu trả lời gốc:", "", "```text", r["Câu trả lời"], "```", "",
                  f"Câu trả lời tách từ ({r['Số câu trả lời']} câu):", "", "```text", r["Câu trả lời tách từ"], "```", ""]

    # 6. thống kê
    L += ["## 6. Thống kê theo nhóm", "",
          "| Nhóm | Số dòng | Từ TB / câu hỏi | Từ TB / câu trả lời | Câu TB / câu trả lời | Từ ghép TB / câu hỏi | Từ ghép TB / câu trả lời |",
          "|---|---|---|---|---|---|---|"]
    for ten, rows in ket_qua:
        L.append(f"| {ten} | {len(rows)} | {tb(rows, lambda r: so_tu(r['Câu hỏi tách từ']))} | "
                 f"{tb(rows, lambda r: so_tu(r['Câu trả lời tách từ']))} | {tb(rows, lambda r: r['Số câu trả lời'])} | "
                 f"{tb(rows, lambda r: len(tu_ghep(r['Câu hỏi tách từ'])))} | "
                 f"{tb(rows, lambda r: len(tu_ghep(r['Câu trả lời tách từ'])))} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return loi


def tb(rows, f):
    return f"{sum(f(r) for r in rows) / len(rows):.1f}" if rows else "0"


# --------------------------------------------------------------------- main

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Tách từ Câu hỏi và Câu trả lời")
    ap.add_argument("--nhom", help="tên thư mục nhóm, ví dụ 06_thay_the_nguyen_lieu")
    args = ap.parse_args()

    tach = TachTu(doc_tu_dien())
    thong_ke = Counter()
    ket_qua = []
    for ten, path in tim_dau_vao(args.nhom):
        rows, trong, newline = doc_csv(path)
        thong_ke["dong_trong"] += trong
        for r in rows:
            r["_hoi_tx"] = tien_xu_ly(r["Câu hỏi"], thong_ke)
            r["_tl_tx"] = tien_xu_ly(r["Câu trả lời"], thong_ke)
            r["Câu hỏi tách từ"] = tach.tach_cau_hoi(r["_hoi_tx"])
            r["Câu trả lời tách từ"], r["Số câu trả lời"] = tach.tach_cau_tra_loi(r["_tl_tx"])
        ket_qua.append((ten, rows))
        print(f"Đã tách {ten}: {len(rows)} dòng")

    # 2 file riêng: tách từ câu hỏi và tách từ câu trả lời (gộp mọi nhóm, giữ thứ tự nhóm)
    tat_ca = [r for _, rows in ket_qua for r in rows]
    duoi = f"_{args.nhom}" if args.nhom else ""
    ghi_csv(OUT_DIR / f"tach_tu_cau_hoi{duoi}.csv", tat_ca, COT_FILE_HOI, newline)
    ghi_csv(OUT_DIR / f"tach_tu_cau_tra_loi{duoi}.csv", tat_ca, COT_FILE_TL, newline)

    if not args.nhom:
        with (OUT_DIR / "tat_ca.jsonl").open("w", encoding="utf-8", newline="\n") as f:
            for _, rows in ket_qua:
                for r in rows:
                    f.write(json.dumps({"id": r["ID"], "nhom": r["Nhóm"], "tap": r["Tập"],
                                        "cau_hoi": r["Câu hỏi"], "cau_hoi_tach_tu": r["Câu hỏi tách từ"],
                                        "cau_tra_loi": r["Câu trả lời"],
                                        "cau_tra_loi_tach_tu": r["Câu trả lời tách từ"]},
                                       ensure_ascii=False) + "\n")
    bc = REPORTS / (f"kiem_tra_tach_tu_{args.nhom}.md" if args.nhom else "kiem_tra_tach_tu.md")
    loi = viet_bao_cao(bc, ket_qua, tach, thong_ke, bool(args.nhom))

    print()
    print(f"{'Nhóm':<32} {'Dòng':>5} {'Lỗi CH':>7} {'Lỗi TL':>7} {'Câu TB/TL':>10} {'Ghép TB':>8}")
    for ten, rows in ket_qua:
        ids = {r["ID"] for r in rows}
        lch = sum(1 for i, c in loi if c == "Câu hỏi" and i in ids)
        ltl = sum(1 for i, c in loi if c == "Câu trả lời" and i in ids)
        ghep = tb(rows, lambda r: len(tu_ghep(r["Câu hỏi tách từ"])) + len(tu_ghep(r["Câu trả lời tách từ"])))
        print(f"{ten:<32} {len(rows):>5} {lch:>7} {ltl:>7} {tb(rows, lambda r: r['Số câu trả lời']):>10} {ghep:>8}")
    print(f"\nBáo cáo: {bc.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
