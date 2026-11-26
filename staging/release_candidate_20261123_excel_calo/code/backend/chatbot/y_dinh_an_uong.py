"""Đối chiếu chủ đề và loại câu hỏi, không coi cùng triệu chứng là cùng ý định."""
import re
from backend.chatbot.ngon_ngu import chuan_hoa, khang_dinh


def nhan_dien_cau_hoi_chung(text):
    q = chuan_hoa(text)
    if re.search(r'\bcam thay\b|\bcam nang\b', q):
        return None
    topics = [t for t in ('cam', 'ho', 'sot') if re.search(r'\b'+t+r'\b', khang_dinh(text))]
    if len(topics) != 1:
        return None
    if re.search(r'\buong\s+(?:gi|nuoc gi)\b', q) and not re.search(r'\ban\s+(?:mon\s+)?gi\b', q):
        intent = 'uong_gi'
    elif re.search(r'\b(?:(?:an|nau)\s+(?:mon\s+)?gi|goi y)\b', q):
        intent = 'an_gi'
    else:
        return None
    # Chỉ đối chiếu tự động câu CHUNG. Có nguyên liệu, trẻ nhỏ, thai kỳ,
    # triệu chứng khác hoặc yêu cầu bổ sung thì giữ đường truy hồi chi tiết.
    common = set(('toi minh ban em anh chi bi dang thi nen an mon gi duoc cho hoi voi a nhe nha '
                  'cam cum lanh ho sot can nau goi y uong nuoc tot nhat the nao bay gio khi giup phu hop de mau khoe hon co the '
                  'tui nhi ne vay ha roi day nhu vai').split())
    words = set(re.findall(r'\w+', q))
    if not words <= common:
        return None
    return topics[0], intent


def chon_cau_hoi_cung_y_dinh(question, metadata, loc_nhom=None):
    target = nhan_dien_cau_hoi_chung(question)
    if not target:
        return {}
    topic, intent = target
    candidates = {}
    for d in metadata:
        if d['nhom_folder'] != '12_goi_y_khi_om_met' or (loc_nhom and d['nhom_folder'] not in loc_nhom):
            continue
        title = chuan_hoa(d['cau_hoi'])
        # Mẫu tiêu đề tổng quát trong kho; không chọn bài có thực phẩm cụ thể,
        # câu có/không, câu kiêng ăn hoặc thêm triệu chứng mà khách chưa nói.
        pattern = (r'^(?:bi |nguoi bi )?'+topic+r'(?: cum| lanh)? (?:thi |nen )?an gi(?: uong gi)?(?: cho mau khoe| cho khoe)?$'
                   if intent == 'an_gi' else
                   r'^(?:bi |nguoi bi )?'+topic+r'(?: cum| lanh)? (?:thi |nen )?uong gi(?: cho de chiu)?$')
        if re.fullmatch(pattern, title):
            candidates.setdefault(d['id_goc'], d)
    # Không đoán khi kho có nhiều bài tổng quát cùng mẫu.
    return candidates if len(candidates) == 1 else {}
