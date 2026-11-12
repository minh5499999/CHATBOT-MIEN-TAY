"""Sửa lỗi nhập tên món bằng đề nghị xác nhận, không tự thay nguyên liệu."""
from difflib import SequenceMatcher
from backend.chatbot.doi_chieu import chi_muc_ten_mon, ten_mon_tu_cau_hoi, chi_muc_cau_hoi
from backend.chatbot.ngon_ngu import khoa_cau_hoi


def de_nghi_ten_mon(question, kho):
    if chi_muc_cau_hoi(kho).get(khoa_cau_hoi(question)):
        return []
    query = ten_mon_tu_cau_hoi(question)
    catalog = chi_muc_ten_mon(kho)
    if query in catalog or not 3 <= len(query.split()) <= 10:
        return []
    scores = []
    for name, rows in catalog.items():
        if len(name.split()) != len(query.split()) or abs(len(name)-len(query)) > 2:
            continue
        ratio = SequenceMatcher(None, query, name).ratio()
        # Đề nghị chỉ khi phần lớn token trùng, tránh chuyển sang món khác.
        same = sum(a == b for a,b in zip(query.split(), name.split()))
        if ratio >= .88 and same >= len(query.split())-2:
            scores.append((ratio, name, rows))
    scores.sort(key=lambda x:(-x[0], x[1]))
    if not scores or (len(scores) > 1 and scores[0][0]-scores[1][0] < .06):
        return []
    return [d['cau_hoi'] for d in scores[0][2].values()][:3]
