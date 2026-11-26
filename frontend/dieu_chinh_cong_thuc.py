"""Recipe comparison cards using authorized reference estimates."""
import re
import streamlit as st
from backend.chatbot.cong_thuc import danh_muc, quy_doi_khau_phan
from frontend import mon_yeu_thich
from frontend.chon_mon_nau import ten_mon
from frontend.du_lieu_dieu_chinh import scenario


def _reset():
    st.session_state.pop('adjust_applied', None)

def _cooking_text(recipe):
    steps = re.search(r'(?im)^\s*(?:sơ chế|cách chế biến|cách làm|các bước)\b', recipe.noi_dung)
    text = recipe.noi_dung[steps.start():] if steps else recipe.noi_dung
    text = re.split(r'(?im)^\s*(?:nguồn|tham khảo)\s*:', text)[0].strip()
    # Keep cooking times/temperatures, but never repeat old ingredient amounts.
    units = r'muỗng canh|muỗng cà phê|thìa canh|thìa cà phê|thìa nhỏ|thìa|muỗng|kg|mg|ml|lít|gam|g|l|quả|trái|củ|tép|nhánh|con|miếng|bó|chén|tô'
    return re.sub(r'\b\d+(?:[.,]\d+|/\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?\s*(?:'+units+r')\b',
                  'lượng đã điều chỉnh của', text, flags=re.I)

def hien_thi_dieu_chinh(kho, ten_tai_khoan, hoi):
    recipes = {r.id_goc: r for r in danh_muc(kho) if r.khau_phan}
    st.markdown('### Phân tích và điều chỉnh công thức')
    with st.chat_message('user'): st.write('Điều chỉnh công thức')
    if not recipes:
        st.info('Kho hiện chưa có công thức ghi rõ số khẩu phần.')
        return
    with st.container(border=True, key='adjust_controls'):
        controls = st.columns([3, 1], vertical_alignment='bottom')
        recipe_id = controls[0].selectbox('Chọn món', list(recipes), format_func=lambda i: ten_mon(recipes[i].cau_hoi),
            index=None, placeholder='Chọn món bạn muốn điều chỉnh…', key='adjust_recipe_id')
        target = controls[1].number_input('Khẩu phần', min_value=1, max_value=30, value=2, key='adjust_target')
        options = st.columns(2)
        salt_cut = options[0].selectbox('Giảm lượng gia vị mặn', [0, 25, 50],
            format_func=lambda x: 'Giữ nguyên' if not x else f'Giảm {x}%', key='adjust_salt_cut')
        oil_cut = options[1].selectbox('Giảm lượng dầu / mỡ thêm vào', [0, 25, 50],
            format_func=lambda x: 'Giữ nguyên' if not x else f'Giảm {x}%', key='adjust_oil_cut')
        st.caption('Dùng công thức tham chiếu. Giảm gia vị mặn không đồng nghĩa natri cả món giảm cùng tỷ lệ.')
        if st.button('Áp dụng điều chỉnh', key='adjust_apply', disabled=recipe_id is None,
                     icon=':material/tune:', type='primary'):
            st.session_state.adjust_applied = (recipe_id, target, salt_cut, oil_cut)
    if recipe_id not in recipes or st.session_state.get('adjust_applied') != (recipe_id, target, salt_cut, oil_cut):
        with st.chat_message('assistant', avatar='🍲'):
            st.write('Bạn chọn món, số khẩu phần và mức điều chỉnh, rồi bấm Áp dụng điều chỉnh nhé.')
        return
    recipe = recipes[recipe_id]
    data = scenario(recipe, target, salt_cut, oil_cut)
    if not data and (salt_cut or oil_cut):
        st.info('Chưa ghép được dữ liệu đúng phiên bản của món này. Bạn chọn Giữ nguyên gia vị và dầu để quy đổi khẩu phần.')
        return
    fallback = quy_doi_khau_phan(recipe, target)
    if not data and not fallback:
        st.info('Công thức chưa đủ định lượng để quy đổi khẩu phần.')
        return
    request = f'Điều chỉnh công thức {ten_mon(recipe.cau_hoi)} cho {target} khẩu phần'
    if salt_cut: request += f', giảm {salt_cut}% lượng gia vị mặn'
    if oil_cut: request += f', giảm {oil_cut}% dầu/mỡ thêm vào'
    with st.chat_message('user'): st.write(request+'.')
    with st.chat_message('assistant', avatar='🍲'):
        st.write(f'Mình đã chuẩn bị công thức cho **{target} khẩu phần**. Bạn xem nguyên liệu và dinh dưỡng ước tính bên dưới nhé.')
    with st.container(key='adjust_main', border=True):
        name = ten_mon(recipe.cau_hoi)
        st.markdown(f'#### {name}')
        st.caption(f'{target} khẩu phần • Công thức gốc: {recipe.khau_phan} phần • Định lượng nhân {target}/{recipe.khau_phan}')
        ingredients_tab, cooking, original_full, full = st.tabs(['So sánh nguyên liệu', 'Cách nấu', 'Công thức gốc', 'Sau điều chỉnh'])
        with ingredients_tab, st.container(height=340, border=False):
            st.markdown('#### So sánh nguyên liệu')
            if data:
                st.table(data['ingredients'], hide_index=True, alt='Nguyên liệu gốc, lượng chuẩn hóa và lượng sau điều chỉnh')
                st.caption('Lượng chuẩn hóa có thể dùng quy đổi hoặc giả định cho “vừa đủ”, trái, muỗng… Xem Nguồn và giả định.')
            else:
                original, adjusted = st.columns(2)
                original.markdown('**Công thức gốc**\n\n'+'\n'.join(recipe.nguyen_lieu))
                adjusted.markdown('**Sau điều chỉnh**\n\n'+'\n'.join(fallback['dong']+fallback['chua_quy_doi']))
                st.caption('Các mục chưa rõ định lượng cần tự cân chỉnh, chưa được tính dinh dưỡng.')
        with original_full, st.container(height=340, border=False):
            st.markdown(recipe.noi_dung)
            if data:
                ref = data['reference']
                st.caption(f"Calo gốc ước tính: {ref['energy_total_kcal']:,.0f} kcal cả mẻ · {ref['energy_per_serving_kcal']:,.0f} kcal/khẩu phần ({ref['servings']:g} phần).")
        with cooking, st.container(height=340, border=False):
            st.caption('Dùng định lượng ở bảng trên; các bước dưới đã bỏ số lượng nguyên liệu gốc để tránh nhầm.')
            if data and data['changes']:
                st.markdown('**Dùng lượng mới ở bảng trên:**\n\n'+'\n'.join('- '+x for x in data['changes']))
            st.markdown(_cooking_text(recipe))
            st.caption('Các bước và thời gian tham khảo công thức gốc; dùng lượng nguyên liệu mới. Thời gian thực tế phụ thuộc lượng nấu và dụng cụ.')
        with full, st.container(height=340, border=False):
            st.markdown(f'**{name} — {target} khẩu phần**')
            if data:
                energy = data['total']['energy_kcal']
                st.caption(f'Calo sau điều chỉnh ước tính: {energy:,.0f} kcal cả mẻ · {energy/target:,.0f} kcal/khẩu phần ({target} phần).')
            if data: st.markdown('\n'.join(f"- {x['Nguyên liệu gốc']} → **{x['Sau điều chỉnh']}**" for x in data['ingredients']))
            else: st.markdown('\n'.join(fallback['dong']+fallback['chua_quy_doi']))
            st.markdown(_cooking_text(recipe))
        with st.container(horizontal=True):
            saved = mon_yeu_thich.da_luu(ten_tai_khoan, recipe.cau_hoi)
            st.button('Đã lưu món gốc' if saved else 'Lưu món gốc', icon=':material/favorite:', key='adjust_recipe_save',
                disabled=saved, on_click=mon_yeu_thich.them, args=(ten_tai_khoan, recipe.cau_hoi))
            st.button('Điều chỉnh lại', icon=':material/refresh:', key='adjust_again', on_click=_reset)
    with st.container(key='adjust_aside'):
        nutrition, explanation = st.columns([1.2, 1], gap='medium')
        with nutrition, st.container(border=True, key='adjust_nutrition_card'):
            st.markdown('#### :material/balance: Calo và dinh dưỡng trước–sau')
            st.caption('Ước tính / 1 khẩu phần • cùng bộ tham chiếu')
            if data:
                display = [dict(row) for row in data['nutrition']]
                for row in display:
                    if row['Chênh lệch'].startswith('-'):
                        row['Sau điều chỉnh'] = ':green['+row['Sau điều chỉnh']+']'
                        row['Chênh lệch'] = ':green['+row['Chênh lệch']+']'
                st.table(display, hide_index=True, alt='So sánh năm chỉ số dinh dưỡng mỗi khẩu phần trước và sau điều chỉnh')
                st.caption('Có thực phẩm đại diện; chưa kiểm nghiệm món chín. Không dùng để xác nhận chế độ ăn điều trị.')
            else: st.caption('Chưa có dữ liệu cùng phiên bản để so sánh. Không lấy số của món tương tự thay thế.')
        with explanation, st.container(border=True, key='adjust_explanation_card'):
            st.markdown('#### :material/lightbulb: Giải thích điều chỉnh')
            st.write(f'Quy đổi định lượng theo tỷ lệ {target}/{recipe.khau_phan}.')
            if data and data['changes']:
                st.write(f"Đã giảm lượng của {len(data['changes'])} nguyên liệu so với bản quy đổi khẩu phần.")
                with st.expander('Xem chi tiết nguyên liệu đã giảm', expanded=False):
                    for change in data['changes']: st.markdown('- '+change)
                st.caption('Tính lại từ từng nguyên liệu; phần trăm trong bảng là chênh lệch ước tính mỗi khẩu phần.')
            else: st.write('Chỉ đổi số phần ăn: dinh dưỡng mỗi phần giữ nguyên, tổng lượng cả mẻ thay đổi.')
        with st.expander('Nguồn và giả định', icon=':material/menu_book:', expanded=False):
            st.markdown('**Nguồn công thức**')
            st.write(recipe.metadata.get('nguon') or (data['reference'].get('recipe_source') if data else None) or 'Kho công thức Bếp Của Ngoại.')
            if data:
                st.markdown('**Nguồn thành phần dinh dưỡng**')
                for i, url in enumerate(data['sources'], 1):
                    if url.startswith('https://'): st.markdown(f'[{i}. Xem tài liệu thành phần]({url})')
                st.caption('Phiên bản '+data['reference']['version']+'; kcal có thể khác bảng calo cũ do nguyên liệu tham chiếu.')
                st.markdown('**Quy đổi và thực phẩm đại diện**')
                for note in data['assumptions']: st.markdown('- '+note)
    question = st.chat_input('Hỏi thêm về món ăn hoặc yêu cầu điều chỉnh khác…', key='adjust_followup')
    if question:
        hoi(question)
        st.rerun()
