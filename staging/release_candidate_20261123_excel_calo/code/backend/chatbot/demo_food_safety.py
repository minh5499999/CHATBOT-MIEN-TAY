"""Sourced, local food-safety FAQ for the demo release."""
from backend.chatbot.ngon_ngu import khoa_cau_hoi

REASON = 'FOOD_SAFETY_FRYING_OIL'
QUESTIONS = {
    'dau an dung chien di chien lai co hai khong',
    'dau chien di chien lai co hai khong',
    'dau chien lai co hai khong',
    'dau chien lai duoc may lan',
    'dau chien dung lai duoc bao nhieu lan',
    'dau an chien lai duoc bao nhieu lan',
    'dau da chien co dung lai duoc khong',
    'dau da chien co tai su dung duoc khong',
    'khi nao nen bo dau chien',
    'bao quan dau da chien the nao',
}
ANSWER = """**Dầu đã chiên có dùng lại được không?**

Không có một số lần dùng lại chung cho mọi mẻ dầu. Dầu xuống cấp tùy loại dầu, nhiệt độ, thời gian đun và lượng cặn từ thực phẩm. Khi chiên, dùng dầu phù hợp và tránh đun đến mức bốc khói.

- Nếu định dùng lại, để dầu nguội hẳn rồi lọc hết cặn bằng rây mịn hoặc khăn lọc. Đựng trong hộp sạch, khô, đậy kín, tránh ánh sáng. USDA FSIS khuyên bảo quản trong tủ lạnh để giữ chất lượng.
- Bỏ dầu nếu dầu sẫm màu bất thường, bị đục, có mùi ôi hoặc mùi lạ, nổi bọt dai hay bốc khói ở nhiệt độ chiên thường dùng. Nếu không rõ dầu đã được đun hoặc bảo quản thế nào, dùng dầu mới.

Nguồn: [USDA FSIS – Can oil be reused safely?](https://ask.fsis.usda.gov/article/Can-oil-be-reused-safely) · [Centre for Food Safety (Hong Kong) – Hướng dẫn sử dụng dầu chiên ngập](https://www.cfs.gov.hk/english/multimedia/multimedia_pub/multimedia_pub_fse_202001.html)"""


def matches(question):
    return khoa_cau_hoi(question) in QUESTIONS


def response(result=None):
    return dict(result or {}, reason_code=REASON, loai='thong_tin_an_toan',
                cau_tra_loi=ANSWER, nguon=[], goi_y=[], doan_truy_hoi=[], chu_de=None,
                giai_thich={})
