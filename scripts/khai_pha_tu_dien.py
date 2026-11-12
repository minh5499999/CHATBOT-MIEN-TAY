"""Tự động khai phá và mở rộng Từ điển ẩm thực miền Tây từ kho dữ liệu.

Quét toàn bộ tên món ăn, nguyên liệu trong `câu hoi.xlsx` và `data/merged/dataset.csv`
để trích xuất các cụm danh từ ẩm thực 2–4 âm tiết chưa có trong `cau_hinh/tu_dien_rieng.txt`.

Cách chạy:
    .venv\\Scripts\\python.exe scripts/khai_pha_tu_dien.py              # xem trước các cụm khai phá được
    .venv\\Scripts\\python.exe scripts/khai_pha_tu_dien.py --cap-nhat   # tự động sao lưu và thêm vào tu_dien_rieng.txt
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TU_DIEN_PATH = ROOT / "cau_hinh" / "tu_dien_rieng.txt"
DATASET_CSV = ROOT / "data" / "merged" / "dataset.csv"
EXCEL_FILES = [ROOT / "câu hoi.xlsx", ROOT / "data" / "raw" / "câu hoi.xlsx"]

TIENG_DAU_AM_THUC = {
    "cá", "tôm", "tép", "cua", "ốc", "ếch", "lươn", "vịt", "gà", "heo", "bò",
    "mắm", "lẩu", "canh", "bún", "bánh", "hủ", "cháo", "gỏi", "chè", "xôi",
    "bông", "rau", "lá", "đọt", "củ", "trái", "quả", "dưa", "măng", "nấm",
    "nước", "dầu", "muối", "đường", "bột", "hạt", "ớt", "hành", "tỏi", "sả",
    "chao", "me", "cơm", "thịt", "sườn", "giò", "chả", "lạp", "khô", "dừa",
}

TU_DUNG_LOAI_BO = {
    "cách", "làm", "nấu", "món", "như", "thế", "nào", "sao", "cho", "ngon",
    "miền", "tây", "tại", "nhà", "đơn", "giản", "nhất", "bao", "nhiêu", "phút",
    "giờ", "người", "ăn", "khi", "bị", "có", "nên", "không", "được", "với",
    "hoặc", "và", "các", "loại", "trong", "ngoài", "trên", "dưới", "của",
    "những", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín",
    "muỗng", "gram", "ml", "lít", "trái", "củ", "nhánh", "tép", "miếng",
}


def _chuan_hoa(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def doc_tu_dien_hien_tai() -> set[str]:
    if not TU_DIEN_PATH.exists():
        return set()
    out = set()
    for line in TU_DIEN_PATH.read_text(encoding="utf-8-sig").splitlines():
        s = _chuan_hoa(line).lower()
        if s and not s.startswith("#"):
            out.add(s)
    return out


def _hop_le_cum_am_thuc(words: list[str]) -> bool:
    if not (2 <= len(words) <= 4):
        return False
    if any(not re.fullmatch(r"[^\W\d_]+", w) for w in words):
        return False
    if words[0] in TU_DUNG_LOAI_BO or words[-1] in TU_DUNG_LOAI_BO:
        return False
    if sum(1 for w in words if w in TU_DUNG_LOAI_BO) >= 2:
        return False
    return words[0] in TIENG_DAU_AM_THUC


def _quet_nguyen_lieu_tu_cau_tra_loi(cau_tra_loi: str, counter: Counter) -> None:
    for line in (cau_tra_loi or "").splitlines():
        line_clean = line.strip(" -•*\t")
        if not line_clean:
            continue
        # Các dòng liệt kê nguyên liệu thường có dấu : hoặc định lượng g, ml, muỗng, củ, quả...
        phan = re.split(r"[:;,()–—-]", line_clean)[0].strip().lower()
        words = re.findall(r"[^\W\d_]+", phan)
        if _hop_le_cum_am_thuc(words):
            counter[" ".join(words)] += 2


def _quet_ten_mon_tu_cau_hoi(cau_hoi: str, counter: Counter) -> None:
    q = _chuan_hoa(cau_hoi).lower()
    for pat in (
        r"(?:cách\s+nấu|cách\s+làm|công\s+thức\s+nấu|công\s+thức\s+làm|món)\s+([^\n,?.!;:]+)",
    ):
        for m in re.finditer(pat, q):
            doan = m.group(1)
            doan = re.split(
                r"\b(?:như thế nào|thế nào|sao cho|tại nhà|miền tây|đơn giản|ngon nhất|cần những gì|gồm những gì|bao lâu)\b",
                doan,
            )[0].strip()
            words = re.findall(r"[^\W\d_]+", doan)
            # Lấy cả cụm 2-4 âm tiết hoặc cửa sổ con bắt đầu bằng từ khóa ẩm thực
            for n in (2, 3, 4):
                for i in range(0, max(0, len(words) - n + 1)):
                    sub = words[i : i + n]
                    if _hop_le_cum_am_thuc(sub):
                        counter[" ".join(sub)] += 1


def khai_pha_cum_am_thuc(min_freq: int = 3, gioi_han: int = 60, cap_nhat: bool = False) -> list[tuple[str, int]]:
    """Quét dataset.csv và câu hoi.xlsx để tìm cụm từ ẩm thực 2-4 âm tiết mới."""
    hien_co = doc_tu_dien_hien_tai()
    counter: Counter = Counter()

    if DATASET_CSV.exists():
        with DATASET_CSV.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                _quet_ten_mon_tu_cau_hoi(row.get("Câu hỏi", ""), counter)
                _quet_nguyen_lieu_tu_cau_tra_loi(row.get("Câu trả lời", ""), counter)

    for excel_path in EXCEL_FILES:
        if excel_path.exists():
            try:
                import openpyxl
                wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
                for sheet in wb.sheetnames:
                    ws = wb[sheet]
                    for row in ws.iter_rows(min_row=2, values_only=True):
                        if not row or len(row) < 5:
                            continue
                        cau_hoi = str(row[3] or "")
                        cau_tra_loi = str(row[4] or "")
                        _quet_ten_mon_tu_cau_hoi(cau_hoi, counter)
                        _quet_nguyen_lieu_tu_cau_tra_loi(cau_tra_loi, counter)
                wb.close()
            except Exception:
                pass
            break

    ket_qua = [
        (cum, freq)
        for cum, freq in counter.most_common()
        if freq >= min_freq and cum not in hien_co
    ][:gioi_han]

    if cap_nhat and ket_qua:
        backup_dir = ROOT / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(TU_DIEN_PATH, backup_dir / f"tu_dien_rieng_BACKUP_{ts}.txt")
        noi_dung_cu = TU_DIEN_PATH.read_text(encoding="utf-8-sig").rstrip()
        bo_sung = "\n".join(c for c, _ in ket_qua)
        TU_DIEN_PATH.write_text(
            f"{noi_dung_cu}\n# --- tự động khai phá ({ts})\n{bo_sung}\n",
            encoding="utf-8",
        )
    return ket_qua


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Khai phá từ điển ẩm thực miền Tây")
    ap.add_argument("--min-freq", type=int, default=3, help="Tần suất xuất hiện tối thiểu")
    ap.add_argument("--limit", type=int, default=50, help="Số cụm tối đa")
    ap.add_argument("--cap-nhat", action="store_true", help="Ghi bổ sung vào cau_hinh/tu_dien_rieng.txt")
    args = ap.parse_args()

    ds = khai_pha_cum_am_thuc(min_freq=args.min_freq, gioi_han=args.limit, cap_nhat=args.cap_nhat)
    print(f"Tìm thấy {len(ds)} cụm từ ẩm thực mới (tần suất >= {args.min_freq}):")
    for i, (cum, freq) in enumerate(ds, 1):
        print(f"  {i:2d}. {cum:<28} ({freq} lần)")
    if args.cap_nhat and ds:
        print(f"\nĐã sao lưu và bổ sung {len(ds)} cụm vào {TU_DIEN_PATH.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()

