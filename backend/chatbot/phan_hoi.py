"""Chọn phản hồi từ template và nội dung nguồn; không có mô hình sinh."""
import hashlib
import re


def kiem_tra_bam_nguon(answer, source):
    """Kiểm tra trích xuất nguyên câu, không bỏ dấu làm mất ý nghĩa/phủ định."""
    normalize = lambda s: ' '.join(s.strip(' \t-*•"“”').lower().split())
    sentences = {normalize(s) for s in re.split(r'[\n.!?]+', source) if s.strip()}
    selected = [normalize(s) for s in re.split(r'[\n.!?]+', answer or '') if s.strip()]
    return bool(selected) and all(s in sentences for s in selected)


TEMPLATES = {
    'cong_thuc': ('Mình hướng dẫn bạn theo công thức có trong kho nhé.',
                 'Bạn tham khảo nguyên liệu và cách làm từ công thức này nhé.',
                 'Mình tìm được hướng dẫn sau trong kho công thức.'),
    'nguyen_lieu': ('Đây là phần nguyên liệu được ghi trong công thức.',
                   'Bạn chuẩn bị nguyên liệu theo nguồn bên dưới nhé.'),
    'so_che': ('Bạn xem phần sơ chế trong công thức nhé.', 'Nguồn hướng dẫn sơ chế như sau.'),
    'che_bien': ('Các bước được hướng dẫn trong nguồn như sau.', 'Bạn thực hiện theo phần chế biến dưới đây nhé.'),
    'thong_tin': ('Mình tìm được thông tin sau trong kho tham khảo.',
                 'Bạn tham khảo nội dung có nguồn dưới đây nhé.'),
}


def chon_phan_hoi(result, question, intents=(), previous_template=None):
    """Thay lời dẫn; giữ nguyên thân nội dung, định lượng và nguồn."""
    if result['loai'] != 'tra_loi' or not result.get('nguon'):
        return result
    if result.get('giai_thich', {}).get('nhom_nguon', '').startswith('12_'):
        result['mau_phan_hoi'] = None
        return result  # Không thêm văn phong như thể đã kiểm duyệt nội dung sức khỏe.
    kind = 'thong_tin'
    if 'cong_thuc' in intents or {'nguyen_lieu', 'che_bien'} <= set(intents):
        kind = 'cong_thuc'
    elif 'nguyen_lieu' in intents:
        kind = 'nguyen_lieu'
    elif 'so_che' in intents:
        kind = 'so_che'
    elif 'che_bien' in intents:
        kind = 'che_bien'
    choices = list(enumerate(TEMPLATES[kind]))
    choices = [(i, s) for i, s in choices if f'{kind}:{i}' != previous_template] or choices
    idx = int(hashlib.sha256(question.encode('utf-8')).hexdigest()[:8], 16) % len(choices)
    number, intro = choices[idx]
    result['cau_tra_loi'] = intro+'\n\n'+result['cau_tra_loi']
    result['mau_phan_hoi'] = f'{kind}:{number}'
    return result
