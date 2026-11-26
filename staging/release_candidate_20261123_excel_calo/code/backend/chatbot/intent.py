"""Nhiều intent và thực thể tiếng Việt; không gọi mô hình sinh hoặc dịch vụ ngoài."""
import re
from backend.chatbot.ngon_ngu import chuan_hoa, chuan_hoa_dia_phuong, dieu_kien, NGUYEN_LIEU

PATTERNS = {
    'nguyen_lieu': r'\b(nguyen lieu|gia vi|can mua gi|chuan bi nhung gi|can nhung gi|thanh phan)\b',
    'so_che': r'\b(so che|lam sach|khu tanh|rua ca|rua thit|uop|chat|thai)\b',
    'che_bien': r'\b(cac buoc|tung buoc|che bien|cach nau|nau sao|nau nhu the nao|lam sao|cach lam)\b',
    'thoi_gian': r'\b(bao lau|bao nhieu phut|mat may phut|thoi gian|trong \d+ phut|duoi \d+ phut)\b',
    'khau_phan': r'\b(khau phan|may nguoi|bao nhieu nguoi|cho \d+ nguoi|\d+ phan an)\b',
    'thay_the': r'\b(thay bang|thay the|dung gi thay|khong co .+ thi|het .+ dung)\b',
    'bao_quan': r'\b(bao quan|de tu lanh|tru dong|cap dong|de duoc bao lau)\b',
    'dinh_duong': r'\b(dinh duong|calo|kcal|protein|chat beo|chat xo|chat dam|giau dam|it beo|it dau|giam can)\b',
    
    'goi_y_mon': (
    r'\b(?:'
    r'goi y|'
    r'(?:an|nau)(?: an)?(?: duoc)? (?:mon )?(?:gi|nao)|'
    r'(?:lam|man) mon (?:nao|gi)|'
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


_INVENTORY = re.compile(
    r'\b(?:(?:o nha|nha(?: minh| toi)?|(?:trong )?tu(?: lanh)?|minh|toi|em) '
    r'(?:(?:chi|dang|van) )?(?:co(?: san)?|con(?: co)?)'
    r'|chi co|dang co|co san|mon (?:an )?tu)\s+'
)
_INGREDIENT_END = re.compile(
    r'[,;.!?]|\b(?:muon|can|thi|nhung|ma|de|lam sao|nau sao|roi|'
    r'(?:nau|an|lam|man) (?:mon )?(?:gi|nao)|khong (?:co|an|dung)|di ung|co the mua)\b'
)
# The existing vocabulary is folded. Keep the original syllable alongside
# its key where stripping tone would collide with a different common word.
_COLLISIONS = {
    'bo': {'bò', 'bơ'}, 'luon': {'lươn'}, 'ca': {'cá', 'cà'}, 'dam': {'đạm'},
    'bot': {'bột'}, 'nam': {'nấm'}, 'chao': {'cháo'},
}
_PROGRAMMING = re.compile(
    r'\b(?:lap trinh|(?:viet|tao|sua|debug) (?:giup (?:toi|minh) )?'
    r'(?:doan code|ma (?:nguon|python)|code|chuong trinh|vong lap)|'
    r'giai (?:bai tap |he )?phuong trinh|sua xe may)\b'
)


def _ingredient_mentions(text, vocabulary):
    words = re.findall(r'\w+', chuan_hoa_dia_phuong(text).casefold())
    folded = [chuan_hoa(word) for word in words]
    found = []
    uncertain = []
    i = 0
    while i < len(words):
        candidate = next((key for key in vocabulary
                          if folded[i:i+len(key)] == list(key)), None)
        if not candidate:
            joined = [key for key in vocabulary if len(key)>1 and ''.join(key)==folded[i]]
            if len(joined)==1:
                found.append(' '.join(joined[0]))
            i += 1
            continue
        original = words[i:i+len(candidate)]
        if any(word != key and key in _COLLISIONS and word not in _COLLISIONS[key]
               for word,key in zip(original,candidate)):
            i += 1
            continue
        if len(candidate) == 1 and original[0] == candidate[0] and candidate[0] in ('bo','luon','nam'):
            uncertain.append(original[0])
        else:
            found.append(' '.join(original) if original[0] in ('bò','bơ') else ' '.join(candidate))
        i += len(candidate)
    return list(dict.fromkeys(found)), list(dict.fromkeys(uncertain))


_ALLERGY_MENTION = re.compile(
    r'\bdi ung(?: voi)?\s+((?:(?!\b(?:thi|nhung|tuy|ma|van|nen|co nen|'
    r'con an|an duoc|la gi|vi sao|tai sao)\b)[^,;.!?])+)',
)
_ALLERGY_HYPOTHETICAL = re.compile(
    r'\b(?:neu|gia su|gia dinh|vi du|truong hop|lieu|co phai)\b',
)
_ALLERGY_OTHER = re.compile(
    r'\b(?:nguoi(?: khac| nha)?|khach|ban toi|ban minh|con toi|con minh|'
    r'vo toi|chong toi|me toi|ba toi|tre(?: em)?|ai do)(?: dang| co the)?(?: bi)?\s*$',
)
_ALLERGY_KNOWLEDGE = re.compile(r'^(?:tai sao|vi sao|ly do|dau hieu|trieu chung|cach nhan biet)\b')
_ALLERGY_NEGATED = re.compile(r'\b(?:khong|chua|chang)(?: con)?(?: bi)?\s*$')
_ALLERGY_CORRECTION = re.compile(r'(?:(?:toi|minh|tui|em) )?khong (?:con )?(?:bi )?$')


def _allergy_mentions(question):
    for match in _ALLERGY_MENTION.finditer(question):
        sentence = re.split(r'[.!?]',question[:match.start()])[-1].strip()
        clause = re.split(r'[,;]|\b(?:nhung|tuy|con)\b(?=\s+(?:toi|minh|tui|em)\b)',sentence)[-1].strip()
        if _ALLERGY_NEGATED.search(clause):
            kind = ('correction' if _ALLERGY_CORRECTION.fullmatch(clause+' ')
                    and not _ALLERGY_HYPOTHETICAL.search(sentence)
                    and not question[match.end():].lstrip().startswith('?')
                    and not re.match(r'\s*\w',question[match.end():]) else 'negative')
        elif _ALLERGY_HYPOTHETICAL.search(sentence):
            kind = 'hypothetical'
        elif (_ALLERGY_KNOWLEDGE.search(clause) or re.match(
                r'\s*(?:la gi|vi sao|tai sao)\b',question[match.end():])
                or (not clause and '?' in question[match.start():])):
            kind = 'knowledge'
        elif _ALLERGY_OTHER.search(clause):
            kind = 'other'
        elif not clause or re.fullmatch(r'(?:toi|minh|tui|em)(?: dang)?(?: bi)?|bi',clause):
            kind = 'personal'
        else:
            kind = 'other'
        yield match,kind


def phan_tich(text, ingredient_names=()):
    normalized = ' '.join(chuan_hoa_dia_phuong(text).split())
    q = chuan_hoa(normalized)
    intents = [name for name, pattern in PATTERNS.items() if re.search(pattern, q)]
    if re.search(r'\b(huong dan|cong thuc|chi (?:minh|toi|tui)|day (?:minh|toi))\b', q):
        intents.append('cong_thuc')
    if re.search(r'^(?:(?:nau|lam|kho|xao|chien|hap|nuong|luoc)\s+.+|.+\s+(?:kho|xao|chien|hap|nuong|luoc))\s+sao cho\b',q):
        intents.append('che_bien')
    if 'che_bien' in intents and not {'thay_the', 'bao_quan', 'thong_tin'} & set(intents):
        intents.append('cong_thuc')
    if re.match(r'^(?:xin )?(?:chào|chao)(?: (?:bạn|bot|ban|anh|chị|chi|em))?[ ?!.]*$',normalized,re.I):
        intents.append('chao_hoi')
    if re.search(r'\b(?:nguon tham khao|dan nguon|trich nguon|kem nguon|lay tu dau)\b',q):
        intents.append('hoi_nguon')
    if re.search(r'\b(?:tai sao|vi sao|ly do)\b',q) and re.search(r'\b(?:nau|ham|kho|trung|chan|chien|cat|uop|xao)\b',q):
        intents.append('ky_thuat_che_bien')
    if re.search(r'\b(?:kcal|calo|nang luong|natri|carbohydrate|protein|chat beo|chat dam)\b',q):
        intents.append('hoi_chi_so_dinh_duong')
    edit = re.match(r'^(?:bo|bot|them|giam|tang|doi|thay)\b',q)
    if (edit and not re.match(r'^(?:bò|bơ|bột)\b',normalized,re.I)
            and not (re.match(r'^(?:bo|bot)\s+(?:kho|xao|chien|hap|nuong|luoc)\b',q)
                     and re.match(r'^(?:bo|bot)\b',normalized,re.I))):
        intents.append('dieu_chinh_nguyen_lieu')
    dk = dieu_kien(text)
    allergy_mentions = list(_allergy_mentions(q))
    persistent_text = normalized
    for match,kind in reversed(allergy_mentions):
        if kind != 'personal':
            persistent_text = persistent_text[:match.start()] + ' ' + persistent_text[match.end():]
    if persistent_text != normalized:
        persistent_diet = dieu_kien(persistent_text)
        dk['loai_tru'] = persistent_diet['loai_tru']
        dk['chua_ro'] = persistent_diet['chua_ro']
    plant_request = re.search(r'\b(?:goi y|chon|tim|muon|nau|lam) (?:cac )?mon chay\b',q)
    if plant_request and not {'cong_thuc','che_bien','nguyen_lieu'} & set(intents):
        intents.append('goi_y_mon')
    if ((plant_request or ('goi_y_mon' in intents and re.search(r'\bchay\b',q)))
            and not re.search(r'\b(?:khong|thoi) (?:an|dung) chay\b',q)):
        dk['an_chay'] = True
    if re.search(r'\bkhong thich (?:an )?cay\b',q):
        dk['loai_tru'] = sorted(set(dk['loai_tru']) | {'cay'})
    terms = {tuple(chuan_hoa(chuan_hoa_dia_phuong(name)).split()) for name in ingredient_names}
    terms.update(tuple(chuan_hoa(name).split()) for name in (*NGUYEN_LIEU,'bò','bơ','nấm','nước mắm'))
    vocabulary = sorted((term for term in terms if term),key=lambda term:(-len(term),term))
    have, required, unavailable, avoid, uncertain = [], [], [], [], []
    plant_ingredient = re.match(r'^(\w+(?: \w+){0,2} chay) (?:nau|lam) (?:mon )?(?:gi|nao)\b',q)
    if plant_ingredient and dk['an_chay']:
        required.append(plant_ingredient[1])
    inventory = _INVENTORY.search(q)
    if inventory and not re.search(r'\b(?:khong|chua)(?: con)?\s*$', q[:inventory.start()]):
        tail = normalized[inventory.end():]
        # A comma can join an ingredient list or start a new instruction.
        boundary = _INGREDIENT_END.search(q[inventory.end():])
        original_span = tail[:boundary.start()] if boundary else tail
        have, uncertain = _ingredient_mentions(original_span,vocabulary)
    elif not inventory:
        inverted = re.match(r'^([^,;.!?]+?)\s+(?:con|dang co)\s+(?:o |trong )tu(?: lanh)?\b',q)
        if inverted:
            have, uncertain = _ingredient_mentions(normalized[:inverted.end(1)],vocabulary)
    for pattern,target in (
        (r'\b(?:phai dung|bat buoc(?: dung)?|nhat dinh dung)\s+',required),
        (r'\b(?:khong|chua) co(?: san)?\s+',unavailable),
        (r'\b(?:khong (?:muon )?(?:dung|an|them)|tranh|kieng)\s+',avoid),
    ):
        for match in re.finditer(pattern,q):
            if target is required and re.match(r'(?:ca hai|ca ba|tat ca)\b',q[match.end():]):
                target.extend(have)
                continue
            end = _INGREDIENT_END.search(q,match.end())
            span = normalized[match.end():end.start() if end else None]
            names, unclear = _ingredient_mentions(span,vocabulary)
            target.extend(names)
            uncertain.extend(unclear)
            if target is unavailable and re.search(r'\bmon (?:an )?chay\s*$',q[:match.start()]):
                avoid.extend(names)
    if 'goi_y_mon' in intents:
        for match in re.finditer(r'(?:^|[,;]\s*|\bnhung )khong\s+(?!co\b|bi\b|di ung\b)',q):
            end = _INGREDIENT_END.search(q,match.end())
            span = normalized[match.end():end.start() if end else None]
            names, unclear = _ingredient_mentions(span,vocabulary)
            avoid.extend(names)
            uncertain.extend(unclear)
    # Only publish supported exclusion keys to the downstream filter.
    # Unavailable ingredients stay local to this utterance.
    known_avoid = {name for name in NGUYEN_LIEU if chuan_hoa(name) in avoid or name in avoid}
    dk['loai_tru'] = sorted(set(dk['loai_tru']) | known_avoid)
    covered = {chuan_hoa(alias) for name in dk['loai_tru'] for alias in (name,*NGUYEN_LIEU[name])}
    unresolved_avoid = {chuan_hoa(item) for item in avoid if chuan_hoa(item) not in covered}
    if 'goi_y_mon' in intents or 'cong_thuc' in intents:
        dk['chua_ro'] = sorted(set(dk['chua_ro']) | unresolved_avoid)
    if 'goi_y_mon' in intents and not have and required:
        have = list(dict.fromkeys(required))
    choices = have[:] if re.search(r'\b(?:hoac|mot trong hai|mot trong so)\b',q) else []
    buying = bool(re.search(r'\b(?:co the|duoc phep) mua them\b',q))
    strict = bool(re.search(r'\b(?:chi co|chi (?:duoc )?dung nguyen lieu(?: dang)? co)\b',q)) and not buying
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
    scoped_allergies, scoped_unknown, corrections = set(), set(), set()
    for match,kind in allergy_mentions:
        allergy_span = match[1].strip()
        if not allergy_span:
            continue
        allergy_dk = dieu_kien('dị ứng '+allergy_span)
        if kind == 'personal':
            allergies.extend(allergy_dk['loai_tru'])
            unknown_allergies.extend(allergy_dk['chua_ro'])
        elif kind == 'correction':
            corrections.add(re.sub(r'\s+nua$','',allergy_span))
        elif kind != 'negative':
            scoped_allergies.update(allergy_dk['loai_tru'])
            scoped_unknown.update(allergy_dk['chua_ro'])
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
    if _PROGRAMMING.search(q):
        intents = ['ngoai_pham_vi']
    # TextRank and the ML group remain diagnostic signals. They never override
    # explicit ingredient, negation or allergy evidence from the utterance.
    return {'cau_goc': text, 'cau_chuan': normalized, 'intents': list(dict.fromkeys(intents)),
            'tinh_trang_suc_khoe': health,
            'di_ung': sorted(set(allergies)),
            'di_ung_chua_ro': sorted(set(unknown_allergies)),
            'di_ung_theo_luot': sorted(scoped_allergies),
            'di_ung_theo_luot_chua_ro': sorted(scoped_unknown),
            'di_ung_xac_nhan_xoa': sorted(corrections),
            'dieu_kien': dk, 'nguyen_lieu_co': have, 'chi_dung_nguyen_lieu_co': strict,
            'nguyen_lieu_bat_buoc': list(dict.fromkeys(required)),
            'nguyen_lieu_lua_chon': choices,
            'nguyen_lieu_khong_co': list(dict.fromkeys(unavailable)),
            'nguyen_lieu_khong_muon_dung': list(dict.fromkeys(avoid)),
            'cho_phep_mua_them': buying,
            'nguyen_lieu_chua_ro': list(dict.fromkeys(uncertain)),
            'thoi_gian_toi_da': int(time[1])*(60 if time[2] == 'gio' else 1) if time else None,
            'khau_phan': int(portions[1]) if portions else None,
            'calo_yeu_cau': int(calories[1]) if calories else None,
            'khong_chien': bool(re.search(r'\b(khong chien|khong ran|tranh chien)\b', q)),
            'tu_khoa_chinh': tu_khoa_textrank,
            'cum_cu_phap': cum_cu_phap,
            'nhom_ml': nhom_ml['nhom'],
            'diem_nhom_ml': nhom_ml['diem']}
