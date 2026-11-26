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


_NEW_MEAL = re.compile(
    r'\b(?:ngay mai|mai|hom sau|bua (?:sau|toi)|lan sau)\s+'
    r'(?:(?:toi|minh|tui|em) )?(?:se |muon |can )?(?:nau|lam|an|goi y|chi co|nha co)\b'
)
_NEW_DISH = re.compile(r'\b(?:doi|chuyen) sang (?:mon |cong thuc )(?!khac\b|moi\b)\w+')
_LONG_TERM = re.compile(
    r'\b(?:tu nay|lau dai|thuong xuyen|luon (?:tranh|an|kieng|khong)|'
    r'(?:toi|minh|em) (?:an chay truong|khong thich))\b'
)


def _clear_request(state):
    """Clear the current meal without touching declared allergies or edit logs."""
    state.update(nguyen_lieu_co=[], chi_dung_nguyen_lieu_co=False, de_xuat=[],
                 thoi_gian_toi_da=None, khong_chien=False, khau_phan=None,
                 mon_hien_tai=None, calo_hien_tai=False)
    for key in ('nguyen_lieu_bat_buoc', 'phan_tich_goi_y', 'yeu_cau_dang_cho',
                'calo_yeu_cau', 'nutrition_context', 'nutrition_portion_status',
                'portion_state_v5', 'excel_pending_change', 'pending_ingredient_change',
                'recipe_edit_v1', 'goi_y_cho_calo'):
        state.pop(key, None)


def _check_pantry_update(state, parsed):
    """Use the existing suggestion metadata for local availability."""
    have = parsed.get('nguyen_lieu_co', ())
    missing = parsed.get('nguyen_lieu_khong_co', ())
    buying = parsed.get('cho_phep_mua_them', False)
    if not (have or missing or buying):
        return
    info = dict(state.get('phan_tich_goi_y') or {})
    present = {chuan_hoa(item) for item in have}
    unavailable = {chuan_hoa(item) for item in missing}
    prior = {chuan_hoa(item) for item in info.get('nguyen_lieu_khong_co', ())}
    info['nguyen_lieu_khong_co'] = sorted((prior-present) | unavailable)
    if buying:
        info['cho_phep_mua_them'] = True
        state['chi_dung_nguyen_lieu_co'] = False
    if have:
        info['cho_phep_mua_them'] = bool(buying)
        state['nguyen_lieu_co'] = list(have)
        state['chi_dung_nguyen_lieu_co'] = bool(parsed.get('chi_dung_nguyen_lieu_co')) and not buying
    state['nguyen_lieu_co'] = [item for item in state.get('nguyen_lieu_co', ()) if chuan_hoa(item) not in unavailable]
    state['phan_tich_goi_y'] = info


def cap_nhat(state, parsed):
    result = copy.deepcopy(state)
    if parsed.get('intents') == ['ngoai_pham_vi']:
        return result
    from backend.chatbot.suc_khoe import cap_nhat as cap_nhat_suc_khoe
    result['tinh_trang_suc_khoe'] = cap_nhat_suc_khoe(result.get('tinh_trang_suc_khoe'), parsed['cau_goc'])
    q = chuan_hoa(parsed['cau_goc'])
    current = copy.deepcopy(parsed['dieu_kien'])
    old = result['dieu_kien']
    stable = copy.deepcopy(result.get('dieu_kien_lau_dai') or {})
    if _LONG_TERM.search(q):
        from backend.chatbot.ngon_ngu import dieu_kien
        for clause in re.split(r'[,;.!?]|\bnhưng\b',parsed['cau_goc'],flags=re.I):
            text = chuan_hoa(clause)
            if not _LONG_TERM.search(text) or re.search(r'\bdi ung\b',text):
                continue
            preference = re.sub(r'\bkhông thích (?:ăn )?', 'không ăn ', clause, flags=re.I)
            declared = dieu_kien(preference)
            stable['loai_tru'] = sorted(set(stable.get('loai_tru', ())) | set(declared['loai_tru']))
            current['loai_tru'] = sorted(set(current['loai_tru']) | set(declared['loai_tru']))
            if declared['an_chay'] or re.search(r'\ban chay truong\b',text):
                stable['an_chay'] = True
    if _NEW_MEAL.search(q) or _NEW_DISH.search(q):
        _clear_request(result)
        old = {'loai_tru':list(stable.get('loai_tru', ())), 'an_chay':bool(stable.get('an_chay')),
               'nhu_cau':[], 'chua_ro':[], 'can_dinh_luong':False}
    if re.search(r'\b(?:huy|thoi|bo qua) (?:yeu cau )?(?:goi y|chon mon)\b',q):
        result.pop('yeu_cau_dang_cho',None)
        result['de_xuat'] = []
    allergies = set(result.get('di_ung', [])) | set(parsed.get('di_ung', []))
    corrections = set(parsed.get('di_ung_xac_nhan_xoa', ()))
    for name, aliases in ALIASES.items():
        if name not in parsed.get('di_ung', ()) and set(aliases).intersection(corrections):
            allergies.discard(name)
            old['loai_tru'] = [n for n in old['loai_tru'] if n != name or n in stable.get('loai_tru', ())]
    result['di_ung'] = sorted(allergies)
    prior_unknown_allergies = set(result.get('di_ung_chua_ro', []))
    unknown_allergies = prior_unknown_allergies | set(parsed.get('di_ung_chua_ro', []))
    unknown_allergies -= set(corrections)-set(parsed.get('di_ung_chua_ro', ()))
    result['di_ung_chua_ro'] = sorted(unknown_allergies)
    if re.search(r'\b(?:bo|xoa) (?:het |tat ca )?dieu kien\b', q):
        old = {'loai_tru': [], 'an_chay': False, 'nhu_cau': [], 'chua_ro': [], 'can_dinh_luong': False}
        result.update(nguyen_lieu_co=[],chi_dung_nguyen_lieu_co=False,thoi_gian_toi_da=None,
                      khong_chien=False,calo_yeu_cau=None)
        for field in ('nguyen_lieu_bat_buoc','phan_tich_goi_y','yeu_cau_dang_cho'):
            result.pop(field,None)
        stable = {}
    removed = set()
    for name, aliases in ALIASES.items():
        for alias in aliases:
            if re.search(r'\b(?:khong kieng|an lai|dung lai|bo dieu kien(?: khong an)?)\s+'+re.escape(alias)+r'\b', q):
                removed.add(name)
    old['loai_tru'] = sorted(((set(old['loai_tru']) | set(current['loai_tru']))-removed) | allergies)
    if 'loai_tru' in stable:
        stable['loai_tru'] = sorted(set(stable['loai_tru']) - removed)
    
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
        stable.pop('an_chay',None)

    if current['nhu_cau']:
        old['nhu_cau'] = list(current['nhu_cau'])
    if re.search(r'\b(?:bo|xoa) (?:muc tieu|yeu cau) dinh duong\b', q):
        old['nhu_cau'] = []
    old['chua_ro'] = sorted((set(old.get('chua_ro', [])) - (prior_unknown_allergies-unknown_allergies)) | set(current['chua_ro']) | unknown_allergies)
    if parsed.get('calo_yeu_cau') is not None:
        result['calo_yeu_cau'] = parsed['calo_yeu_cau']
    old['can_dinh_luong'] = bool(current['can_dinh_luong'] or result.get('calo_yeu_cau'))
    if re.search(r'\b(?:bo|xoa) (?:muc tieu|yeu cau) dinh duong\b', q):
        result['calo_yeu_cau'] = None
        old['can_dinh_luong'] = False
    result['dieu_kien'] = old
    if stable:
        result['dieu_kien_lau_dai'] = stable
    else:
        result.pop('dieu_kien_lau_dai',None)
    _check_pantry_update(result,parsed)
    if parsed['thoi_gian_toi_da'] is not None:
        result['thoi_gian_toi_da'] = parsed['thoi_gian_toi_da']
    if parsed['khau_phan'] is not None:
        result['khau_phan'] = parsed['khau_phan']
    result['khong_chien'] = result.get('khong_chien', False) or parsed['khong_chien']
    result['intents'] = parsed['intents']
    return result


def chon_theo_so(text, state):
    q = chuan_hoa(text)
    match = re.search(r'\bmon (?:thu |so )?(mot|hai|ba|bon|nam|sau|bay|tam|chin|\d{1,3})\b', q)
    if not match:
        return None, None
    numbers = dict(zip('mot hai ba bon nam sau bay tam chin'.split(),range(1,10)))
    number = numbers.get(match[1], int(match[1]) if match[1].isdigit() else 0)
    options = state.get('de_xuat', [])
    if not 1 <= number <= len(options):
        return None, f'Mình chưa có món thứ {number} trong danh sách hiện tại. Bạn chọn một món trong danh sách vừa gợi ý nhé.'
    return copy.deepcopy(options[number-1]), None


def la_cau_noi_tiep(text):
    q = chuan_hoa(text)
    return bool(re.search(r'\b(mon do|mon nay|mon tren|cai do|no|khong dung|khong them|cho \d+ nguoi|an lai|dung lai|khong kieng)\b', q))
