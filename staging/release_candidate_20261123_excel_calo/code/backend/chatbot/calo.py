"""Calo của phiên bản chuẩn hóa: chọn đúng công thức, không suy từ tên món."""
import json
from backend.chatbot.recipe_views_v5 import _name_spans, _surface_score, normalize, recipe_aliases
import re
from functools import lru_cache
from pathlib import Path

from backend.chatbot.ngon_ngu import chuan_hoa, chuan_hoa_dia_phuong

DATA = Path(__file__).resolve().parents[3] / 'excel_calo.json'


@lru_cache(maxsize=12000)
def key(text):
    return ' '.join(re.findall(r'\w+', chuan_hoa(chuan_hoa_dia_phuong(text))))


@lru_cache(maxsize=4)
def _load(path, stamp):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data['schema_version'] != 1:
        raise ValueError('Unsupported calorie schema')
    return data


def load_data():
    return _load(str(DATA), DATA.stat().st_mtime_ns)


@lru_cache(maxsize=512)
def aliases(question):
    from backend.chatbot.doi_chieu import ten_mon_tu_cau_hoi
    name = key(question)
    name = re.sub(r'^(?:(?:minh|toi|ban|hay|muon|huong dan|chi|day|cach|cong thuc|lam|nau|kho|do|goi|mon)\s+)+', '', name)
    name = re.split(r'\b(?:lam sao|nau sao|nau nhu|lam nhu|lam the|nau the|the nao|nhu the|ra sao|sao cho|cho gion|cho ngon|chi minh|sao ban|la gi|bang noi|kieu mien tay|kieu ben tre|tai nha|nau voi)\b', name)[0]
    name = re.sub(r'\s+(?:voi|nhe|nha|ban|di)$', '', name).strip()
    return {x for x in (name, re.sub(r'\s+mien tay$', '', name), ten_mon_tu_cau_hoi(question)) if len(x.split()) >= 2}


def is_request(question, state):
    q = key(question)
    if re.search(r'\b(?:calo|kcal|calorie|calories|nang luong)\b', q):
        return True
    return bool(state.get('calo_hien_tai') and re.search(r'\b(?:nua|phan tu|(?:mot|hai|ba|bon|\d+(?: \d+)?)(?: khau)? phan|mot to|mot dia|100 ?g|ca me)\b|1\s*/\s*[24]', chuan_hoa(question)))


def _result(text, recipe=None, record=None, suggestions=()):
    from backend.chatbot.sinh_cau_tra_loi import mo_ta_nguon
    source = [mo_ta_nguon(dict(recipe.metadata, diem=0.0))] if recipe else []
    return dict(cau_tra_loi=text, loai='tra_loi' if recipe else 'khong_chac', nguon=source,
        goi_y=list(suggestions), nhan_goi_y='Chọn đúng bản công thức:', doan_truy_hoi=[],
        chu_de=dict(id_goc=recipe.id_goc, cau_hoi=recipe.cau_hoi) if recipe else None,
        giai_thich=dict(calo_chuan_hoa=True, phien_ban_calo=record['version'] if record else None))


def related_options(result, options, label):
    """Cùng một danh sách cho nút bấm và chọn món theo số."""
    result['goi_y'] = [text for recipe, text in options]
    result['nhan_goi_y'] = label
    result['giai_thich']['calo_goi_y'] = [dict(id_goc=recipe.id_goc, cau_hoi=text) for recipe, text in options]
    return result


def nearby_recipes(question, available):
    # Chỉ tìm tên có đủ từ món/cách nấu theo thứ tự; không tự chọn một loài cá.
    fillers = set('mon an bao nhieu calo kcal calorie calories nang luong vay thi la co cho toi minh ban hoi muon biet cua cong thuc mot khau phan'.split())
    words = [word for word in key(question).split() if word not in fillers]
    if not 2 <= len(words) <= 8 or any(word in words for word in ('khong','tranh','di','ung')):
        return []
    pattern = r'(?<!\w)' + r'\b(?:\s+\w+)*\s+'.join(re.escape(word) for word in words) + r'(?!\w)'
    return [(p, r) for p, r in available if any(re.search(pattern, a) for a in recipe_aliases(p))][:5]


def _fuzzy_calorie_choices(question, kho, available):
    from backend.chatbot.fuzzy import de_nghi_ten_mon

    surface = chuan_hoa_dia_phuong(question)
    folded = normalize(surface)
    head = re.match(r'^(?:(?:calo|kcal|calorie|calories|nang luong) (?:cua|trong) (?:mon )?)',folded)
    tail = re.search(r'\s+(?:(?:co |la )?bao nhieu(?: (?:calo|kcal|calorie|calories|nang luong))?|calo|kcal|calorie|calories|nang luong)\s*[?!.]*$',folded)
    if not (head or tail):
        return []
    name = surface[head.end() if head else 0:tail.start() if tail else None].strip()
    by_title = {recipe.cau_hoi:(recipe,record) for recipe,record in available}
    return [by_title[title] for title in de_nghi_ten_mon(name,kho) if title in by_title]


def answer_calories(question, kho, state, previous):
    """None = không thuộc nhánh calo. Chỉ dùng công thức có trong kho đang chọn."""
    if not is_request(question, previous):
        return None
    if re.search(r'\b(?:goi y|mon nao|an gi|nau gi)\b', key(question)):
        return None  # Giữ luồng gợi ý, không chứng nhận món đáp ứng mức kcal yêu cầu.
    from backend.chatbot.knowledge_policy import policy
    from backend.chatbot.cong_thuc import danh_muc
    try:
        data = load_data()
    except (OSError, ValueError, KeyError):
        return _result('Chưa nạp được bảng calo. Mình chưa thể đưa ra số calo cho món này.')
    q = key(question)
    records = {key(r['question']): r for r in data['recipes']}
    available = [(recipe, records[key(recipe.cau_hoi)]) for recipe in danh_muc(kho)
                 if key(recipe.cau_hoi) in records]
    # Câu hỏi giống mẫu Excel cũng phải thuộc kho hiện tại (không rò Test sang Train).
    exact_ids = {x['recipe_id'] for x in data['questions'] if key(x['question']) == q}
    if exact_ids:
        exact_rows = [(recipe,record) for recipe,record in available if record['id'] in exact_ids]
        scores = [(recipe,record,_surface_score(question,recipe.cau_hoi)) for recipe,record in exact_rows]
        best = max((score for _,_,score in scores),default=-1)
        candidates = [(recipe,record) for recipe,record,score in scores if score==best and score>=0]
        conflicting = bool(exact_rows and not candidates)
    else:
        spans = list(_name_spans(question,(recipe for recipe,_ in available)))
        compatible = [(start,end,score,recipe.id_goc) for start,end,score,recipe in spans if score>=0]
        conflicting = bool(spans and not compatible)
        # Keep separate named dishes even when their matches use different accent coverage.
        ids = {rid for start,end,score,rid in compatible if not any(
            left<=start and end<=right and (left<start or end<right or rank>score)
            for left,right,rank,_ in compatible
        )}
        candidates = [(recipe,record) for recipe,record in available if recipe.id_goc in ids]
    if not candidates and not exact_ids and not conflicting:
        contextual = re.search(r'\b(?:mon do|mon nay|mon tren|cai do)\b', q) or re.fullmatch(
            r'(?:(?:vay|con|toi|minh|an) )*(?:nua|1 2|mot phan tu|1 4|hai|ba|bon|mot|\d+(?: \d+)?)(?: khau)? (?:phan|to|dia)(?: (?:thi|sao|co|bao|nhieu|calo|kcal|nang|luong|a|nhe|vay))*', q)
        current = state.get('mon_hien_tai')
        if contextual and current:
            candidates = [(p, r) for p, r in available if p.id_goc == current['id_goc']]
    dk = state.get('dieu_kien', {})
    restricted = (state.get('di_ung') or state.get('di_ung_chua_ro')
                  or any(dk.get(field) for field in ('loai_tru','chua_ro','an_chay')))
    if len(candidates) != 1:
        matches = []
        if not restricted and not conflicting:
            matches = candidates[:5]
            if not matches and not exact_ids:
                matches = _fuzzy_calorie_choices(question,kho,available)
                if not matches:
                    compatible = [(p,r) for p,r in available if _surface_score(question,p.cau_hoi)>=0]
                    matches = nearby_recipes(question,compatible)
        text = ('Mình tìm được các công thức liên quan dưới đây. Calo phụ thuộc loại nguyên liệu và định lượng của từng công thức; bạn chọn đúng món để xem calo cả món và mỗi khẩu phần nhé.' if matches else
                'Mình chưa tìm được đúng công thức cho tên món này. Bạn cho biết tên món hoặc loại nguyên liệu chính để mình tìm calo và các mục liên quan nhé.')
        result = _result(text)
        return related_options(result, [(p, 'Calo: '+p.cau_hoi) for p, _ in matches], 'Chọn món bạn muốn xem calo:')
    recipe, record = candidates[0]
    # Tên/ID giống nhau chưa bảo đảm cùng phiên bản nguyên liệu.
    section = re.search(r'(?ims)^\s*(?:nguyên liệu|chuẩn bị nguyên liệu)[^\n]*\n(.*?)(?=^\s*(?:sơ chế|cách chế biến|cách làm|các bước|chế biến|hoàn thành)\b|\Z)', record['original_answer'])
    original_lines = [key(line) for line in section[1].splitlines() if line.strip().startswith(('-', '•'))] if section else []
    if sorted(key(line) for line in recipe.nguyen_lieu) != sorted(original_lines):
        return _result('Nguyên liệu công thức hiện tại khác phiên bản đã tính calo. Cần tính lại trước khi dùng số trong bảng.')
    control = re.sub(re.escape(recipe.cau_hoi), '', question, flags=re.I)
    command = key(control)
    changed = re.search(r'\b(?:them|giam|thay|khong dung|khong them|tang)\b|\bbot (?:di|luong|duong|dau|muoi)\b|\bdoi (?:sang|thanh|cong thuc)\b', command) or re.search(r'\b(?:bỏ|bớt|đổi)\b', control.lower()) or re.search(r'\bbo (?:nguyen lieu|duong|dau|muoi|bot ngot|nuoc mam)\b', command)
    if exact_ids:
        changed = False  # Các từ nằm trong tiêu đề gốc không phải lệnh sửa công thức.
    if restricted or changed:
        return _result('Bảng calo áp dụng cho công thức chuẩn hóa nguyên bản. Với yêu cầu thay đổi nguyên liệu hoặc điều kiện ăn uống đang giữ, cần xác nhận lại định lượng và tính lại; mình chưa dùng số cũ cho phiên bản điều chỉnh.')
    total, per = record['total'], record['per_serving']
    number = lambda value: f'{value:,.0f}'
    lines = [f"**{recipe.cau_hoi}**", f"Theo bản chuẩn hóa **{record['version']}**, chia thành {record['servings']:g} phần bằng nhau:",
             f'- Cả công thức: khoảng **{number(total)} kcal**.', f'- Mỗi khẩu phần: khoảng **{number(per)} kcal**.']
    raw = chuan_hoa(re.sub(re.escape(recipe.cau_hoi), '', question, flags=re.I))
    portion_match = re.search(r'\b(\d+(?:[.,]\d+)?)\s*(?:khau\s+)?phan\b', raw)
    fraction = None
    if re.search(r'\b(?:nua|mot phan hai)\b|1\s*/\s*2', raw):
        fraction = .5
    elif re.search(r'\bmot phan tu\b|1\s*/\s*4', raw):
        fraction = .25
    elif re.search(r'\bhai (?:khau )?phan\b', raw):
        fraction = 2
    elif re.search(r'\b(?:ba|bon) (?:khau )?phan\b', raw):
        fraction = 3 if re.search(r'\bba (?:khau )?phan\b', raw) else 4
    elif portion_match:
        fraction = float(portion_match[1].replace(',', '.'))
    if re.search(r'\b(?:100\s*g|100\s*gram|mot tram gam)\b', raw):
        lines.append('**Chưa đủ dữ liệu tính kcal/100 g món chín.** Cần cân tổng khối lượng món chín ăn được; kcal/100 g = kcal cả mẻ ÷ khối lượng đó (g) × 100. Không lấy khối lượng nguyên liệu sống thay cho món chín.')
    elif re.search(r'\b(?:tô|đĩa|bát|chén)\b', question.lower()) or re.search(r'\b(?:mot|1|moi|hai|2) (?:to|dia|bat|chen)\b', q):
        lines.append('**Cần xác định lượng trong tô/đĩa/bát/chén.** Chỉ khi đúng bằng một khẩu phần chuẩn hóa và không thêm đồ ăn kèm thì mới dùng số mỗi khẩu phần ở trên. Bạn ăn lượng tương đương mấy khẩu phần?')
    elif fraction is not None:
        whole = bool(re.search(r'(?:\bnua|\bmot phan tu|1\s*/\s*[24])\s+(?:me|noi|cong thuc|ca mon)\b', raw))
        value = total if whole else per
        basis = 'mẻ chuẩn hóa' if whole else 'khẩu phần chuẩn hóa'
        lines.append(f'- Lượng bạn hỏi ({fraction:g} {basis}): khoảng **{number(value*fraction)} kcal**.')
    if re.search(r'\b(?:bo sung|an kem|com|bun|nuoc cham)\b', q) and not exact_ids:
        lines.append('Đồ ăn kèm chỉ được tính nếu đã nằm trong định lượng chuẩn hóa; phần thêm ngoài công thức chưa được cộng.')
    lines += ['**Đây là ước tính theo định lượng chuẩn hóa**, không phải số đo món bạn đã nấu. Nếu nấu khác lượng hoặc thêm đồ ăn kèm cần tính lại.',
              'Cơ sở chia phần: '+record['portion_basis']+'.']
    if record['proxy_count']:
        lines.append(f"Có {record['proxy_count']} nguyên liệu dùng dữ liệu đại diện/mô hình, đóng góp khoảng {record['proxy_share']:.1%} năng lượng; xem giả định trước khi sử dụng.")
    lines.append('Giả định: '+record['notes'])
    urls = list(dict.fromkeys(data['foods'][x['source_key']]['url'] for x in record['ingredients']))
    lines.append('Nguồn thành phần năng lượng: '+'; '.join(urls))
    if re.search(r'\b(?:dam|protein|beo|carbohydrate|carb|natri)\b', q):
        lines.append('Bảng này chỉ có năng lượng; chưa đủ dữ liệu để trả số đạm, béo, carbohydrate hoặc natri.')
    result = _result('\n\n'.join(lines), recipe, record)
    result['giai_thich']['calo'] = dict(total=total, per_serving=per, servings=record['servings'], workbook=data['workbook'], workbook_sha256=data['workbook_sha256'])
    return related_options(result, [(recipe, 'Một khẩu phần của công thức “'+recipe.cau_hoi+'” có bao nhiêu calo?'),
                                    (recipe, 'Nửa khẩu phần của công thức “'+recipe.cau_hoi+'” có bao nhiêu calo?'),
                                    (recipe, recipe.cau_hoi)], 'Bạn muốn xem thêm mục nào?')
