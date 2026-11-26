"""Connect food suggestions to existing, authorized cooking recipes."""
import copy
import re


def _recipe_views():
    try:
        import backend.chatbot.recipe_views_v5 as views
    except ModuleNotFoundError as error:
        if error.name != 'backend.chatbot.recipe_views_v5':
            raise
        return None
    return views


def cau_hoi_tim_cong_thuc(question, kho):
    """A generic request to cook porridge needs recipe choices, not health Q&A."""
    views = _recipe_views()
    if views is None:
        return question
    from backend.chatbot.cong_thuc import danh_muc
    q = views.normalize(question)
    if views.find_recipe(question, danh_muc(kho)):
        return question
    # Match only a bare category at the end; keep constraints and named dishes
    # on the normal router, and never turn a medical question into cooking.
    pattern = r'\b(?:cach nau|huong dan nau|nau) (?:mon )?(chao|canh|lau|sup)(?: (?:di|nhe|nha|voi|a))*[ ?!.]*$'
    match = re.search(pattern, q)
    if not match or re.search(r'\b(?:khong|dung|chua|tri|thuoc|kieng|thay|giam|buoc|bao quan)\b', q):
        return question
    # Soup is not a supported category in the existing recipe router.
    if match[1] == 'sup':
        return question
    return q[:match.start()] + 'gợi ý món ' + {'chao': 'cháo', 'canh': 'canh', 'lau': 'lẩu'}[match[1]]


def cong_thuc_goi_y(question, result, kho):
    """Only offer full recipes already selected or positively named in the answer."""
    from backend.chatbot.cong_thuc import danh_muc
    from backend.chatbot.knowledge_policy import policy
    from backend.chatbot.ngon_ngu import khoa_cau_hoi

    if result.get('structured_view') or result.get('loai') not in ('tra_loi', 'khong_chac'):
        return []
    if not result.get('goi_y') and result.get('reason_code') != 'SOURCE_QA':
        return []
    views = _recipe_views()
    if views is None:
        # The original backend only exposes recipe suggestions as question titles.
        titles = {r.cau_hoi: r.id_goc for r in danh_muc(kho)}
        return [dict(id=titles[q], question=q)
                for q in dict.fromkeys(result.get('goi_y', ())) if q in titles]
    p = policy(kho)
    if not p:
        return []
    document = views.document
    simple_recipe_options = views.simple_recipe_options
    normalize = views.normalize
    manifest, ledger = p
    state = copy.deepcopy(result.get('trang_thai') or {})
    if not state.get('dieu_kien') or state['dieu_kien'].get('chua_ro'):
        return []
    # These are reference recipes, not verified nutrient/medical recommendations.
    # Keep ingredient exclusions and all concrete cooking constraints intact.
    if result.get('reason_code') == 'SOURCE_QA':
        state['dieu_kien']['nhu_cau'] = []
    recipes = danh_muc(kho)
    selected = [khoa_cau_hoi(q) for q in result.get('goi_y', ())]
    rows = []
    if selected:
        by_title = {khoa_cau_hoi(r['question']): r for r in ledger.values()}
        rows = [by_title[title] for title in selected if title in by_title]
    elif result.get('loai') == 'tra_loi' and result.get('reason_code') == 'SOURCE_QA':
        # Reuse the existing nutrition choices when available.
        from backend.chatbot.goi_y_mon_chay import suggestions
        rows = [ledger[item['id']] for item in suggestions(question, result, kho)]
        if not rows:
            text = normalize(result.get('cau_tra_loi', ''))
            text = re.sub(r'\b(?:tranh|han che|khong nen|khong duoc|khong an|khong dung)\b[^.;!?\n]*', ' ', text)
            for word in ('chao', 'canh', 'lau'):
                if re.search(r'\b' + word + r'\b', text):
                    rows.extend(simple_recipe_options('', recipes, ledger, state, category=word))
    candidates = {r['id'] for r in rows}
    # Apply the same ingredient, time and source constraints as recipe suggestions.
    # Check each candidate separately so filtering never changes displayed order
    # or the meaning of “món thứ hai” stored by the dialogue backend.
    eligible = set()
    for recipe in recipes:
        if recipe.id_goc in candidates and simple_recipe_options('', (recipe,), ledger, state):
            eligible.add(recipe.id_goc)
    excluded = set(manifest.get('demo_excluded_recipe_ids', ()))
    unique = {r['id']: r for r in rows}
    return [dict(id=r['id'], question=r['question']) for r in unique.values()
            if r['id'] in eligible and r['id'] not in excluded
            and {'ingredients', 'steps'} <= document(r)['sections'].keys()][:3]


def hien_huong_dan(options, *, vi_tri, on_chon):
    import streamlit as st
    from frontend.chi_tiet_cong_thuc import ten_hien_thi

    if not options:
        return
    with st.container(border=True, key=f'cooking_suggestions_{vi_tri}'):
        st.markdown('#### Hướng dẫn nấu')
        st.caption('Chọn món để xem nguyên liệu và các bước nấu:')
        for item in options:
            st.button('Cách nấu '+ten_hien_thi(item['question']),
                      key=f'cooking_suggestion_{vi_tri}_{item["id"]}',
                      icon=':material/skillet:', width='stretch',
                      on_click=on_chon, args=(item['question'],))
        st.caption('Công thức tham khảo trong kho; chưa xác nhận từng món đáp ứng yêu cầu dinh dưỡng cụ thể hoặc có tác dụng điều trị bệnh.')
