"""Ràng buộc tên món trước khi chọn kết quả ngữ nghĩa."""
import re
from backend.chatbot.ngon_ngu import chuan_hoa, co_cum, chuan_hoa_dia_phuong

NGUYEN_LIEU = (
    ("thịt heo", ("thit heo", "thit lon")),
    ("thịt bò", ("thit bo",)), ("thịt gà", ("thit ga", "ga")),
    ("thịt vịt", ("thit vit", "vit")),
    ("đậu hũ", ("dau hu", "dau phu", "tau hu")),
    ("thịt", ("thit",)), ("cá", ("ca",)), ("tôm", ("tom",)),
)
CACH_NAU = {"kho": "kho", "xao": "xào", "chien": "chiên", "hap": "hấp",
            "luoc": "luộc", "nuong": "nướng"}


def nhan_dien_mon(cau_hoi):
    q = chuan_hoa(chuan_hoa_dia_phuong(cau_hoi))
    q = re.sub(r'\btrung\s+(vit|ga|cut)\b', lambda m: 'trung_'+m[1], q)
    # Chỉ bỏ lời dẫn ở đầu câu, không bỏ tên nguyên liệu hay phần mô tả món.
    clean = re.sub(r"^(?:(?:ban|hay|vui long|lam on|huong dan|chi|day|cho|toi|minh|em|anh|chi|cach|lam|nau|mon)\s+)+", "", q)
    clean = re.sub(r"(?:\s+(?:di|nhe|nha|voi|a|duoc khong))+[.!?]*$", "", clean).strip(' .!?')
    for ten, aliases in NGUYEN_LIEU:
        for method, method_vi in CACH_NAU.items():
            # Ràng buộc cụm tên món rõ ràng như 'thịt kho'. Câu hỏi theo
            # cấu trúc khác vẫn đi qua truy hồi hiện có, không suy đoán tên món.
            matches = [a for a in aliases if co_cum(q, a + ' ' + method)]
            if matches:
                phrases = tuple(a + ' ' + method for a in aliases)
                generic = any(clean in (a+' '+method, method+' '+a) for a in aliases)
                return {"ten": ten+' '+method_vi, "cum_tu": phrases, "hoi_chung": generic}
    return None


def dung_ten_mon(tieu_de, mon):
    # Tên món phải khớp trong tiêu đề, không chấp nhận nguyên liệu phụ
    # trong một đoạn công thức khác để đổi 'thịt kho' thành 'cá kho'.
    return mon is None or any(co_cum(tieu_de, phrase) for phrase in mon['cum_tu'])


DAC_TRUNG = (
    'trứng vịt', 'trứng gà', 'trứng cút',
    'cá bông lau', 'cá lóc', 'cá kèo', 'cá rô', 'cá linh', 'cá basa', 'cá trê', 'cá lăng', 'cá hú', 'cá bống',
    'cá tai tượng', 'cá chạch', 'cá đối', 'cá chẽm', 'cá diêu hồng',
    'thịt bò', 'thịt gà', 'thịt vịt', 'vịt xiêm',
    'lươn', 'ếch', 'ốc bươu', 'bông điên điển', 'bông súng', 'bông so đũa',
    'rau lang', 'rau muống', 'rau ngót', 'rau đắng', 'rau nhút',
    'củ hủ dừa', 'ngó sen', 'khoai mỡ', 'khoai mì', 'bí đao', 'bí đỏ', 'khổ qua',
)


def dac_trung_mon(question):
    """Cụm dài trước: trứng vịt không tạo ra nhãn thịt vịt."""
    q = chuan_hoa(chuan_hoa_dia_phuong(question))
    if re.search(r'\b(khac nhau|khac gi|thay bang|thay the|so sanh|hay la)\b', q):
        return []
    return [phrase for phrase in DAC_TRUNG if co_cum(q, phrase)]


def dung_dac_trung(title, content, features):
    for phrase in features:
        # Loại trứng có thể chỉ được ghi trong danh sách nguyên liệu.
        text = title+' '+content if phrase.startswith('trứng ') else title
        if phrase.startswith('thịt '):
            text = re.sub(r'\btrứng\s+(vịt|gà|cút)\b', 'trứng', chuan_hoa_dia_phuong(text), flags=re.I)
        aliases = [phrase, phrase[5:]] if phrase.startswith('thịt ') else [phrase]
        if not any(co_cum(chuan_hoa_dia_phuong(text), a) for a in aliases):
            return False
    return True
