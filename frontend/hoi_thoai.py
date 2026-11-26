"""Preserve approved social replies and delegate cooking dialogue to the backend."""
import re
import unicodedata


def normalized(text):
    text = unicodedata.normalize('NFD', text.casefold()).replace('đ', 'd')
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return ' '.join(re.sub(r'[^\w\s]', ' ', text).split())


def conversational_row(question, ledger):
    rows = [r for r in ledger.values()
            if r.get('allowed_for_answer') and r.get('scope') == 'CONVERSATIONAL']
    key = normalized(question)
    # Keep original wording for exact conversational entries (thanks, goodbye,
    # introductions), but do not confuse explicitly accented cháo with chào.
    if re.search(r'\bcháo\b', unicodedata.normalize('NFC', question.casefold())):
        return None
    exact = next((r for r in rows if normalized(r['question']) == key), None)
    if exact:
        return exact
    if re.fullmatch(r'(?:xin )?chao(?: (?:ban|bot|nha|em|anh|chi|shop))?|hello|hi|alo', key):
        return next((r for r in rows if normalized(r['question']) == 'xin chao'), None)
    return None


def cooking_family(question):
    """Extract an explicitly requested dish family, not health/omission advice."""
    key = normalized(question)
    if not re.search(r'\b(?:nau|che bien|huong dan|cong thuc)\b', key):
        return None
    if (re.search(r'\b(?:ho|sot|benh|thuoc|tri|kieng|khong|di ung|bo|thay|giam)\b', key)
            or re.search(r'\bchữa\b', unicodedata.normalize('NFC', question.casefold()))):
        return None
    key = re.sub(r'^(?:(?:toi|minh|tui|em|muon|can|xin|cho|giup)|huong dan|cach|cong thuc|nau|che bien|lam|mon)\s+', '', key)
    # Prefixes repeat in natural speech: "tôi muốn hướng dẫn nấu món ...".
    previous = None
    while previous != key:
        previous = key
        key = re.sub(r'^(?:toi|minh|tui|em|muon|can|xin|cho|giup|huong dan|cach|cong thuc|nau|che bien|lam|mon)\s+', '', key)
    key = re.sub(r'(?:\s+(?:di|nhe|nha|voi|a|giup|minh|toi))+$', '', key)
    return key if 1 <= len(key.split()) <= 5 else None


def tra_loi(question, history=None):
    from backend.chatbot.che_do_du_lieu import chon_kho
    from backend.chatbot.knowledge_policy import policy, sanitize_history, seal_result
    store, _ = chon_kho()
    selected = policy(store)
    row = conversational_row(question, selected[1]) if selected else None
    if row:
        from backend.chatbot.trang_thai import lay_trang_thai
        result = dict(cau_tra_loi=row['answer_text'], loai='chao_hoi', nguon=[],
                      goi_y=[], doan_truy_hoi=[], chu_de=None, giai_thich={},
                      trang_thai=lay_trang_thai(sanitize_history(history or [], store)))
        return seal_result(result, store)
    # The backend resolves follow-ups and constraints together. A frontend
    # dish-family shortcut can mistake a reference to the current dish for a
    # new query and erase its recipe state.
    from backend.chatbot.sinh_cau_tra_loi import tra_loi as answer
    return answer(question, history)
