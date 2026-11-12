"""Đối chiếu câu hỏi với tên nguồn: không dùng cosine làm bằng chứng duy nhất."""
from functools import lru_cache
import re
from backend.chatbot.ngon_ngu import khoa_cau_hoi



def ten_mon_tu_cau_hoi(text):
    q = khoa_cau_hoi(text)

    # Bỏ chuỗi lời dẫn ở đầu câu nhưng giữ nguyên tên món/nguyên liệu.
    q = re.sub(
        r"^(?:(?:ban|hay|vui long|lam on|huong dan|chi|day|cho|toi|minh|tui|em|anh|cach|cong thuc|muon|lam|nau|mon)\s+)+",
        "",
        q,
    )

    q = re.split(
        r"\b(?:tai nha|nau nhu the nao|lam nhu the nao|nhu the nao|"
        r"can nguyen lieu gi|nguyen lieu gi|thi can|"
        r"lam kieu nao|kieu nao|sao cho|lam sao|nau sao|the nao|ra sao)\b",
        q,
    )[0]

    q = re.sub(
        r"(?:\s+(?:nhe|nha|ban|di|voi|a))+$",
        "",
        q.strip(),
    )

    return q.strip()


@lru_cache(maxsize=8)
def chi_muc_ten_mon(kho):
    from backend.chatbot.truy_hoi import nap_kho
    _, metadata, _ = nap_kho(kho)
    result = {}
    for d in metadata:
        if d['nhom_folder'] in ('02_huong_dan_nau_an', '03_huong_dan_nau_mon_mien_tay'):
            name = ten_mon_tu_cau_hoi(d['cau_hoi'])
            if len(name.split()) >= 2:
                result.setdefault(name, {}).setdefault(d['id_goc'], d)
                short = re.sub(r'\s+mien tay$', '', name).strip()
                if short != name and len(short.split()) >= 2:
                    result.setdefault(short, {}).setdefault(d['id_goc'], d)
    return result


@lru_cache(maxsize=8)
def chi_muc_cau_hoi(kho):
    from backend.chatbot.truy_hoi import nap_kho
    _, metadata, _ = nap_kho(kho)
    result = {}
    for d in metadata:
        result.setdefault(khoa_cau_hoi(d['cau_hoi']), {}).setdefault(d['id_goc'], d)
    return result


def doi_chieu_cau_goc(result, question, loc_nhom=None):
    matches = chi_muc_cau_hoi(result['kho']).get(khoa_cau_hoi(question), {})
    if loc_nhom:
        matches = {i: d for i, d in matches.items() if d['nhom_folder'] in loc_nhom}
    result['id_khop_chinh_xac'] = list(matches)
    kind = 'cau_goc'
    # Chỉ khớp TOÀN BỘ phần tên/yêu cầu đã bỏ lời dẫn. Không tìm một tên món
    # con trong câu phủ định. Từ 'không' trong 'nồi chiên không dầu' hoặc
    # 'không bị dai' không được coi là lệnh loại trừ món.
    if not matches:
        matches = chi_muc_ten_mon(result['kho']).get(ten_mon_tu_cau_hoi(question), {})
        if loc_nhom:
            matches = {i:d for i,d in matches.items() if d['nhom_folder'] in loc_nhom}
        kind = 'ten_mon'
    result['id_khop_ten_mon'] = list(matches) if kind == 'ten_mon' else []
    if matches:
        existing = {d['id_goc']: d for d in result['doan']}
        # diem vẫn là điểm vector/BM25 nếu có. Câu khớp nguyên văn dùng cờ
        # riêng, không giả mạo điểm cosine = 1.
        promoted = [dict(existing.get(i, d), diem=existing.get(i, {}).get('diem', 0.0),
                         khop_chinh_xac=kind == 'cau_goc', khop_ten_mon=kind == 'ten_mon') for i, d in matches.items()]
        result['doan'] = promoted + [d for d in result['doan'] if d['id_goc'] not in matches]
    return result
