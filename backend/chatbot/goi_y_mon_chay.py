"""Concrete cooking choices for the nutrition menu, using existing source recipes."""
TOPICS = {692:(182,48,118), 695:(212,129,132), 696:(212,129,132), 701:(182,195,227)}
CHECKED = {
    212:'2d43cd2b5aed963f8c76151e84678697b887ed62cee33794fa069cfbf60ba957',
    129:'8539309b32ad39bbb7a78e452c39f19c3487ba71187a867b4fef570ab9d786ca',
    132:'f694be8c08817a8e07a69d45c74678c8bc178b17ec54d4325366de7362a1ac92',
}

def recipe_choices(question, sources):
    """Match the topic and positive food examples, not just four menu IDs."""
    import re
    from backend.chatbot.goi_y_lien_quan import fold
    titles=fold(question.casefold()+' '+' '.join(r['question'].casefold() for r in sources))
    if re.search(r'\b(?:an toi|bua toi|nhe bung)\b',titles):
        return (48,243,276),False
    if re.search(r'\b(?:chay|thuc vat)\b',titles) and re.search(r'\b(?:dam|protein|du chat|bua com)\b',titles):
        return tuple(CHECKED),True
    if re.search(r'\b(?:van phong|cong ty)\b',titles):
        return (182,195,227),False
    for row in sources:
        if row['id'] in TOPICS:return TOPICS[row['id']],row['id'] in (695,696)
    answer=' '.join(r['answer_text'].casefold() for r in sources)
    answer=re.sub(r'\b(?:tránh|hạn chế|không nên|không được|thay vì)\b[^.;!?\n]*',' ',answer)
    answer=fold(answer)
    candidates=[]
    # Offer only examples actually mentioned in the answer, with original recipes.
    if re.search(r'\bchao\b',answer):candidates.extend((48,243))
    if re.search(r'\brau (?:xanh )?luoc\b',answer):candidates.append(276)
    if re.search(r'\bcanh\b',answer):candidates.extend((182,195))
    if re.search(r'\b(?:dau (?:hu|phu)|tau hu)\b',answer) and 'chien' not in fold(question.casefold()):
        candidates.extend((129,132))
    return tuple(dict.fromkeys(candidates))[:3],False

def checked_recipe(row):
    return bool(row and row.get('allowed_for_answer') and row.get('scope')=='IN_SCOPE'
                and CHECKED.get(row.get('id'))==row.get('answer_sha256'))

def suggestions(question,result,kho):
    from backend.chatbot.knowledge_policy import policy
    from backend.chatbot.ngon_ngu import vi_pham
    if result.get('loai')!='tra_loi' or result.get('reason_code')!='SOURCE_QA':return []
    source_ids={s.get('id_goc') for s in result.get('nguon',())}
    state=result.get('trang_thai') or {}
    if state.get('tinh_trang_suc_khoe') or (state.get('health_context_v5') or {}).get('active'):return []
    dk=state.get('dieu_kien') or {}
    if dk.get('chua_ro'):return []
    p=policy(kho)
    if not p:return []
    manifest,ledger=p
    sources=[ledger[i] for i in source_ids if i in ledger and ledger[i].get('allowed_for_answer') and ledger[i].get('scope')=='IN_SCOPE']
    ids,vegetarian=recipe_choices(question,sources)
    options=[]
    for rid in ids:
        row=ledger.get(rid)
        if not row or not row.get('allowed_for_answer') or row.get('scope')!='IN_SCOPE' or rid in manifest.get('demo_excluded_recipe_ids',()):continue
        if (vegetarian or dk.get('an_chay')) and not checked_recipe(row):continue
        if vi_pham(row['answer_text'],dict(loai_tru=dk.get('loai_tru',[]),an_chay=False)):continue
        options.append(dict(id=rid,question=row['question'],vegetarian=rid in CHECKED))
    return options
