"""Keyword suggestions from authorized Train/Test questions; never generate answers."""
import math
import re
import unicodedata
from collections import Counter
from functools import lru_cache

STOP = set('ban minh toi tui em anh chi hay vui long lam on huong dan giup cach cong thuc nau lam mon an mot cai co khong la gi nao nhu the sao vay cho cua va voi thi ve duoc can muon biet hoi noi nay do di nhe nha a oi nhung cac nhieu it hon rat qua dang se da chua phai phan khau nua thu tu'.split())
STOP.update('bạn mình tôi chỉ hãy lòng làm ơn hướng dẫn giúp cách công thức nấu món ăn một cái có không là gì nào như thế vậy của và với thì về được cần muốn biết hỏi nói này đó đi nhé ạ ơi những các nhiều ít hơn rất quá đang sẽ đã chưa phải phần khẩu nửa thứ từ giảm giam'.split())
STOP.update('người việc nên trong ngoài để bằng mỗi cũng lành này tốt nhất thì vì ngày làm thế luôn'.split())
GROUPS = [ {'muối','natri','sodium'}, {'calo','kcal','calorie','calories'},
           {'đạm','protein'}, {'béo','lipid','fat'}, {'carbohydrate','carb','glucid'},
           {'đường','sugar'}, {'bảo_quản','lưu_trữ'}, {'chiên','rán'} ]
PHRASES = {'năng lượng':'calo','nang luong':'calo','chất đạm':'protein','chat dam':'protein',
           'chất béo':'lipid','chat beo':'lipid','bảo quản':'bảo_quản','bao quan':'bảo_quản',
           'lưu trữ':'lưu_trữ','luu tru':'lưu_trữ'}
PHRASES.update({'văn phòng':'văn_phòng','van phong':'văn_phòng','bữa phụ':'bữa_phụ',
    'bữa trưa':'bữa_trưa','trái cây':'trái_cây','sữa chua':'sữa_chua',
    'thực phẩm':'thực_phẩm','người lớn tuổi':'người_lớn_tuổi','làm việc nặng':'việc_nặng'})

def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.replace('đ','d')) if unicodedata.category(c)!='Mn')

def words(text):
    text=unicodedata.normalize('NFC',text.casefold())
    for phrase,token in PHRASES.items():
        text=re.sub(r'(?<!\w)'+phrase+r'(?!\w)',token,text)
    return {w for w in re.findall(r'\w+',text) if len(w)>1 and w not in STOP and not w.isdigit()}

def expand(tokens):
    result=set(tokens)
    for group in GROUPS:
        if result & group: result.update(group)
    return result

@lru_cache(maxsize=4)
def index(rows):
    docs=[];df=Counter()
    for rid,question in rows:
        terms=expand(words(question))
        # These source IDs have explicit calorie records in the synchronized
        # workbook; expose the supported calorie command without inventing QA.
        if 41 <= rid <= 290: terms.update({'calo','kcal','calorie','calories'})
        docs.append((rid,question,terms));df.update(terms)
    return docs,df

def related(question, kho, result, limit=6):
    """Use rare meaningful anchors, preserving allergies and existing policy holds."""
    from backend.chatbot.knowledge_policy import policy
    from backend.chatbot.ngon_ngu import vi_pham,du_bang_chung
    p=policy(kho)
    if not p or result.get('loai')=='ngoai_pham_vi': return []
    manifest,ledger=p
    state=result.get('trang_thai') or {}
    if state.get('tinh_trang_suc_khoe') or (state.get('health_context_v5') or {}).get('active'):
        return []
    if result.get('reason_code') in {'HELD_HEALTH','HEALTH_CURE_UNSUPPORTED','DEMO_RECIPE_UNDER_REVIEW','VALIDATION_FAILED','HISTORY_UNSEALED'}:
        return []
    excluded=set(manifest.get('demo_excluded_recipe_ids',()))
    available={rid:r for rid,r in ledger.items() if r['allowed_for_answer'] and r['scope']=='IN_SCOPE' and rid not in excluded}
    docs,df=index(tuple((rid,r['question']) for rid,r in sorted(available.items())))
    raw=words(question);query=expand(raw)
    low_salt=bool(re.search(r'\b(?:giảm|bớt|ít) (?:lượng )?(?:muối|natri|mặn)\b|\băn nhạt\b',question.casefold()))
    if low_salt:
        query.add('nhạt')
    known={w for w in query if df[w]}
    # Fall back to accent-free matching only when the query has no Vietnamese
    # accents and no direct meaningful match. English synonyms stay unambiguous.
    folded=False
    if query-known and fold(question.casefold())==question.casefold():
        docs=[(rid,title,{fold(w) for w in terms}) for rid,title,terms in docs]
        df=Counter(w for _,_,terms in docs for w in terms)
        query={fold(w) for w in query};raw={fold(w) for w in raw}
        known={w for w in query if df[w]};folded=True
    current=(result.get('chu_de') or state.get('mon_hien_tai') or {}).get('id_goc')
    energy=bool(query & {'calo','kcal','calorie','calories'})
    if not known or (energy and not (known-{'calo','kcal','calorie','calories'})):
        if current in available:
            context=expand(words(available[current]['question']))
            query.update({fold(w) for w in context} if folded else context)
            known={w for w in query if df[w]}
    if not known: return []
    # Anchor on a rare word/group so "cá kèo" cannot degrade to every "cá" dish.
    existing=set(result.get('goi_y') or ())
    useful={w for w in known if any(w in terms and rid!=current and title not in existing and words(title)!=raw
                                   for rid,title,terms in docs)}
    anchor=min(useful or known,key=lambda w:(df[w],w))
    anchors=expand({anchor})
    conditions=dict(loai_tru=[],chua_ro=[],an_chay=False,nhu_cau=[])
    conditions.update(state.get('dieu_kien') or {})
    if conditions['chua_ro']: return []
    ranked=[]
    for rid,title,terms in docs:
        if not terms & anchors: continue
        row=available[rid]
        if low_salt and re.search(r'\b(?:nêm thêm|thêm muối|tăng muối)\b',title.casefold()): continue
        if vi_pham(row['answer_text'],conditions) or not du_bang_chung(row['answer_text']+' '+title,conditions): continue
        if state.get('khong_chien') and re.search(r'\b(?:chien|ran)\b',' '.join(terms)): continue
        overlap=query & terms
        score=sum(math.log((len(docs)+1)/(df[w]+1))+1 for w in overlap)
        if len(raw)>1:
            ordered=[w for w in re.findall(r'\w+',unicodedata.normalize('NFC',question.casefold())) if w not in STOP and w in raw]
            phrase=' '.join(ordered)
            title_text=title.casefold()
            if folded:title_text=fold(title_text)
            if phrase and phrase in title_text:score+=10
        # Only return exact source questions, or the supported calorie command.
        label='Calo: '+title if energy and rid>=41 and rid<=290 else title
        if label in existing or (rid==current and not energy): continue
        if words(title)==raw and not energy: continue
        ranked.append((-score,rid,dict(id=rid,question=label,source_question=title,split=row['split'],matched=sorted(overlap))))
    ranked.sort(key=lambda x:(x[0],x[1]))
    selected=[item for _,_,item in ranked[:limit]]
    if len(selected)<limit and result.get('reason_code')=='SOURCE_QA':
        selected += answer_related(result,available,docs,conditions,{x['id'] for x in selected},existing,limit-len(selected))
    return selected

def answer_related(result,available,docs,conditions,used,existing,limit):
    """Use source answer context when the exact question has few title matches."""
    from backend.chatbot.ngon_ngu import vi_pham,du_bang_chung
    source_ids={s.get('id_goc') for s in result.get('nguon',())}
    sources=[available[i] for i in source_ids if i in available]
    if not sources:return []
    text='\n'.join(r['answer_text'] for r in sources)
    # Do not turn discouraged foods into positive suggestions.
    text=re.sub(r'\b(?:tránh|hạn chế|không nên|không được|thay vì)\b[^.;!?\n]*',' ',text,flags=re.I)
    context=expand(words(text))
    ranked=[]
    for rid,title,terms in docs:
        if rid in source_ids or rid in used or title in existing:continue
        row=available[rid]
        # Here the goal is follow-up questions about the explanation; recipe
        # suggestions remain handled by the ingredient and checked-plant flows.
        if row['group_folder'] in {'02_huong_dan_nau_an','03_huong_dan_nau_mon_mien_tay'}:continue
        if all(r['group_folder'].startswith(('08_','09_')) for r in sources) and not row['group_folder'].startswith(('08_','09_')):continue
        shared=terms & context
        if len(shared)<2 and not any('_' in term for term in shared):continue
        if vi_pham(row['answer_text'],conditions) or not du_bang_chung(row['answer_text']+' '+title,conditions):continue
        score=sum(4 if '_' in term else 1 for term in shared)/math.sqrt(max(3,len(terms)))
        ranked.append((-score,rid,dict(id=rid,question=title,source_question=title,split=row['split'],matched=sorted(shared))))
    ranked.sort(key=lambda x:(x[0],x[1]))
    return [item for _,_,item in ranked[:limit]]
