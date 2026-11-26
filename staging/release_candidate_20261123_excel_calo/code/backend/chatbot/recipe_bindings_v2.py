"""Source-bound ingredient and instruction bindings for recipe edits."""
from collections import Counter
from fractions import Fraction
import re
import unicodedata

from backend.chatbot.recipe_views_v5 import document, ingredient_components

OPTIONAL = {
    'tieu': ('tieu xay','tieu bot','hat tieu','tieu'),
    'hat nem': ('hat nem','bot nem'),
    'bot ngot': ('bot ngot','mi chinh'),
    'nuoc mam': ('nuoc mam',),
    'dau an': ('dau an',),
    'muoi': ('muoi',),
    'duong': ('duong', 'duong trang'),
}
REMOVABLE = {'tieu','hat nem','bot ngot','nuoc mam'}
UNITS = (r'muong ca phe|muong canh|thia ca phe|thia canh|muong nho|thia nho|'
         r'kg|mg|gram|gam|g|ml|lit|l|tep|qua|trai|cui|cu|nhanh|con|mieng|'
         r'bo|cay|la|goi|chen|to|muong|thia')
DECIMAL = r'\d+(?:[.,]\d+|/\d+)?'
QUALIFIER = r'vua du|vua an|mot it|mot chut|tuy chon|tuy y|tuy khau vi'
QUANTITY = re.compile(r'(?<![\w/.-])(?P<value>'+DECIMAL+r')\s*(?P<unit>'+UNITS+r')\b')
TRAILING_QTY = re.compile(r'(?P<name>.+?)\s+(?P<value>'+DECIMAL+r')\s*(?P<unit>'+UNITS+r')$')
RANGE_GUARD = re.compile(r'\b(?:khoang|gan|tu|den|uoc chung)\b|\d|[/()]')
ACTION = re.compile(r'\b(?:uop|nem|rac|them|cho|tron|pha|phi|thang|ngam|cha|rua|'
                    r'bao quan|len men|lam dong|lam no|lam nuoc cham|lam nuoc mam)\b')
FLAVOUR = {'uop','nem','rac','them','cho','tron'}
CRITICAL = re.compile(r'\b(?:bao quan|len men|dong lanh|ngam|cha|rua|thang|rim duong|'
                      r'lam dong|lam no|tao dong|lam nuoc cham|lam nuoc mam)\b')
HARD_SCALE = re.compile(r'\b(?:lam banh|cach u|len men|nuong|lo nuong|say|u bot|'
                        r'tao dong|dong khuon|bao quan|ngam chua|cach muoi|thang duong|chien|nhan thit|nhan tom)\b')
DISCRETE = {'trai','qua','bo','cay','la','goi','con'}
SEPARATOR = re.compile(r'\s*(?:,\s*(?:va\s+)?|\bva\s+)\s*')
LEFT_END = re.compile(r'(?:,\s*(?:va\s+)?|\bva\s+)$')


def fold(text):
    """One output character per source character so offsets remain valid."""
    return ''.join('d' if c in 'đĐ' else unicodedata.normalize('NFD',c.lower())[0] for c in text)


def frac(value):
    return Fraction(value.replace(',','.'))


def unit_key(unit):
    return {'gram':'g','gam':'g','l':'lit'}.get(fold(unit),fold(unit))


def ident(name):
    cleaned=fold(name).strip()
    return next((key for key,names in OPTIONAL.items() if cleaned in names),cleaned)


def exact_word(name):
    return r'(?<!\w)'+re.escape(name)+r'(?!\w)'


def ref_pattern(key):
    return re.compile('|'.join(exact_word(name) for name in OPTIONAL[key])) if key!='tieu' else re.compile(
        r'(?<!\w)(?:hat tieu|tieu xay|tieu bot|tieu)(?!\w|\s+(?:xanh|den|do|trang|so|hoa)\b)')


def parse_items(doc):
    parsed=[]
    for entry in ingredient_components(doc):
        raw=entry['text']
        label=re.match(r'^Gia vị\s*',raw,re.I)
        raw=raw[label.end():] if label else raw
        if not raw:continue
        q=fold(raw)
        item=TRAILING_QTY.fullmatch(q)
        name=raw[:item.end('name')] if item else re.sub(r'\s+(?:'+QUALIFIER+r')$', '', q)
        if not item:name=raw[:len(name)]
        if item and (RANGE_GUARD.search(fold(name)) or re.search(r'\bhoac\b',fold(name))):
            item=None
            name=raw
        qty=frac(item['value']) if item else None
        if qty is not None and qty<=0:
            item=None;qty=None;name=raw
        tag=entry['original_line']
        role='Ăn kèm' if re.match(r'^[-•]\s*Ăn kèm\s*:',tag,re.I) else ''
        parsed.append(dict(name=name,key=ident(name),quantity=str(qty) if qty is not None else None,
                           unit=raw[item.start('unit'):item.end('unit')] if item else None,
                           raw=raw,start=entry['start']+(label.end() if label else 0),end=entry['end'],
                           role=role))
    return parsed


def steps_for(row, doc):
    records=[]
    text=row['answer_text']
    for section in ('prep','steps','finish'):
        span=doc['sections'].get(section)
        if not span:continue
        part=text[span['start']:span['end']]
        offset=span['start']+len(part.splitlines(keepends=True)[0])
        for line in part.splitlines(keepends=True)[1:]:
            trimmed=line.strip()
            closing=section=='finish' and re.match(r'^(?:chuc ban|vay la (?:xong|da xong))\b',fold(trimmed))
            if trimmed and not closing:
                first=offset+len(line)-len(line.lstrip())
                records.append(dict(id=len(records),section=section,original=trimmed,text=trimmed,
                                    start=first,end=first+len(trimmed),changed=False))
            offset+=len(line)
    return records


def profile(row):
    if not row.get('allowed_for_answer') or row.get('scope')!='IN_SCOPE':
        raise ValueError('SOURCE_NOT_ALLOWED')
    doc=document(row)
    if not {'ingredients','steps'}<=doc['sections'].keys():
        raise ValueError('MISSING_INGREDIENT_OR_STEP_SECTION')
    items=parse_items(doc)
    steps=steps_for(row,doc)
    if not items or not any(s['section']=='steps' and s['text'].startswith(('-', '•')) for s in steps):
        raise ValueError('MISSING_USABLE_STEPS')
    return doc,items,steps


def list_item(q, names):
    scalar=QUANTITY.match(q)
    if scalar:q=q[scalar.end():].lstrip()
    q=re.sub(r'^(?:chut|mot chut|mot it|phan |it )\s*','',q)
    return any(re.match(exact_word(name),q) for name in names)


def removal(line, key, names):
    """Remove only a recognized flavor-list item or a stand-alone flavor step."""
    q=fold(line)
    refs=list(ref_pattern(key).finditer(q))
    if not refs:return line
    if len(refs)!=1 or CRITICAL.search(q):
        raise ValueError('UNBOUND_OR_CRITICAL_STEP_REFERENCE')
    m=refs[0]
    preceding=q[:m.start()]
    trailing=q[m.end():]
    quantities=[n for n in QUANTITY.finditer(preceding) if not preceding[n.end():].strip()]
    start=quantities[-1].start() if quantities else m.start()
    leading=re.search(r'\b(?:chut|mot chut|mot it|it)\s+$',q[:start])
    if leading:start=leading.start()
    prefix=q[:start]
    # Nearest governing action in the same sentence, including prep safety actions.
    # A previous independent sentence cannot authorize an edit.
    clause=re.split(r'[.!?]\s+(?=[-a-z])',prefix)[-1]
    verbs=list(ACTION.finditer(clause))
    if not verbs or verbs[-1][0] not in FLAVOUR:
        raise ValueError('UNBOUND_STEP_ROLE')
    if key=='nuoc mam' and re.search(r'\b(?:nuoc sot|nuoc cham|mam chua ngot)\b',clause+trailing):
        raise ValueError('SAUCE_OR_CORE_INGREDIENT')
    left=LEFT_END.search(prefix)
    right=SEPARATOR.match(trailing)
    if right and list_item(trailing[right.end():],names):
        return line[:start]+line[m.end()+right.end():]
    suffix_ok=not trailing.strip(' .!?,') or bool(re.match(
        r'\s*(?:,|[.!?]|vao\b|len\b|trong\s+\d|cho vua an\b|roi\b|de\b|thi\b)',trailing))
    if left and suffix_ok:
        # A preceding comma is safe only inside the same flavor list.
        between=clause[verbs[-1].end():]
        if re.search(r'\b(?:noi|chao|to|lua|sau do|tiep theo)\s*,\s*$',between):
            raise ValueError('AMBIGUOUS_LIST_BOUNDARY')
        return line[:left.start()].rstrip()+line[m.end():]
    if re.fullmatch(r'\s*[-•]?\s*(?:nem|rac|them|cho)\s*',prefix) and re.fullmatch(
            r'\s*(?:(?:vao|len tren|len mat|cho vua an|tuy khau vi)\s*)?[.!]?\s*',trailing):
        return ''
    raise ValueError('UNRESOLVED_STEP_LIST')


def ranges_for(step):
    q=fold(step)
    for m in QUANTITY.finditer(q):
        if re.search(r'(?:\d\s*[-–]\s*|\d\s+den\s+|\bkhoang\s+)$',q[:m.start()]) or re.match(
                r'\s*(?:[-–]\s*\d|den\s+\d)',q[m.end():]):
            yield m, None
        else:
            try:yield m,frac(m['value'])
            except ZeroDivisionError:yield m,None


def bound_amounts(step, items):
    """Link a quantity immediately before or after its uniquely parsed ingredient."""
    q=fold(step)
    names=sorted({(fold(i['name']),i['key']) for i in items if i['name']},key=lambda x:-len(x[0]))
    results=[]
    for m, val in ranges_for(step):
        matching=[]
        for name,key in names:
            variants=OPTIONAL.get(key,(name,))
            if any(re.match(exact_word(alias),q[m.end():].lstrip()) or
                   re.search(exact_word(alias)+r'\s*$',q[:m.start()]) for alias in variants):
                matching.append((len(name),key))
        tied={key for size,key in matching if size==max((n for n,_ in matching),default=0)}
        results.append((m,val,next(iter(tied)) if len(tied)==1 else None))
    return results


def edit_refs(key, item, lines):
    q=ref_pattern(key)
    refs=[s for s in lines if q.search(fold(s['text']))]
    if not refs:
        raise ValueError('NO_STEP_BINDING')
    if key=='dau an' and any(re.search(r'\b(?:chien|ngap dau|ran|quay)\b',fold(s['text'])) for s in lines):
        raise ValueError('OIL_AMOUNT_AFFECTS_COOKING_METHOD')
    if key=='duong' and any(re.search(r'\b(?:canh gian|thang duong|caramel|lam banh)\b',fold(s['text'])) for s in lines):
        raise ValueError('SUGAR_AMOUNT_AFFECTS_COOKING_METHOD')
    for step in refs:
        body=fold(step['text'])
        if CRITICAL.search(body) or (key=='nuoc mam' and re.search(r'\b(?:nuoc cham|nuoc sot)\b',body)):
            raise ValueError('AMBIGUOUS_OR_CRITICAL_ROLE')
    # Qualitative uses inherit the ingredient plan. Every explicit amount must be
    # a single total assignment with a compatible source quantity and unit.
    linked=[(s,m,value) for s in lines for m,value,k in bound_amounts(s['text'],[item]) if k==key]
    if len(linked)>1 or any(value!=frac(item['quantity']) or unit_key(m['unit'])!=unit_key(item['unit'])
                            for _,m,value in linked):
        raise ValueError('CONFLICTING_INGREDIENT_AMOUNT')
    return linked


def scale_amounts(lines, items, multiplier):
    # Reject batches that would leave an ambiguous quantity in an instruction.
    quantities={i['key']:i for i in items if i['quantity']}
    updates={}
    usage=Counter()
    for step in lines:
        edits=[]
        for m,value,key in bound_amounts(step['text'],items):
            item=quantities.get(key)
            if (item and value is not None and unit_key(m['unit'])==unit_key(item['unit'])
                    and value<=frac(item['quantity'])):
                usage[key]+=value
                if usage[key]>frac(item['quantity']):
                    raise ValueError('CONFLICTING_STEP_TOTAL')
                if unit_key(item['unit']) in DISCRETE and (value*multiplier).denominator!=1:
                    raise ValueError('FRACTIONAL_STEP_COUNT')
                edits.append((m.start('value'),m.end('value'),str(value*multiplier)))
            elif re.match(r'\s*(?:nuoc(?: loc)?|nuoc da)\b',fold(step['text'])[m.end():]) and re.search(
                    r'\b(?:rua|ngam|luoc)\b',fold(step['text'])):
                # Water used in a separate cleaning/blanching action stays fixed.
                if value is None:raise ValueError('UNBOUND_STEP_QUANTITY')
            elif m['unit'] in ('la','con','to','bo','cay','mieng') and not key:
                # Tokens such as “cắt 2 miếng” describe technique only.
                if not re.search(r'\b(?:cat|chia|khoi)\s*$',fold(step['text'])[:m.start()]):
                    raise ValueError('UNBOUND_STEP_QUANTITY')
            else:
                raise ValueError('UNBOUND_STEP_QUANTITY')
        updates[step['id']]=edits
    return updates


def patch(text, edits):
    for start,end,value in sorted(edits,reverse=True):
        text=text[:start]+value+text[end:]
    return text


def replay(row, events, active):
    doc,items,original=profile(row)
    instances=Counter(i['key'] for i in items)
    known={i['key']:i for i in items if instances[i['key']]==1}
    quantities={k:frac(v['quantity']) for k,v in known.items() if v['quantity']}
    anchor=quantities.copy()
    basis=portions=doc['base_portions']
    title=fold(row['question'])
    multiplier=Fraction(1)
    removed=set()
    changed=set()
    replacements={}
    for index in active:
        cmd=events[index]['command'];op=cmd['kind'];key=cmd.get('name')
        if op in ('scale','divide'):
            count=cmd['count']
            if not basis or type(count) is not int or not 1<=count<=100:
                raise ValueError('AMBIGUOUS_PORTIONS')
            portions=count
            if op=='scale':
                if HARD_SCALE.search(title) or any(HARD_SCALE.search(fold(s['text'])) for s in original) or not items[0]['quantity'] or any(
                    (not i['quantity'] and i['key'] not in OPTIONAL and not i['role']) or instances[i['key']]>1
                    for i in items if i['key'] not in removed):
                    raise ValueError('INCOMPLETE_BATCH_QUANTITIES')
                factor=Fraction(count,basis)
                multiplier*=factor;basis=count
                quantities={k:v*factor for k,v in quantities.items()}
                if any(unit_key(known[k]['unit']) in DISCRETE and v.denominator!=1
                       for k,v in quantities.items() if k not in removed):
                    raise ValueError('FRACTIONAL_COUNT')
        elif op=='remove':
            if key not in REMOVABLE or key not in known or key in removed or (ref_pattern(key).search(title) or (key=='nuoc mam' and re.search(r'\b(?:mam|kho quet)\b',title))):
                raise ValueError('TARGET_NOT_OPTIONAL_OR_UNRESOLVED')
            removed.add(key)
        elif op in ('fraction','set'):
            if key not in OPTIONAL or key not in quantities or key in removed:
                raise ValueError('NO_SINGLE_EXACT_TARGET_QUANTITY')
            if key=='nuoc mam' and re.search(r'\b(?:mam|kho quet)\b',title):
                raise ValueError('TARGET_IS_CORE')
            if key in ('muoi','duong') and (HARD_SCALE.search(title) or any(CRITICAL.search(fold(s['text'])) and ref_pattern(key).search(fold(s['text'])) for s in original)):
                raise ValueError('AMBIGUOUS_OR_CRITICAL_ROLE')
            if op=='fraction':
                ratio=frac(cmd['value'])
                if not 0<ratio<1 or cmd['anchor'] not in ('base','current'):raise ValueError('INVALID_RATIO')
                limit=(anchor if cmd['anchor']=='base' else quantities)[key]
                value=limit*ratio
            else:
                limit=quantities[key]
                value=frac(cmd['value'])
                if unit_key(cmd['unit'])!=unit_key(known[key]['unit']):raise ValueError('UNIT_MISMATCH')
            if not 0<value<=limit:raise ValueError('INVALID_REDUCTION')
            quantities[key]=value;changed.add(key)
        elif op=='replace':
            from backend.chatbot.recipe_alternatives import option
            offer=option(row,key,cmd.get('new'))
            if not offer or cmd.get('new')!=offer['chosen'] or offer['item']['start'] in replacements:
                raise ValueError('NO_SOURCE_ALTERNATIVE')
            replacements[offer['item']['start']]=offer
        else:
            raise ValueError('NO_SOURCE_ALTERNATIVE')
    remaining=[i for i in items if i['key'] not in removed]
    names={fold(i['name']) for i in items} | {a for aa in OPTIONAL.values() for a in aa}
    lines=[dict(s) for s in original]
    if replacements:
        from backend.chatbot.recipe_alternatives import NAMES
        for offer in replacements.values():
            label=NAMES[offer['chosen']]
            for index,start,end in offer['usages']:
                step=lines[index]
                step['text']=patch(step['text'],[(start,end,label[:1].upper()+label[1:] if start==2 else label)])
            item=next(i for i in remaining if i['start']==offer['item']['start'])
            item.update(name=label,key=offer['chosen'],quantity=offer['quantity'],unit=offer['unit'],
                        raw=label+' '+offer['amount'])

    for key in sorted(removed):
        if not any(ref_pattern(key).search(fold(s['text'])) for s in lines):
            raise ValueError('NO_STEP_BINDING')
        for step in lines:
            text=removal(step['text'],key,names)
            step['text']=text
        if any(ref_pattern(key).search(fold(s['text'])) for s in lines):
            raise ValueError('REMAINING_OMITTED_REFERENCE')
    edits=scale_amounts(lines,remaining,multiplier) if multiplier!=1 else {}
    for key in sorted(changed-removed):
        for step,m,_ in edit_refs(key,known[key],lines):
            edit=(m.start('value'),m.end('value'),str(quantities[key]))
            current=edits.setdefault(step['id'],[])
            current[:]=[x for x in current if x[:2]!=edit[:2]]
            current.append(edit)
    for step in lines:
        step['text']=patch(step['text'],edits.get(step['id'],[]))
        step['changed']=step['text']!=step['original']
    if not remaining or not any(s['section']=='steps' and s['text'].startswith(('-', '•')) for s in lines):
        raise ValueError('MISSING_USABLE_STEPS')
    for i in remaining:
        if i['key'] in quantities:i['quantity']=str(quantities[i['key']])
    return dict(items=remaining,steps=lines,portions=portions,base_range=doc['base_range'],
                active=active,scale=str(multiplier),changed=bool(active),removed=sorted(removed),
                replaced=bool(replacements),substitutions=[dict(
                    chosen=x['chosen'], alternatives=x['alternatives'], role=x['role'],
                    ingredient_span=[x['item']['start'],x['item']['end']], step_ids=[i for i,_,_ in x['usages']])
                    for x in replacements.values()],source_status=row['source_verification'],model='source_bindings_v2')

