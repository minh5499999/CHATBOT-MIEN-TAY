"""Typed source views and exact arithmetic. No new recipes, health claims or LLM."""
import copy
from fractions import Fraction
import hashlib
import re
from backend.chatbot.ngon_ngu import chuan_hoa, chuan_hoa_dia_phuong, vi_pham, du_bang_chung

from backend.chatbot.phan_hoi import CAU_NGOAI_PHAM_VI

REASONS = {
 'MISSING_DISH':'Mình chưa tìm thấy món này trong danh mục công thức được phép tham khảo. Bạn ghi rõ tên món giúp mình nhé.',
 'MISSING_RECIPE':'Chưa có đủ phần công thức được phép tham khảo cho yêu cầu này.',
 'MISSING_STEP':'Công thức chưa ghi rõ bước được hỏi. Mình không tự tạo thêm bước nấu.',
 'MISSING_NUTRITION':'Chưa đủ dữ liệu thành phần, khối lượng và khẩu phần để tính kcal, protein, lipid, carbohydrate hoặc natri hay xác nhận điều kiện dinh dưỡng bạn yêu cầu.',
 'SOURCE_UNVERIFIED':'Nguồn công thức chưa được xác minh độc lập. Mình có URL đã lưu, chưa có bản nguồn gốc và đoạn chứng cứ để đối chiếu.',
 'HELD_HEALTH':'Chưa có nội dung sức khỏe được thẩm định đủ cho nhu cầu này. Mình chưa thể đưa lời khuyên riêng cho cảm, ho, sốt hoặc kinh nguyệt; không chẩn đoán hay hướng dẫn điều trị.',
 'MODIFICATION_UNSUPPORTED':'Chưa đủ căn cứ để bỏ, giảm hoặc thay nguyên liệu và cập nhật toàn bộ bước nấu. Mình chưa tạo công thức đã điều chỉnh; không tự thêm nguyên liệu thay thế.',
 'OUT_OF_SCOPE':CAU_NGOAI_PHAM_VI,
 'HISTORY_UNSEALED':'Lịch sử thuộc phiên chạy cũ hoặc chưa có seal hợp lệ. Nội dung vẫn được lưu; bạn hỏi lại để mình kiểm tra quyền sử dụng nguồn hiện tại.',
 'VALIDATION_FAILED':'Kết quả chưa qua kiểm tra nguồn hoặc phép tính nên mình chưa hiển thị nội dung đó.',
 'MISSING_CONDITIONAL_RECIPE':'Chưa tìm được công thức có đủ dữ liệu để đáp ứng các điều kiện đang giữ. Mình không tự đổi món hoặc nguyên liệu.'}
NOTICE='Nội dung tham khảo trong bản staging; nguồn chưa được xác minh độc lập.'

def normalize(s):return chuan_hoa(chuan_hoa_dia_phuong(s))
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
    s=sections.get('ingredients');ingredients=[];base=None
    if s:
        block=text[s['start']:s['end']]
        count=re.search(r'cho\s+(\d+)\s*(?:người|phần)',block.splitlines()[0],re.I)
        if count and not re.search(r'\d+\s*(?:[-–]|đến)\s*\d+',block.splitlines()[0]):base=int(count[1])
        for m in re.finditer(r'(?m)^\s*[-•][^\n]+',block):
            raw=m[0].strip();start=s['start']+m.start()+len(m[0])-len(m[0].lstrip())
            ingredients.append(dict(text=raw,start=start,end=start+len(raw)))
    return dict(recipe_id=row['id'],version=row['answer_sha256'],base_portions=base,sections=sections,ingredients=ingredients)

def portion_transform(row,target):
    doc=document(row);base=doc['base_portions']
    if type(target) is not int or not 1<=target<=100 or not base:raise ValueError('Ambiguous or unsupported serving count')
    factor=Fraction(target,base);items=[]
    # Count units remain counts: never infer grams; household measures remain unresolved.
    pattern=r'^(.*?)\s+(\d+(?:[.,]\d+|/\d+)?)\s*(kg|mg|g|ml|lít|l|quả|trái|củ|tép|nhánh|con|miếng)$'
    for entry in doc['ingredients']:
        raw=entry['text'];m=re.fullmatch(pattern,raw.lstrip('-• ').strip(),re.I)
        item={**entry,'source_id':row['id'],'source_version':row['answer_sha256'],'source':row['source']}
        if m:
            quantity=Fraction(m[2].replace(',','.'))
            item.update(status='SCALED',name=m[1],quantity=str(quantity),unit=m[3],factor=str(factor),result=str(quantity*factor))
        else:item.update(status='UNRESOLVED',reason='Không có một định lượng/đơn vị rõ ràng; giữ dòng gốc để đối chiếu, chưa áp dụng cho khẩu phần mới.')
        items.append(item)
    return dict(schema=1,recipe_id=row['id'],recipe_version=row['answer_sha256'],source=row['source'],base_portions=base,target_portions=target,factor=str(factor),items=items)

def validate_transform(row,value):
    if not isinstance(value,dict) or value!=portion_transform(row,value.get('target_portions')):raise ValueError('Transformation provenance/arithmetic mismatch')
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

def view(row,mode='full',target=None,selector=None):
    doc=document(row)
    if not doc['ingredients']:raise ValueError('Missing recipe')
    if target is not None and (type(target) is not int or not 1<=target<=100):raise ValueError('Invalid target portions')
    if selector is not None and mode!='step':raise ValueError('Unexpected selector')
    result=dict(schema=1,recipe_id=row['id'],recipe_version=row['answer_sha256'],mode=mode,target_portions=target,selector=selector)
    if mode=='portion':result['transform']=portion_transform(row,doc['base_portions'] if target is None else target)
    return result

def render_view(row,value):
    if value!=view(row,value.get('mode'),value.get('target_portions'),value.get('selector')):raise ValueError('View/provenance mismatch')
    doc=document(row);mode=value['mode'];text=row['answer_text']
    if mode=='portion':
        t=value['transform'];validate_transform(row,t)
        lines=[NOTICE,f"**Định lượng tính theo dữ liệu nội bộ cho {t['target_portions']} người** (gốc {t['base_portions']} người; hệ số {t['factor']})."]
        for item in t['items']:
            if item['status']=='SCALED':lines.append(f"- {item['name']}: {item['quantity']} × {t['factor']} = {item['result']} {item['unit']}")
        unknown=[i['text'] for i in t['items'] if i['status']=='UNRESOLVED']
        if unknown:lines+=['**Chưa quy đổi — dòng gốc để đối chiếu, không phải định lượng cho khẩu phần mới:**',*unknown]
        lines+=['Chỉ quy đổi cùng đơn vị, không suy ra khối lượng từ trái/con hoặc muỗng. Chưa tạo lại toàn bộ bước nấu cho khẩu phần mới; không tự nhân thời gian nấu.']
        return '\n\n'.join(lines)
    if mode=='full':return NOTICE+'\n\n'+text
    if mode in ('ingredients','prep','steps'):
        span=doc['sections'].get(mode)
        if not span:raise ValueError('Missing requested section')
        part=text[span['start']:span['end']].strip()
    elif mode=='time':
        part='\n'.join(line for line in text.splitlines() if re.search(r'\d+\s*(phút|giờ)',line,re.I))
        if not part:raise ValueError('No time evidence')
        part='Các mốc thời gian ghi trong công thức (chưa có tổng thời gian được xác nhận):\n'+part
    elif mode=='step':
        selection=value['selector']
        if not isinstance(selection,dict) or set(selection)!={'start','end'}:raise ValueError('Invalid step span')
        start,end=selection['start'],selection['end']
        if type(start) is not int or type(end) is not int or not 0<=start<end<=len(text):raise ValueError('Invalid offsets')
        # Only an existing complete bullet or named cooking subsection is selectable.
        if selection not in step_spans(row):raise ValueError('Not a source step')
        part=text[start:end].strip()
    else:raise ValueError('Unsupported view mode')
    serving=f"\n\nPhần trích nguyên văn công thức gốc cho {doc['base_portions']} người; khẩu phần đang giữ là {value['target_portions']} người. Chưa tự viết lại định lượng trong bước nấu." if value['target_portions'] and value['target_portions']!=doc['base_portions'] else ''
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

def find_recipe(question,recipes):
    from backend.chatbot.doi_chieu import ten_mon_tu_cau_hoi
    q=normalize(question);matches=[]
    for recipe in recipes:
        alias=ten_mon_tu_cau_hoi(recipe.cau_hoi)
        alias=re.sub(r'\s+cho\s+(?:gion|ngon|thom|ngot|mem|dam|beo|khong|vua)\b.*$','',alias)
        alias=re.sub(r'\s+(?:sao|vay|nghen|ne)$','',alias)
        alias=re.sub(r'^do\s+','',alias)
        aliases={alias,re.sub(r'\s+(?:kieu\s+)?mien tay$','',alias)}
        for name in aliases:
            if len(name.split())>=2 and re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',q):matches.append((len(name.split()),recipe))
    if not matches:return None
    best=max(n for n,_ in matches);items={r.id_goc:r for n,r in matches if n==best}
    return next(iter(items.values())) if len(items)==1 else None

def limitation(code,topic=None):
    return dict(loai='ngoai_pham_vi' if code=='OUT_OF_SCOPE' else 'khong_chac',reason_code=code,cau_tra_loi=REASONS[code],nguon=[],goi_y=[],doan_truy_hoi=[],chu_de=topic,giai_thich={})

def route(payload,manifest,ledger):
    """Called inside the existing LCEL answer node, only for opt-in policy v4."""
    from backend.chatbot.cong_thuc import danh_muc
    from backend.chatbot.ngon_ngu import khoa_cau_hoi, khang_dinh
    q=normalize(payload['question']);state=payload['state'];kho=payload['kho']
    if any(khoa_cau_hoi(payload['question'])==khoa_cau_hoi(r['question']) and not r['allowed_for_answer'] for r in ledger.values()):return limitation('HELD_HEALTH')
    if re.search(r'^(?:chao ban|xin chao)\b',q):return dict(loai='chao_hoi',cau_tra_loi='Mình là trợ lý nấu ăn. Bạn muốn xem công thức món nào?',nguon=[],goi_y=[],doan_truy_hoi=[],chu_de=None,giai_thich={})
    if re.search(r'^(?:cam on|cam on ban|tam biet)\b',q):return None
    if re.search(r'\b(ngan hang|co phieu|la ma|lap trinh|ma python|bong da|chinh tri)\b',q):return limitation('OUT_OF_SCOPE')
    if state.get('tinh_trang_suc_khoe') or re.search(r'\b(?:bi|dang|khi)\s+(?:cam|ho|sot)\b|\bkinh nguyet\b|\bthuoc\b',khang_dinh(q)) or re.search(r'\b(chua khoi|chua benh|ke thuoc|uong thuoc)\b',q):return limitation('HELD_HEALTH')
    if re.search(r'\b(kcal|calo|protein|lipid|carbohydrate|natri|vitamin|chat dam|chat beo|giau dam|it natri|dinh duong)\b',q):return limitation('MISSING_NUTRITION',state.get('mon_hien_tai'))
    recipes=danh_muc(kho);recipe=find_recipe(payload['question'],recipes)
    prior=state.get('mon_hien_tai')
    follow=bool(re.search(r'\b(mon do|mon nay|cong thuc do|khau phan hien tai|(?:cho|thanh|con) \d+ (?:nguoi|phan)|doi (?:thanh|con)|hien tai)\b',q))
    if not recipe and prior and (follow or re.search(r'\b(nguyen lieu|so che|cac buoc|nguon|bo|giam|thay|khau phan)\b',q)):
        recipe=next((r for r in recipes if r.id_goc==prior['id_goc']),None)
    if not recipe:
        if re.search(r'\b(cong thuc|cach (?:nau|lam)|huong dan|bay .*nau)\b',q):return limitation('MISSING_DISH',prior)
        return None
    row=ledger[recipe.id_goc];topic=dict(id_goc=row['id'],cau_hoi=row['question'])
    target=re.search(r'\b(?:cho|khau phan|thanh|con)\s+(\d+)\s*(?:nguoi|phan)\b',q)
    if target:
        if not 1<=int(target[1])<=100:return limitation('MODIFICATION_UNSUPPORTED',topic)
        state['khau_phan']=int(target[1])
    removing=re.sub(r'\bkhong (?:bo|giam|thay)\b','giu nguyen',q)
    modification=bool(re.search(r'(?<!toan )(?<!bun )(?<!thit )\bbo\s+|\b(giam|thay bang|thay the|khong dung|khong them|khong co)\b|\bthay\s+.+?\s+bang\b',removing))
    dk=state['dieu_kien']
    if re.search(r'\b(nguon|chung cu|bai goc|verified)\b',q):
        result=limitation('SOURCE_UNVERIFIED',topic);result['nguon']=[reference(row)];return result
    pending=state.get('pending_ingredient_change')
    if pending and pending['recipe_id']==row['id'] and re.search(r'\b(giu nguyen|cong thuc goc|huy yeu cau)\b',q):
        state.pop('pending_ingredient_change',None);pending=None
    if pending and pending['recipe_id']==row['id']:
        return limitation('MODIFICATION_UNSUPPORTED',topic)
    if modification or dk.get('chua_ro') or dk.get('loai_tru') or dk.get('an_chay'):
        result=limitation('MODIFICATION_UNSUPPORTED',topic)
        result['adjustment_request']=adjustment_request(row,payload['question'])
        if re.search(r'(?<!toan )\bbo\s+|\b(giam|khong dung|khong them)\b',removing):
            state['pending_ingredient_change']=dict(recipe_id=row['id'],source_version=row['answer_sha256'],status='NOT_APPLIED',request=result['adjustment_request'])
        return result
    mode='full';selector=None
    if target or re.search(r'\b(khau phan|may nguoi|bao nhieu nguoi)\b',q):mode='portion'
    elif re.search(r'\b(bao lau|thoi gian|may phut)\b',q):mode='time'
    elif re.search(r'\b(nguyen lieu|gia vi|can mua gi)\b',q) and not re.search(r'\b(cac buoc|cach nau|tu dau|toan bo|day du)\b',q):mode='ingredients'
    elif re.search(r'\b(so che|lam sach|khu tanh)\b',q):mode='prep'
    elif re.search(r'\b(cac buoc|cac buoc nau|cac buoc che bien)\b',q) and not re.search(r'\b(tu dau|toan bo|tron mon)\b',q):mode='steps'
    else:
        step_request=re.search(r'\b(buoc \d+|uop|luoc|xao|nau nuoc)\b',q)
        if step_request:
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
        value=view(row,mode,state.get('khau_phan'),selector)
        if mode=='portion':state['khau_phan']=value['transform']['target_portions']
        render_view(row,value)
    except (ValueError,ZeroDivisionError):return limitation('MISSING_RECIPE',topic)
    return dict(loai='tra_loi',cau_tra_loi='',nguon=[reference(row)],goi_y=[],doan_truy_hoi=[],chu_de=topic,giai_thich={'nhom_nguon':row['group_folder']},structured_view=value,reason_code='SOURCE_UNVERIFIED')

def enforce(result,manifest,ledger):
    from backend.chatbot.knowledge_policy import allowed,limited
    r=copy.deepcopy(result)
    ids=[s['id_goc'] for s in r.get('nguon',[])]+[s['id_goc'] for s in r.get('doan_truy_hoi',[])]
    if r.get('chu_de'):ids.append(r['chu_de']['id_goc'])
    if any(not allowed(ledger,i) for i in ids):return limited(r)
    if r.get('structured_view'):
        value=r['structured_view'];row=ledger.get(value.get('recipe_id'))
        try:
            if not row or not row['allowed_for_answer'] or set(ids)!={row['id']}:raise ValueError('Wrong source/view')
            r['cau_tra_loi']=render_view(row,value);r['nguon']=[reference(row)]
        except (ValueError,KeyError,TypeError,ZeroDivisionError):
            r=limitation('VALIDATION_FAILED')
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
    titles={x['question'] for x in ledger.values() if x['allowed_for_answer']}
    r['goi_y']=[q for q in r.get('goi_y',[]) if q in titles]
    r.setdefault('giai_thich',{})['knowledge_build_id']=manifest['build_id']
    return r
