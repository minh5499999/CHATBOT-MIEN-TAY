"""Chọn công thức thật trước khi yêu cầu hướng dẫn nấu."""
import re
import streamlit as st


def ten_mon(cau_hoi):
    return re.sub(r'^(?:cách\s+(?:nấu|làm|chế biến)|hướng dẫn\s+(?:nấu|làm))\s+', '',
                  cau_hoi.strip(), flags=re.I).rstrip(' ?').capitalize()


def hien_thi_chon_mon(kho, on_chon):
    from backend.chatbot.cong_thuc import danh_muc
    from backend.chatbot.ngon_ngu import chuan_hoa

    with st.chat_message('assistant', avatar='🍲'):
        st.markdown('### Bạn muốn học nấu món nào?')
        st.markdown('Bấm chọn một món bên dưới để xem nguyên liệu và từng bước thực hiện nhé!')
        recipes = danh_muc(kho)
        query = st.text_input('Tìm món ăn', placeholder='Nhập tên món bạn muốn nấu…', key='tim_mon_huong_dan')
        matches = [r for r in recipes if chuan_hoa(query) in chuan_hoa(r.cau_hoi)]
        if not matches:
            st.info('Chưa tìm thấy công thức phù hợp. Bạn thử tên món khác nhé.')
            return
        # Paging keeps all recipes available without making the chat excessively long.
        pages = max(1, (len(matches) + 11) // 12)
        page = st.selectbox('Trang danh sách món', range(pages),
                            format_func=lambda i: f'Trang {i + 1}/{pages}',
                            key=f'trang_mon_{pages}') if pages > 1 else 0
        cols = st.columns(2)
        for i, recipe in enumerate(matches[page * 12:(page + 1) * 12]):
            cols[i % 2].button(ten_mon(recipe.cau_hoi), key=f'chon_cong_thuc_{recipe.id_goc}',
                               icon=':material/skillet:', width='stretch', on_click=on_chon,
                               args=(recipe.cau_hoi,))
