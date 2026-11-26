"""Replay recipe derivatives against source-bound ingredient/step rules."""
from datetime import datetime, timezone
from fractions import Fraction
import re

from backend.chatbot.recipe_views_v5 import (
    NOTICE, PORTION_CHANGE, PORTION_WORDS, document, normalize, reference,
    ingredient_components, parse_quantity_component, view, confirm_base, validate_transform,
)

# A rule is valid only for the exact source revision listed in SOURCE_VERSIONS.
# Replacements in step rules preserve the source's action order.
RULES = {
    41: {
        'nuoc mam': ('Nước mắm', '1', 'muỗng canh', (
            ('1 muỗng canh nước mắm, ', ''),
            (', cá lóc chấm thêm nước mắm là ngon nhất.', '.'))),
        'tieu': ('Tiêu', '1/2', 'muỗng canh', ((' và 1/2 muỗng canh tiêu', ''),)),
    },
    42: {
        'nuoc mam': ('Nước mắm', '2', 'thìa', (('2 thìa nước mắm, ', ''),)),
        'tieu': ('Tiêu xay', '1', 'thìa nhỏ', (('1 thìa nhỏ tiêu và ', ''),)),
        'hat nem': ('Hạt nêm', '1', 'thìa nhỏ', ((' và 1 thìa nhỏ hạt nêm', ''),)),
    },
    220: {
        'toi': ('Tỏi', '4', 'tép', (('- Tỏi bóc vỏ, đập dập', ''),
            ('đợi dầu nóng cho tỏi vào phi vàng thơm', 'đợi dầu nóng'))),
        'dau an': ('Dầu ăn', '2', 'muỗng canh', ()),
        'tieu': ('Tiêu xay', None, None, ((', rắc thêm chút tiêu xay', ''),)),
        'hat nem': ('Hạt nêm', '2', 'muỗng cà phê', (('2 muỗng cà phê hạt nêm, ', ''),)),
        'bot ngot': ('Bột ngọt', '1/2', 'muỗng cà phê', ((', 1/2 muỗng cà phê bột ngọt', ''),)),
    },
    230: {
        'toi': ('Tỏi', '3', 'tép', (('- Tỏi bóc vỏ, đập nát rồi băm nhỏ', ''),
            (', phi tỏi băm đến khi thơm', ''))),
        'dau an': ('Dầu ăn', '2', 'muỗng canh', ()),
        'tieu': ('Tiêu', None, None, ()),
        'hat nem': ('Hạt nêm', '2', 'muỗng cà phê', (('2 muỗng cà phê hạt nêm, ', ''),)),
        'bot ngot': ('Bột ngọt', '1/2', 'muỗng cà phê', ((', 1/2 muỗng cà phê bột ngọt', ''),)),
    },
    288: {'toi': ('Tỏi','3','tép', (('- Tỏi lột vỏ đập dập rồi băm nhuyễn',''),
                                    (', phi tỏi băm thơm vàng',''))),
          'dau an': ('Dầu ăn','2','muỗng canh', ())},
}
SCALE = {42, 220, 230}
REPLACEMENT = {44: ('bia', 'nuoc khoang co ga', 'Bia hoặc nước khoáng có ga',
                    'Nước khoáng có ga', '500', 'ml', 'nước có ga')}
ALIASES = {'tieu xay':'tieu', 'hat tieu':'tieu', 'mi chinh':'bot ngot', 'dau':'dau an', 'bot nem':'hat nem',
           'nuoc co ga':'nuoc khoang co ga', 'nuoc khoang co ga':'nuoc khoang co ga'}
SOURCE_VERSIONS = {41: 'c81d3ad7f2421a626db0482bab7d30b084a2c702358be674de9afb484924bcc4', 42: '85075ef09166ee84aaad8def6eeedba0dd2927255f24532996359d5fa45884d7', 44: '76307958c4b828ccd28db9532277fde53db10d5700047abed647a06cbff487b8', 220: '5d24c83052f26056f0437a1c8c3564f40ea4e9673858ef0047afdaaec4c77b9e', 230: '2596a4d8857dc8330adbe4c7de13c50f8d9f2509692c78001e32cf9abb4f79dd', 288: 'c1336e94e0de232520b890eaaff621f7451c1cdbdc83cc3b92c9ed44dacd0f48'}
NOUNS = r'nuoc khoang co ga|nuoc co ga|nuoc mam|tieu xay|hat tieu|hat nem|bot nem|bot ngot|mi chinh|dau an|hanh tim|hanh la|ngo ri|ngo gai|rau ram|hung que|thit heo|thit ga|la chuoi|nuoc tuong|muoi|duong|tieu|dau|toi|bia|ngheu|nam|thit|trung'
AMOUNT = r'\d+(?:[.,]\d+|/\d+)?|' + '|'.join(PORTION_WORDS)
UNIT = r'muong ca phe|muong canh|thia ca phe|thia canh|thia nho|muong nho|muong|thia|kg|mg|g|ml|lit|tep|qua|trai|cui?'
STEP_QTY = re.compile(r'(?<![\w/])(\d+(?:[.,]\d+|/\d+)?) (muỗng cà phê|muỗng canh|thìa nhỏ|thìa) (nước mắm|nước màu|hạt nêm|tiêu(?: xay)?|bột ngọt|dầu ăn)',re.I)
NAME = re.compile(r'\b('+NOUNS+r')\b')


def number(s):
    return Fraction(PORTION_WORDS[s] if s in PORTION_WORDS else s.replace(',','.'))


def match_name(q):
    m=NAME.search(q)
    return ALIASES.get(m[1],m[1]) if m else None


def operation(q):
    """Return a typed, JSON-safe command, or None to let the existing router run."""
    if re.search(r'\b(?:thoi khong doi nua|huy yeu cau|thoi dung doi)\b',q):
        return {'kind':'cancel'}
    if re.search(r'\b(?:quay ve|tro ve|dat lai|khoi phuc) (?:ban |cong thuc )?(?:ban dau|goc)',q):
        return {'kind':'reset'}
    if re.search(r'\bhoan tac\b',q):
        return {'kind':'undo','name':match_name(q)}
    if re.search(r'\b(?:khong (?:bo|giam|thay)|dung (?:bo|giam|thay))\b',q):
        return {'kind':'cancel'}
    combined=re.search(r'\bviet lai.{0,32}\bsau khi bo (.+)',q)
    if combined:
        return {'kind':'remove','name':match_name(combined[1])}
    if re.search(r'\b(?:viet lai|cong thuc .{0,20}sua lai|xem lai (?:cong thuc|cach nau)(?: hien tai)?)\b',q):
        return {'kind':'rewrite'}
    if re.search(r'\bthay (?:luon|di)\b',q):
        return {'kind':'confirm'}
    if re.search(r'\b(?:thay|thay the|khong co)\b',q):
        m=re.search(r'\bdung (.+?) thay(?: cho)? (.+)',q)
        if m:
            old,new=match_name(m[2]),match_name(m[1])
        else:
            m=re.search(r'\b(?:thay(?: the| luon)?|khong co) (.+?) (?:bang|thanh) (.+)',q)
            old,new=(match_name(m[1]),match_name(m[2])) if m else (match_name(q),None)
        return {'kind':'replace_proposal' if re.search(r'\b(duoc khong|bang gi|gi khac)\b',q) or not new else 'replace',
                'name':old,'new':new}
    if re.search(r'^(?:(?:co the|toi muon|minh muon) )?(?:cho them|them vao)\s+\S',q):
        return {'kind':'add'}
    m=re.search(r'\bchia (?:me (?:nay|do) )?(?:thanh|ra) ('+AMOUNT+r')\s*phan\b',q)
    if m:
        return {'kind':'divide','count':int(number(m[1]))}
    m=re.search(PORTION_CHANGE,q) or re.search(r'\b(?:nau|cho ca nha|giam xuong) ('+AMOUNT+r')\s*(?:phan|nguoi)\b',q)
    if m and 1<=number(m[1])<=100 and number(m[1]).denominator==1:
        return {'kind':'scale','count':int(number(m[1]))}
    # “Bỏ cuống” and other directions in a recipe title aren't editing commands.
    m=re.match(r'^(?:(?:toi|minh|tui|em) )?(?:bo|loai|dung cho|khong (?:an|dung|them|cho))\s+(.+)',q)
    if m:
        return {'kind':'remove','name':match_name(m[1])}
    m=re.search(r'\b(?:giam|bot|cho it|dung it|cho nua|dung .+ thoi)\b',q)
    if not m:return None
    tail=q[m.start():]
    name=match_name(tail)
    amount=re.search(r'\b('+AMOUNT+r')\s+('+UNIT+r')\b',tail)
    percent=re.search(r'\b(\d+(?:[.,]\d+)?)\s*%',tail)
    anchor='base' if re.search(r'\b(?:ban dau|luong goc|cong thuc goc)\b',tail) else 'current'
    if amount:
        return {'kind':'set','name':name,'value':str(number(amount[1])),'unit':amount[2]}
    if percent or re.search(r'\b(?:mot nua|nua luong)\b',tail):
        fraction=1-number(percent[1])/100 if percent else Fraction(1,2)
        if percent and re.search(r'\bcon\s+\d',tail):fraction=1-fraction
        return {'kind':'fraction','name':name,'value':str(fraction),'anchor':anchor}
    return {'kind':'quantity_clarify','name':name}


def combined_operations(q):
    clauses = re.split(r'\s*;\s*|,\s+(?!\d)|\s+(?:roi|va)\s+(?=(?:bo|bot|giam|thay|nau cho|doi|chia)\b)',q)
    if len(clauses)!=2:
        return None
    commands = [operation(part) for part in clauses]
    if all(cmd and cmd['kind'] in ('set','fraction','remove','replace','scale','divide')
           for cmd in commands):
        return commands
    return None


def canon_unit(u):
    return normalize(u).replace('muong','thia')


def ingredient_plan(row):
    doc=document(row)
    items=[]
    for i in ingredient_components(doc):
        text=i['text']
        text=re.sub(r'^Gia vị\s*','',text,flags=re.I)
        if not text:continue
        m=parse_quantity_component(text)
        if not m:
            m=re.fullmatch(r'(.+?)\s+(\d+(?:[.,]\d+|/\d+)?)\s*(muỗng cà phê|muỗng canh|thìa cà phê|thìa nhỏ|thìa|muỗng)',text,re.I)
        name=m[1] if m else re.sub(r'\s+(?:vừa đủ|một ít|tùy chọn)$','',text,flags=re.I)
        key=ALIASES.get(normalize(name),normalize(name))
        if key=='tieu xay':key='tieu'
        items.append(dict(start=i['start'],end=i['end'],raw=text,name=name,key=key,
                          quantity=str(number(m[2])) if m else None,unit=m[3] if m else None))
    # Quantities can be explicitly supplied by a step where the ingredient line is qualitative.
    for item in items:
        rule=RULES.get(row['id'],{}).get(item['key'])
        if rule and rule[1] and not item['quantity']:
            item.update(quantity=rule[1],unit=rule[2])
    return doc,items


def section_lines(row, doc):
    return [(key, line.strip()) for key in ('prep','steps','finish') if key in doc['sections']
            for line in row['answer_text'][doc['sections'][key]['start']:doc['sections'][key]['end']].splitlines()[1:]
            if line.strip()][:80]


def _replay_v1(row, events):
    if row['answer_sha256']!=SOURCE_VERSIONS.get(row['id']):
        raise ValueError('source revision')
    if len(events)>40:raise ValueError('too many events')
    doc,items=ingredient_plan(row)
    rules=RULES.get(row['id'],{})
    by_name={i['key']:i for i in items}
    anchor={key:Fraction(i['quantity']) for key,i in by_name.items() if i['quantity']}
    quantities=anchor.copy()
    basis=doc['base_portions'];portions=basis
    removed=set(); replaced=False; scaled=Fraction(1)
    active=[i for i,e in enumerate(events) if e['command']['kind'] not in ('undo','reset')]
    for i,e in enumerate(events):
        mode=e['command']['kind']
        if mode=='reset':active=[j for j in active if j>i]
        elif mode=='undo':
            target=e['command']['index']
            if type(target) is not int or target>=i or target not in active:raise ValueError('undo target')
            active.remove(target)
    affected={}
    for i in active:
        cmd=events[i]['command'];op=cmd['kind'];key=cmd.get('name')
        if op=='scale':
            count=cmd['count']
            if row['id'] not in SCALE or type(count) is not int or not 1<=count<=100:raise ValueError('scale')
            factor=Fraction(count,basis)
            quantities={k:v*factor for k,v in quantities.items()}
            scaled*=factor
            basis=portions=count
        elif op=='divide':
            count=cmd['count']
            if not basis or type(count) is not int or not 1<=count<=100:raise ValueError('divide')
            portions=count
        elif op=='replace':
            rule=REPLACEMENT.get(row['id'])
            if not rule or (key,cmd.get('new'))!=rule[:2] or replaced:raise ValueError('replacement')
            replaced=True
        elif op=='remove':
            if key not in rules or key not in by_name or key in removed or (key=='dau an'):
                raise ValueError('essential or unknown')
            removed.add(key)
        elif op in ('fraction','set'):
            if key not in rules or key not in quantities or key in removed:raise ValueError('unknown amount')
            if op=='fraction':
                ratio=Fraction(cmd['value'])
                if not 0<ratio<1 or cmd['anchor'] not in ('base','current'):raise ValueError('invalid ratio')
                after=(anchor if cmd['anchor']=='base' else quantities)[key]*ratio
            else:
                after=Fraction(cmd['value'])
                unit=canon_unit(rules[key][2])
                if canon_unit(cmd['unit']) not in (unit, 'thia') or (canon_unit(cmd['unit'])=='thia' and not unit.startswith('thia')):
                    raise ValueError('different unit')
            limit=anchor[key] if op=='fraction' and cmd['anchor']=='base' else quantities[key]
            if not 0<after<=limit:raise ValueError('invalid reduction')
            quantities[key]=after
        else:raise ValueError('unknown operation')
        affected[i]=key
    if len(removed & {'nuoc mam','hat nem','tieu'})>=2 and row['id']==42:
        # Combined deletions require handling the punctuation and the empty marinade separately.
        raise ValueError('combined marinade')
    if {'hat nem','bot ngot'}<=removed and row['id'] in (220,230):
        raise ValueError('combined seasoning')
    steps=[]
    for index,(section,original) in enumerate(section_lines(row,doc)):
        line=original
        # Descriptive sign-offs are kept in the base record, outside the operational plan.
        if section=='finish' and re.search(r'\b(chuc ban|vay la xong)\b',normalize(line)) and not line.startswith(('-', '•')):
            continue
        for key in removed:
            for old,new in rules[key][3]:
                if old in line:line=line.replace(old,new)
            if line.endswith(', trong 15 phút'):line=line.replace(', trong 15 phút',' trong 15 phút')
        if replaced:
            original_name=REPLACEMENT[row['id']][6]
            line=line.replace(original_name,'nước khoáng có ga')
        if quantities or scaled!=1:
            def step_quantity(m):
                value,unit,words=m.groups()
                k=match_name(normalize(words))
                if k in rules and k in quantities and canon_unit(unit)==canon_unit(rules[k][2]) and Fraction(value)==Fraction(rules[k][1]):
                    return f'{quantities[k]} {unit} {words}'
                if scaled!=1:return f'{number(value)*scaled} {unit} {words}'
                return m[0]
            line=STEP_QTY.sub(step_quantity,line)
        normalized=normalize(line)
        if any(re.search(r'\b'+re.escape(key)+r'\b',normalized) for key in removed):
            raise ValueError('remaining removed ingredient')
        if line:
            steps.append(dict(id=index,section=section,text=line,original=original,changed=line!=original))
        elif original:
            steps.append(dict(id=index,section=section,text='',original=original,changed=True))
    new_items=[]
    for item in items:
        key=item['key']
        if key in removed:continue
        if replaced and normalize(item['name'])=='bia hoac nuoc khoang co ga':
            item={**item,'name':REPLACEMENT[row['id']][3],'quantity':'500','unit':'ml'}
        elif key in quantities:
            item={**item,'quantity':str(quantities[key])}
        new_items.append(item)
    if replaced and not any(i['name']==REPLACEMENT[row['id']][3] for i in new_items):
        raise ValueError('replacement source missing')
    if not new_items or not any(s['section']=='steps' and s['text'] for s in steps):
        raise ValueError('missing operational plan')
    return dict(items=new_items,steps=steps,portions=portions,base_range=doc['base_range'],
                active=active, scale=str(scaled), changed=bool(active), removed=sorted(removed),
                replaced=replaced, source_status=row['source_verification'])


def replay(row, events):
    if row['id'] in SOURCE_VERSIONS:
        try:
            return _replay_v1(row, events)
        except ValueError:
            # Existing reviewed recipes retain their established behavior. New
            # operations can proceed if the source can be bound by the shared rules.
            pass
    from backend.chatbot.recipe_bindings_v2 import replay as replay_bindings
    if len(events)>40:raise ValueError('too many events')
    active=[]
    for index,event in enumerate(events):
        cmd=event['command']
        if cmd['kind']=='reset':
            active.clear()
        elif cmd['kind']=='undo':
            if type(cmd['index']) is not int or cmd['index'] not in active:
                raise ValueError('undo target')
            active.remove(cmd['index'])
        else:
            active.append(index)
    return replay_bindings(row,events,active)


def text_for(row, events, aspect=None):
    plan=replay(row,events)
    if plan.get('model')=='source_bindings_v2':
        from backend.chatbot.recipe_bindings_v2 import parse_items
        original_names={i['key']:i['name'] for i in parse_items(document(row))}
    else:
        original_names={k:v[0] for k,v in RULES.get(row['id'],{}).items()}
    portions=(str(plan['portions']) if plan['portions'] is not None
              else '–'.join(map(str,plan['base_range'])) if plan['base_range'] else 'chưa rõ')
    if aspect=='servings':
        return f'{NOTICE}\n\nPhiên bản hiện tại giữ **{portions} phần**.',plan
    if aspect not in (None,'ingredients'):raise ValueError('Unsupported derivative aspect')
    out=[NOTICE, f"**{row['question']} — bản dẫn xuất v{len(events)}**",
         f"**Khẩu phần** {portions}", '**Nguyên liệu**']
    for item in plan['items']:
        out.append('- '+(f"{item['role']} — " if item.get('role') else '')+(f"{item['name']}: {item['quantity']} {item['unit']}" if item['quantity'] else item['raw']+(' (dòng gốc, chưa quy đổi)' if plan['scale']!='1' else ' (chưa đủ định lượng)')))
    if aspect=='ingredients':return '\n'.join(out),plan
    if row['id']==44:
        out+=['', 'Nguồn có nhắc gia vị ướp và hành phi trong bước nấu nhưng chưa ghi đủ định lượng riêng. Các bước này được giữ theo nguồn để đối chiếu.']
    if row['id']==41:
        out+=['', 'Nguồn có dùng nước trong bước dằm me và nấu; xem lượng ghi ngay tại bước.']
    for key,title in [('prep','Sơ chế'),('steps','Cách chế biến'),('finish','Hoàn thành món ăn')]:
        lines=[s['text'] for s in plan['steps'] if s['section']==key and s['text']]
        if lines:out+=['',f'**{title}**',*lines]
    edited=[events[i] for i in plan['active'] if events[i]['command']['kind'] in ('set','fraction')]
    if edited:
        out+=['','**Đã chỉnh định lượng** '+', '.join(dict.fromkeys(original_names[e['command']['name']] for e in edited))+'.']
    if plan['removed']:
        out+=['','**Đã bỏ** '+', '.join(original_names[k] for k in plan['removed'])+
               '. Giữ phần đã bỏ ngoài cả bước nêm lại; kiểm tra thành phần của gia vị pha sẵn.']
    if plan['scale']!='1':
        out+=['',f"**Hệ số nguyên liệu** {plan['scale']}. Giữ mốc thời gian nguồn để tham khảo; kiểm tra độ chín theo điều kiện bếp."]
    if any(events[i]['command']['kind']=='divide' for i in plan['active']):
        out+=['','Chia cùng mẻ đã nấu; không tăng lượng nguyên liệu.']
    if plan.get('substitutions'):
        from backend.chatbot.recipe_alternatives import NAMES
        out+=['','Lựa chọn ghi trong công thức gốc: '+', '.join(NAMES[x['chosen']] for x in plan['substitutions'])+'.']
    elif plan['replaced']:
        out+=['','Dùng nước khoáng có ga theo lựa chọn đã ghi ngay trong công thức gốc.']
    out+=['', 'Dinh dưỡng của bản dẫn xuất cần hồ sơ riêng đã duyệt.']
    return '\n'.join(out),plan


def base_edit(row,state):
    previous=(state.get('recipe_edits_v1') or {}).get(str(row['id']),state.get('recipe_edit_v1'))
    if previous and previous.get('id')==row['id'] and previous.get('base')==row['answer_sha256']:
        return previous
    return {'id':row['id'],'base':row['answer_sha256'],'events':[],'pending':None}


def save_edit(state,edit):
    state.setdefault('recipe_edits_v1',{})[str(edit['id'])]=edit
    state['recipe_edit_v1']=edit


def append_event(row,events,cmd):
    before=replay(row,events)
    record=dict(command=cmd, timestamp=datetime.now(timezone.utc).isoformat(), basis='USER_REQUEST_AND_SOURCE_RULE',
                status='APPLIED')
    new=events+[record]
    after=replay(row,new)
    old_by={i['key']:(i['quantity'],i['unit']) for i in before['items']}
    new_by={i['key']:(i['quantity'],i['unit']) for i in after['items']}
    record.update(before={k:list(v) for k,v in old_by.items() if new_by.get(k)!=v},
                  after={k:list(v) for k,v in new_by.items() if old_by.get(k)!=v},
                  portions_before=before['portions'],portions_after=after['portions'],
                  affected_steps=[b['id'] for a,b in zip(before['steps'],after['steps']) if a['text']!=b['text']])
    return new


MESSAGES={
 'EDIT_AMBIGUOUS_PORTIONS':'Nguồn chưa ghi một khẩu phần gốc duy nhất. Bạn hãy xác nhận mốc gốc trong khoảng nguồn trước khi quy đổi.',
 'EDIT_NEED_DISH':'Bạn muốn chỉnh công thức món nào?',
 'EDIT_NEED_QUANTITY':'Bạn muốn giảm nguyên liệu nào, còn bao nhiêu và theo đơn vị nào? Mình chưa áp dụng thay đổi.',
 'EDIT_NEED_REPLACEMENT':'Bạn muốn thay bằng nguyên liệu nào? Mình cần lựa chọn đã có căn cứ trong công thức trước khi áp dụng.',
 'EDIT_SOURCE_OPTION_PROPOSED':'Mình tìm được một lựa chọn được ghi cùng vai trò trong công thức gốc. Mình chưa áp dụng. Bạn có thể nói “Thay luôn đi” để chọn phương án này.',
 'EDIT_REPLACEMENT_PROPOSED':'Công thức có ghi bia hoặc nước khoáng có ga cho cùng phần bột. Nếu bạn muốn dùng lựa chọn nước khoáng có ga, hãy nói “Thay luôn đi”. Mình chưa áp dụng.',
 'EDIT_ADD_UNSUPPORTED':'Công thức hiện tại chưa có căn cứ về lượng và cách nấu khi thêm nguyên liệu này. Mình giữ phiên bản đang dùng.',
 'EDIT_ALLERGY_UNCONFIRMED':'Mình chưa thể xác nhận các thành phần và phương án điều chỉnh đáp ứng điều kiện dị ứng bạn đã nêu.',
 'EDIT_UNSUPPORTED':'Nguồn hiện chưa đủ căn cứ để đổi lượng hoặc sửa các bước an toàn cho yêu cầu này. Phiên bản hiện tại được giữ nguyên.',
 'EDIT_NO_UNDO':'Mình chưa tìm thấy thao tác đã áp dụng phù hợp để hoàn tác.',
 'EDIT_CANCELLED':'Mình giữ phiên bản hiện tại và hủy yêu cầu đang chờ.',
 'EDIT_NUTRITION_BLOCKED':'Phiên bản đang dùng đã thay đổi lượng, nguyên liệu hoặc cách chia phần. Chưa có hồ sơ duyệt cho bản này để tính lại dinh dưỡng.',
}
def respond(code,topic=None):
    return dict(loai='khong_chac',reason_code=code,cau_tra_loi=MESSAGES[code],nguon=[],goi_y=[],doan_truy_hoi=[],chu_de=topic,giai_thich={})


def route_edit(question, state, row, cmd):
    topic={'id_goc':row['id'],'cau_hoi':row['question']}
    edit=base_edit(row,state)
    if cmd['kind'] in ('scale','divide') and not document(row)['base_portions']:
        return respond('EDIT_AMBIGUOUS_PORTIONS',topic)
    if not row.get('allowed_for_answer') or row.get('scope')!='IN_SCOPE':
        return respond('EDIT_UNSUPPORTED',topic)
    if state.get('di_ung') or state.get('di_ung_chua_ro'):
        return respond('EDIT_ALLERGY_UNCONFIRMED',topic)
    if state['dieu_kien'].get('an_chay'):
        return respond('EDIT_UNSUPPORTED',topic)
    events=edit['events']
    if cmd['kind']=='add':
        return respond('EDIT_ADD_UNSUPPORTED',topic)
    # A serving view may already have applied a portion change before the
    # derivative event stream starts. Import the validated scale exactly once.
    portion=state.get('portion_state_v5') or {}
    target=portion.get('target_applied')
    if (not events and cmd['kind'] not in ('cancel','reset','scale')
            and portion.get('recipe_id')==row['id']
            and portion.get('recipe_version')==row['answer_sha256']
            and type(target) is int and target!=document(row)['base_portions']):
        try:
            portion_view=view(row,mode='portion',target=target,confirmation=portion.get('base_confirmation'))
            validate_transform(row,portion_view['transform'])
            events=append_event(row,[],{'kind':'scale','count':target})
        except (ValueError,TypeError,KeyError,ZeroDivisionError):
            return respond('EDIT_UNSUPPORTED',topic)
    pending=edit['pending']
    op=cmd['kind']
    if op=='cancel':
        save_edit(state,{**edit,'pending':None})
        return respond('EDIT_CANCELLED',topic)
    if op=='confirm':
        if not pending or pending['kind']!='replace':return respond('EDIT_NEED_REPLACEMENT',topic)
        cmd=pending
        op=cmd['kind']
    if pending and pending['kind']=='quantity_clarify' and re.match(r'^(?:con|dung|cho)\s',normalize(question)):
        clarification=operation('giam '+normalize(question))
        if clarification and clarification['kind']=='set':
            cmd={**clarification,'name':pending['name']}
            op='set'
    if op in ('replace','replace_proposal') and (cmd.get('name') is None or cmd.get('new') is None) and op=='replace':
        return respond('EDIT_NEED_REPLACEMENT',topic)
    if op=='replace_proposal':
        rule=REPLACEMENT.get(row['id'])
        if rule and cmd['name']==rule[0] and cmd['new'] in (None,rule[1]):
            save_edit(state,{**edit,'pending':{'kind':'replace','name':rule[0],'new':rule[1]}})
            return respond('EDIT_REPLACEMENT_PROPOSED',topic)
        from backend.chatbot.recipe_alternatives import option
        offer=option(row,cmd.get('name'),cmd.get('new'))
        if offer:
            save_edit(state,{**edit,'pending':{'kind':'replace','name':cmd['name'],'new':offer['chosen']}})
            return respond('EDIT_SOURCE_OPTION_PROPOSED',topic)
        return respond('EDIT_NEED_REPLACEMENT',topic) if not cmd['new'] else respond('EDIT_UNSUPPORTED',topic)
    if op in ('set','fraction') and not cmd['name'] and pending and pending['kind']=='quantity_clarify':
        cmd={**cmd,'name':pending['name']}
    if op=='quantity_clarify' and cmd.get('name') and row['id'] not in SOURCE_VERSIONS:
        from backend.chatbot.recipe_bindings_v2 import parse_items
        matching=[i for i in parse_items(document(row)) if i['key']==cmd['name']]
        if len(matching)!=1:return respond('EDIT_UNSUPPORTED',topic)
    if op=='quantity_clarify' or (op in ('fraction','set') and not cmd['name']):
        save_edit(state,{**edit,'pending':{'kind':'quantity_clarify','name':cmd.get('name')}})
        return respond('EDIT_NEED_QUANTITY',topic)
    if op=='undo':
        try:
            candidates=[i for i in replay(row,events)['active'] if cmd['name'] in (None,events[i]['command'].get('name'))]
        except (ValueError,TypeError,KeyError,ZeroDivisionError):
            return respond('EDIT_UNSUPPORTED',topic)
        if not candidates:return respond('EDIT_NO_UNDO',topic)
        cmd={'kind':'undo','index':candidates[-1]}
    try:
        if op!='rewrite':
            events=append_event(row,events,cmd)
        _,plan=text_for(row,events)
    except (ValueError,TypeError,KeyError,ZeroDivisionError):
        return respond('EDIT_UNSUPPORTED',topic)
    save_edit(state,{**edit,'events':events,'pending':None})
    state.pop('nutrition_context',None)
    state.pop('pending_ingredient_change',None)
    state['khau_phan']=plan['portions']
    if not plan['changed']:
        state.pop('portion_state_v5',None)
        return dict(loai='tra_loi',reason_code='SOURCE_UNVERIFIED',cau_tra_loi='',nguon=[reference(row)],
                    goi_y=[],doan_truy_hoi=[],chu_de=topic,structured_view=view(row))
    return dict(loai='tra_loi',reason_code='EDIT_REWRITTEN' if op=='rewrite' else 'EDIT_APPLIED',
                cau_tra_loi='',nguon=[reference(row)],goi_y=[],doan_truy_hoi=[],chu_de=topic,
                structured_view=dict(mode='recipe_edit',recipe_id=row['id'],recipe_version=row['answer_sha256'],events=events,aspect=cmd.get('aspect')))


def active_for(row,state):
    if not row:return False
    events=base_edit(row,state)['events']
    if not events:return False
    try:return replay(row,events)['changed']
    except (ValueError,TypeError,KeyError,ZeroDivisionError):return True

