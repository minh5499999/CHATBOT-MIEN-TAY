"""Resolve exact authorized non-recipe QA before the numeric nutrition router."""
import re
import unicodedata

def question_key(text):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFC',text).casefold()).strip().rstrip(' ?!.')

def route(payload,manifest,ledger):
    from backend.chatbot.recipe_views_v5 import reference
    from backend.chatbot.ngon_ngu import vi_pham
    state=payload['state']
    if state.get('tinh_trang_suc_khoe') or (state.get('health_context_v5') or {}).get('active'):
        return None
    question=question_key(payload['question'])
    matches=[r for r in ledger.values() if question_key(r['question'])==question]
    if len(matches)!=1:return None
    row=matches[0]
    if not row['allowed_for_answer'] or row['scope']!='IN_SCOPE' or row['id'] in manifest.get('demo_excluded_recipe_ids',()):return None
    if row['group_folder'] in {'02_huong_dan_nau_an','03_huong_dan_nau_mon_mien_tay'}:return None
    dk=state.get('dieu_kien') or {}
    if dk.get('chua_ro'):return None
    # Preserve explicit ingredient exclusions; do not mistake educational prose
    # containing plant milk for a non-vegetarian recipe.
    if vi_pham(row['answer_text'],dict(loai_tru=dk.get('loai_tru',[]),an_chay=False)):return None
    for name in ('nutrition_context','nutrition_portion_status','portion_state_v5'):
        state.pop(name,None)
    state['mon_hien_tai']=None
    state['khau_phan']=None
    return dict(loai='tra_loi',reason_code='SOURCE_QA',cau_tra_loi=row['answer_text'],
        nguon=[reference(row)],goi_y=[],doan_truy_hoi=[],chu_de=None,
        giai_thich={'nhom_nguon':row['group_folder']})
