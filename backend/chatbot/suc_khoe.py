"""Thực thể sức khỏe và bằng chứng chủ đề; không suy ra chế độ ăn từ bệnh danh."""
from functools import lru_cache
import re
from backend.chatbot.ngon_ngu import chuan_hoa, co_cum, khang_dinh

# Chỉ nhận diện chủ đề, không chứa quy tắc điều trị hay danh sách món an toàn.
TINH_TRANG = {
    'tiểu đường': ('tieu duong', 'dai thao duong'),
    'tăng huyết áp': ('tang huyet ap', 'cao huyet ap', 'huyet ap cao'),
    'hạ huyết áp': ('ha huyet ap', 'huyet ap thap'),
    'gút': ('gout', 'gut'),
    'bệnh thận': ('benh than', 'suy than'),
    'bệnh gan': ('benh gan', 'suy gan', 'viem gan'),
    'gan nhiễm mỡ': ('gan nhiem mo',),
    'mỡ máu': ('mo mau', 'roi loan lipid mau'),
    'bệnh tim': ('benh tim', 'suy tim', 'benh tim mach'),
    'bệnh dạ dày': ('benh da day', 'dau da day', 'viem loet da day'),
}


def nhan_dien(text):
    positive = khang_dinh(text)
    return [name for name, aliases in TINH_TRANG.items() if any(co_cum(positive,a) for a in aliases)]


def cap_nhat(previous, text):
    result = set(previous or []) | set(nhan_dien(text))
    q = chuan_hoa(text)
    for name, aliases in TINH_TRANG.items():
        if any(re.search(r'\b(?:khong|chua)(?: con)? (?:bi |mac )?'+re.escape(a)+r'\b',q) for a in aliases):
            result.discard(name)
    if re.search(r'\b(?:bo|xoa) dieu kien suc khoe\b',q):
        result.clear()
    return sorted(result)


def dung_chu_de(text, conditions):
    positive = khang_dinh(text)
    return all(any(co_cum(positive,a) for a in TINH_TRANG[name]) for name in conditions)


@lru_cache(maxsize=64)
def id_co_bang_chung(kho, conditions, hoi_mon=True):
    from backend.chatbot.truy_hoi import nap_kho
    _, rows, _ = nap_kho(kho)
    grouped = {}
    for row in rows:
        grouped.setdefault(row['id_goc'], []).append(row)
    # Gợi ý món cần tài liệu có tiêu đề chuyên biệt cho tình trạng được hỏi;
    # nhắc thoáng qua trong bài hoặc có nhãn ít đường không đủ bằng chứng.
    return frozenset(idx for idx, chunks in grouped.items() if dung_chu_de(
        chunks[0]['cau_hoi'] if hoi_mon else '\n'.join(d['cau_hoi']+' '+d['noi_dung'] for d in chunks), conditions))


def thong_bao_thieu(conditions):
    return (f"Bạn đang hỏi về ăn uống cho người có tình trạng **{', '.join(conditions)}**. "
            'Kho hiện tại chưa có tài liệu chuyên biệt đủ để xác nhận món ăn phù hợp với yêu cầu này. '
            'Mình cần bổ sung nguồn dinh dưỡng phù hợp cho tình trạng này trước khi gợi ý món có căn cứ.')
