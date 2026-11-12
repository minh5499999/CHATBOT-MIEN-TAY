"""Nhiều intent và thực thể tiếng Việt; không gọi mô hình sinh hoặc dịch vụ ngoài."""
import re
from backend.chatbot.ngon_ngu import chuan_hoa, chuan_hoa_dia_phuong, dieu_kien

PATTERNS = {
    'nguyen_lieu': r'\b(nguyen lieu|gia vi|can mua gi|chuan bi nhung gi|can nhung gi|thanh phan)\b',
    'so_che': r'\b(so che|lam sach|khu tanh|rua ca|rua thit|uop|chat|thai)\b',
    'che_bien': r'\b(cac buoc|tung buoc|che bien|cach nau|nau sao|nau nhu the nao|lam sao|cach lam)\b',
    'thoi_gian': r'\b(bao lau|mat may phut|thoi gian|trong \d+ phut|duoi \d+ phut)\b',
    'khau_phan': r'\b(khau phan|may nguoi|bao nhieu nguoi|cho \d+ nguoi|\d+ phan an)\b',
    'thay_the': r'\b(thay bang|thay the|dung gi thay|khong co .+ thi|het .+ dung)\b',
    'bao_quan': r'\b(bao quan|de tu lanh|tru dong|cap dong|de duoc bao lau)\b',
    'dinh_duong': r'\b(dinh duong|calo|kcal|protein|chat beo|chat xo|chat dam|giau dam|it beo|it dau|giam can)\b',
    
    'goi_y_mon': (
    r'\b(?:'
    r'goi y|'
    r'(?:an|nau)(?: an)?(?: duoc)? (?:mon )?(?:gi|nao)|'
    r'lam mon (?:nao|gi)|'
    r'mon nao|mon an tu|'
    r'nau gi|lam gi|an gi|'
    r'co mon nao|'
    r'mon gi ngon|'
    r'mon gi de lam|'
    r'mon gi nhanh|'
    r'nau mon gi|'
    r'lam mon gi'
    r')\b'
),

    'nau_nhanh': (
    r'\b(?:'
    r'nau nhanh|lam nhanh|nau le|lam le|'
    r'mon nhanh|mon de lam|'
    r'nau gi le|lam gi le|'
    r'nau mon gi cho nhanh|'
    r'nau mon nao cho nhanh|'
    r'nau gi cho nhanh|'
    r'lam mon gi cho nhanh|'
    r'lam gi cho nhanh|'
    r'mon nao nau nhanh|'
    r'mon gi nau nhanh|'
    r'nau mon nao nhanh|'
    r'nau mon gi nhanh|'
    r'nau gi nhanh|'
    r'nau mon nao de nhanh|'
    r'mon nao nhanh gon'
    r')\b'
),

    'uong_gi': r'\buong (?:nuoc )?gi\b',
    'kieng_gi': r'\b(kieng (?:an )?gi|tranh an gi)\b',
    'thong_tin': r'\b(la gi|khac nhau|khac gi|vi sao|tai sao|co nen|duoc khong)\b',
}


def phan_tich(text, ingredient_names=()):
    normalized = chuan_hoa_dia_phuong(text)
    q = chuan_hoa(normalized)
    intents = [name for name, pattern in PATTERNS.items() if re.search(pattern, q)]
    if re.search(r'\b(huong dan|cong thuc|chi (?:minh|toi|tui)|day (?:minh|toi))\b', q):
        intents.append('cong_thuc')
    if 'che_bien' in intents and not {'thay_the', 'bao_quan', 'thong_tin'} & set(intents):
        intents.append('cong_thuc')
    dk = dieu_kien(text)
    have = []
    inventory = re.search(r'\b(?:chi co|dang co|minh co|toi co|co san|tu lanh co|tu)\s+(.+)', q)
    if inventory:
        span = re.split(r'\b(?:muon|can|thi|nhung|de|lam sao|nau sao)\b', inventory[1])[0]
        for name in dict.fromkeys(chuan_hoa(chuan_hoa_dia_phuong(n)) for n in ingredient_names):
            if re.search(r'(?<!\w)'+re.escape(chuan_hoa(name))+r'(?!\w)', span):
                if not any(chuan_hoa(name) in chuan_hoa(old) for old in have):
                    have.append(name)
        # Cụm dài giữ trước để không tách trứng vịt thành vịt.
        have = [name for name in have if not any(name != other and chuan_hoa(name) in chuan_hoa(other) for other in have)]
    time = re.search(r'\b(?:trong|duoi|toi da|khong qua|khoang)\s+(\d+)\s*(phut|gio)\b', q)
    portions = re.search(r'\b(?:cho|khau phan)\s*(\d+)\s*(?:nguoi|phan)\b', q)
    calories = re.search(r'\b(\d+)\s*(?:kcal|calo)\b', q)
    if 'goi_y_mon' in intents and have:
        intents.append('goi_y_theo_nguyen_lieu')
    if 'goi_y_mon' in intents and (dk['nhu_cau'] or calories):
        intents.append('goi_y_dinh_duong')
    if re.search(r'\b(mon do|mon nay|mon thu|mon so|khong dung|cho \d+ nguoi)\b', q):
        intents.append('noi_tiep')
    if re.search(r'\b(bi cam|bi ho|bi sot|om met)\b', q):
        intents.append('an_uong_khi_om')
    allergies, unknown_allergies = [], []
    for match in re.finditer(r'(?<!khong )(?<!chua )\bdi ung(?: voi)?\s+([^,;.!?]+)', q):
        if re.search(r'\b(?:khong|chua)(?: con)?\s*$',q[max(0,match.start()-16):match.start()]):
            continue
        allergy_dk = dieu_kien('dị ứng '+match[1])
        allergies.extend(allergy_dk['loai_tru'])
        unknown_allergies.extend(allergy_dk['chua_ro'])
    from backend.chatbot.suc_khoe import nhan_dien
    from backend.chatbot.trich_xuat_thuc_the import (
        trich_xuat_textrank,
        trich_xuat_cum_cu_phap,
        lay_bo_phan_loai_ml,
    )
    health = nhan_dien(normalized)
    if health:
        intents.append('an_uong_theo_suc_khoe')
    tu_khoa_textrank = [k for k, _ in trich_xuat_textrank(text, top_k=5)]
    cum_cu_phap = trich_xuat_cum_cu_phap(text)
    nhom_ml = lay_bo_phan_loai_ml().du_doan(text)
    return {'cau_goc': text, 'cau_chuan': normalized, 'intents': list(dict.fromkeys(intents)),
            'tinh_trang_suc_khoe': health,
            'di_ung': sorted(set(allergies)),
            'di_ung_chua_ro': sorted(set(unknown_allergies)),
            'dieu_kien': dk, 'nguyen_lieu_co': have, 'chi_dung_nguyen_lieu_co': bool(re.search(r'\bchi co\b', q)),
            'thoi_gian_toi_da': int(time[1])*(60 if time[2] == 'gio' else 1) if time else None,
            'khau_phan': int(portions[1]) if portions else None,
            'calo_yeu_cau': int(calories[1]) if calories else None,
            'khong_chien': bool(re.search(r'\b(khong chien|khong ran|tranh chien)\b', q)),
            'tu_khoa_chinh': tu_khoa_textrank,
            'cum_cu_phap': cum_cu_phap,
            'nhom_ml': nhom_ml['nhom'],
            'diem_nhom_ml': nhom_ml['diem']}
