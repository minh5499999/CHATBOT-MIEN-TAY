"""Đề nghị tên công thức để người dùng xác nhận."""
import re
from difflib import SequenceMatcher

from backend.chatbot.doi_chieu import chi_muc_cau_hoi, chi_muc_ten_mon, ten_mon_tu_cau_hoi
from backend.chatbot.knowledge_policy import policy, store_cache
from backend.chatbot.ngon_ngu import chuan_hoa, chuan_hoa_dia_phuong, khoa_cau_hoi

_COLLISIONS = {'bo', 'luon', 'chao', 'ca', 'dam', 'nam', 'tieu', 'bot'}
_CONDITIONS = re.compile(r'\b(?:di ung|kieng|tranh|khong|chua co|thay bang|bo nguyen lieu)\b')
_MIN_RATIO = .88
_CLOSE_SCORE = .06


def _spellings(text):
    spellings = {}
    words = re.findall(r'\w+', chuan_hoa_dia_phuong(text).lower())
    for word in (*words, *(a+b for a,b in zip(words,words[1:]))):
        key = chuan_hoa(word)
        if key in _COLLISIONS:
            spellings.setdefault(key,set()).add(word)
    return spellings


@store_cache(maxsize=8)
def _recipe_names(kho):
    from backend.chatbot.cong_thuc import danh_muc
    from backend.chatbot.recipe_views_v5 import recipe_aliases

    knowledge = policy(kho)
    excluded = set(knowledge[0].get('demo_excluded_recipe_ids',())) if knowledge else set()
    records = []
    for recipe in danh_muc(kho):
        if recipe.id_goc in excluded:
            continue
        names = {tuple(name.split()) for name in recipe_aliases(recipe)}
        records.extend((name,recipe.id_goc,recipe.cau_hoi,_spellings(recipe.cau_hoi))
                       for name in sorted(names) if 2<=len(name)<=14)
    vocabulary = {word for name,_,_,_ in records for word in name}
    return records,vocabulary


def _one_edit(given, expected):
    if min(len(given),len(expected)) < 3 or abs(len(given)-len(expected)) > 1:
        return False
    if len(given)==len(expected):
        changes = [i for i,(a,b) in enumerate(zip(given,expected)) if a!=b]
        return len(changes)==1 or (len(changes)==2 and changes[1]==changes[0]+1
                                  and given[changes[0]:changes[1]+1]==expected[changes[0]:changes[1]+1][::-1])
    shorter,longer = sorted((given,expected),key=len)
    i = next((i for i,(a,b) in enumerate(zip(shorter,longer)) if a!=b),len(shorter))
    return shorter==longer[:i]+longer[i+1:]


def _match(query, prefix, vocabulary):
    if query==prefix or ''.join(query)==''.join(prefix):
        return 1.0
    if len(query)!=len(prefix):
        return None
    changes = [(given,expected) for given,expected in zip(query,prefix) if given!=expected]
    if len(changes)!=1:
        return None
    given,expected = changes[0]
    if given in vocabulary or given in _COLLISIONS or expected in _COLLISIONS or not _one_edit(given,expected):
        return None
    score = SequenceMatcher(None,' '.join(query),' '.join(prefix),autojunk=False).ratio()
    return score if score>=_MIN_RATIO else None


def de_nghi_ten_mon(question, kho):
    key = khoa_cau_hoi(question)
    if chi_muc_cau_hoi(kho).get(key) or _CONDITIONS.search(key):
        return []
    query = tuple(ten_mon_tu_cau_hoi(question).split())
    if not 2<=len(query)<=10 or ' '.join(query) in chi_muc_ten_mon(kho):
        return []
    spellings = _spellings(question)
    records,vocabulary = _recipe_names(kho)
    scores = {}
    for name,rid,title,title_spellings in records:
        if name==query and all(forms <= title_spellings.get(word,set()) | {word}
                               for word,forms in spellings.items() if word in name):
            return []
        if any(not forms <= title_spellings.get(word,set()) | {word}
               for word,forms in spellings.items() if word in name):
            continue
        for width in range(max(2,len(query)-1),min(len(name),len(query)+1)+1):
            prefix = name[:width]
            score = _match(query,prefix,vocabulary)
            if score is None:
                continue
            # Literal wording takes priority over repairs, then prefer a full name.
            rank = (-score,width!=len(name),len(name)-width,title)
            if rid not in scores or rank<scores[rid]:
                scores[rid] = rank
    if not scores:
        return []
    ordered = sorted(scores.values())
    return [title for score,partial,_,title in ordered
            if score-ordered[0][0]<_CLOSE_SCORE and (partial==ordered[0][1] or score==ordered[0][0])][:3]
