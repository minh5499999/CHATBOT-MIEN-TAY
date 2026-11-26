"""Render only durations evidenced by the authorized recipe."""
import re
from backend.chatbot.ngon_ngu import chuan_hoa

DURATION = re.compile(r'(?<![\w/])(?P<a>\d+)(?:\s*(?:[-–—]|đến|to)\s*(?P<b>\d+))?\s*(?P<unit>phút|giờ)\b(?:\s+(?P<minutes>[0-5]?\d)\s*phút\b)?', re.I)
COOK = r'nau|che bien|lam|luoc|hap|chien|xao|kho|nuong|ran|dun|rim|sot|ham|chung|phi'
ACTIONS = {'luoc':'Luộc','hap':'Hấp','xao':'Xào','chien':'Chiên','kho':'Kho',
           'nuong':'Nướng','ran':'Rán','dun':'Đun','rim':'Rim','ham':'Hầm','phi':'Phi'}
LABELS = {'prep':'Chuẩn bị', 'marinate':'Ướp', 'cook':'Nấu', 'total':'Tổng thời gian'}
VALID_PHASES = {'all','prep','marinate','cook','total',*ACTIONS}


def requested_phase(question):
    for phase, pattern in (
        ('total',r'\b(tong(?: thoi gian)?|tat ca mat|tu dau den cuoi)\b'),
        ('marinate',r'\buop\b'),
        ('prep',r'\b(chuan bi|so che|ngam|rua)\b'),
    ):
        if re.search(pattern,question):
            return phase
    if re.search(r'\b(?:thoi gian (?:nau|che bien)|nau (?:trong )?(?:bao lau|mat))\b',question):
        return 'cook'
    for action in ACTIONS:
        if (re.search(rf'\b{action}\s+(?:trong\s+)?(?:mat\s+)?(?:bao|may|thoi gian)',question)
                or re.search(rf'\b(?:bao lau|bao nhieu phut) de {action}\b',question)):
            return action
    return 'all'


def duration_text(value):
    span = value['a']
    if value['b']:
        span += '–'+value['b']
    text=span+' '+value['unit'].lower()
    if value['minutes'] and value['unit'].lower()=='giờ':
        text+=' '+value['minutes']+' phút'
    return text


def summary_durations(text, sections):
    """Read labeled header metadata, including the recipe's serving heading."""
    header_end=min((v['start'] for v in sections.values()),default=0)
    header=text[:header_end].splitlines()
    span=sections.get('ingredients')
    if span:
        heading=text[span['start']:span['end']].splitlines()[0]
        header.extend(re.findall(r'\(([^()]*)\)',heading))
    for line in header:
        chunks=re.split(r'[,;]|\s+và\s+',line)
        for part in chunks:
            value=DURATION.search(part)
            if not value:
                continue
            prefix=chuan_hoa(part[:value.start()]).strip(' :-–')
            if re.fullmatch(r'(?:tong(?: cong| thoi gian)?)(?: mat| khoang)?',prefix):
                yield 'total', '', value
            elif re.fullmatch(r'(?:thoi gian )?(?:chuan bi|so che)(?: mat| khoang)?',prefix):
                yield 'prep', '', value
            elif re.fullmatch(r'(?:thoi gian )?uop(?: mat| khoang)?',prefix):
                yield 'marinate', '', value
            elif re.fullmatch(rf'(?:thoi gian )?(?:{COOK})(?: mat| khoang)?',prefix):
                yield 'cook', '', value


def step_durations(text, sections):
    for section in ('prep','steps'):
        span=sections.get(section)
        if not span:
            continue
        for line in text[span['start']:span['end']].splitlines()[1:]:
            # Limit action inference to instruction clauses, never to the ingredients heading.
            for clause in re.split(r'[;.!?]',line):
                matches=list(DURATION.finditer(clause))
                for i, value in enumerate(matches):
                    prefix=chuan_hoa(clause[:value.start()])
                    # Action closest to the timer. “đã ướp” refers to an earlier action.
                    valid=[a for a in re.finditer(rf'\b(uop|ngam|{COOK})\b',prefix) if
                           not re.search(r'\bda\s*$',prefix[:a.start()])]
                    if not valid:
                        continue
                    word=valid[-1][1]
                    phase='marinate' if word=='uop' else 'prep' if word=='ngam' else 'cook'
                    end=matches[i+1].start() if i+1<len(matches) else len(clause)
                    tail=chuan_hoa(clause[value.end():end])
                    condition=''
                    if re.search(r'\bneu thai soi\b',tail):condition=' (thái sợi)'
                    elif re.search(r'\bneu thai mieng vuong\b',tail):condition=' (thái miếng vuông)'
                    elif re.search(r'\bmoi mat\b',tail):condition=' mỗi mặt'
                    action=ACTIONS.get(word,'') if phase=='cook' else ''
                    yield phase, word if action else '', duration_text(value)+condition


def render_times(text, sections, request):
    if request not in VALID_PHASES:
        raise ValueError('Unknown time phase')
    summary=list(summary_durations(text, sections))
    displayed=[(phase,action,duration_text(value)) for phase,action,value in summary]
    displayed+=list(step_durations(text,sections))
    totals={value for phase,_,value in displayed if phase=='total'}
    has_total=len(totals)==1
    result=[]
    for phase,action,value in dict.fromkeys(displayed):
        if phase=='total' and not has_total:
            continue
        if request in ('all',phase,action):
            label=ACTIONS[action] if action else LABELS[phase]
            result.append(f'- {label}: {value}.')
    if not result and request not in ('all','total'):
        label=(ACTIONS.get(request) or LABELS[request]).lower()
        result.append(f'Nguồn chưa ghi rõ thời gian {label}.')
    if request in ('all','total') and not has_total:
        result.append('Nguồn chưa xác định tổng thời gian.')
    return '\n'.join(result)

def explicit_total_minutes(header):
    """Use a single explicit total for recommendations with a time constraint."""
    totals=[]
    for phase,_,value in summary_durations(header,{'meta':{'start':len(header)}}):
        if phase=='total' and not value['b']:
            if value['unit'].lower()=='giờ':
                totals.append(int(value['a'])*60+int(value['minutes'] or 0))
            else:
                totals.append(int(value['a']))
    return totals[0] if len(set(totals))==1 else None
