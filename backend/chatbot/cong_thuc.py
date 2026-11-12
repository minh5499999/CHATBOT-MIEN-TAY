"""Danh mục công thức trích từ nguồn, không tạo số liệu dưỡng chất."""
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import re
from backend.chatbot.ngon_ngu import chuan_hoa, chuan_hoa_dia_phuong, vi_pham, du_bang_chung


@dataclass(frozen=True)
class CongThuc:
    id_goc: int
    cau_hoi: str
    noi_dung: str
    nguyen_lieu: tuple
    khau_phan: int | None
    tong_phut: int | None
    metadata: dict


def ten_nguyen_lieu(line):
    text = line.strip().lstrip('-• ').strip()
    text = re.split(r'\d', text, maxsplit=1)[0].strip(' :,-')
    return re.sub(r'\s+(?:vua du|mot it|tuy chon)$', '', chuan_hoa(chuan_hoa_dia_phuong(text))).strip()


@lru_cache(maxsize=8)
def danh_muc(kho):
    from backend.chatbot.truy_hoi import nap_kho
    _, rows, _ = nap_kho(kho)
    grouped = {}
    for row in rows:
        grouped.setdefault(row['id_goc'], []).append(row)
    result = []
    for idx, chunks in grouped.items():
        chunks = sorted(chunks, key=lambda d:d['thu_tu_doan'])
        text = '\n'.join(d['noi_dung'] for d in chunks)
        # Phân biệt công thức thật có danh sách nguyên liệu với bài giới thiệu.
        section = re.search(r'(?ims)^\s*(?:nguyên liệu|chuẩn bị nguyên liệu)[^\n]*\n(.*?)(?=^\s*(?:sơ chế|cách chế biến|cách làm|các bước|chế biến|hoàn thành)\b|\Z)', text)
        if not section:
            continue
        ingredients = tuple(line.strip() for line in section[1].splitlines() if line.strip().startswith(('-', '•')))
        if not ingredients:
            continue
        header = text[:section.start(1)]
        count = re.search(r'cho\s+(\d+)\s*(?:người|phần)', header, re.I)
        # Không tự biến khoảng 10–11 phần thành chính xác 10 phần.
        if re.search(r'\d+\s*(?:đến|[-–])\s*\d+\s*(?:người|phần)', header, re.I):
            count = None
        prep = re.search(r'chuẩn bị\s+(\d+)\s*(phút|giờ)', header, re.I)
        cook = re.search(r'(?:nấu|kho|hấp|chiên|nướng)\s+(?:khoảng\s+)?(\d+)\s*(phút|giờ)', header, re.I)
        minutes = lambda m: int(m[1])*(60 if m[2].lower() == 'giờ' else 1)
        total = minutes(prep)+minutes(cook) if prep and cook else None
        result.append(CongThuc(idx, chunks[0]['cau_hoi'], text, ingredients,
                              int(count[1]) if count else None, total, dict(chunks[0])))
    return tuple(result)


def tu_vung_nguyen_lieu(kho):
    names = {ten_nguyen_lieu(line) for r in danh_muc(kho) for line in r.nguyen_lieu}
    names.update(('cá lóc', 'cá quả', 'thịt gà', 'trứng', 'trứng vịt', 'trứng gà', 'cà chua', 'đậu hũ', 'ớt'))
    return tuple(sorted((n for n in names if len(n) >= 2), key=len, reverse=True))


def goi_y_theo_dieu_kien(kho, state):
    dk = state['dieu_kien']
    results = []
    nau_nhanh = 'nau_nhanh' in state.get('intents', [])
    for recipe in danh_muc(kho):
        if vi_pham(recipe.noi_dung, dk) or not du_bang_chung(recipe.noi_dung+' '+recipe.cau_hoi, dk):
            continue
        if dk.get('chua_ro') or dk.get('can_dinh_luong'):
            continue
        if state.get('khong_chien') and re.search(r'\b(?:chien|ran)\b', chuan_hoa(recipe.noi_dung)):
            continue
        limit = state.get('thoi_gian_toi_da')
        if limit is not None:
            if recipe.tong_phut is None or recipe.tong_phut > limit:
                continue
        elif nau_nhanh and recipe.tong_phut is None:
            continue
        raw_names = [ten_nguyen_lieu(x) for x in recipe.nguyen_lieu]
        have = state.get('nguyen_lieu_co', [])
        matched = [n for n in have if any(chuan_hoa(n) in x for x in raw_names)]
        if have and not matched:
            continue
        missing = [x for x in raw_names if not any(chuan_hoa(n) in x for n in have)]
        if state.get('chi_dung_nguyen_lieu_co') and missing:
            continue
        results.append((len(matched)/max(len(have), 1), -len(missing), recipe, missing))

    if nau_nhanh:
        results.sort(
            key=lambda row: (
                row[2].tong_phut if row[2].tong_phut is not None else float('inf'),
                -row[0],
                -row[1],
                row[2].id_goc
            )
        )
    else:
        results.sort(
            key=lambda row: (
                -row[0],
                -row[1],
                row[2].id_goc
            )
        )
    return results[:3]


def quy_doi_khau_phan(recipe, target):
    if not recipe.khau_phan or target <= 0:
        return None
    factor = Fraction(target, recipe.khau_phan)
    units = r'(?:muỗng canh|muỗng cà phê|kg|mg|ml|lít|g|l|quả|trái|củ|tép|nhánh|con|miếng|bó|chén|tô)'
    lines, unknown = [], []
    for line in recipe.nguyen_lieu:
        if re.search(r'\d+\s*(?:[-–]|đến)\s*\d+', line):
            unknown.append(line)
            continue
        match = re.match(r'^(.*?\s)(\d+(?:[.,]\d+|/\d+)?)\s*('+units+r')(.*)$', line, re.I)
        if not match or re.search(r'\d', match[4]):
            unknown.append(line)
            continue
        value = Fraction(match[2].replace(',', '.'))*factor
        number = format(float(value), '.3f').rstrip('0').rstrip('.')
        lines.append(f'{match[1]}{number} {match[3]}{match[4]}')
    return {'goc': recipe.khau_phan, 'dich': target, 'he_so': str(factor), 'dong': lines, 'chua_quy_doi': unknown}
