"""Typed source views and exact arithmetic. No new recipes, health claims or LLM."""
import copy
from fractions import Fraction
import hashlib
import re
from backend.chatbot.ngon_ngu import chuan_hoa, chuan_hoa_dia_phuong, vi_pham, du_bang_chung
from backend.chatbot.recipe_time import (
    ACTIONS, LABELS, VALID_PHASES, duration_text, render_times, requested_phase,
    step_durations, summary_durations,
)

PORTION_WORDS = dict(zip('mot hai ba bon nam sau bay tam chin muoi'.split(), range(1, 11)))
PORTION_CHANGE = (
    r'\b(?:cho|khau phan|thanh|con|(?:doi|tang|giam) (?:khau phan )?(?:sang|len|xuong))\s+'
    r'(\d{1,3}|' + '|'.join(PORTION_WORDS) + r')\s*(?:nguoi|phan)\b'
)
RECIPE_REFERENCE = r'\b(?:mon (?:do|nay|ay|kia|hoi nay|vua roi|vua chon)|cong thuc (?:do|nay)|mon moi)\b'
RECIPE_SOURCE = r'\b(?:nguon|chung cu|bai goc|verified)\b'
COOKING_REQUEST = r'\b(?:huong dan|(?:chi|bay)(?: (?:tui|minh|toi|em))? (?:cach|lam|nau|luoc|hap|xao|kho|chien|nuong)|cach (?:nau|lam)|(?:nau|lam|che bien) (?:nhu )?(?:the nao|ra sao)|nau sao)\b'
WHOLE_REQUEST = r'\b(?:huong dan|(?:chi|bay)(?: (?:tui|minh|toi|em))? (?:cach|lam|nau|luoc|hap|xao|kho|chien|nuong)|cach (?:nau|lam)|tu dau|toan bo|tron (?:mon|cong thuc)|day du|(?:nau|lam|che bien) (?:nhu )?(?:the nao|ra sao)|nau sao)\b'
INGREDIENT_REQUEST = r'\b(?:nguyen lieu|gia vi|can mua (?:nhung )?gi|can chuan bi (?:nhung )?gi|can nhung gi)\b'
TIME_REQUEST = r'\b(?:bao lau|thoi gian|may phut|bao nhieu phut)\b'
SERVING_QUESTION = r'\b(?:may nguoi|bao nhieu nguoi|bao nhieu phan|may phan)\b'

from backend.chatbot.phan_hoi import CAU_NGOAI_PHAM_VI

REASONS = {
 'TECHNIQUE_SOURCE_MISSING':'Mình chưa có nguồn được phép dùng giải thích đúng kỹ thuật bạn hỏi.',
 'GENERAL_SOURCE_MISSING':'Mình chưa có nguồn được phép dùng để trả lời câu hỏi này.',
 'STOMACH_MEAL_CLARIFY':'Bạn muốn tìm món mềm, món có vị nhạt hay món tránh một nguyên liệu cụ thể? Cho mình biết điều bạn muốn tránh hoặc nguyên liệu đang có, mình sẽ lọc công thức theo đó.',
 'COMFORT_MEAL_CLARIFY':'Mình chưa tìm được món mềm phù hợp với các điều kiện bạn nêu. Bạn đang có nguyên liệu gì?',
 'DEMO_RECIPE_UNDER_REVIEW':'Món này đang chờ rà soát bước chế biến nên tạm ẩn trong demo. Bạn có thể thử đậu bắp xào tỏi hoặc bắp cải luộc.',
 'NUTRITION_CONTEXT_REQUIRED':'Bạn muốn tính chỉ số nào cho mỗi phần của món nào?',
 'RECIPE_CLARIFICATION':'Mình chưa xác định chắc đúng món và cách chế biến bạn muốn. Bạn nói rõ món canh, xào, kho hay cách nấu khác nhé; mình chưa chuyển sang công thức gần tên.',
 'HEALTH_CURE_UNSUPPORTED':'Mình không có căn cứ để nói món ăn hoặc việc nấu thêm sẽ chữa hay làm hết bệnh. Mình chỉ có thể hướng dẫn nấu ăn theo công thức; không chẩn đoán, kê thuốc hay hướng dẫn điều trị.',
 'AMBIGUOUS_BASE_PORTIONS':'Công thức gốc ghi khẩu phần dạng khoảng hoặc chưa có mốc chính xác, nên mình chưa quy đổi và vẫn giữ công thức gốc. Bạn có thể xác nhận một mốc gốc trong khoảng để tính theo giả định do bạn khai báo; mốc đó không được coi là nguồn đã xác minh.',
 'BASE_PORTION_CONFLICT':'Mốc gốc bạn xác nhận không phù hợp khẩu phần ghi trong công thức. Mình chưa quy đổi; cần làm rõ mốc gốc trước.',
 'INGREDIENT_UNAVAILABLE':'Mình ghi nhận nguyên liệu này đang thiếu và giữ nguyên công thức. Nếu muốn đổi, bạn có thể hỏi cách thay thế hoặc yêu cầu bỏ nguyên liệu.',
 'REMOVE_CONFIRMATION':'Mình chưa đổi công thức. Nếu muốn bỏ nguyên liệu, hãy xác nhận bằng lệnh bỏ nguyên liệu đó trong món hiện tại.',
 'MISSING_DISH':'Mình chưa tìm thấy món này trong danh mục công thức được phép tham khảo. Bạn ghi rõ tên món giúp mình nhé.',
 'MISSING_RECIPE':'Chưa có đủ phần công thức được phép tham khảo cho yêu cầu này.',
 'MISSING_STEP':'Công thức chưa ghi rõ bước được hỏi. Mình không tự tạo thêm bước nấu.',
 'MISSING_NUTRITION':'Chưa đủ dữ liệu thành phần, khối lượng và khẩu phần để tính kcal, protein, lipid, carbohydrate hoặc natri hay xác nhận điều kiện dinh dưỡng bạn yêu cầu.',
 'SOURCE_UNVERIFIED':'Nguồn công thức chưa được xác minh độc lập. Mình có URL đã lưu, chưa có bản nguồn gốc và đoạn chứng cứ để đối chiếu.',
 'FOOD_SAFETY_UNVERIFIED':'Mình chưa có hướng dẫn an toàn thực phẩm đã duyệt cho câu này.',
 'HELD_HEALTH':'Chưa có nội dung sức khỏe được thẩm định đủ cho nhu cầu này. Mình chưa đủ căn cứ để phân tích công thức hoặc gợi ý món phù hợp với tình trạng sức khỏe bạn nêu.',
 'MODIFICATION_UNSUPPORTED':'Chưa đủ căn cứ để bỏ, giảm hoặc thay nguyên liệu và cập nhật toàn bộ bước nấu. Mình chưa tạo công thức đã điều chỉnh; không tự thêm nguyên liệu thay thế.',
 'OUT_OF_SCOPE':CAU_NGOAI_PHAM_VI,
 'HISTORY_UNSEALED':'Lịch sử thuộc phiên chạy cũ hoặc chưa có seal hợp lệ. Nội dung vẫn được lưu; bạn hỏi lại để mình kiểm tra quyền sử dụng nguồn hiện tại.',
 'VALIDATION_FAILED':'Kết quả chưa qua kiểm tra nguồn hoặc phép tính nên mình chưa hiển thị nội dung đó.',
 'ALLERGY_CLARIFICATION':'Bạn cho mình biết cụ thể nguyên liệu hoặc thành phần gây dị ứng để mình kiểm tra công thức.',
 'ALLERGY_CONFLICT':'Công thức có ghi thành phần liên quan đến dị ứng bạn đã khai báo. Mình không đề xuất công thức này.',
 'PANTRY_MISMATCH':'Mình chưa tìm được công thức đủ điều kiện nguyên liệu. Bạn có thể cho biết nguyên liệu nào bắt buộc hoặc có thể mua thêm gì.',
 'MISSING_CONDITIONAL_RECIPE':'Chưa tìm được công thức có đủ dữ liệu để đáp ứng các điều kiện đang giữ. Mình không tự đổi món hoặc nguyên liệu.'}
NOTICE='Theo công thức lưu trong kho. Nguồn chưa được xác minh độc lập.'

def normalize(s):
    value=chuan_hoa(chuan_hoa_dia_phuong(s))
    return re.sub(r'\bsuon sao chua ngot\b', 'suon xao chua ngot', value)
def hash_text(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()
def reference(row):
    urls=re.findall(r'https?://[^\s)]+',row['source'])
    return dict(id_goc=row['id'],cau_hoi=row['question'],nhom=row['group'],ten_muc='',diem=0.0,nguon=urls[0] if urls else row['source'])

def document(row):
    """Spans refer to the authorized answer, never to an assumed external page."""
    text=row['answer_text']
    headers=list(re.finditer(r'(?im)^(Nguyên liệu[^\n]*|Sơ chế[^\n]*|Cách chế biến[^\n]*|Hoàn thành món ăn[^\n]*)$',text))
    sections={}
    keys={'nguyen lieu':'ingredients','so che':'prep','cach che bien':'steps','hoan thanh':'finish'}
    for i,h in enumerate(headers):
        key=next((value for prefix,value in keys.items() if normalize(h[0]).startswith(prefix)),None)
        if key:sections[key]=dict(start=h.start(),end=headers[i+1].start() if i+1<len(headers) else len(text))
    s=sections.get('ingredients');ingredients=[];base=None;bounds=None
    if s:
        block=text[s['start']:s['end']]
        count=re.search(r'cho\s+(\d+)\s*(?:người|phần)',block.splitlines()[0],re.I)
        interval=re.search(r'(\d+)\s*(?:[-–]|đến)\s*(\d+)\s*(?:người|phần)',block.splitlines()[0])
        if interval:bounds=[int(interval[1]),int(interval[2])]
        elif count:base=int(count[1])
        for m in re.finditer(r'(?m)^\s*[-•][^\n]+',block):
            raw=m[0].strip();start=s['start']+m.start()+len(m[0])-len(m[0].lstrip())
            ingredients.append(dict(text=raw,start=start,end=start+len(raw)))
    return dict(recipe_id=row['id'],version=row['answer_sha256'],base_portions=base,base_range=bounds,sections=sections,ingredients=ingredients)

def confirm_base(row,statement):
    q=normalize(statement);doc=document(row)
    match=re.search(r'\b(?:xac nhan|chot|lay|moc goc|khau phan goc)\s+(?:(?:moc|khau phan|goc|la|cho)\s+)*(\d+)\s*(?:nguoi|phan)\b',q)
    if not match:return None
    base=int(match[1]);bounds=doc['base_range']
    if type(base) is not int or not 1<=base<=100 or (bounds and not bounds[0]<=base<=bounds[1]) or (doc['base_portions'] and base!=doc['base_portions']):raise ValueError('Base conflicts with source')
    if not bounds and not doc['base_portions']:raise ValueError('No source serving basis')
    return dict(recipe_id=row['id'],recipe_version=row['answer_sha256'],confirmed_base=base,source_range=bounds,basis='USER_DECLARED_SCENARIO',statement=statement)

def ingredient_components(doc):
    result=[]
    for entry in doc['ingredients']:
        raw=entry['text'];prefix=re.match(r'^[-•]\s*(?:Phần vỏ|Phần nhân|Ăn kèm|Gia vị)\s*:\s*',raw,re.I)
        start=prefix.end() if prefix else len(raw)-len(raw.lstrip('-• '))
        for part in re.finditer(r'[^,;]+(?:,(?=\d)[^,;]+)*',raw[start:]):
            content=part[0].strip();offset=start+part.start()+len(part[0])-len(part[0].lstrip())
            if content:result.append(dict(text=content,start=entry['start']+offset,end=entry['start']+offset+len(content),original_line=raw,parent_start=entry['start'],parent_end=entry['end']))
    return result

def parse_quantity_component(text):
    match=re.fullmatch(r'(.*?)\s+(\d+(?:[.,]\d+|/\d+)?)\s*(kg|mg|g|ml|lít|l|quả|trái|củ|tép|nhánh|con|miếng)',text.lstrip('-• ').strip(),re.I)
    if not match or re.search(r'\d|\b(?:khoảng|đến|từ)\b',match[1],re.I):return None
    return match

def portion_transform(row,target,confirmation=None):
    doc=document(row);base=doc['base_portions']
    if confirmation is not None:
        if confirmation!=confirm_base(row,confirmation.get('statement','')):raise ValueError('Invalid base provenance')
        base=confirmation['confirmed_base']
    if type(target) is not int or not 1<=target<=100 or not base:raise ValueError('Ambiguous or unsupported serving count')
    factor=Fraction(target,base);items=[]
    # Count units remain counts: never infer grams; household measures remain unresolved.
    for entry in ingredient_components(doc):
        raw=entry['text'];m=parse_quantity_component(raw)
        item={**entry,'source_id':row['id'],'source_version':row['answer_sha256'],'source':row['source']}
        if m:
            quantity=Fraction(m[2].replace(',','.'))
            item.update(status='SCALED',name=m[1],quantity=str(quantity),unit=m[3],factor=str(factor),result=str(quantity*factor))
        else:item.update(status='UNRESOLVED',reason='Không có một định lượng/đơn vị rõ ràng; giữ dòng gốc để đối chiếu, chưa áp dụng cho khẩu phần mới.')
        items.append(item)
    return dict(schema=2,recipe_id=row['id'],recipe_version=row['answer_sha256'],source=row['source'],base_portions=base,source_base_portions=doc['base_portions'],source_base_range=doc['base_range'],base_confirmation=confirmation,target_portions=target,factor=str(factor),items=items)

def validate_transform(row,value):
    if not isinstance(value,dict) or value!=portion_transform(row,value.get('target_portions'),value.get('base_confirmation')):raise ValueError('Transformation provenance/arithmetic mismatch')
    return True

def adjustment_request(row,question):
    """Inventory and step occurrences, including unresolved compound sauces; no approval."""
    doc=document(row);q=normalize(question)
    target=re.split(r'\b(?:bo|khong dung|khong them|loai bo|giam|thay)\s+',q,maxsplit=1)[-1]
    target=re.split(r'\b(?:khoi|trong|roi|va|thi|bang|viet|cho|mot nua)\b',target)[0].strip()
    target=re.sub(r'^(?:(?:mot nua|bot|het|tat ca|toan bo)\s+)+','',target)
    aliases={'fish sauce':'nuoc mam','bot nem':'hat nem'}
    target=aliases.get(target,target)
    matches=[i for i in doc['ingredients'] if target and target in normalize(i['text'])]
    occurrences=[]
    for m in re.finditer(r'(?m)^.*$',row['answer_text']):
        if target and target in normalize(m[0]):occurrences.append(dict(start=m.start(),end=m.end(),text=m[0]))
    compounds=[i for i in doc['ingredients'] if re.search(r'\b(sot|hat nem|bot nem|gia vi|hon hop)\b',normalize(i['text']))]
    return dict(recipe_id=row['id'],recipe_version=row['answer_sha256'],requested_target=target,ingredient_matches=matches,source_occurrences=occurrences,unresolved_compound_ingredients=compounds,status='UNSUPPORTED_NO_VERIFIED_OMISSION_RULE')

def view(row,mode='full',target=None,selector=None,confirmation=None):
    doc=document(row)
    if not doc['ingredients']:raise ValueError('Missing recipe')
    if target is not None and (type(target) is not int or not 1<=target<=100):raise ValueError('Invalid target portions')
    if mode=='time':
        if selector is not None and (not isinstance(selector,dict) or set(selector)!={'phase'} or selector['phase'] not in VALID_PHASES):
            raise ValueError('Unexpected time selector')
    elif selector is not None and mode!='step':raise ValueError('Unexpected selector')
    if confirmation is not None and confirmation!=confirm_base(row,confirmation.get('statement','')):raise ValueError('Invalid confirmation')
    result=dict(schema=2,recipe_id=row['id'],recipe_version=row['answer_sha256'],mode=mode,target_portions=target,selector=selector,base_confirmation=confirmation)
    if mode in ('portion','applied_full'):result['transform']=portion_transform(row,doc['base_portions'] if target is None else target,confirmation)
    return result

def render_view(row,value):
    if value!=view(row,value.get('mode'),value.get('target_portions'),value.get('selector'),value.get('base_confirmation')):raise ValueError('View/provenance mismatch')
    doc=document(row);mode=value['mode'];text=row['answer_text']
    if mode=='applied_full':
        portion=view(row,'portion',value['target_portions'],confirmation=value['base_confirmation'])
        source_steps=[text[span['start']:span['end']].strip()
                      for key in ('prep','steps','finish') if (span := doc['sections'].get(key))]
        return render_view(row,portion) + '\n\n**Các bước theo nguồn gốc, chưa quy đổi:**\n\n' + (
            '\n\n'.join(source_steps) or 'Nguồn chưa ghi rõ các bước.')
    if mode=='portion':
        t=value['transform'];validate_transform(row,t)
        lines=[NOTICE,f"**Định lượng tính theo dữ liệu nội bộ cho {t['target_portions']} người** (gốc {t['base_portions']} người; hệ số {t['factor']})."]
        if t['base_confirmation'] and t['source_base_range']:lines.insert(1,f"Mốc {t['base_portions']} người do bạn xác nhận để tính theo giả định. Nguồn chỉ ghi {t['source_base_range']}; chưa được xác minh thành mốc chính xác.")
        for item in t['items']:
            if item['status']=='SCALED':lines.append(f"- {item['name']}: {item['quantity']} × {t['factor']} = {item['result']} {item['unit']}")
        unknown=[i['text'] for i in t['items'] if i['status']=='UNRESOLVED']
        if unknown:lines+=['**Chưa quy đổi — dòng gốc để đối chiếu, không phải định lượng cho khẩu phần mới:**',*unknown]
        lines+=['Chỉ quy đổi cùng đơn vị, không suy ra khối lượng từ trái/con hoặc muỗng. Chưa tạo lại toàn bộ bước nấu cho khẩu phần mới; không tự nhân thời gian nấu.']
        return '\n\n'.join(lines)
    if mode=='full':
        missing = []
        if 'steps' not in doc['sections']:
            missing.append('các bước chế biến')
        if not (doc['base_portions'] or doc['base_range']):
            missing.append('số phần gốc')
        note = '\n\nNguồn chưa ghi rõ ' + ' và '.join(missing) + '.' if missing else ''
        return NOTICE+'\n\n'+text+note
    if mode=='servings':
        base = doc['base_portions']
        bounds = doc['base_range']
        if base is None and not bounds:
            raise ValueError('No recorded servings')
        count = str(base) if base else '–'.join(map(str,bounds))
        return NOTICE+f'\n\nCông thức gốc ghi **{count} người**.'
    if mode in ('ingredients','prep','steps'):
        span=doc['sections'].get(mode)
        if not span:raise ValueError('Missing requested section')
        part=text[span['start']:span['end']].strip()
    elif mode=='time':
        phase=(value['selector'] or {}).get('phase','all')
        return NOTICE+'\n\n'+render_times(text,doc['sections'],phase)
    elif mode=='step':
        selection=value['selector']
        if not isinstance(selection,dict) or set(selection)!={'start','end'}:raise ValueError('Invalid step span')
        start,end=selection['start'],selection['end']
        if type(start) is not int or type(end) is not int or not 0<=start<end<=len(text):raise ValueError('Invalid offsets')
        # Only an existing complete bullet or named cooking subsection is selectable.
        if selection not in step_spans(row):raise ValueError('Not a source step')
        part=text[start:end].strip()
    else:raise ValueError('Unsupported view mode')
    source_portions=str(doc['base_portions']) if doc['base_portions'] else ('–'.join(map(str,doc['base_range'])) if doc['base_range'] else 'chưa rõ')
    serving=f"\n\nPhần trích nguyên văn công thức gốc cho {source_portions} người; khẩu phần đang giữ là {value['target_portions']} người. Chưa tự viết lại định lượng trong bước nấu." if value['target_portions'] and value['target_portions']!=doc['base_portions'] else ''
    return NOTICE+'\n\n'+part+serving

def step_spans(row):
    text=row['answer_text'];doc=document(row);spans=[]
    for key in ('prep','steps'):
        section=doc['sections'].get(key)
        if not section:continue
        block=text[section['start']:section['end']]
        for m in re.finditer(r'(?m)^[-•][^\n]+',block):spans.append(dict(start=section['start']+m.start(),end=section['start']+m.end()))
        headings=list(re.finditer(r'(?m)^(?![-•\s])[^\n]+$',block))
        for i,h in enumerate(headings[1:],1):spans.append(dict(start=section['start']+h.start(),end=section['start']+(headings[i+1].start() if i+1<len(headings) else len(block))))
    return spans

def recipe_aliases(recipe):
    from backend.chatbot.doi_chieu import ten_mon_tu_cau_hoi
    alias=ten_mon_tu_cau_hoi(recipe.cau_hoi)
    alias=re.sub(r'\s+(?:chi|day|huong dan) (?:minh|toi|tui)(?:\s+.*)?$','',alias)
    alias=re.sub(r'\s+cho\s+(?:gion|ngon|thom|ngot|mem|dam|beo|khong|vua)\b.*$','',alias)
    alias=re.sub(r'\s+(?:sao|vay|nghen|ne)$','',alias)
    alias=re.sub(r'^do\s+','',alias)
    aliases={alias,re.sub(r'\s+(?:kieu\s+)?mien tay$','',alias)}
    mixed_salad = re.fullmatch(r'(?:tron\s+)?(goi .+?)(?:\s+gion(?: ngon)?)?', alias)
    if mixed_salad:
        aliases.add(mixed_salad[1])

    stir_fry = re.fullmatch(r'xao (.+?) voi (.+)', alias)
    if stir_fry:
        aliases.add(f'{stir_fry[1]} xao {stir_fry[2]}')
    title = normalize(recipe.cau_hoi)
    boiled = re.match(r'^luoc (.+?) (?:sao|the nao)\b', title)
    if boiled:
        ingredient = boiled[1]
        aliases.update((f'luoc {ingredient}', f'{ingredient} luoc'))
    for name in tuple(aliases):
        if name.startswith('canh '):
            words=name.split()[1:]
            # Derive "gà nấu lá giang" from an actual "canh gà lá giang" title.
            # Never derive this alias from a stir-fry/roast recipe.
            for cut in range(1,min(4,len(words))):aliases.add(' '.join(words[:cut]+['nau']+words[cut:]))
        if name.startswith('canh chua '):aliases.add(name[len('canh chua '):]+' nau canh chua')
    return aliases

def _surface_score(surface, title):
    from backend.chatbot.fuzzy import _spellings

    given = _spellings(surface)
    if not given:
        return 0
    expected = _spellings(title)
    score = 0
    for key, forms in given.items():
        explicit = forms-{key}
        if explicit and key in expected:
            if not (explicit & expected[key]):
                return -1
            score += 1
    return score


def _name_spans(question, recipes):
    q = normalize(question)
    surface = chuan_hoa_dia_phuong(question).lower()
    style_marker = re.search(r'\bkieu\b',q)
    for recipe in recipes:
        for alias in recipe_aliases(recipe):
            if len(alias.split()) < 2:
                continue
            pattern = re.escape(alias)
            if style_marker:
                pattern = pattern.replace(r'\ ',r'\s+(?:(?:theo )?kieu\s+)?')
            for match in re.finditer(r'(?<!\w)'+pattern+r'(?!\w)',q):
                score = _surface_score(surface[match.start():match.end()],recipe.cau_hoi)
                yield match.start(),match.end(),score,recipe


def find_recipe(question,recipes):
    surface = chuan_hoa_dia_phuong(question).casefold()
    exact = [recipe for recipe in recipes if chuan_hoa_dia_phuong(recipe.cau_hoi).casefold()==surface]
    if len(exact)==1:
        return exact[0]
    folded = normalize(question)
    exact = [recipe for recipe in recipes if normalize(recipe.cau_hoi)==folded
             and _surface_score(surface,recipe.cau_hoi)>=0]
    if len(exact)==1:
        return exact[0]
    matches = [(len(folded[start:end].split()),score,recipe) for start,end,score,recipe in _name_spans(question,recipes) if score>=0]
    if not matches:
        return None
    best = max((width,score) for width,score,_ in matches)
    items = {recipe.id_goc:recipe for width,score,recipe in matches if (width,score)==best}
    return next(iter(items.values())) if len(items)==1 else None


def named_recipe_ids(question, recipes):
    # Keep the longest compatible name at each location.
    spans = [(start,end,recipe.id_goc) for start,end,score,recipe in _name_spans(question,recipes) if score>=0]
    return {rid for start, end, rid in spans
            if not any(a <= start and end <= b and (a < start or end < b) for a, b, _ in spans)}


def limitation(code,topic=None):
    return dict(loai='ngoai_pham_vi' if code=='OUT_OF_SCOPE' else 'khong_chac',reason_code=code,cau_tra_loi=REASONS[code],nguon=[],goi_y=[],doan_truy_hoi=[],chu_de=topic,giai_thich={})

# Review applies to these exact V3 text/source pairs, not to an ID in general.
# Keep the rows held in normal retrieval. A changed text or link needs review.
MEDICAL_DISPLAY_DIGESTS = {
    728: '27ae1dd44f5ceef19db30f257a871a18f5544e0d6d448ff5ef944abd027ef50f',
    755: '6e1401c4755b16c973d9255fc64245a5afb31a61e058f1eb434cbad45ca3fecb',
    824: '2ed1b5020e2afc135443d4b0f79f031be5be3b9dc26810e1e98f41c7f0416f37',
    836: '2a7bd983f7d2aa4f61162c13f99aa087b1822331a62b0093e391adfbbfea7dad',
}


def reviewed_medical_row(row):
    return (row and row.get('decision') == 'HOLD_V3_MEDICAL_LIMITED'
            and row.get('allowed_for_answer') is False
            and hash_text(row['answer_text'] + '\0' + row['source']) == MEDICAL_DISPLAY_DIGESTS.get(row['id']))


def direct_reviewed_result(row, reason):
    return dict(loai='tra_loi', reason_code=reason, cau_tra_loi=row['answer_text'],
                nguon=[reference(row)], goi_y=[], doan_truy_hoi=[], chu_de=None,
                giai_thich={'nhom_nguon': row['group_folder']})


def low_spice_preference(question, state, previous):
    """A taste preference is not an unresolved ingredient or allergy."""
    conditions = state['dieu_kien']
    taste_flags = set(conditions.get('chua_ro', ())) | set(conditions.get('loai_tru', ()))
    return (taste_flags == {'cay'}
            and not (conditions.get('an_chay')
                     or conditions.get('nhu_cau') or conditions.get('can_dinh_luong')
                     or state.get('di_ung') or state.get('di_ung_chua_ro')
                     or (previous.get('dieu_kien') or {}).get('chua_ro'))
            and bool(re.search(r'\bkhong an cay\b', question))
            and not re.search(r'\b(?:di ung|kieng|benh|tre so sinh)\b', question))

def technique_evidence(question, ledger, excluded, conditions):
    """Find a source sentence naming the same operation and explaining its purpose."""
    q = normalize(question)
    if not re.search(r'\b(?:tai sao|vi sao|ly do|de lam gi|co tac dung gi|co ich gi)\b', q):
        return None
    # Technique vocabulary, including regional aliases, rather than FAQ text.
    actions = (r'(?:trung|chan|luoc so) xuong', r'(?:thang|lam) nuoc hang')
    action = next((pattern for pattern in actions if re.search(r'\b' + pattern + r'\b', q)), None)
    if not action or conditions.get('chua_ro'):
        return None
    for row in ledger.values():
        if (row['id'] in excluded or not row['allowed_for_answer'] or row['scope'] != 'IN_SCOPE'
                or row['split'] != 'Train'
                or row['group_folder'] not in ('07_dieu_chinh_cong_thuc', '10_bao_quan_che_bien')):
            continue
        for sentence in re.split(r'(?<=[.!?])\s+|\n+|&#10;', row['answer_text']):
            sentence = sentence.strip()
            text = normalize(sentence)
            match = re.search(r'\b' + action + r'\b', text)
            if not match or vi_pham(sentence, conditions):
                continue
            if re.search(r'\b(?:muon|giup|de|vi)\b', text):
                return row, sentence
    return None


_TECHNIQUE_GOAL = re.compile(
    r'\b(?:sao cho|de|cho|cach|lam sao|the nao|ma)\s+(?:[a-z0-9]+\s+){0,2}?'
    r'(?:bot|do|giam|het|khong (?:bi|con)?)\s*(?:(?:mui|vi|do)\s+)?'
    r'(?P<effect>nhot|dai|dang|tanh)\b'
)
_TECHNIQUE_EFFECTS = {'nhot':'nhớt','dai':'dai','dang':'đắng','tanh':'tanh'}
_TECHNIQUE_STOP = set('tui minh ban cho co voi cung va vao de bang theo kieu sao lam cach xu ly '
                      'nhu the nao giup nghen nhe nha nau'.split())
_TECHNIQUE_ACTION = r'\b(?:rua|ngam|luoc|chan|trung|xa|xao|nau|chien|khua|tuoc|vot|uop|chao|hap|nuong|kho|cat|cham|cha|bop|lam sach)\b'


def _recipe_technique(payload, recipes, recipe, ledger, excluded):
    from backend.chatbot.doi_chieu import ten_mon_tu_cau_hoi
    from backend.chatbot.recipe_edit_v1 import active_for, operation
    from backend.chatbot.truy_hoi import truy_hoi

    question = payload['question']
    state = payload['state']
    q = normalize(question)
    goal = _TECHNIQUE_GOAL.search(q)
    if not goal or operation(q[:goal.start()]):
        return None
    effect = goal['effect']
    original_effect = chuan_hoa_dia_phuong(question).casefold()[goal.start('effect'):goal.end('effect')]
    if original_effect not in (effect,_TECHNIQUE_EFFECTS[effect]):
        return None
    # A separate mutation in the same utterance belongs to the editor.
    remainder = q[goal.end():]
    if any(operation(part.strip()) for part in re.split(r'[,;]|\b(?:va|roi)\b',remainder) if part.strip()):
        return None
    if re.search(RECIPE_REFERENCE,q):
        if recipe is None:
            prior = state.get('mon_hien_tai') or {}
            recipe = next((r for r in recipes if r.id_goc==prior.get('id_goc')),None)
    else:
        lead = re.sub(r'\btu dau\b',' ',q[:goal.start()])
        lead = re.sub(r'\bdon\b','nhoi',lead)
        identity = set(re.findall(r'\w+',ten_mon_tu_cau_hoi(lead)))-_TECHNIQUE_STOP

        def matches_identity(candidate):
            return (_surface_score(question,candidate.cau_hoi)>=0
                    and any(identity <= set(alias.split()) for alias in recipe_aliases(candidate)))

        if recipe is not None and identity and not matches_identity(recipe):
            recipe = None
        if recipe is None and len(identity)>=2:
            compatible = [r for r in recipes if matches_identity(r)]
            if len(compatible)==1:
                options = truy_hoi(question,k=5,kho=payload['kho'],gop_theo_id_goc=True)['doan']
                recipe = next((r for r in compatible if any(d['id_goc']==r.id_goc for d in options)),None)

    if recipe is None:
        return limitation('RECIPE_CLARIFICATION')
    row = ledger.get(recipe.id_goc)
    if not row or not row['allowed_for_answer'] or row['scope']!='IN_SCOPE' or row['id'] in excluded:
        return limitation('TECHNIQUE_SOURCE_MISSING')
    rejection,_,_ = _check_recipe(row,state)
    if rejection:
        return limitation(rejection)
    if active_for(row,state) or (state.get('pending_ingredient_change') or {}).get('recipe_id')==row['id']:
        return limitation('TECHNIQUE_SOURCE_MISSING')
    sentences = [part.strip() for part in re.split(r'(?<=[.!?])\s+|\n+|&#10;',row['answer_text'])]
    evidence = next((part for part in sorted(sentences,key=lambda part:not part.startswith('-'))
                     if re.search(r'\b'+_TECHNIQUE_EFFECTS[effect]+r'\b',chuan_hoa_dia_phuong(part),re.I)
                     and re.search(_TECHNIQUE_ACTION,normalize(part))),None)
    if (evidence is None and effect=='dai'
            and re.search(r'\bkhong (?:bi )?dai\b',normalize(row['question']))):
        # The source may record the cooking step without making a causal claim.
        doc = document(row)
        span = doc['sections'].get('steps')
        if span:
            block = row['answer_text'][span['start']:span['end']]
            evidence = next((part.strip() for part in block.splitlines() if part.lstrip().startswith('-')
                             and re.search(r'\b(?:xao|nau|ham|luoc|hap)\b.*\b(?:mem|chin deu)\b',normalize(part))),None)
    if not evidence:
        return limitation('TECHNIQUE_SOURCE_MISSING')
    return dict(loai='tra_loi',reason_code='TECHNIQUE_SOURCE',cau_tra_loi=evidence,
                nguon=[reference(row)],goi_y=[],doan_truy_hoi=[],
                chu_de={'id_goc':row['id'],'cau_hoi':row['question']},
                giai_thich={'nhom_nguon':row['group_folder'],'ky_thuat_cong_thuc':True})


RECIPE_READ = r'\b(?:(?:xem|coi)(?: lai)? (?:cong thuc|mon (?:nay|do|vua roi)|(?:cac )?buoc)|cong thuc (?:hien tai|dang dung|sau khi chinh)|cac buoc (?:nau|che bien))\b'
BASE_READ = r'\b(?:xem|coi)(?: lai)? (?:ban goc|cong thuc goc)\b'


def recipe_read_view(row, state, question):
    from backend.chatbot.recipe_edit_v1 import base_edit, replay
    edit = base_edit(row,state)
    events = edit['events']
    plan = replay(row,events) if events else None
    portion = state.get('portion_state_v5') or {}
    target = (portion.get('target_applied') if portion.get('recipe_id') == row['id']
              and portion.get('recipe_version') == row['answer_sha256'] else None)
    doc = document(row)
    if plan is not None:
        target = plan['portions']
    state['khau_phan'] = target if target is not None else doc['base_portions']
    if re.search(BASE_READ,question):
        return view(row)
    steps = bool(re.search(r'\b(?:cac buoc|buoc che bien|buoc nau)\b',question))
    ingredients = bool(re.search(INGREDIENT_REQUEST,question))
    aspect = ('servings' if re.search(SERVING_QUESTION,question) else
              'ingredients' if ingredients and not (steps or re.search(WHOLE_REQUEST,question)) else
              'steps' if steps and not ingredients else None)
    if plan and plan['changed']:
        return dict(mode='recipe_edit',recipe_id=row['id'],recipe_version=row['answer_sha256'],
                    events=events,aspect=aspect)
    if target is not None and target != doc['base_portions']:
        mode = 'portion' if aspect in ('ingredients','servings') else 'applied_full'
        return view(row,mode,target,confirmation=portion.get('base_confirmation'))
    return view(row,aspect or 'full')


def route(payload,manifest,ledger):
    """Called inside the existing LCEL answer node, only for opt-in policy v4."""
    from backend.chatbot.cong_thuc import danh_muc
    from backend.chatbot.ngon_ngu import khoa_cau_hoi
    from backend.chatbot.health_context_v5 import analyze,food_text
    q=normalize(payload['question']);state=payload['state'];kho=payload['kho']
    recipes=danh_muc(kho);recipe=find_recipe(payload['question'],recipes)
    prior=state.get('mon_hien_tai')
    topic=dict(id_goc=recipe.id_goc,cau_hoi=recipe.cau_hoi) if recipe else prior
    health=analyze(payload['question'],state.get('health_context_v5'))
    state['health_context_v5']=health['context']
    health_active = bool(state.get('tinh_trang_suc_khoe') or health['context']['active'] or health['health_need'])
    medical = re.search(r'\b(?:thuoc|dieu tri|chan doan|phac do|lieu dung|kieng gi|khong nen an)\b', q)
    if re.search(r'\b(ngan hang|co phieu|la ma|lap trinh|ma python|bong da|chinh tri)\b',q):
        return limitation('OUT_OF_SCOPE')
    from backend.chatbot.source_qa_gate import question_key
    exact_key = question_key(payload['question'])
    question_folded = khoa_cau_hoi(payload['question'])
    exact = [r for r in ledger.values()
             if question_key(r['question']) == exact_key
             or (exact_key.isascii() and khoa_cau_hoi(r['question']) == question_folded)]
    held = [r for r in ledger.values() if not r['allowed_for_answer']
            and question_folded == khoa_cau_hoi(r['question'])]
    excluded = set(manifest.get('demo_excluded_recipe_ids', ()))
    if len(exact) == 1 and exact[0]['id'] not in excluded:
        row = exact[0]
        if reviewed_medical_row(row):
            return direct_reviewed_result(row, 'MEDICAL_LIMITED_V3')
        if (row.get('decision') == 'ALLOW_V3_REVIEWED_EXACT' and row['allowed_for_answer']
                and row['scope'] == 'IN_SCOPE' and row['group_folder'].startswith('07_')
                and not (health_active or medical or health['cure_question'])
                and low_spice_preference(q, state, payload['previous'])):
            return direct_reviewed_result(row, 'CULINARY_PREFERENCE_SOURCE')
    if not health['cooking_only'] and re.search(
            r'\b(?:dau bung|(?:bi|dau|benh|viem|loet)(?: (?:dau|viem|loet))? (?:bao tu|da day))\b',
            re.sub(r'\b(?:khong|chua|het|khoi)(?: con)?(?: bi)? (?:dau bung|(?:dau |benh |viem |loet )?(?:bao tu|da day))\b',' ',q)):
        return limitation('HELD_HEALTH',topic)
    if not (health['health_need'] or health['cure_question'] or medical):
        evidence = technique_evidence(payload['question'], ledger, excluded, state['dieu_kien'])
        if evidence:
            row, sentence = evidence
            return dict(loai='tra_loi', reason_code='TECHNIQUE_SOURCE', cau_tra_loi=sentence,
                        nguon=[reference(row)], goi_y=[], doan_truy_hoi=[], chu_de=None,
                        giai_thich={'nhom_nguon': row['group_folder']})
        if held and all(r['group_folder'].startswith(('04_', '07_', '10_')) for r in held):
            return limitation('TECHNIQUE_SOURCE_MISSING')
        if held and all(r['group_folder'].startswith('08_') for r in held):
            return limitation('GENERAL_SOURCE_MISSING')
    if held:
        return limitation('HELD_HEALTH',topic)
    if re.search(r'\btao bon{1,2}\b', q) and re.search(r'\b(?:an|uong|kieng)\b', q):
        # Do not repurpose the reviewed FAQ for a symptom paraphrase, or let a
        # one-letter typo turn it into unconstrained recipe recommendations.
        return limitation('HELD_HEALTH')
    meal_words = re.search(r'\b(?:an gi|nau (?:mon )?(?:gi|chi)|mon (?:gi|chi|nao)|goi y|muon an|nen an)\b',q)
    stomach_options = bool(meal_words and not recipe and not medical and not health['cure_question']
                           and re.search(r'\b(?:bi|dau|benh|viem|loet)(?: (?:dau|viem|loet))? da day\b', q))
    low_effort = bool(meal_words and not recipe and not medical and not health['cure_question']
                      and (re.search(r'\b(?:nau nhanh|lam nhanh|cho nhanh)\b',q) or TIRED_REQUEST.search(q))
                      and not health['health_need'])
    feels_unwell = re.search(r'\b(?:khong|chang|hong|hem) (?:duoc )?khoe\b|\b(?:cam thay|thay|nguoi) kho chiu\b', q)
    comfort = bool((health_active or feels_unwell) and not low_effort and not recipe and not medical and meal_words)
    cooking = bool(re.search(COOKING_REQUEST,q)
                   or ((recipe or prior) and any(re.search(p,q) for p in
                       (INGREDIENT_REQUEST,TIME_REQUEST,SERVING_QUESTION,RECIPE_SOURCE,PORTION_CHANGE)))
                   or (prior and re.search(r'^(?:bo|bot|giam|thay|viet lai|hoan tac|nau cho)\b',q)))
    if health['cure_question'] and (not comfort or (feels_unwell and not health_active)):return limitation('HEALTH_CURE_UNSUPPORTED',topic)
    if health_active and not health['cooking_only'] and re.search(
            r'\b(?:phan tich|canh bao|dieu chinh|phu hop|anh huong)\b',q):
        return limitation('HELD_HEALTH',topic)
    if health_active and not (health['cooking_only'] or comfort or low_effort or stomach_options or
                              (not medical and (cooking or payload.get('choice') or (recipe and not health['health_need'])))):
        return limitation('HELD_HEALTH',topic)
    if re.search(r'^(?:chao ban|xin chao)\b',q):return dict(loai='chao_hoi',cau_tra_loi='Mình là trợ lý nấu ăn. Bạn muốn xem công thức món nào?',nguon=[],goi_y=[],doan_truy_hoi=[],chu_de=None,giai_thich={})
    if re.search(r'^(?:cam on|cam on ban|tam biet)\b',q):return None
    from backend.chatbot.demo_food_safety import matches, response
    if matches(payload['question']):
        return response()
    if re.search(r'\bdau\b.{0,35}\bchien\b.{0,24}\blai\b|\bdau\b.{0,30}\btai su dung\b',q):
        return limitation('FOOD_SAFETY_UNVERIFIED')
    named = named_recipe_ids(payload['question'], recipes)
    if recipe and q==normalize(recipe.cau_hoi):named={recipe.id_goc}
    if excluded.intersection(named) or (topic and topic.get('id_goc') in excluded):
        return limitation('DEMO_RECIPE_UNDER_REVIEW')
    recipes = tuple(r for r in recipes if r.id_goc not in excluded)
    if payload['parsed'].get('nguyen_lieu_co'):
        state.pop('nguyen_lieu_bat_buoc', None)
    _ingredient_constraint_state(q,state)
    state.pop('goi_y_cho_calo',None)
    if state.get('di_ung_chua_ro') and (meal_words or cooking or payload.get('choice') or topic):
        return limitation('ALLERGY_CLARIFICATION',topic)


    if not (health_active or medical or health['cure_question'] or payload.get('choice')):
        technique = _recipe_technique(payload,recipes,recipe,ledger,excluded)
        if technique is not None:
            return technique

    # Resolve the planned action before the dish-family branch can clear the
    # current recipe. Use the edit parser for quantities and replay semantics.
    edit_q = q
    command = None
    if manifest.get('recipe_edit_version') == 1:
        from backend.chatbot.recipe_edit_v1 import operation
        if recipe:
            for alias in sorted(recipe_aliases(recipe),key=len,reverse=True):
                if alias.startswith('bo ') and re.match(re.escape(alias)+r'\b',q):
                    edit_q = 'mon '+q[len(alias):].lstrip()
                    break
        raw = chuan_hoa_dia_phuong(payload['question']).strip().casefold()
        explicit_dish = bool(re.match(r'^(?:bò|bơ|bột)\b',raw) or
                             re.match(r'^bo (?:kho|xao|nuong|hap|luoc)\b',raw))
        reason_question = re.match(r'^(?:tai sao|vi sao|ly do)\b',q)
        allergy_declaration = re.search(r'\bdi ung\b',q)
        availability_only = (re.match(r'^(?:(?:toi|minh|tui|em) )?khong co\b',q)
                             and not re.search(r'\b(?:thay|bang|dung gi)\b',q))
        if prior and availability_only and not meal_words:
            return limitation('INGREDIENT_UNAVAILABLE',topic)
        if reason_question and re.search(r'\b(?:bo|giam|thay)\b',q) and not meal_words:
            return limitation('TECHNIQUE_SOURCE_MISSING',topic)
        if re.match(r'^(?:doi|nau|giam xuong)\b',edit_q):
            edit_q = re.sub(r'\b(cho|thanh|con) (\d+|'+'|'.join(PORTION_WORDS)+r') khau phan\b',
                            r'\1 \2 phan',edit_q)
        edit_q = re.sub(r'^chia (?:cung (?:mot )?|mot )me\b','chia me nay',edit_q)
        if not (explicit_dish or reason_question or allergy_declaration or availability_only or meal_words):
            edit_and_view = re.split(r'\s+(?:va|roi)\s+(?=xem lai (?:cong thuc|cach nau)\b)',edit_q,maxsplit=1)
            command = operation(edit_and_view[0])
            if len(edit_and_view)>1 and not command:
                command = operation(edit_q)
        if prior and not command and re.match(r'^(?:co the|lieu co the) bo\b',q):
            return limitation('REMOVE_CONFIRMATION',topic)

    # Explicit dish references in an edit must bind before editing. An
    # ambiguous named target must not change the previously active dish.
    named_edit = bool(command and re.search(r'\b(?:trong|cua|cho) mon\b',q))
    if named_edit and not recipe:
        if len(named) != 1:
            return limitation('RECIPE_CLARIFICATION',topic)
        recipe = next((r for r in recipes if r.id_goc in named),None)
        if recipe is None:
            return limitation('RECIPE_CLARIFICATION',topic)
        topic = dict(id_goc=recipe.id_goc,cau_hoi=recipe.cau_hoi)
    if named_edit and recipe and (prior or {}).get('id_goc') != recipe.id_goc:
        state['khau_phan'] = document(ledger[recipe.id_goc])['base_portions']
        for field in ('portion_state_v5','nutrition_context','nutrition_portion_status'):
            state.pop(field,None)
    if command and prior and not named_edit and not recipe:
        # Short verb-led edits have no independent dish-family target.
        named = set()

    # An ingredient name may identify several cooking methods, not a missing dish.
    if not command and not payload.get('choice') and not recipe and not health_active and not medical and not re.search(RECIPE_REFERENCE,q):
        from backend.chatbot.doi_chieu import ten_mon_tu_cau_hoi
        family = ten_mon_tu_cau_hoi(payload['question'])
        if (cooking or q == family) and 1 <= len(family.split()) <= 4 and len(family) >= 2 and re.fullmatch(r'[a-z0-9 ]+', family):
            family_recipes = recipes
            if len(family.split()) == 1:
                from backend.chatbot.goi_y_lien_quan import words, fold
                terms = words(payload['question'])
                if len(terms) == 1 and any(term != fold(term) for term in terms):
                    family_recipes = tuple(r for r in recipes if terms <= words(r.cau_hoi))
            compatible = tuple(r for r in family_recipes if _surface_score(payload['question'],r.cau_hoi)>=0)
            options = simple_recipe_options(q, compatible, ledger, state, name_filter=family)
            if not options and not named and any(
                _surface_score(payload['question'],r.cau_hoi)<0
                and (family==alias or alias.startswith(family+' '))
                for r in family_recipes for alias in recipe_aliases(r)
            ):
                return limitation('RECIPE_CLARIFICATION')
            if options:
                state.pop('nutrition_context', None)
                state.pop('nutrition_portion_status', None)
                state.pop('portion_state_v5', None)
                state['mon_hien_tai'] = None
                state['khau_phan'] = None
                result = limitation('MISSING_CONDITIONAL_RECIPE')
                result.update(reason_code='DISH_FAMILY_OPTIONS', nguon=[reference(row) for row in options],
                              goi_y=[row['question'] for row in options])
                return result

    if (not recipe and not health_active and not medical and not payload.get('choice')
            and payload['parsed'].get('nguyen_lieu_co')
            and re.search(r'\b(?:co the|duoc phep) mua them\b', q)
            and not re.search(RECIPE_REFERENCE,q)):
        options = simple_recipe_options(q,recipes,ledger,state)
        if options:
            state['mon_hien_tai'] = None
            result = limitation('MISSING_CONDITIONAL_RECIPE')
            result.update(reason_code='RECIPE_OPTIONS',nguon=[reference(row) for row in options],
                          goi_y=[row['question'] for row in options])
            return result
        return limitation('PANTRY_MISMATCH')
    change_unspecified = not recipe and re.search(r'\b(?:doi|chuyen) (?:sang )?mon khac\b', q)
    if len(named) > 1 or change_unspecified:
        state.pop('nutrition_context', None)
        state['mon_hien_tai'] = None
        return limitation('RECIPE_CLARIFICATION')
    suggestion = re.search(r'\b(goi y|nau (?:mon )?gi|mon nao)\b', q) and re.search(r'\b(mon|nau|an)\b', q)
    category = re.search(r'\bmon (canh|lau|chao|goi|banh|kho|xao|chien|hap|luoc)\b', q)
    requested_type = category.group(1) if category else None
    if category and not named:
        before = q[:category.start()]
        after = q[category.end():]
        regional_request = re.fullmatch(r' *(?:(?:cua|kieu|o|vung) )?mien tay[ ?!.]*', after)
        generic_request = not after.strip(' ?!.') or regional_request
        wants_a_dish = re.search(r'\b(?:muon (?:an|nau|lam)|them|kiem|tim|co|cho (?:toi|minh|tui|em)) *$', before)
        suggestion = suggestion or bool(generic_request and wants_a_dish)
    if not recipe and not payload.get('choice') and state.get('nguyen_lieu_co'):
        suggestion = suggestion or bool(payload['parsed'].get('nguyen_lieu_co') and not re.search(RECIPE_REFERENCE,q))
    if suggestion and not recipe and state['dieu_kien'].get('nhu_cau') and re.search(
            r'\b(?:calo|kcal|dinh duong)\b', q):
        options = simple_recipe_options(q,recipes,ledger,state,category=requested_type)
        if not options:
            return limitation('MISSING_NUTRITION')
        state['goi_y_cho_calo'] = True
        result = limitation('MISSING_NUTRITION')
        result.update(reason_code='RECIPE_OPTIONS',nguon=[reference(r) for r in options],
                      goi_y=[r['question'] for r in options])
        return result
    simple = suggestion and not recipe and not re.search(r'\b(kcal|calo|protein|natri|dinh duong|giau dam|it beo|it dau|nau nhanh|nguyen lieu)\b',q)
    if (simple and not command) or comfort or low_effort or stomach_options:
        state.pop('nutrition_context', None)
        state.pop('nutrition_portion_status', None)
        state['calo_yeu_cau'] = None
        state['dieu_kien']['can_dinh_luong'] = False
        state['mon_hien_tai'] = None
        state.pop('portion_state_v5', None)
        state['khau_phan'] = None
        options = simple_recipe_options(q, recipes, ledger, state, comfort=comfort or stomach_options, category=requested_type,
                                        low_effort=low_effort, stomach=stomach_options)
        if options:
            result=limitation('MISSING_CONDITIONAL_RECIPE')
            code = 'LOW_EFFORT_MEAL_OPTIONS' if low_effort else 'COMFORT_MEAL_OPTIONS' if comfort else 'RECIPE_OPTIONS'
            if stomach_options:
                code = 'STOMACH_MEAL_OPTIONS'
            result.update(reason_code=code,nguon=[reference(row) for row in options],
                          goi_y=[row['question'] for row in options])
            return result
        if stomach_options:
            return limitation('STOMACH_MEAL_CLARIFY', topic)
        if not comfort and (state.get('nguyen_lieu_bat_buoc') or state.get('chi_dung_nguyen_lieu_co')):
            return limitation('PANTRY_MISMATCH')
        return limitation('COMFORT_MEAL_CLARIFY' if comfort else 'MISSING_CONDITIONAL_RECIPE')
    original_q = normalize(payload['parsed'].get('cau_goc') or payload['question'])
    wants_full = bool(re.search(COOKING_REQUEST,original_q) and not re.search(TIME_REQUEST,original_q))
    if manifest.get('recipe_edit_version')==1:
        from backend.chatbot.recipe_edit_v1 import operation, route_edit, respond, active_for, base_edit
        from backend.chatbot.nutrition_runtime import METRICS, PER_SERVING
        current=ledger.get(topic['id_goc']) if topic else None
        if current and q==normalize(current['question']):command=None
        previous_edit=base_edit(current,state) if current else {}
        if current and command is None and (previous_edit.get('pending') or {}).get('kind')=='quantity_clarify' and re.match(r'^(?:con|dung|cho)\s',q):
            command={'kind':'quantity_clarify','name':None}
        read = (re.search(RECIPE_READ,original_q) or re.search(BASE_READ,original_q)
                or re.search(INGREDIENT_REQUEST,original_q) or re.search(SERVING_QUESTION,original_q)
                or (wants_full and (re.search(RECIPE_REFERENCE,original_q)
                                    or recipe and recipe.id_goc == (prior or {}).get('id_goc'))))
        if (read and (not command or command['kind']=='rewrite') and current and prior
                and current['id']==prior['id_goc'] and not (named-{current['id']})
                and not re.search(TIME_REQUEST,original_q)
                and not payload.get('choice') and not (health['health_need'] or health['cure_question'] or medical)
                and not re.search(r'\b(?:calo|kcal|dinh duong|nguon tham khao|dan nguon)\b',original_q)
                and current['allowed_for_answer'] and current['scope']=='IN_SCOPE'):
            try:
                value = recipe_read_view(current,state,original_q)
            except (ValueError,TypeError,KeyError,ZeroDivisionError):
                return limitation('MISSING_RECIPE',topic)
            return dict(loai='tra_loi',cau_tra_loi='',nguon=[reference(current)],goi_y=[],doan_truy_hoi=[],
                        chu_de=topic,giai_thich={},structured_view=value,
                        reason_code='EDIT_REWRITTEN' if value['mode']=='recipe_edit' else 'SOURCE_UNVERIFIED')
        active=active_for(current,state)
        dietary=any(state.get('dieu_kien',{}).get(k) for k in ('loai_tru','chua_ro','an_chay'))
        asks_nutrition=(re.search(r'\b(?:calo|kcal|dinh duong|protein|natri|chat beo|lipid|carbohydrate)\b',q)
                       or any(re.search(r'\b(?:'+words+r')\b',q) for words in METRICS.values())
                       or re.search(PER_SERVING,q))
        if active and asks_nutrition and not wants_full and (not command or command['kind'] not in ('divide','reset','cancel','undo')):
            from backend.chatbot.derived_nutrition import answer as derived_answer
            metrics=[key for key,terms in METRICS.items() if re.search(r'\b(?:'+terms+r')\b',q)]
            metric=metrics[0] if len(metrics)==1 else None
            licensed=None if dietary else derived_answer(current,state,manifest,metric)
            if licensed:
                contract,data,text=licensed
                return dict(loai='tra_loi',reason_code='NUTRITION_CALCULATED',cau_tra_loi=text,
                    nguon=[],goi_y=[],doan_truy_hoi=[],chu_de=topic,giai_thich={},
                    nutrition_request={'recipe_id':current['id'],'derivative_version':contract['recipe_version'],'metric':metric},
                    nutrition_result=data)
            return respond('EDIT_NUTRITION_BLOCKED',topic)
        if active and not command and re.search(INGREDIENT_REQUEST,q) and not re.search(WHOLE_REQUEST,q):
            command={'kind':'rewrite','aspect':'ingredients'}
        if active and not command and re.search(SERVING_QUESTION,q):
            command={'kind':'rewrite','aspect':'servings'}
        if active and not command and re.search(WHOLE_REQUEST,original_q):
            command={'kind':'rewrite'}
        if command and command['kind']=='remove' and command.get('name') and current:
            # An instruction about this recipe is distinct from a standing exclusion.
            previous_conditions=payload['previous'].get('dieu_kien',{})
            if (not any(previous_conditions.get(k) for k in ('loai_tru','chua_ro','an_chay'))
                    and not (state.get('di_ung') or state.get('di_ung_chua_ro'))
                    and not re.search(r'\b(?:di ung|kieng|an chay|va|hoac)\b',q)):
                for key in ('loai_tru','chua_ro'):
                    state['dieu_kien'][key]=list(previous_conditions.get(key,[]))
                dietary=bool(state['dieu_kien'].get('an_chay'))
        if current and not dietary and not re.search(r'\b(?:khong|dung) (?:bot|giam|bo|thay)\b',q):
            from backend.chatbot.recipe_edit_v1 import combined_operations
            bundle = combined_operations(edit_q)
            if bundle and current['id'] not in excluded:
                trial = copy.deepcopy(state)
                for instruction in bundle:
                    result = route_edit(payload['question'],trial,current,instruction)
                    if result['reason_code'] != 'EDIT_APPLIED':
                        prior_topic = payload['previous'].get('mon_hien_tai') or {}
                        state['khau_phan'] = (payload['previous'].get('khau_phan')
                                             if prior_topic.get('id_goc') == current['id']
                                             else document(current)['base_portions'])
                        return result
                state.update(trial)
                return result
        if (command and command['kind']=='cancel' and active
                and re.search(r'\b(?:khong|dung) bo\b.+\bgiu (?:nguyen |nhung )?.*thay doi\b',q)):
            from backend.chatbot.recipe_edit_v1 import replay
            removal = operation(re.sub(r'^.*?\b(?:khong|dung) bo\b','bo',q,count=1)) or {}
            name = removal.get('name')
            events = base_edit(current,state)['events']
            try:
                matching = [events[i]['command'] for i in replay(current,events)['active']
                            if events[i]['command'].get('name')==name]
            except (ValueError,TypeError,KeyError,ZeroDivisionError):
                return respond('EDIT_UNSUPPORTED',topic)
            if name and matching and matching[-1]['kind']=='remove':
                command = {'kind':'undo','name':name}
        if command and not dietary:
            kind=command['kind']
            # Keep existing serving and vague legacy behavior until the explicit edit flow starts.
            should_edit=(kind not in ('scale','divide') or active or bool(previous_edit.get('pending')) 
                         or (not recipe and kind=='scale' and current and not state.get('nutrition_context') and document(current)['base_portions']
                             and re.match(r'^(nau|doi|giam xuong|cho ca nha)\b',q)))
            if kind=='divide' and not state.get('nutrition_context'):should_edit=True
            if should_edit:
                if not current:return respond('EDIT_NEED_DISH')
                if current['allowed_for_answer'] and current['scope']=='IN_SCOPE':
                    if kind=='cancel' and re.search(WHOLE_REQUEST,q):
                        route_edit(payload['question'],state,current,command)
                        if active:
                            return route_edit(payload['question'],state,current,{'kind':'rewrite'})
                    else:
                        result = route_edit(payload['question'],state,current,command)
                        if kind in ('scale','divide') and result['loai']!='tra_loi':
                            prior_topic = payload['previous'].get('mon_hien_tai') or {}
                            state['khau_phan'] = (payload['previous'].get('khau_phan')
                                                 if prior_topic.get('id_goc') == current['id']
                                                 else document(current)['base_portions'])
                        return result
    if manifest.get('nutrition_integration_version')==1 and not wants_full:
        from backend.chatbot.nutrition_runtime import route as nutrition_route
        nutrition=nutrition_route(payload,manifest,ledger,recipe)
        if nutrition is not None:return nutrition
    if not wants_full and re.search(r'\b(kcal|calo|protein|lipid|carbohydrate|natri|vitamin|chat dam|chat beo|giau dam|it natri|dinh duong)\b',q):return limitation('MISSING_NUTRITION',state.get('mon_hien_tai'))
    follow = bool(re.search(RECIPE_REFERENCE, q) or re.search(PORTION_CHANGE, q)
                  or re.search(r'\b(khau phan|doi (?:thanh|con)|hien tai|xac nhan|moc goc|tinh nguyen lieu)\b', q))
    method_named=bool(re.search(r'\b(?:ga|ca(?: \w+){0,2}?|thit(?: ga|heo)?|tom|vit|rau)\s+(?:nau|xao|kho|chien|nuong|hap|say|la giang)\b|\b(?:canh|lau|chao)\s+(?!(?:de|don gian|ngon|nhanh|gi|nao)\b)\w+',q))
    if not recipe and method_named and not re.search(RECIPE_REFERENCE,q):
        dk = state['dieu_kien']
        if (not command and not health_active and not medical and not payload.get('choice')
                and not any(dk.get(key) for key in ('loai_tru','chua_ro','an_chay'))
                and not (state.get('di_ung') or state.get('di_ung_chua_ro'))):
            from backend.chatbot.fuzzy import de_nghi_ten_mon

            titles = set(de_nghi_ten_mon(payload['question'],kho))
            options = [ledger[r.id_goc] for r in recipes if r.cau_hoi in titles
                       and not _check_recipe(ledger[r.id_goc],state)[0]]
            if options:
                for field in ('nutrition_context','nutrition_portion_status','portion_state_v5'):
                    state.pop(field,None)
                state['mon_hien_tai'] = None
                state['khau_phan'] = None
                return dict(limitation('RECIPE_CLARIFICATION'),reason_code='RECIPE_OPTIONS',
                            nguon=[reference(row) for row in options],goi_y=[row['question'] for row in options])
        state.pop('nutrition_context', None)
        state['mon_hien_tai'] = None
        return limitation('RECIPE_CLARIFICATION')
    aspect = any(re.search(p, q) for p in (INGREDIENT_REQUEST, TIME_REQUEST, SERVING_QUESTION, RECIPE_SOURCE))
    choice = payload.get('choice')
    if choice:
        selected = next((r for r in recipes if r.id_goc == choice['id_goc']),None)
        if not selected:
            return limitation('RECIPE_CLARIFICATION')
        recipe = selected
    if not recipe and prior and (follow or aspect or payload.get('choice') or wants_full or re.search(r'\b(so che|lam sach|buoc|bo|giam|thay)\b', q)):
        recipe=next((r for r in recipes if r.id_goc==prior['id_goc']),None)
    if not recipe:
        if aspect or re.search(RECIPE_REFERENCE,q):
            return limitation('RECIPE_CLARIFICATION')
        if re.search(WHOLE_REQUEST,q) and not re.search(r'\bgoi y\b',q):
            return limitation('MISSING_DISH')
        return None
    row=ledger[recipe.id_goc];topic=dict(id_goc=row['id'],cau_hoi=row['question'])
    doc=document(row)
    ps=state.get('portion_state_v5')
    if not ps or ps.get('recipe_id')!=row['id'] or ps.get('recipe_version')!=row['answer_sha256']:
        ps=dict(recipe_id=row['id'],recipe_version=row['answer_sha256'],target_requested=None,target_applied=doc['base_portions'],base_confirmation=None)
        state['portion_state_v5']=ps
    state['khau_phan']=ps['target_applied']
    try:confirmation=confirm_base(row,payload['question'])
    except ValueError:return limitation('BASE_PORTION_CONFLICT',topic)
    if confirmation:ps['base_confirmation']=confirmation
    target=re.search(PORTION_CHANGE,q)
    if confirmation:target=None
    if target:
        size = int(target[1]) if target[1].isdigit() else PORTION_WORDS[target[1]]
        if not 1<=size<=100:return limitation('MODIFICATION_UNSUPPORTED',topic)
        ps['target_requested']=size
    removing=normalize(food_text(payload['question']))
    for alias in sorted(recipe_aliases(recipe), key=len, reverse=True):
        if alias.startswith('bo '):
            removing=re.sub(r'(?<!\w)' + re.escape(alias) + r'\b', 'mon', removing)
    removing=re.sub(r'\b(?:khong|dung|cho) (?:bo|giam|thay)\b','giu nguyen',removing)
    modification=bool(re.search(r'(?<!toan )(?<!bun )(?<!thit )\bbo\s+|\b(giam|thay bang|thay the|khong dung|khong them|khong co)\b|\bthay\s+.+?\s+bang\b',removing))
    lighter = bool(re.search(r'\b(?:cho|dung|nem) it (?:muoi|duong|dau|tieu|nuoc mam)\b',removing))
    dk=state['dieu_kien']
    if re.search(r'\b(nguon|chung cu|bai goc|verified)\b',q):
        result=limitation('SOURCE_UNVERIFIED',topic);result['nguon']=[reference(row)];return result
    pending=state.get('pending_ingredient_change')
    if pending and pending['recipe_id']==row['id'] and re.search(r'\b(giu nguyen|cong thuc goc|huy yeu cau)\b',q):
        state.pop('pending_ingredient_change',None);pending=None
    if pending and pending['recipe_id']==row['id']:
        return limitation('MODIFICATION_UNSUPPORTED',topic)
    from backend.chatbot.goi_y_mon_chay import checked_recipe
    rejection, _, _ = _check_recipe(row,state)
    if rejection and not (modification or lighter):
        return limitation(rejection,topic)
    if modification or lighter:
        result=limitation('MODIFICATION_UNSUPPORTED',topic)
        result['adjustment_request']=adjustment_request(row,payload['question'])
        if lighter or re.search(r'(?<!toan )\bbo\s+|\b(giam|khong dung|khong them)\b',removing):
            state['pending_ingredient_change']=dict(recipe_id=row['id'],source_version=row['answer_sha256'],status='NOT_APPLIED',request=result['adjustment_request'])
        return result
    mode='full';selector=None
    if target or confirmation or re.search(r'\b(khau phan hien tai|tinh nguyen lieu|doi khau phan)\b',q):mode='portion'
    elif re.search(SERVING_QUESTION,q) or re.search(r'\bkhau phan\b',q):mode='servings'
    elif re.search(TIME_REQUEST,q) or re.search(r'\btong(?: thoi gian)? mat\b',q):
        mode='time';selector={'phase':requested_phase(q)}
    elif re.search(r'\b(so che|lam sach|khu tanh)\b',q):mode='prep'
    elif re.search(INGREDIENT_REQUEST,q) and not re.search(WHOLE_REQUEST,q):mode='ingredients'
    elif re.search(r'\b(cac buoc|cac buoc nau|cac buoc che bien)\b',q) and not re.search(r'\b(tu dau|toan bo|tron mon)\b',q):mode='steps'
    else:
        step_request=re.search(r'\b(buoc \d+|uop|luoc|xao|nau nuoc)\b',q)
        if step_request and (not re.search(WHOLE_REQUEST,q) or re.search(r'\bbuoc \d+\b',q)) and (not named or re.search(r'\b(?:buoc \d+|uop|nau nuoc)\b',q)):
            numbered=re.search(r'\bbuoc\s+(\d+)\b',q)
            choices=[]
            for span in step_spans(row):
                raw=row['answer_text'][span['start']:span['end']].splitlines()[0]
                line=normalize(raw.lstrip('-• '))
                if numbered:
                    if re.match(r'(?:buoc\s+)?'+re.escape(numbered[1])+r'(?:\b|[.)])',line):choices.append((100,span))
                elif not raw.startswith(('-', '•')):
                    if line and line in q:choices.append((100+len(line.split()),span))
                elif re.match(r'^(uop|luoc|xao|phi|loc|ngam|rua|cat|thai|nuong|chien|hap|kho|dun|cho|them|nem)\b',line):
                    for n in (3,2):
                        if len(line.split())>=n and ' '.join(line.split()[:n]) in q:choices.append((n,span));break
            if not choices:return limitation('MISSING_STEP',topic)
            best=max(n for n,_ in choices);spans=[s for n,s in choices if n==best]
            if len(spans)!=1:return limitation('MISSING_STEP',topic)
            selector=spans[0]
            mode='step'
    try:
        if mode=='servings' and not (doc['base_portions'] or doc['base_range']):return limitation('AMBIGUOUS_BASE_PORTIONS',topic)
        if mode=='portion' and not doc['base_portions'] and not ps['base_confirmation']:return limitation('AMBIGUOUS_BASE_PORTIONS',topic)
        desired=ps['target_requested'] or ps['target_applied'] or (ps['base_confirmation']['confirmed_base'] if ps['base_confirmation'] else None)
        value=view(row,mode,desired if mode=='portion' else state.get('khau_phan'),selector,ps['base_confirmation'])
        if mode=='portion':
            ps['target_applied']=value['transform']['target_portions']
            state['khau_phan']=ps['target_applied']
        render_view(row,value)
    except (ValueError,ZeroDivisionError):return limitation('MISSING_RECIPE',topic)
    return dict(loai='tra_loi',cau_tra_loi='',nguon=[reference(row)],goi_y=[],doan_truy_hoi=[],chu_de=topic,giai_thich={'nhom_nguon':row['group_folder']},structured_view=value,reason_code='SOURCE_UNVERIFIED')

def light_meal_group(title):
    if re.search(r'^chao\b', title):
        return 'porridge'
    if re.search(r'^sup\b', title):
        return 'soup'
    if re.search(r'\bcanh\b', title) and not re.search(r'\bcanh chua\b', title):
        return 'soup'
    if re.search(r'\bluoc\b', title):
        return 'boiled'
    return None


TIRED_REQUEST = re.compile(r'\b(?:cam thay|thay|hoi|qua|dang) met\b|\b(?:hom nay|nay).{0,25}\bmet\b|(?:^|[,;.!?]\s*)(?:(?:toi|minh|tui|em) )?met\b')


ALLERGY_LIMIT = ('Mình chưa thấy chất gây dị ứng đã khai báo trong nội dung kiểm tra được. '
                 'Công thức chưa xác minh đầy đủ thành phần gia vị, nước chấm, nước sốt '
                 'và nguy cơ tiếp xúc chéo. Hãy kiểm tra nhãn và cách chuẩn bị trước khi dùng.')


def _ingredient_constraint_state(question, state):
    """Give the already parsed inventory explicit meaning for recipe selection."""
    have = state.get('nguyen_lieu_co', ())
    if have and re.search(r'\b(?:phai dung|bat buoc|nhat dinh (?:dung|co))\b', question):
        if re.search(r'\b(?:ca hai|ca ba|tat ca|het)\b', question):
            state['nguyen_lieu_bat_buoc'] = list(have)
        else:
            tail = re.split(r'\b(?:phai dung|bat buoc(?: dung)?|nhat dinh (?:dung|co))\b', question, maxsplit=1)[-1]
            lead = re.split(r'[,;.!?]|\b(?:thi|de|nau|lam)\b', tail, maxsplit=1)[0]
            named = [item for item in have if re.search(r'(?<!\w)'+re.escape(normalize(item))+r'(?!\w)',lead)]
            if named:
                state['nguyen_lieu_bat_buoc'] = named
    if have and re.search(r'\b(?:co the|duoc phep) mua them\b', question):
        state['chi_dung_nguyen_lieu_co'] = False
    if have and re.search(r'\bchi co\b', question):
        state['chi_dung_nguyen_lieu_co'] = True
    if re.search(r'\b(?:mot trong hai|dung mot trong|dung nguyen lieu nao cung duoc)\b',question) and not re.search(r'\b(?:phai dung|bat buoc)\b',question):
        state.pop('nguyen_lieu_bat_buoc', None)


def _contains_ingredient(required, names):
    """Match a complete ingredient phrase at the start of a source item."""
    phrase = chuan_hoa_dia_phuong(required).casefold().strip()
    if not phrase:
        return False
    if phrase.isascii():
        phrase = normalize(phrase)
        names = [normalize(name) for name in names]
        prefix = r'(?:(?:phi le|mieng|thit) )?'
    else:
        prefix = r'(?:(?:phi lê|miếng|thịt) )?'
    pattern = re.compile(r'^'+prefix+re.escape(phrase)+r'(?![^\W\d])')
    return any(pattern.search(name) for name in names)


def _check_recipe(row, state, *, rendered=None, ingredient_lines=None, require_inventory_match=False):
    """Return a rejection code, count matched pantry items, and missing lines."""
    conditions = state.get('dieu_kien') or {}
    allergies = state.get('di_ung', ())
    if state.get('di_ung_chua_ro'):
        return 'ALLERGY_CLARIFICATION', 0, []
    source = rendered if rendered is not None else row['answer_text']
    if allergies:
        from backend.chatbot.ngon_ngu import NGUYEN_LIEU
        for kind in allergies:
            terms = NGUYEN_LIEU.get(kind)
            if not terms:
                return 'ALLERGY_CLARIFICATION', 0, []
            # Treat even an ambiguous mention in a sauce, serving note or
            # instruction as a conflict. "Bỏ tôm vào" is not an exclusion.
            text = source.casefold()
            if text.isascii():
                terms = tuple(normalize(term) for term in terms)
            if any(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',text) for term in terms):
                return 'ALLERGY_CONFLICT', 0, []
    if conditions.get('chua_ro') or vi_pham(source, {
        'loai_tru':conditions.get('loai_tru', ()), 'an_chay':conditions.get('an_chay', False)
    }):
        return 'MISSING_CONDITIONAL_RECIPE', 0, []
    if not du_bang_chung(source, {'nhu_cau':conditions.get('nhu_cau', ())}):
        return 'MISSING_NUTRITION', 0, []
    if state.get('khong_chien') and re.search(r'\b(?:chien|ran)\b', normalize(source)):
        return 'MISSING_CONDITIONAL_RECIPE', 0, []
    lines = ingredient_lines if ingredient_lines is not None else [i['text'] for i in document(row)['ingredients']]
    names = [chuan_hoa_dia_phuong(line.lstrip('-• ').strip()).casefold() for line in lines]
    required = state.get('nguyen_lieu_bat_buoc', ())
    have = state.get('nguyen_lieu_co', ())
    matched = sum(_contains_ingredient(item, names) for item in have)
    missing = [line.lstrip('-• ').strip() for line, name in zip(lines,names)
               if have and not any(_contains_ingredient(item, (name,)) for item in have)]
    if (not all(_contains_ingredient(item, names) for item in required)
            or (require_inventory_match and have and not matched)
            or (state.get('chi_dung_nguyen_lieu_co') and missing)):
        return 'PANTRY_MISMATCH', matched, missing
    return None, matched, missing


def simple_recipe_options(question, recipes, ledger, state, *, comfort=False, category=None, low_effort=False, stomach=False, name_filter=None):
    light_and_quick = low_effort and TIRED_REQUEST.search(question)
    conditions=state['dieu_kien']
    if conditions['chua_ro']:
        return []
    western='mien tay' in question
    options=[]
    for recipe in recipes:
        if name_filter and not any(re.search(r'(?<!\w)' + re.escape(name_filter) + r'(?!\w)', alias) for alias in recipe_aliases(recipe)):
            continue
        row=ledger.get(recipe.id_goc)
        if not row or not row['allowed_for_answer'] or row['scope']!='IN_SCOPE':
            continue
        if western and not row['group_folder'].endswith('mon_mien_tay'):
            continue
        title = normalize(recipe_option_label(row['question']))
        if category:
            name_pattern = r'^' if category in ('lau', 'chao', 'goi', 'banh') else r'\b'
            if not re.search(name_pattern + category + r'\b', title):
                continue
        group = light_meal_group(title)
        if light_and_quick and (not group or re.search(r'\b(?:chien|ran|xao)\b',title)):
            continue
        if comfort and not group:
            continue
        d=document(row)
        if not {'ingredients','steps'} <= d['sections'].keys():
            continue
        rejection, matched, missing = _check_recipe(row,state,require_inventory_match=True)
        if rejection:
            continue
        if state.get('thoi_gian_toi_da') is not None and (recipe.tong_phut is None or recipe.tong_phut > state['thoi_gian_toi_da']):
            continue
        ingredients, steps = len(d['ingredients']), len(step_spans(row))
        minutes = recipe.tong_phut if recipe.tong_phut is not None else float('inf')
        rank = (-matched, len(missing), minutes, steps, ingredients)
        options.append((*rank, row['id'], row, group))
    ranked = sorted(options)
    if not comfort or category:
        return [row for *_, row, _group in ranked[:9 if name_filter else 3]]

    if re.search(r'\b(?:bi cam|cam lanh|cam cum|bi cum)\b', question):
        # Excel 771/773/794 suggest cháo and súp. Use permitted recipe
        # records only, after applying the normal ingredient constraints.
        def relevance(item):
            *_, row, group = item
            title = normalize(recipe_option_label(row['question']))
            if title.startswith('chao') and re.search(r'\bga\b', title):
                return 0
            if title.startswith('sup '):
                return 1
            return 2 if group == 'porridge' else 3

        meals = [item for item in ranked if item[-1] in ('porridge', 'soup')]
        return [item[-2] for item in sorted(meals, key=relevance)[:3]]

    # Offer different kinds of food before listing several versions of one dish.
    groups = ('porridge', 'boiled') if stomach else ('soup', 'porridge', 'boiled')
    choices = []
    for group in groups:
        option = next((row for *_, row, kind in ranked if kind == group), None)
        if option:
            choices.append(option)
    return choices


def recipe_option_label(question):
    name = re.sub(r'^(?:(?:cho (?:mình|tôi|tui|em)|hướng dẫn|công thức|cách|làm|nấu|món)\s+)+', '', question.strip(), flags=re.I)
    name = re.split(r'\s+(?:(?:nấu|làm) như thế nào|(?:nấu|làm) vậy có đúng cách chưa|như thế nào|kiểu (?:gì|nào)|sao cho|làm sao|nấu sao|thế nào|ra sao)\b',
                    name, maxsplit=1, flags=re.I)[0].strip(' ?!.')
    name = re.sub(r'\s+đơn giản(?: với| nha| nhé)?$', '', name, flags=re.I)
    return name[:1].upper() + name[1:] if name else question


def enforce(result,manifest,ledger):
    from backend.chatbot.knowledge_policy import allowed,limited
    r=copy.deepcopy(result)
    ids=[s['id_goc'] for s in r.get('nguon',[])]+[s['id_goc'] for s in r.get('doan_truy_hoi',[])]
    if r.get('chu_de'):ids.append(r['chu_de']['id_goc'])
    excluded = set(manifest.get('demo_excluded_recipe_ids', ()))
    if r.get('reason_code') == 'MEDICAL_LIMITED_V3':
        row = ledger.get(ids[0]) if len(ids) == 1 and ids[0] not in excluded else None
        if not reviewed_medical_row(row):
            return limitation('VALIDATION_FAILED')
        # Reconstruct from reviewed ledger bytes both before sealing and on render.
        r.update(direct_reviewed_result(row, 'MEDICAL_LIMITED_V3'))
        r['giai_thich']['knowledge_build_id'] = manifest['build_id']
        return r
    if any(not allowed(ledger,i) for i in ids):return limited(r)
    titles = {row['question'] for row in ledger.values() if row['allowed_for_answer'] and row['id'] not in excluded}
    r['goi_y'] = [title for title in r.get('goi_y', []) if title in titles]
    if r.get('reason_code') == 'TECHNIQUE_SOURCE':
        from backend.chatbot.phan_hoi import TEMPLATES
        if not ids or len(set(ids)) != 1 or ids[0] in excluded:
            return limitation('VALIDATION_FAILED')
        row = ledger[ids[0]]
        sentences = re.split(r'(?<=[.!?])\s+|\n+|&#10;', row['answer_text'])
        text = r['cau_tra_loi']
        intro, separator, excerpt = text.partition('\n\n')
        if separator and (intro == NOTICE or any(intro in options for options in TEMPLATES.values())):
            text = excerpt
        if row['scope'] != 'IN_SCOPE' or text not in {s.strip() for s in sentences}:
            return limitation('VALIDATION_FAILED')
        if r.get('chu_de') or r.get('giai_thich',{}).get('ky_thuat_cong_thuc'):
            state = r.get('trang_thai') or {}
            rejection,_,_ = _check_recipe(row,state)
            if rejection:
                return limitation(rejection) | {'trang_thai':state}
        r['cau_tra_loi'] = NOTICE+'\n\n'+text
        r['nguon'] = [reference(row)]
    elif r.get('structured_view'):
        value=r['structured_view'];row=ledger.get(value.get('recipe_id'))
        try:
            if (not row or not row['allowed_for_answer'] or row['scope']!='IN_SCOPE'
                    or row['id'] in excluded or set(ids)!={row['id']}):
                raise ValueError('Wrong source/view')
            if value.get('mode')=='recipe_edit' and manifest.get('recipe_edit_version')==1:
                from backend.chatbot.recipe_edit_v1 import base_edit, replay, text_for
                edit=base_edit(row,r.get('trang_thai') or {})
                if (not edit['events'] or value.get('recipe_version')!=row['answer_sha256']
                        or edit['events']!=value.get('events')):
                    raise ValueError('Invalid derivative provenance')
                aspect=value.get('aspect')
                if aspect=='steps':
                    plan=replay(row,value['events'])
                    steps=[step['text'] for step in plan['steps'] if step['section']=='steps' and step['text']]
                    if not steps:
                        raise ValueError('Missing derivative steps')
                    r['cau_tra_loi']='\n\n'.join((NOTICE,f"**Các bước chế biến — {plan['portions']} phần**",'\n'.join(steps)))
                else:
                    r['cau_tra_loi']=text_for(row,value['events'],aspect)[0]
            else:
                if value['mode']=='applied_full':
                    portion=(r.get('trang_thai') or {}).get('portion_state_v5') or {}
                    if (portion.get('recipe_id')!=row['id'] or portion.get('recipe_version')!=row['answer_sha256']
                            or portion.get('target_applied')!=value.get('target_portions')
                            or portion.get('base_confirmation')!=value.get('base_confirmation')):
                        raise ValueError('Invalid applied portion provenance')
                r['cau_tra_loi']=render_view(row,value)
            state = r.get('trang_thai') or {}
            checked_text = None
            ingredient_lines = None
            if value.get('mode') == 'recipe_edit':
                from backend.chatbot.recipe_edit_v1 import replay
                plan = replay(row,value['events'])
                ingredient_lines = [item['name'] for item in plan['items']]
                checked_text = '\n'.join([*ingredient_lines, *(step['text'] for step in plan['steps'] if step['text'])])
            rejection, _, _ = _check_recipe(row,state,rendered=checked_text,ingredient_lines=ingredient_lines)
            if rejection:
                return limitation(rejection,r.get('chu_de')) | {'trang_thai':state}
            if state.get('di_ung'):
                r['cau_tra_loi'] += '\n\n'+ALLERGY_LIMIT
            if value.get('mode') in ('full','applied_full','recipe_edit') and not value.get('aspect'):
                from backend.chatbot.nutrition_runtime import recipe_footer
                r['cau_tra_loi'] += '\n\n'+recipe_footer(row,value,r.get('trang_thai') or {},manifest,ledger)
            r['nguon']=[reference(row)]
        except (ValueError,KeyError,TypeError,ZeroDivisionError):
            r=limitation('VALIDATION_FAILED')
    elif r.get('reason_code') in (None, 'RECIPE_OPTIONS', 'DISH_FAMILY_OPTIONS', 'COMFORT_MEAL_OPTIONS', 'LOW_EFFORT_MEAL_OPTIONS', 'STOMACH_MEAL_OPTIONS') and r.get('loai') == 'khong_chac' and r['goi_y']:
        stomach_options = r.get('reason_code') == 'STOMACH_MEAL_OPTIONS'
        comfort = stomach_options or r.get('reason_code') == 'COMFORT_MEAL_OPTIONS'
        low_effort = r.get('reason_code') == 'LOW_EFFORT_MEAL_OPTIONS'
        r['reason_code'] = r.get('reason_code') or 'RECIPE_OPTIONS'
        valid_recipe_titles={row['question']:row for row in ledger.values()
                             if row['allowed_for_answer'] and row['scope']=='IN_SCOPE' and row['id'] not in excluded
                             and {'ingredients','steps'} <= document(row)['sections'].keys()
                             and (not comfort or light_meal_group(normalize(recipe_option_label(row['question']))))}
        state = r.get('trang_thai') or {}
        checked = {title:_check_recipe(row,state,require_inventory_match=True)
                   for title in dict.fromkeys(r['goi_y']) if (row := valid_recipe_titles.get(title))}
        r['goi_y'] = [title for title, (rejection, _, _) in checked.items() if not rejection][:9 if r.get('reason_code') == 'DISH_FAMILY_OPTIONS' else 3]
        if 'trang_thai' in r:
            saved = {item['id_goc']:item for item in state.get('de_xuat', ())}
            r['trang_thai']['de_xuat'] = [dict(saved.get(valid_recipe_titles[title]['id'], {}),
                                               id_goc=valid_recipe_titles[title]['id'],cau_hoi=title)
                                          for title in r['goi_y']]

        choices=[valid_recipe_titles[title] for title in r['goi_y']]
        if not choices:
            code = 'ALLERGY_CLARIFICATION' if state.get('di_ung_chua_ro') else 'MISSING_CONDITIONAL_RECIPE'
            return limitation(code) | {'trang_thai':state}
        names = [recipe_option_label(row['question']) for row in choices]
        labels = []
        for row, name in zip(choices,names):
            title = row['question']
            missing = checked[title][2]
            timing = ''
            if low_effort:
                text = row['answer_text']
                sections = document(row)['sections']
                summary = list(summary_durations(text,sections))
                totals = {duration_text(value) for phase, _, value in summary if phase=='total'}
                if len(totals)==1:
                    timing = 'Tổng thời gian: '+next(iter(totals))
                else:
                    details = [f'{LABELS[phase]}: {duration_text(value)}'
                               for phase, _, value in summary if phase!='total']
                    if not any(phase=='cook' for phase, _, _ in summary):
                        details.extend(f'{ACTIONS.get(action,LABELS[phase])}: {value}'
                                       for phase, action, value in step_durations(text,sections))
                    timing = ' · '.join([*dict.fromkeys(details),'Chưa rõ tổng thời gian'])
            labels.append('- '+name+(' — '+timing if timing else '')
                          +('\n  Cần mua thêm theo công thức: '+', '.join(missing)+'.' if missing else ''))
        intro = ('Nếu bạn muốn ăn món mềm hoặc có nước, mình gợi ý vài món dưới đây. Chọn món để xem cách nấu nhé.'
                 if comfort else 'Bạn có thể chọn một trong các món dưới đây để xem công thức.')
        if r.get('reason_code') == 'DISH_FAMILY_OPTIONS':
            intro = 'Trong dữ liệu có các món dưới đây. Bạn chọn cách chế biến muốn xem nhé.'
        if low_effort:
            intro = 'Mình gợi ý vài món nấu gọn. Bạn chọn món để xem cách làm nhé.'
        if stomach_options:
            intro = 'Nếu bạn muốn một bữa đơn giản, mình gợi ý vài món mềm hoặc luộc. Bạn có thể nói thêm nguyên liệu muốn tránh để mình lọc theo đó.'
        r['recipe_option_labels'] = names
        if state.get('goi_y_cho_calo'):
            intro += '\n\nMình cần đúng món, phiên bản và khẩu phần để tra calo; hãy chọn công thức bạn muốn.'
        if state.get('di_ung'):
            intro += '\n\n' + ALLERGY_LIMIT
        r['cau_tra_loi'] = intro+'\n\n'+'\n'.join(labels)
        r['nguon'] = [reference(row) for row in choices]
    elif str(r.get('reason_code','')).startswith('EDIT_') and manifest.get('recipe_edit_version')==1:
        from backend.chatbot.recipe_edit_v1 import MESSAGES
        r.update(cau_tra_loi=MESSAGES.get(r['reason_code'],REASONS['VALIDATION_FAILED']),
                 loai='khong_chac',nguon=[],goi_y=[],doan_truy_hoi=[])
        if r['reason_code']=='EDIT_SOURCE_OPTION_PROPOSED':
            from backend.chatbot.recipe_alternatives import NAMES,option
            from backend.chatbot.recipe_edit_v1 import base_edit
            current=ledger.get((r.get('chu_de') or {}).get('id_goc'))
            pending=(base_edit(current,r.get('trang_thai') or {}).get('pending') or {}) if current else {}
            offer=option(current,pending.get('name'),pending.get('new')) if current else None
            if offer:
                r['cau_tra_loi']=f"Mình tìm thấy **{NAMES[offer['chosen']]}** (lượng nguồn ghi: {offer['amount']}) trong công thức gốc. Mình chưa áp dụng. Bạn có thể nói “Thay luôn đi”."

    elif r.get('reason_code') in REASONS:
        r['cau_tra_loi']=REASONS[r['reason_code']]
        r['loai']='ngoai_pham_vi' if r['reason_code']=='OUT_OF_SCOPE' else 'khong_chac'
        r['nguon']=[reference(ledger[i]) for i in dict.fromkeys(ids) if i in ledger] if r['reason_code']=='SOURCE_UNVERIFIED' else []
        r['goi_y']=[]
    elif r.get('loai')=='tra_loi' and r.get('nguon'):
        r['cau_tra_loi']=NOTICE+'\n\n'+'\n\n'.join(ledger[i]['answer_text'] for i in dict.fromkeys(s['id_goc'] for s in r['nguon']))
    elif r.get('loai')=='chao_hoi':
        texts={x['answer_text'] for x in ledger.values() if x['allowed_for_answer'] and x['scope']=='CONVERSATIONAL'}
        if r.get('cau_tra_loi') not in texts:r['cau_tra_loi']='Mình là trợ lý nấu ăn. Bạn muốn xem công thức món nào?'
    else:
        code='OUT_OF_SCOPE' if r.get('loai')=='ngoai_pham_vi' else 'MISSING_CONDITIONAL_RECIPE' if r.get('goi_y') else 'MISSING_DISH'
        r['reason_code']=code;r['cau_tra_loi']=REASONS[code]
    r.setdefault('giai_thich',{})['knowledge_build_id']=manifest['build_id']
    return r
