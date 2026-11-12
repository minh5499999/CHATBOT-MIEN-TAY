"""Trạng thái JSON theo cuộc trò chuyện; không biến global chứa hồ sơ người dùng."""
import copy
import re
from backend.chatbot.ngon_ngu import chuan_hoa, ALIASES


def lay_trang_thai(history):
    for turn in reversed(history or []):
        if isinstance(turn.get('trang_thai'), dict):
            return copy.deepcopy(turn['trang_thai'])
    return {'phien_ban': 2, 'dieu_kien': {'loai_tru': [], 'an_chay': False, 'nhu_cau': [],
                                         'chua_ro': [], 'can_dinh_luong': False},
            'de_xuat': [], 'mon_hien_tai': None, 'nguyen_lieu_co': [], 'di_ung': [],
            'thoi_gian_toi_da': None, 'khau_phan': None, 'khong_chien': False}


def cap_nhat(state, parsed):
    result = copy.deepcopy(state)
    from backend.chatbot.suc_khoe import cap_nhat as cap_nhat_suc_khoe
    result['tinh_trang_suc_khoe'] = cap_nhat_suc_khoe(result.get('tinh_trang_suc_khoe'), parsed['cau_goc'])
    q = chuan_hoa(parsed['cau_goc'])
    current = parsed['dieu_kien']
    old = result['dieu_kien']
    allergies = set(result.get('di_ung', [])) | set(parsed.get('di_ung', []))
    for name, aliases in ALIASES.items():
        if any(re.search(r'\bkhong (?:con )?di ung\s+'+re.escape(alias)+r'\b', q) for alias in aliases):
            allergies.discard(name)
            old['loai_tru'] = [n for n in old['loai_tru'] if n != name]
    result['di_ung'] = sorted(allergies)
    prior_unknown_allergies = set(result.get('di_ung_chua_ro', []))
    unknown_allergies = prior_unknown_allergies | set(parsed.get('di_ung_chua_ro', []))
    unknown_allergies = {name for name in unknown_allergies if not re.search(r'\bkhong (?:con )?di ung\s+'+re.escape(name)+r'\b',q)}
    result['di_ung_chua_ro'] = sorted(unknown_allergies)
    if re.search(r'\b(?:bo|xoa) (?:het |tat ca )?dieu kien\b', q):
        old = {'loai_tru': [], 'an_chay': False, 'nhu_cau': [], 'chua_ro': [], 'can_dinh_luong': False}
        result.update(nguyen_lieu_co=[], thoi_gian_toi_da=None, khong_chien=False)
    removed = set()
    for name, aliases in ALIASES.items():
        for alias in aliases:
            if re.search(r'\b(?:khong kieng|an lai|dung lai|bo dieu kien(?: khong an)?)\s+'+re.escape(alias)+r'\b', q):
                removed.add(name)
    old['loai_tru'] = sorted(((set(old['loai_tru']) | set(current['loai_tru']))-removed) | allergies)
    
    # Ghi nhớ chế độ ăn chay từ các lượt trước.
    old['an_chay'] = old['an_chay'] or current['an_chay']

    # Nhận diện người dùng muốn ngừng ăn chay.
    bo_an_chay = re.search(
        r'\b(?:'
        r'khong an chay nua|'
        r'bo dieu kien an chay|'
        r'ngung an chay|'
        r'thoi an chay|'
        r'gio an man|'
        r'bay gio an man|'
        r'muon an man|'
        r'khong can an chay'
        r')\b',
        q
    )

    if bo_an_chay:
        old['an_chay'] = False

    if current['nhu_cau']:
        old['nhu_cau'] = list(current['nhu_cau'])
    if re.search(r'\b(?:bo|xoa) (?:muc tieu|yeu cau) dinh duong\b', q):
        old['nhu_cau'] = []
    old['chua_ro'] = sorted((set(old.get('chua_ro', [])) - (prior_unknown_allergies-unknown_allergies)) | set(current['chua_ro']) | unknown_allergies)
    old['can_dinh_luong'] = bool(current['can_dinh_luong'] or result.get('calo_yeu_cau'))
    if parsed.get('calo_yeu_cau') is not None:
        result['calo_yeu_cau'] = parsed['calo_yeu_cau']
    if re.search(r'\b(?:bo|xoa) (?:muc tieu|yeu cau) dinh duong\b', q):
        result['calo_yeu_cau'] = None
        old['can_dinh_luong'] = False
    result['dieu_kien'] = old
    if parsed['nguyen_lieu_co']:
        result['nguyen_lieu_co'] = list(parsed['nguyen_lieu_co'])
        result['chi_dung_nguyen_lieu_co'] = parsed['chi_dung_nguyen_lieu_co']
    if parsed['thoi_gian_toi_da'] is not None:
        result['thoi_gian_toi_da'] = parsed['thoi_gian_toi_da']
    if parsed['khau_phan'] is not None:
        result['khau_phan'] = parsed['khau_phan']
    result['khong_chien'] = result.get('khong_chien', False) or parsed['khong_chien']
    result['intents'] = parsed['intents']
    return result


def chon_theo_so(text, state):
    q = chuan_hoa(text)
    match = re.search(r'\bmon (?:thu |so )?(mot|hai|ba|bon|nam|\d+)\b', q)
    if not match:
        return None, None
    numbers = {'mot':1, 'hai':2, 'ba':3, 'bon':4, 'nam':5}
    number = numbers.get(match[1], int(match[1]) if match[1].isdigit() else 0)
    options = state.get('de_xuat', [])
    if not 1 <= number <= len(options):
        return None, f'Mình chưa có món thứ {number} trong danh sách hiện tại. Bạn chọn một món trong danh sách vừa gợi ý nhé.'
    return copy.deepcopy(options[number-1]), None


def la_cau_noi_tiep(text):
    q = chuan_hoa(text)
    return bool(re.search(r'\b(mon do|mon nay|mon tren|cai do|no|khong dung|khong them|cho \d+ nguoi|an lai|dung lai|khong kieng)\b', q))
