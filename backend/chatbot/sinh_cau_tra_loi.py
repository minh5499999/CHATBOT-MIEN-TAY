"""Luồng LCEL truy hồi lai, lọc điều kiện, trả lời có nguồn bằng trích xuất/template."""
import hashlib
import json
import re
import time
from datetime import datetime

from backend.chatbot.cau_hinh import ROOT, doc_cau_hinh
from backend.chatbot.truy_hoi import nap_kho
from backend.chatbot.chuoi_langchain import truy_hoi_langchain as truy_hoi
from backend.chatbot.ngon_ngu import dieu_kien, vi_pham, du_bang_chung, mo_rong_keyword, chuan_hoa, chuan_hoa_dia_phuong
from backend.chatbot.nhan_dien_mon import nhan_dien_mon, dung_ten_mon, dac_trung_mon, dung_dac_trung
from backend.chatbot.doi_chieu import ten_mon_tu_cau_hoi

NHOM_CHAO_HOI = "01_chao_hoi"
NHOM_CONG_THUC = ("02_huong_dan_nau_an", "03_huong_dan_nau_mon_mien_tay", "04_mon_an_mien_tay")
# từ chỉ trỏ mạnh: chắc chắn đang nói về món ở lượt trước; từ yếu: chỉ ghép khi câu gốc tìm không chắc
TU_NOI_TIEP_MANH = re.compile(r"\b(món đó|món này|món kia|món trên|cái đó|cái này|nó|đó|này)\b", re.IGNORECASE)
TU_NOI_TIEP_YEU = re.compile(r"\b(vậy|thế|còn|luôn|nữa)\b", re.IGNORECASE)
TU_SUC_KHOE = re.compile(r"\b(tiểu đường|đái tháo đường|huyết áp|gout|gút|mang thai|có bầu|bà bầu|mẹ bầu|"
                         r"bệnh|ốm|sốt|ho|cảm cúm|kinh nguyệt|dạ dày|mỡ máu|cholesterol|thận|gan|tim mạch|"
                         r"dị ứng|ăn kiêng|giảm cân)\b", re.IGNORECASE)
# phân loại ý định xã giao bằng quy tắc (mô hình vector phân biệt kém các câu rất ngắn như "xin chào")
Y_DINH_XA_GIAO = [
    ("cảm ơn", re.compile(r"\b(cảm ơn|cám ơn|cam on|thank|thanks|tks)\b", re.IGNORECASE)),
    ("tạm biệt", re.compile(r"\b(tạm biệt|tam biet|bye|hẹn gặp lại|hen gap lai|gặp lại sau)\b", re.IGNORECASE)),
    # "chao" không dấu chỉ tính khi cả câu là lời chào, vì còn có thể là "cháo" (cach nau chao ga)
    ("chào", re.compile(r"\b(xin chào|chào|xin chao|hello|hi|alo)\b|^chao( ban| bot| nha| em| anh| chi| shop)?\W*$",
                        re.IGNORECASE)),
]

CAU_NGOAI_PHAM_VI = ("Xin lỗi bạn nha, câu này nằm ngoài phạm vi của mình rồi. Mình là trợ lý nấu ăn, "
                     "có thể giúp bạn:\n\n- Hướng dẫn nấu món ăn, nhất là món miền Tây\n"
                     "- Giải thích nguyên liệu, gia vị và cách thay thế\n"
                     "- Gợi ý món theo nhu cầu dinh dưỡng\n- Mẹo bảo quản và an toàn thực phẩm")
CAU_KHONG_CHAC = ("Mình chưa tìm được câu trả lời đủ chắc chắn cho câu này. "
                  "Có phải bạn muốn hỏi một trong các câu dưới đây không?")
CAU_KHONG_DAU = "Mẹo: bạn gõ có dấu thì mình tìm chính xác hơn nhiều nha. "
CAU_NHAC_SUC_KHOE = ("\n\n> Lưu ý: thông tin trên chỉ là gợi ý món ăn theo dữ liệu tham khảo. "
                     "Bạn nên hỏi bác sĩ hoặc chuyên gia dinh dưỡng cho tình trạng sức khỏe cụ thể của mình.")


# ------------------------------------------------------------------ tiện ích

def nhan_dien_xa_giao(cau_hoi):
    """Câu ngắn (≤ 8 từ) chỉ để chào / cảm ơn / tạm biệt → trả về từ khóa ý định, ngược lại None."""
    if len(cau_hoi.split()) > 8:
        return None
    return next((tu for tu, mau in Y_DINH_XA_GIAO if mau.search(cau_hoi)), None)


def tra_loi_xa_giao(y_dinh, kho):
    """Lấy câu trả lời mẫu trong nhóm Chào hỏi có câu hỏi gốc chứa đúng từ khóa ý định."""
    _, sieu, _ = nap_kho(kho)
    return next((d for d in sieu if d["nhom_folder"] == NHOM_CHAO_HOI and y_dinh in d["cau_hoi"].lower()), None)


def chu_de_truoc(lich_su):
    """Chủ đề gần nhất {cau_hoi, id_goc} (câu hỏi gốc khớp nhất của lượt trước), không có thì None."""
    return next((luot["chu_de"] for luot in reversed(lich_su) if luot.get("chu_de")), None)


def noi_dung_day_du(kho, id_goc):
    """Toàn bộ câu trả lời gốc của một id_goc (nối mọi đoạn theo thu_tu_doan)."""
    _, sieu, _ = nap_kho(kho)
    cac_doan = sorted((d for d in sieu if d["id_goc"] == id_goc), key=lambda d: d["thu_tu_doan"])
    return "\n".join(d["noi_dung"] for d in cac_doan)


TU_KHIA_CANH = [
    ("nguyen_lieu", re.compile(r"\b(nguyên liệu|gia vị|cần mua gì|chuẩn bị những gì|cần những gì|thành phần)\b", re.IGNORECASE)),
    ("so_che", re.compile(r"\b(sơ chế|làm sạch|khử tanh|rửa cá|rửa thịt|ướp|chặt|thái)\b", re.IGNORECASE)),
    ("che_bien", re.compile(r"\b(chế biến|các bước|nấu bao lâu)\b", re.IGNORECASE)),
    ("dinh_luong", re.compile(r"\b(mấy người|bao nhiêu người|khẩu phần|định lượng)\b", re.IGNORECASE)),
]


def nhan_dien_khia_canh(cau_hoi):
    """Nhận diện khía cạnh cụ thể mà người dùng đang hỏi về món ăn."""
    if not cau_hoi:
        return None
    from backend.chatbot.intent import phan_tich
    intents = set(phan_tich(cau_hoi)['intents'])
    if 'nguyen_lieu' in intents and intents & {'che_bien', 'cong_thuc', 'so_che'}:
        return None
    if TU_KHIA_CANH[0][1].search(cau_hoi) and TU_KHIA_CANH[2][1].search(cau_hoi):
        return None  # Hỏi cả nguyên liệu và bước nấu: trả đủ công thức.
    for kc, mau in TU_KHIA_CANH:
        if mau.search(cau_hoi):
            return kc
    return None


def noi_dung_theo_yeu_cau(kho, id_goc, cau_hoi):
    """Nếu câu hỏi nhắm vào một mục cụ thể (nguyên liệu, sơ chế, cách nấu...), trích xuất đúng mục đó."""
    _, sieu, _ = nap_kho(kho)
    cac_doan = sorted((d for d in sieu if d["id_goc"] == id_goc), key=lambda d: d["thu_tu_doan"])
    if len(cac_doan) <= 1:
        return "\n".join(d["noi_dung"] for d in cac_doan), None

    kc = nhan_dien_khia_canh(cau_hoi)
    if not kc:
        return "\n".join(d["noi_dung"] for d in cac_doan), None

    doan_khop = None
    if kc in ("nguyen_lieu", "dinh_luong"):
        doan_khop = next((d for d in cac_doan if any(w in d.get("ten_muc", "").lower() for w in ("nguyên liệu", "chuẩn bị"))), None)
    elif kc == "so_che":
        doan_khop = next((d for d in cac_doan if "sơ chế" in d.get("ten_muc", "").lower()), None)
    elif kc == "che_bien":
        doan_khop = next((d for d in cac_doan if any(w in d.get("ten_muc", "").lower() for w in ("chế biến", "cách nấu", "hoàn thành"))), None)

    if doan_khop:
        ten_muc = doan_khop.get("ten_muc", "").strip()
        noi_dung = doan_khop["noi_dung"]
        goi_y_xem_tiep = "\n\n*(💡 Bạn có thể hỏi thêm: \"Các bước chế biến món này\" hoặc \"Cách sơ chế\" để xem tiếp các phần khác)*"
        return f"{noi_dung}{goi_y_xem_tiep}", kc

    return "\n".join(d["noi_dung"] for d in cac_doan), None


def dinh_dang(van_ban):
    """Câu trả lời gốc → Markdown: dòng tiêu đề mục (ngay trên danh sách gạch đầu dòng) in đậm,
    các đoạn văn tách bằng dòng trống để không bị dính vào danh sách."""
    dong = [d.rstrip() for d in van_ban.split("\n")]
    ra = []
    for i, d in enumerate(dong):
        if not d:
            continue
        la_muc = d.startswith("- ")
        sau = next((x for x in dong[i + 1:] if x), "")
        if not la_muc and sau.startswith("- ") and len(d) <= 90:
            ra.append(f"\n**{d}**\n")
        elif la_muc:
            ra.append(d)
        else:
            ra.append(f"\n{d}\n")
    return "\n".join(ra).strip()


def mo_ta_nguon(d):
    return {
        "id_goc": d["id_goc"], "cau_hoi": d["cau_hoi"], "ten_muc": d["ten_muc"], "nhom": d["nhom"],
        "diem": d["diem"], "nguon": next(iter(re.findall(r"https?://[^\s)]+", str(d["nguon"]))), ""),
    }


def cau_hoi_khac_nhau(cac_doan, bo_qua=(), toi_da=3):
    """Các câu hỏi gốc khác nhau (theo thứ tự xếp hạng) để gợi ý cho người dùng bấm hỏi tiếp."""
    da_co, kq = set(bo_qua), []
    for d in cac_doan:
        if d["id_goc"] not in da_co and d["nhom_folder"] != NHOM_CHAO_HOI:
            da_co.add(d["id_goc"])
            kq.append(d["cau_hoi"])
        if len(kq) == toi_da:
            break
    return kq


TIEN_TO_TIM_KIEM = re.compile(
    r"^(cách làm món|cách nấu món|hướng dẫn nấu món|hướng dẫn làm món|hướng dẫn nấu|hướng dẫn làm|"
    r"cách chế biến món|cách chế biến|chỉ mình cách nấu|chỉ mình cách làm|chỉ cách nấu|chỉ cách làm|"
    r"cách nấu|cách làm|cách kho|cách xào|cách chiên|cách hấp|cách luộc|công thức món|công thức nấu|"
    r"công thức làm|công thức|hướng dẫn|món ăn|món|chỉ mình|chỉ em|dạy mình|dạy em)\s+",
    re.IGNORECASE
)


TU_Y_DINH_NAU = re.compile(
    r"\b(cách làm|cách nấu|cách kho|cách xào|cách chiên|cách hấp|cách luộc|cách nướng|công thức|hướng dẫn|chỉ cách|"
    r"nấu sao|nấu như thế nào|làm sao|sao cho|như thế nào|làm kiểu nào|kiểu gì|chỉ mình|chỉ em|dạy mình|dạy em|"
    r"nấu món|làm món|nguyên liệu|sơ chế|chế biến|xào tỏi|nấu canh|nấu cháo|kho thịt|kho cá)\b",
    re.IGNORECASE
)

NGUYEN_LIEU_CHINH = [
    "thịt bò", "bò", "thịt bằm", "thịt băm", "thịt ba rọi", "thịt ba chỉ", "thịt heo", "thịt lợn",
    "thịt gà", "gà", "thịt vịt", "vịt", "cá lóc", "cá kèo", "cá bông lau", "cá linh", "cá trê", "cá chạch", "cá bống", "cá",
    "tôm", "tép", "cua", "sườn", "ếch", "nghêu", "ngao", "trứng", "đậu hũ",
    "rau xanh", "rau ngót", "rau dền", "rau muống", "rau lang", "rau đắng", "cải thảo", "cải ngọt", "cải bẹ", "cải",
    "súp lơ", "bông điên điển", "bông bí", "bông so đũa", "bí đao", "bí đỏ", "bầu", "mướp", "khổ qua",
    "cà rốt", "khoai mỡ", "khoai tây", "cà chua", "nấm", "giá đỗ",
    "gừng", "sả", "lá giang",
    "cháo", "canh", "súp", "lẩu"
]


def trich_xuat_tu_khoa_nau_an(van_ban, cau_hoi=""):
    """Trích xuất các nguyên liệu hoặc món ăn xuất hiện trong văn bản trả lời hoặc câu hỏi."""
    vb = f"{cau_hoi} {van_ban}".lower()
    vb = re.sub(r"\bhấp\s+(thu|thụ)\b", "", vb)
    tim_thay = []
    ds_sap_xep = sorted(NGUYEN_LIEU_CHINH, key=len, reverse=True)
    for nl in ds_sap_xep:
        if re.search(r'\b' + re.escape(nl) + r'\b', vb):
            if not any(nl in t for t in tim_thay):
                tim_thay.append(nl)
    return tim_thay


def tim_goi_y_cong_thuc(cau_hoi, noi_dung_tra_loi, dau=None, kho=None, toi_da=3):
    """Tìm gợi ý các câu hỏi về CÔNG THỨC VÀ CÁCH NẤU ĂN liên quan đến nguyên liệu/món vừa được đề xuất."""
    bo_qua = {dau["id_goc"]} if dau else set()
    tu_khoa = trich_xuat_tu_khoa_nau_an(noi_dung_tra_loi, cau_hoi)
    da_co = set(bo_qua)
    goi_y = []

    # 1. Ưu tiên tìm đa dạng theo từng nhóm nguyên liệu/món chính trong câu trả lời
    if tu_khoa:
        for kw in tu_khoa[:3]:
            kq_kw = truy_hoi(f"cách làm món {kw}", k=3, loc_nhom=list(NHOM_CONG_THUC), kho=kho)
            for d in kq_kw["doan"]:
                if d["id_goc"] not in da_co:
                    da_co.add(d["id_goc"])
                    goi_y.append(d["cau_hoi"])
                    break
            if len(goi_y) >= toi_da:
                break

    # 2. Nếu chưa đủ: tìm tổng hợp trong nhóm công thức
    if len(goi_y) < toi_da:
        truy_van = f"món ăn {' '.join(tu_khoa[:4])}" if tu_khoa else cau_hoi
        kq_tong = truy_hoi(truy_van, k=toi_da + 5, loc_nhom=list(NHOM_CONG_THUC), kho=kho)
        for d in kq_tong["doan"]:
            if d["id_goc"] not in da_co:
                da_co.add(d["id_goc"])
                goi_y.append(d["cau_hoi"])
            if len(goi_y) >= toi_da:
                break

    return goi_y


def tao_goi_y_phu_hop(cau_hoi, van_ban, dau, cac_doan, kho=None, toi_da=3):
    """Tạo gợi ý luôn hướng người dùng đến CÔNG THỨC VÀ CÁCH NẤU ĂN."""
    if not dau:
        return [d["cau_hoi"] for d in cac_doan if d.get("nhom_folder") != NHOM_CHAO_HOI][:toi_da]

    bo_qua = {dau["id_goc"]}
    la_bai_cong_thuc = (
        dau.get("nhom_folder") in NHOM_CONG_THUC
        or any(k in dau.get("ten_muc", "").lower() for k in ("nguyên liệu", "chế biến", "cách nấu", "sơ chế"))
    )

    if la_bai_cong_thuc:
        # Nếu bài hiện tại đã là một công thức nấu ăn:
        # 1. Lấy các bài công thức khác trong top truy hồi
        goi_y = [d["cau_hoi"] for d in cac_doan if d["id_goc"] not in bo_qua and d.get("nhom_folder") in NHOM_CONG_THUC]
        goi_y = list(dict.fromkeys(goi_y))[:toi_da]
        # Nếu chưa đủ 3 món: tìm thêm các công thức liên quan đến nguyên liệu của món này
        if len(goi_y) < toi_da:
            them = tim_goi_y_cong_thuc(cau_hoi, van_ban, dau, kho=kho, toi_da=toi_da - len(goi_y))
            for c in them:
                if c not in goi_y:
                    goi_y.append(c)
        return goi_y[:toi_da]
    else:
        # Nếu bài hiện tại KHÔNG PHẢI là công thức (ví dụ: tư vấn dinh dưỡng, ốm mệt, kinh nguyệt, nguyên liệu):
        # TUYỆT ĐỐI KHÔNG gợi ý thêm câu hỏi y tế/bệnh tật!
        # LUÔN tìm và gợi ý CÁCH NẤU CÁC MÓN ĂN phù hợp với nguyên liệu được đề xuất!
        return tim_goi_y_cong_thuc(cau_hoi, van_ban, dau, kho=kho, toi_da=toi_da)


def tao_cau_hoi_lam_ro(cau_hoi, cac_doan):
    """Tạo câu hỏi làm rõ tự nhiên khi người dùng hỏi một món ăn/chủ đề chung chung."""
    co_y_nau = bool(TU_Y_DINH_NAU.search(cau_hoi))

    # 1. Nếu người dùng hỏi một món ăn chung (thịt kho, canh chua, bánh xèo...)
    chu_de = TIEN_TO_TIM_KIEM.sub("", cau_hoi.strip()).strip()
    chu_de = re.sub(r"[?!.,;:]+$", "", chu_de).strip()

    if co_y_nau and chu_de and 2 <= len(chu_de) <= 35 and len(chu_de.split()) <= 4:
        tu_khoa = chu_de.lower()
        khop = sum(1 for d in cac_doan[:3] if tu_khoa in d.get("cau_hoi", "").lower() or tu_khoa in d.get("noi_dung", "").lower())
        if khop >= 1:
            return f"Món **{chu_de}** có nhiều kiểu nấu đặc trưng lắm nè! Bạn muốn xem công thức của món nào dưới đây?"

    # 2. Nếu là câu hỏi sức khỏe mở (KHÔNG phải đang hỏi công thức nấu cụ thể)
    if not co_y_nau:
        co_om_met = (
            any(d.get("nhom_folder") == "12_goi_y_khi_om_met" for d in cac_doan[:3])
            or bool(re.search(r"\b(không khỏe|mệt|mệt mỏi|uể oải|ốm|sốt|ho|cảm|đau|bệnh|dạ dày|khó tiêu)\b", cau_hoi, re.IGNORECASE))
        )
        if co_om_met:
            return ("Dưới đây là một số gợi ý món ăn bồi bổ sức khỏe phù hợp, bạn bấm chọn để xem công thức chi tiết nha:")

    # 3. Mặc định thân thiện hướng tới công thức nấu
    return "Ý bạn có phải là một trong những món dưới đây không? Bạn bấm chọn để mình hướng dẫn công thức chi tiết nhé:"


def mo_rong_cau_hoi(cau_hoi):
    """Bổ sung các từ khóa chuẩn hóa ngữ nghĩa và từ đồng nghĩa ẩm thực."""
    return mo_rong_keyword(cau_hoi)


def ghi_nhat_ky(ban_ghi):
    """Ghi một dòng vào logs/hoi_thoai.jsonl. Mặc định không ghi nguyên văn câu hỏi (chỉ mã băm + độ dài)."""
    ch = doc_cau_hinh()
    if not ch.get("ghi_nhat_ky", True):
        return
    if not ch.get("ghi_nguyen_van_cau_hoi", False):
        for khoa in ("cau_hoi", "cau_hoi_viet_lai"):
            if ban_ghi.get(khoa):
                van_ban = ban_ghi.pop(khoa)
                ban_ghi[khoa + "_bam"] = hashlib.sha256(van_ban.encode("utf-8")).hexdigest()[:12]
                ban_ghi[khoa + "_do_dai"] = len(van_ban)
    thu_muc = ROOT / "logs"
    thu_muc.mkdir(exist_ok=True)
    with open(thu_muc / "hoi_thoai.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(ban_ghi, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ hàm chính

def _tra_loi_truy_hoi(cau_hoi, lich_su=None, tuy_chon=None):
    """Trả lời một lượt hỏi.

    lich_su: các lượt trước [{cau_hoi, cau_tra_loi, chu_de}] (chỉ giữ so_luot_nho lượt gần nhất),
             chu_de là giá trị "chu_de" mà hàm này trả về ở lượt đó.
    tuy_chon: ghi đè cấu hình cho lượt này: k, che_do_truy_hoi ("vector" | "lai" | "bm25"), loc_nhom, kho.
    Trả về dict: cau_tra_loi (Markdown), loai, nguon, goi_y, doan_truy_hoi, chu_de, giai_thich.
    loai ∈ chao_hoi | ngoai_pham_vi | khong_chac | tra_loi.
    """
    t0 = time.perf_counter()
    ch = doc_cau_hinh()
    tc = tuy_chon or {}
    lich_su = (lich_su or [])[-ch["so_luot_nho"]:]
    dk = tc.get("dieu_kien") or dieu_kien(cau_hoi, lich_su)
    mon = nhan_dien_mon(chuan_hoa_dia_phuong(cau_hoi))
    dac_trung = dac_trung_mon(cau_hoi)
    if mon:
        for protein in ('thịt bò', 'thịt gà', 'thịt vịt'):
            if mon['ten'].startswith(protein+' ') and protein not in dac_trung:
                dac_trung.append(protein)
    co_dieu_kien = bool(dk["loai_tru"] or dk["an_chay"] or dk["nhu_cau"] or dk["chua_ro"] or dk["can_dinh_luong"])
    tim = lambda q: truy_hoi(q, k=max(tc.get("k") or ch["k"], 60) if co_dieu_kien or mon or dac_trung else tc.get("k"), loc_nhom=tc.get("loc_nhom"),
                             che_do=tc.get("che_do_truy_hoi"), kho=tc.get("kho"))

    # 1–2. viết lại câu nối tiếp (lượt đầu không viết lại), mở rộng ngữ nghĩa rồi truy hồi
    cau_tim = "cách nấu " + mon['ten'] if mon and mon['hoi_chung'] else cau_hoi
    tr, cau_viet_lai, theo_chu_de = tim(cau_tim), None, False
    chu_de = chu_de_truoc(lich_su)
    y_dinh = nhan_dien_xa_giao(cau_hoi)
    if chu_de and len(cau_hoi.split()) <= 15 and not y_dinh:
        manh = TU_NOI_TIEP_MANH.search(cau_hoi) or re.search(r"\b(mon do|mon nay|mon kia|cai do|cai nay)\b", chuan_hoa(cau_hoi))
        yeu = TU_NOI_TIEP_YEU.search(cau_hoi) and tr["diem_cao_nhat"] < tr["nguong_tin_cay"]
        if manh or yeu:
            cau_viet_lai = f"{chu_de['cau_hoi']}: {cau_hoi}"
            tr = tim(cau_viet_lai)
            # "món đó / món này" chỉ đúng món của lượt trước → món đó có trong top-k thì đưa lên đầu
            vi_tri = next((i for i, d in enumerate(tr["doan"]) if d["id_goc"] == chu_de["id_goc"]), None)
            if manh and vi_tri is not None:
                tr["doan"].insert(0, tr["doan"].pop(vi_tri))
                theo_chu_de = True
            elif manh:
                # Chủ đề đã xác nhận có ID, không cần mong vector tìm lại
                # đúng nó trong top-k cho một câu đại từ ngắn.
                _, metadata, _ = nap_kho(tr['kho'])
                prior = next((d for d in metadata if d['id_goc'] == chu_de['id_goc']), None)
                if prior and (not tc.get('loc_nhom') or prior['nhom_folder'] in tc['loc_nhom']):
                    tr['doan'].insert(0, dict(prior, diem=0.0, theo_chu_de=True))
                    theo_chu_de = True
    if tc.get('id_chu_de') is not None:
        _, metadata, _ = nap_kho(tr['kho'])
        forced = next((d for d in metadata if d['id_goc'] == tc['id_chu_de']), None)
        if forced and (not tc.get('loc_nhom') or forced['nhom_folder'] in tc['loc_nhom']):
            existing = next((d for d in tr['doan'] if d['id_goc'] == forced['id_goc']), None)
            tr['doan'] = [dict(existing or forced, diem=(existing or {}).get('diem',0.0))] + [d for d in tr['doan'] if d['id_goc'] != forced['id_goc']]
            theo_chu_de = True
    if mon:
        tr['doan'] = [d for d in tr['doan'] if dung_ten_mon(d['cau_hoi'], mon)
                      and (not mon['hoi_chung'] or d['nhom_folder'] in NHOM_CONG_THUC)]
    goi_y_tham_khao = []
    if dac_trung and not any(d.get('khop_chinh_xac') for d in tr['doan']):
        truoc_loc = tr['doan']
        tr['doan'] = [d for d in truoc_loc if dung_dac_trung(d['cau_hoi'], noi_dung_day_du(tr['kho'], d['id_goc']), dac_trung)]
        if not tr['doan'] and mon and not co_dieu_kien:
            gan_nhat = [d for d in truoc_loc if d['nhom_folder'] in NHOM_CONG_THUC]
            if any(p.startswith('trứng ') for p in dac_trung):
                gan_nhat = [d for d in gan_nhat if 'trung' in chuan_hoa(d['cau_hoi']).split()]
            goi_y_tham_khao = cau_hoi_khac_nhau(gan_nhat)
    if co_dieu_kien:
        # Kiểm tra toàn bộ công thức, không chỉ đoạn truy hồi hiện tại.
        # Không gán độ phù hợp dinh dưỡng từ tên nguyên liệu.
        toan_bo = {}
        for d in tr["doan"]:
            toan_bo.setdefault(d["id_goc"], None)
        toan_bo = {i: noi_dung_day_du(tr["kho"], i) for i in toan_bo}
        tr["doan"] = [d for d in tr["doan"]
                      if (d.get('khop_chinh_xac') and d['nhom_folder'] not in NHOM_CONG_THUC)
                      or (not dk["chua_ro"] and not dk["can_dinh_luong"]
                          and not vi_pham(d["cau_hoi"] + "\n" + toan_bo[d["id_goc"]], dk)
                          and du_bang_chung(d["cau_hoi"] + "\n" + toan_bo[d["id_goc"]], dk))]
        tr["diem_cao_nhat"] = max((d["diem"] for d in tr["doan"]), default=0.0)
        tr["ngoai_pham_vi"] = tr["diem_cao_nhat"] < tr["nguong"]
        topic_id = tc.get('id_chu_de', (chu_de or {}).get('id_goc'))
        theo_chu_de = theo_chu_de and any(d["id_goc"] == topic_id for d in tr["doan"])
    if mon or dac_trung:
        tr['diem_cao_nhat'] = max((d['diem'] for d in tr['doan']), default=0.0)
        tr['ngoai_pham_vi'] = tr['diem_cao_nhat'] < tr['nguong']
    if tc.get('id_chu_de') is not None:
        # Đang hỏi món đã chọn: điều kiện mới không được âm thầm đổi món.
        tr['doan'] = [d for d in tr['doan'] if d['id_goc'] == tc['id_chu_de']]
    cac_doan = tr["doan"]
    dau = cac_doan[0] if cac_doan else None
    khop_nguyen_lieu = False
    recipe_matches = [d for d in cac_doan if d['nhom_folder'] in ('02_huong_dan_nau_an', '03_huong_dan_nau_mon_mien_tay')]
    if mon and dac_trung and len({d['id_goc'] for d in recipe_matches}) == 1:
        known = set(chuan_hoa(mon['ten']).split()) | set(chuan_hoa(' '.join(dac_trung)).split())
        requested = set(ten_mon_tu_cau_hoi(cau_hoi).split()) - {'co', 'voi'}
        # Tên món ngắn, đúng phương pháp và đúng nguyên liệu trong công thức
        # duy nhất: đây là bằng chứng riêng, không nâng giả điểm cosine.
        khop_nguyen_lieu = bool(requested) and requested <= known
        if khop_nguyen_lieu:
            dau = recipe_matches[0]
            cac_doan.remove(dau)
            cac_doan.insert(0, dau)
    khop_nguon = bool(dau and (dau.get('khop_chinh_xac') or dau.get('khop_ten_mon') or dau.get('khop_y_dinh') or khop_nguyen_lieu or theo_chu_de))
    nhieu_ban_mon = len({d['id_goc'] for d in cac_doan if d.get('khop_ten_mon')}) > 1

    # 3. định tuyến
    nguon, goi_y, chu_de_moi = [], [], None
    mau = dau if khop_nguon and dau['nhom_folder'] == NHOM_CHAO_HOI else None
    if mau is None and y_dinh and not khop_nguon:
        mau = tra_loi_xa_giao(y_dinh, tr['kho'])
    if mau is None and dau and dau["nhom_folder"] == NHOM_CHAO_HOI and dau["diem"] >= ch["nguong_chao_hoi"]:
        mau = dau
    if mau is not None:
        loai, van_ban = "chao_hoi", mau["noi_dung"]
    elif dac_trung and not cac_doan and not co_dieu_kien:
        loai = 'khong_chac'
        van_ban = (f"Mình chưa tìm được tài liệu ghi đúng **{', '.join(dac_trung)}** cho món bạn hỏi. "
                   "Mình sẽ không tự thay nguyên liệu. Bạn có thể chọn công thức gần nhất dưới đây để tham khảo; "
                   "nguyên liệu trong đó có thể khác yêu cầu của bạn." if goi_y_tham_khao else
                   f"Mình chưa có tài liệu đủ rõ cho **{', '.join(dac_trung)}** trong câu hỏi này. Bạn cho mình tên món cụ thể hơn nhé.")
        goi_y = goi_y_tham_khao
    elif nhieu_ban_mon or (mon and mon['hoi_chung'] and cac_doan and not khop_nguon):
        loai = 'khong_chac'
        goi_y = cau_hoi_khac_nhau(cac_doan)
        van_ban = (f"Bạn muốn làm **{mon['ten'] if mon else 'món này'}** theo kiểu nào? "
                   "Mình tìm được các công thức dưới đây; bạn chọn một món để xem nguyên liệu và cách nấu nhé.")
    elif mon and not cac_doan and not co_dieu_kien:
        loai, van_ban = 'khong_chac', f"Mình chưa tìm được công thức đúng **{mon['ten']}** trong dữ liệu. Bạn cho mình tên món cụ thể hơn nhé."
    elif co_dieu_kien and (not cac_doan or (tr["ngoai_pham_vi"] and not khop_nguon)):
        loai = "khong_chac"
        van_ban = ("Mình chưa tìm được công thức có đủ thông tin để đáp ứng các điều kiện bạn đưa ra. "
                   "Bạn muốn nấu món gì và có thể dùng những nguyên liệu nào? "
                   "Mình sẽ tìm tiếp dựa trên dữ liệu có sẵn.")
        if dk["chua_ro"]:
            van_ban = ("Mình chưa nhận diện chắc chắn nguyên liệu cần tránh trong yêu cầu này. "
                       "Bạn ghi riêng từng nguyên liệu cần loại trừ giúp mình nhé. "
                       "Mình chưa đề xuất món cho đến khi xác định được điều kiện đó.")
        elif dk["can_dinh_luong"]:
            van_ban = ("Kho hiện tại chưa có bảng dưỡng chất theo khối lượng và khẩu phần để xác nhận con số bạn yêu cầu. "
                       "Mình có thể tìm món theo mô tả ít béo, ít đường hoặc giàu đạm trong tài liệu; "
                       "bạn muốn tìm theo tiêu chí nào?")
    elif (tr["ngoai_pham_vi"] and not khop_nguon) or not cac_doan:
        loai, van_ban = "ngoai_pham_vi", CAU_NGOAI_PHAM_VI
    elif dau["diem"] < tr["nguong_tin_cay"] and not theo_chu_de and not khop_nguon:
        loai = "khong_chac"
        goi_y = cau_hoi_khac_nhau(cac_doan)
        van_ban = tao_cau_hoi_lam_ro(cau_hoi, cac_doan)
        if tr["che_do_truy_hoi"] == "khong_dau":
            van_ban = CAU_KHONG_DAU + van_ban
        # Chưa xác nhận món: không đặt một kết quả phỏng đoán làm chủ đề hội thoại.
    else:
        loai, chu_de_moi = "tra_loi", {"cau_hoi": dau["cau_hoi"], "id_goc": dau["id_goc"]}
        raw_noi_dung, _ = noi_dung_theo_yeu_cau(tr["kho"], dau["id_goc"], cau_viet_lai or cau_hoi)
        van_ban = dinh_dang(raw_noi_dung)
        nguon = [mo_ta_nguon(dau)]
        goi_y = tao_goi_y_phu_hop(cau_viet_lai or cau_hoi, van_ban, dau, cac_doan, kho=tr["kho"])


    if mon:
        # Các nút công thức phải cùng món đang hỏi, kể cả khi gợi ý phụ
        # được tìm bằng một truy vấn riêng ở tao_goi_y_phu_hop.
        goi_y = [q for q in goi_y if dung_ten_mon(q, mon)]
    if co_dieu_kien:
        # Các nút gợi ý cũng phải qua bộ lọc; không để nút đề xuất lại món bị cấm.
        goi_y = [d["cau_hoi"] for d in cac_doan if d["nhom_folder"] != NHOM_CHAO_HOI
                 and (d.get('khop_chinh_xac') or d["diem"] >= (tr["nguong_tin_cay"] if loai == 'tra_loi' else tr['nguong']))][:3]
        if loai == "tra_loi":
            if (dk["loai_tru"] or dk["an_chay"]) and dau and dau['nhom_folder'] in NHOM_CONG_THUC:
                van_ban += ("\n\n*Mình đã lọc theo nguyên liệu được ghi trong công thức. "
                            "Bạn cần kiểm tra thêm nhãn gia vị và nguy cơ tiếp xúc chéo nếu có dị ứng.*")
            if dk["nhu_cau"]:
                van_ban += "\n\n*Đặc điểm dinh dưỡng dựa trên mô tả trong nguồn, chưa có phép tính kcal hoặc dưỡng chất theo khẩu phần.*"

    # 4. lời nhắc sức khỏe
    if loai == "tra_loi" and (TU_SUC_KHOE.search(cau_viet_lai or cau_hoi) or (dau and dau["nhom_folder"].startswith("12_"))):
        van_ban += CAU_NHAC_SUC_KHOE

    thoi_gian = round(time.perf_counter() - t0, 3)
    giai_thich = {"cau_hoi_sach": tr["cau_hoi_sach"], "cau_hoi_vao_mo_hinh": tr["cau_hoi_vao_mo_hinh"],
                  "cau_hoi_viet_lai": cau_viet_lai, "che_do_truy_hoi": tr["che_do_truy_hoi"], "kho": tr["kho"],
                  "may_tim": tr["may_tim"], "framework": "langchain", "dieu_kien": dk, "nhom_nguon": dau["nhom_folder"] if dau else "",
                  'khop_cau_goc': bool(dau and dau.get('khop_chinh_xac')),
                  'khop_ten_mon': bool(dau and dau.get('khop_ten_mon')), 'khop_nguyen_lieu': khop_nguyen_lieu,
                  'khop_y_dinh': bool(dau and dau.get('khop_y_dinh')),
                  'dac_trung_mon': dac_trung,
                  "diem_cao_nhat": tr["diem_cao_nhat"], "nguong_ngoai_pham_vi": tr["nguong"],
                  "nguong_tin_cay": tr["nguong_tin_cay"], "thoi_gian_giay": thoi_gian}

    # 5. nhật ký
    ghi_nhat_ky({
        "thoi_gian": datetime.now().isoformat(timespec="seconds"),
        "cau_hoi": cau_hoi, "cau_hoi_viet_lai": cau_viet_lai,
        "che_do_truy_hoi": tr["che_do_truy_hoi"], "kho": tr["kho"], "may_tim": tr["may_tim"],
        "doan": [{"chunk_id": d["chunk_id"], "diem": d["diem"]} for d in cac_doan],
        "loai": loai, "nguon_id_goc": [n["id_goc"] for n in nguon], "thoi_gian_xu_ly_giay": thoi_gian,
    })
    nhan_goi_y = "👉 Gợi ý công thức món ăn bạn có thể nấu:" if loai == "tra_loi" else "👉 Chọn món bạn muốn xem công thức:"
    for i,d in enumerate(cac_doan, 1):
        d.setdefault('xep_hang',i)
    return {"cau_tra_loi": van_ban, "loai": loai, "nguon": nguon, "goi_y": goi_y,
            "nhan_goi_y": nhan_goi_y, "doan_truy_hoi": cac_doan,
            "chu_de": chu_de_moi, "giai_thich": giai_thich}


def tra_loi(cau_hoi, lich_su=None, tuy_chon=None):
    """API tương thích giao diện, điều phối trạng thái và phản hồi bằng LCEL."""
    from backend.chatbot.hoi_thoai import tra_loi_co_trang_thai
    return tra_loi_co_trang_thai(cau_hoi, lich_su, tuy_chon)
