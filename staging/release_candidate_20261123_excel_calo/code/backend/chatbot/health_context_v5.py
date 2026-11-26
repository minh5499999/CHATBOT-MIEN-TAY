"""User-declared context, not a diagnosis. No treatment or food-health rules."""
import copy,re
from backend.chatbot.ngon_ngu import chuan_hoa,chuan_hoa_dia_phuong

CONDITIONS={'ho':r'\bho\b','sốt':r'\bsot\b','cảm':r'\bcam(?: cum)?\b','kinh nguyệt':r'\b(?:kinh nguyet|ky kinh)\b','bệnh chưa xác định':r'\bbenh\b'}

def food_text(text):
    """Exclude a negated health declaration from ingredient-omission parsing."""
    return re.sub(r'\b(?:không|khong)(?:\s+(?:còn|con))?\s+(?:(?:bị|bi|có|co|mắc|mac|đang|dang)\s+)?(?:bệnh|benh|ho|sốt|sot|cảm|cam)\b',' ',text,flags=re.I)

def analyze(text,previous=None):
    q=chuan_hoa(chuan_hoa_dia_phuong(text))
    context=copy.deepcopy(previous or {'schema':1,'conditions':{}})
    context.setdefault('conditions',{})
    # A question about efficacy is not a declaration that the user has the illness.
    interrogative=bool(re.search(r'\b(?:co|lieu|giup|de|cho|lam sao)\b.*\b(?:het benh|khoi benh|het ho|khoi ho|het sot|chua ho|chua benh|tri ho|chua cam)\b',q))
    explicit_cure=bool(re.search(r'\b(?:chua|tri|dieu tri)\s+(?:duoc |khoi )?(?:benh|ho|sot|cam)\b|\b(?:ke|uong) thuoc\b',q))
    # "Tôi chưa ho" is absent, not an efficacy question (accented chữa remains distinct).
    if re.search(r'\b(?:toi|minh|tui|em) chua (?:bi )?(?:ho|sot|cam)\b',q) and 'chữa' not in text.lower():explicit_cure=False
    cooking_only=bool(re.search(r'\b(?:khong hoi|khong noi ve)\b.*\b(?:chua|dieu tri|benh)\b',q) and re.search(r'\bchi hoi\b.*\b(?:thoi gian|nau|so che|nguyen lieu)\b',q))
    cure=(interrogative or explicit_cure) and not cooking_only
    first_person=bool(re.search(r'\b(?:toi|minh|tui|em|ban than)\b',q))
    clauses=re.split(r'[,;.!?]|\b(?:nhung|ma|tuy nhien)\b',q)
    for clause in clauses:
        if not clause.strip():continue
        if re.search(r'\b(?:khong hoi|khong noi ve)\b',clause):continue
        negative=bool(re.search(r'\b(?:khong|chua)(?: con)?\s+(?:bi |mac |dang )?\b',clause))
        recovered=bool(re.search(r'\b(?:da |vua )?(?:het|khoi)\s+(?:benh|ho|sot|cam)\b',clause))
        declaration=first_person or bool(re.search(r'\b(?:dang|van|con|khong con|da het|da khoi|chua het|chua khoi)\b',clause))
        question_clause=bool(re.search(r'\b(?:co|lieu).*(?:het|khoi|chua|tri)\b|\b(?:nen an|an gi|co chua)\b',clause))
        self_report=bool(re.search(r'\b(?:toi|minh|tui|em)\s+(?:dang |van |con |da )?(?:bi|ho|sot|cam|het|khoi|khong|chua)\b',clause))
        if (question_clause and not self_report) or (cure and question_clause) or not declaration:continue
        for condition,pattern in CONDITIONS.items():
            # "Cảm ơn" is conversational, never a reported cold.
            if condition=='cảm' and not re.search(r'\bcam\b(?! (?:on|thay)\b)',clause):continue
            if not re.search(pattern,clause):continue
            status='RESOLVED_USER_DECLARED' if recovered and not negative else 'ABSENT_USER_DECLARED' if negative else 'ACTIVE_USER_DECLARED'
            # "Chưa hết sốt" is still active. No clinical inference beyond the statement.
            if re.search(r'\b(?:chua|khong)\s+(?:het|khoi)\b',clause):status='ACTIVE_USER_DECLARED'
            context['conditions'][condition]={'status':status,'statement':text,'basis':'USER_DECLARED_NOT_MEDICALLY_VERIFIED'}
            if condition=='bệnh chưa xác định' and status=='RESOLVED_USER_DECLARED':
                for transient in ('ho','sốt','cảm'):
                    if transient in context['conditions']:context['conditions'][transient]={'status':status,'statement':text,'basis':'USER_DECLARED_GENERAL_RECOVERY'}
    context['active']=[k for k,v in context['conditions'].items() if v['status']=='ACTIVE_USER_DECLARED']
    context['last_statement']=text
    # Symptoms mentioned as a need still require review, without declaring them as facts.
    throat = r'(?:dau|rat|viem) hong'
    throat_need = bool(re.search(r'\b' + throat + r'\b', q)) and not bool(
        re.search(r'\b(?:khong(?: con)?|da het|het) (?:bi |con )?' + throat + r'\b', q))
    health_need=throat_need or (bool(re.search(r'\b(?:bi|dang|khi)\s+(?:ho|sot|cam)\b|\b(?:kinh nguyet|ky kinh)\b',q)) and not bool(re.search(r'\b(?:khong|chua)(?: con)?\s+(?:bi |dang )?(?:ho|sot|cam)\b',q)))
    return dict(context=context,cure_question=cure,cooking_only=cooking_only,health_need=health_need)
