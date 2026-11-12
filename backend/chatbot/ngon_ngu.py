"""Chuẩn hóa keyword và điều kiện ăn uống; không tải model, không gọi mạng.

Lọc theo văn bản là biện pháp bảo thủ, không phải chứng nhận món ăn không dị ứng
hay phép tính thành phần dinh dưỡng. Không suy ra calo từ tên món.
"""
import re
import unicodedata


def chuan_hoa(text):
    text = unicodedata.normalize("NFD", text.lower().replace("_", " "))
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Mn")
                    .replace("đ", "d").split())


def co_cum(text, phrase):
    return bool(re.search(r"(?<!\w)" + re.escape(chuan_hoa(phrase)) + r"(?!\w)", chuan_hoa(text)))


# Đổi cụm đầy đủ, không đổi riêng 'hột' vì hột é là hạt, không phải trứng.
DIA_PHUONG = (
    ('hột vịt', 'trứng vịt'), ('hot vit', 'trứng vịt'),
    ('hột gà', 'trứng gà'), ('hot ga', 'trứng gà'),
    ('hột cút', 'trứng cút'), ('hot cut', 'trứng cút'),
    ('mướp đắng', 'khổ qua'), ('muop dang', 'khổ qua'),
    ('đậu phụ', 'đậu hũ'), ('dau phu', 'đậu hũ'),
    ('thịt lợn', 'thịt heo'), ('thit lon', 'thịt heo'),
    ('thịt ba rọi', 'thịt ba chỉ'), ('thit ba roi', 'thịt ba chỉ'),
    ('thịt bằm', 'thịt băm'), ('thit bam', 'thịt băm'),
    ('người ốm', 'người bệnh'), ('nguoi om', 'người bệnh'),
    ('cá quả', 'cá lóc'), ('ca qua', 'cá lóc'),
    ('cá chuối', 'cá lóc'), ('ca chuoi', 'cá lóc'),
    ('cá điêu hồng', 'cá diêu hồng'), ('ca dieu hong', 'cá diêu hồng'),
    ('mì chính', 'bột ngọt'), ('mi chinh', 'bột ngọt'),
    ('rau mùi tàu', 'ngò gai'), ('mùi tàu', 'ngò gai'), ('mui tau', 'ngò gai'),
    ('dọc mùng', 'bạc hà'), ('doc mung', 'bạc hà'),
    ('củ lạc', 'đậu phộng'), ('hạt lạc', 'đậu phộng'),
    ('tui', 'mình'), ('mik', 'mình'), ('mk', 'mình'), ('mjk', 'mình'),
    ('ko', 'không'), ('k0', 'không'), ('hok', 'không'), ('khum', 'không'),
    ('hong', 'không'), ('hổng', 'không'), ('hem', 'không'),
    ('đc', 'được'), ('dc', 'được'), ('bik', 'biết'), ('bít', 'biết'),
    ('ntn', 'như thế nào'), ('bnh', 'bao nhiêu'),
)


def chuan_hoa_dia_phuong(text):
    result = unicodedata.normalize('NFC', text)
    for alias, canonical in DIA_PHUONG:
        result = re.sub(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', canonical, result, flags=re.I)
    return result


def khoa_cau_hoi(text):
    """Khóa so khớp câu FAQ, bỏ lời dẫn/lịch sự nhưng giữ ý định và phủ định."""
    q = chuan_hoa(chuan_hoa_dia_phuong(text))
    q = re.sub(r'[^\w\s]', ' ', q)
    q = ' '.join(q.split())
    q = q.replace('luu y', 'chu y').replace('nau do an', 'nau an').replace('dieu gi', 'gi')
    q = re.sub(r'^(?:(?:ban oi|cho minh hoi|cho toi hoi|minh muon hoi|toi muon hoi|xin hoi)\s+)+', '', q)
    # Không bỏ 'nha': sau khi bỏ dấu, 'nhà' và tiểu từ 'nha' trùng nhau.
    return re.sub(r'(?:\s+(?:nhe|a))+$', '', q).strip()


def khang_dinh(text):
    """Bỏ mệnh đề phủ định trước khi nhận diện triệu chứng/nhu cầu.

    Giữ nguyên câu người dùng ở nơi khác; không xóa phủ định khỏi câu truy hồi.
    """
    text = chuan_hoa(text)
    return re.sub(r"\b(?:khong|chua|chang|het)\b.*?(?=[,;.!?]|\bnhung\b|$)", " ", text)


DONG_NGHIA = [
    (("protein", "nhieu dam", "giau dam", "tang co"), "giàu đạm protein"),
    (("it duong", "giam duong", "low sugar"), "ít đường"),
    (("it muoi", "giam muoi", "an nhat", "it natri"), "ít muối ít natri"),
    (("it beo", "low fat"), "ít béo"),
    (("it dau", "it dau mo", "han che dau"), "ít dầu"),
    (("giam can", "it calo", "low calorie"), "giảm cân ít năng lượng"),
    (("chat xo", "fiber", "nhieu xo"), "giàu chất xơ"),
    (("thit bam", "thit bam nho"), "thịt băm thịt bằm"),
    (("thit ba roi", "thit ba chi"), "thịt ba chỉ thịt ba rọi"),
    (("dau hu", "dau phu"), "đậu hũ đậu phụ"),
    (("kho qua", "muop dang"), "khổ qua mướp đắng"),
    (("nguoi met", "met", "met moi", "ue oai", "khong khoe"), "mệt mỏi dưỡng sức"),
    (("bi sot", "dang sot"), "bị sốt"),
    (("bi ho", "dau hong", "rat hong"), "đau họng thức ăn mềm"),
    (("tieu duong", "dai thao duong", "duong huyet cao"), "tiểu đường đái tháo đường đường huyết cao"),
    (("thanh dam", "an thanh dam"), "thanh đạm ít béo nhẹ bụng"),
]


def mo_rong_keyword(text):
    text = chuan_hoa_dia_phuong(text)
    positive = khang_dinh(text)
    # "không khỏe" là một triệu chứng, không phải phủ định triệu chứng.
    positive += " met moi" if co_cum(text, "khong khoe") else ""
    additions = [canonical for aliases, canonical in DONG_NGHIA
                 if any(co_cum(positive, alias) for alias in aliases)]
    return " ".join([text.strip(), *additions]).strip()


NGUYEN_LIEU = {
    "tôm": ("tôm", "tép", "ruốc tôm", "mắm tôm", "mắm ruốc"),
    "cua": ("cua", "ghẹ"),
    "cá": ("cá", "nước mắm", "mắm", "chả cá"),
    "hải sản": ("tôm", "tép", "cua", "ghẹ", "mực", "nghêu", "ngao", "sò", "ốc", "hàu", "mắm tôm", "mắm ruốc"),
    "đậu phộng": ("đậu phộng", "lạc", "bơ đậu phộng"),
    "sữa": ("sữa", "bơ", "phô mai", "phômai", "phomai", "kem tươi", "whey"),
    "trứng": ("trứng", "mayonnaise"),
    "đậu nành": ("đậu nành", "đậu hũ", "đậu phụ", "tàu hũ", "nước tương", "xì dầu"),
    "thịt heo": ("heo", "lợn", "ba chỉ", "ba rọi", "giò lụa", "chả lụa", "mỡ heo"),
    "thịt bò": ("bò", "bê"),
    "thịt gà": ("gà",),
    "thịt": ("thịt", "heo", "lợn", "bò", "bê", "gà", "vịt", "ngan", "dê", "cừu", "thỏ", "giò", "chả", "xương"),
    "gluten": ("bột mì", "bánh mì", "mì sợi", "lúa mì", "nước tương", "xì dầu"),
    "cay": ("ớt", "tiêu", "sa tế", "cay"),
    "cơm": ("cơm",),
    "ớt": ("ớt", "sa tế"),
    "me": ("me", "me chua", "nước cốt me"),
    "nước cốt dừa": ("nước cốt dừa", "cốt dừa"),
    "hành": ("hành lá", "hành tím", "hành phi", "hành tây"),
    "tỏi": ("tỏi", "tỏi băm", "tỏi phi"),
    "tiêu": ("tiêu", "hạt tiêu", "tiêu xay"),
}
ALIASES = {"tôm": ("tom", "tep"), "cua": ("cua", "ghe"), "cá": ("ca",),
           "hải sản": ("hai san",), "đậu phộng": ("dau phong", "lac"),
           "sữa": ("sua",), "trứng": ("trung",), "đậu nành": ("dau nanh",),
           "thịt heo": ("thit heo", "thit lon", "heo", "lon"),
           "thịt bò": ("thit bo",), "thịt gà": ("thit ga",), "gluten": ("gluten",), "cay": ("cay",), "cơm": ("com",), "ớt": ('ot',),
           "me": ("me", "me chua", "nuoc cot me"),
           "nước cốt dừa": ("nuoc cot dua", "cot dua"),
           "hành": ("hanh", "hanh la", "hanh tim", "hanh phi"),
           "tỏi": ("toi bam", "toi phi", "cu toi", "tep toi", "nhanh toi"),
           "tiêu": ("tieu", "hat tieu")}
THIT_CA = ("thịt", "heo", "lợn", "bò", "gà", "vịt", "cá", "tôm", "tép", "cua", "ghẹ",
           "mực", "nghêu", "ngao", "ốc", "ếch", "lươn", "nước mắm", "mắm", "xương", "chả lụa", "giò lụa")
NHU_CAU = {
    "giàu đạm": ("giau dam", "nhieu dam", "giau protein", "nhieu protein", "high protein"),
    "ít đường": ("it duong", "giam duong", "low sugar"),
    "ít muối": ("it muoi", "giam muoi", "it natri", "an nhat"),
    "ít béo": ("it beo", "giam beo", "low fat"),
    "ít dầu": ("it dau", "it dau mo", "han che dau"),
    "giảm cân": ("giam can", "it calo", "low calorie"),
    "giàu chất xơ": ("giau chat xo", "nhieu chat xo", "nhieu xo"),
}


def dieu_kien(text, lich_su=None):
    """Nhớ loại trừ ở các lượt được truyền vào; nhu cầu dinh dưỡng lấy lượt hiện tại."""
    cam = set()
    chay = False
    chua_ro = []
    # Không đọc câu trả lời bot để tránh biến nguyên liệu gợi ý thành sở thích.
    for q in [*(h.get("cau_hoi", "") for h in (lich_su or [])), text]:
        q = chuan_hoa(chuan_hoa_dia_phuong(q))
        # Chỉ đọc phạm vi sau động từ loại trừ, dừng ở chuyển ý/yêu cầu mới.
        for m in re.finditer(r"\b(?:di ung(?: voi)?|khong an(?: duoc)?|khong dung|khong them|(?<!an )kieng|tranh)\s+([^,;.!?]+)", q):
            span = re.split(r"\b(?:nhung|con|muon|can|hay|goi y|nau|thich|thi|de|nen|la gi)\b", m[1])[0]
            # Câu hỏi về kiêng gì/ngộ độc/dị ứng nói chung không phải khai báo
            # danh sách nguyên liệu cá nhân. Không lưu các từ này vào hồ sơ.
            if re.match(r'^(?:gi\b|an gi\b|thuc pham\b|thuc an\b|ngo doc\b|nhiem khuan\b|sao\b|trong\b|ma\b)', span):
                continue
            # "không dị ứng" không được xem là một dị ứng. Tránh nhầm "canh chua" với "chưa"
            if re.search(r"(?<!canh\s)(?<!me\s)(?<!mang\s)(?<!ca\s)(?<!tai\s)\b(?:khong|chua)(?: con)?\s*$", q[max(0, m.start()-16):m.start()]):
                continue
            remaining = span
            for name, aliases in ALIASES.items():
                if any(co_cum(span, a) for a in aliases):
                    cam.add(name)
                for alias in sorted(aliases, key=len, reverse=True):
                    remaining = re.sub(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", " ", remaining)
            if co_cum(span, "thit"):
                # Chỉ thêm loại thịt chung khi span không chỉ rõ loài.
                if not any(name in cam for name in ("thịt heo", "thịt bò", "thịt gà")):
                    cam.add("thịt")
                remaining = re.sub(r"\bthit\b", " ", remaining)
            remaining = re.sub(r"\b(?:va|voi|hoac|cac|loai|bat ky|duoc|ca|nua|chay|an|nha|nhe|a)\b", " ", remaining)
            if remaining.strip():
                chua_ro.append(remaining.strip())
        if co_cum(khang_dinh(q), "an chay") or co_cum(q, "thuan chay") or co_cum(q, "vegan"):
            chay = True
    positive = khang_dinh(text)
    needs = [name for name, aliases in NHU_CAU.items() if any(co_cum(positive, a) for a in aliases)]
    if not needs and re.search(r"\b(mon do|mon nay|mon kia|cai do|cai nay)\b", chuan_hoa(text)):
        for luot in reversed(lich_su or []):
            previous = dieu_kien(luot.get("cau_hoi", ""))["nhu_cau"]
            if previous:
                needs = previous
                break
    dinh_luong = bool(re.search(r"\d+(?:[.,]\d+)?\s*(?:kcal|calo|calories|g\s*(?:dam|protein|chat beo|carb))\b", chuan_hoa(text)))
    return {"loai_tru": sorted(cam), "an_chay": chay, "nhu_cau": needs,
            "chua_ro": chua_ro, "can_dinh_luong": dinh_luong}


def vi_pham(text, dk):
    forbidden = [alias for name in dk["loai_tru"] for alias in NGUYEN_LIEU[name]]
    if dk["an_chay"]:
        forbidden += [*THIT_CA, "trứng", "sữa", "phô mai"]  # bảo thủ: thuần chay
    # Dữ liệu có dấu: phân biệt bò/bỏ, cá/cả, lợn/lớn. Câu không dấu mới bỏ dấu.
    original = unicodedata.normalize("NFC", text.lower().replace("_", " "))
    if chuan_hoa(original) == " ".join(original.split()):
        original = chuan_hoa(original)
        forbidden = [chuan_hoa(a) for a in forbidden]
    for alias in forbidden:
        for match in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", original):
            prefix = chuan_hoa(original[max(0, match.start()-75):match.start()])
            if re.search(r'\b(?:khong|tranh|kieng|bo)(?:\s+(?:an|dung|them|cho|bi|chua|nen|can|duoc|muon))*\s*$', prefix):
                continue
            return True
    return False


def du_bang_chung(text, dk):
    """Chỉ công nhận nhu cầu định tính nếu tài liệu có nhãn tương ứng.

    Không tự gán 'giàu đạm' chỉ vì món có thịt; số liệu kcal/g cần dữ liệu khác.
    """
    positive = khang_dinh(text)
    return all(any(co_cum(positive, a) for a in NHU_CAU[name]) for name in dk["nhu_cau"])


def tach_phu_dinh(text, lich_su=None):
    """Tách rõ 2 tập: positive_keywords (cần tìm) và negative_keywords (cần loại trừ)."""
    dk = dieu_kien(text, lich_su)
    neg = list(dk["loai_tru"])
    for c in dk["chua_ro"]:
        if c and c not in neg:
            neg.append(c)
    pos_clause = khang_dinh(chuan_hoa_dia_phuong(text))
    pos = []
    for name, aliases in ALIASES.items():
        if name not in neg and any(co_cum(pos_clause, a) for a in aliases):
            pos.append(name)
    for need in dk["nhu_cau"]:
        if need not in pos:
            pos.append(need)
    return {"positive_keywords": pos, "negative_keywords": neg}

