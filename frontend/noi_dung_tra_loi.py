"""Hiển thị nguồn dinh dưỡng trong mục thu gọn, giữ nguyên nội dung đã xác thực."""
import re
import streamlit as st


def tom_tat_calo(result):
    """Extract display values only from the already rendered calorie answer."""
    if result.get('reason_code') != 'EXCEL_CALORIE_ESTIMATE': return None
    text=result.get('cau_tra_loi','')
    whole=re.search(r'Cả công thức:\s*khoảng\s*\*\*([^*]+kcal)\*\*',text)
    portion=re.search(r'Mỗi khẩu phần:\s*khoảng\s*\*\*([^*]+kcal)\*\*',text)
    if not whole or not portion: return None
    important=[p for p in re.split(r'\n\s*\n',text) if any(term in p for term in
        ('Lượng bạn hỏi (','Chưa đủ dữ liệu tính kcal/100 g','Cần xác định lượng trong tô/đĩa'))]
    servings=re.search(r'chia thành ([\d.]+) phần bằng nhau',text)
    return dict(whole=whole[1],portion=portion[1],important=important,servings=servings[1] if servings else None)


def hien_calo_truc_tiep(result):
    summary=tom_tat_calo(result)
    if not summary: return False
    hien_noi_dung(result['cau_tra_loi'])
    return True


def calo_kem_cong_thuc(result, kho):
    """Attach only to a complete, unchanged cooking answer after policy rendering."""
    if result.get('loai') != 'tra_loi' or result.get('excel_calo_request'):
        return None
    topic = result.get('chu_de') or {}
    recipe_id = topic.get('id_goc')
    if recipe_id is None:
        return None
    from backend.chatbot.cong_thuc import danh_muc
    from frontend.du_lieu_dieu_chinh import original_scenario, clean
    recipe = next((r for r in danh_muc(kho) if r.id_goc == recipe_id), None)
    if not recipe:
        return None
    # Topic alone also occurs for ingredient-only and follow-up answers.
    if clean(recipe.noi_dung) not in clean(result.get('cau_tra_loi', '')):
        return None
    return original_scenario(recipe)


def hien_calo_cong_thuc(result, kho, *, key, on_adjust=None):
    data = calo_kem_cong_thuc(result, kho)
    if not data:
        return
    ref = data['reference']
    with st.container(border=True):
        st.markdown('#### Năng lượng của công thức này')
        whole, serving = st.columns(2)
        whole.metric('Cả công thức', f"≈ {ref['energy_total_kcal']:,.0f} kcal")
        serving.metric('Mỗi khẩu phần', f"≈ {ref['energy_per_serving_kcal']:,.0f} kcal")
        st.caption(f"Chia {ref['servings']:g} khẩu phần theo công thức tham chiếu. Đây là ước tính, chưa tính cơm hoặc món ăn kèm ngoài công thức.")
        st.caption('Cơ sở khẩu phần: '+ref['portion_basis']+'. Nếu nguồn ghi một khoảng, bảng dùng trung điểm để ước tính, không phải số phần chính xác của mẻ bạn nấu.')
        with st.expander('Xem chi tiết calo từng nguyên liệu', expanded=False, icon=':material/table_chart:'):
            st.markdown('**Calo được tính như thế nào?**')
            st.write(f"Tổng năng lượng các nguyên liệu ≈ {ref['energy_total_kcal']:,.1f} kcal. "
                     f"Mỗi phần = {ref['energy_total_kcal']:,.1f} ÷ {ref['servings']:g} ≈ {ref['energy_per_serving_kcal']:,.0f} kcal.")
            st.markdown('**Đóng góp của từng nguyên liệu**')
            rows=[]
            for item in data['energy_breakdown']:
                share=item['energy_kcal']/ref['energy_total_kcal']*100 if ref['energy_total_kcal'] else 0
                rows.append({'Nguyên liệu':item['ingredient'],
                    'Lượng tính calo':f"{item['mass']:,.1f} {item['unit']}",
                    'Calo cả mẻ':f"≈ {item['energy_kcal']:,.1f} kcal",
                    'Tỷ lệ':f'{share:.1f}%', 'Cơ sở':item['note']})
            st.dataframe(rows,hide_index=True,width='stretch',height=min(350,38+35*len(rows)),
                alt='Lượng nguyên liệu dùng tính năng lượng, calo đóng góp và tỷ lệ trong tổng cả mẻ')
            st.caption('Lượng tính calo đã áp dụng quy đổi, phần ăn được và hệ số giữ lại năng lượng giả định. '
                       'Ví dụ lượng cá nguyên con có thể khác lượng thịt cá ăn được. Số hiển thị được làm tròn; tổng tính từ số chưa làm tròn.')
        with st.expander('Xem nguồn và cách tính calo', expanded=False, icon=':material/menu_book:'):
            st.caption('Dùng cùng bộ tham chiếu với bảng so sánh khi điều chỉnh. '+ref['note'])
            st.write(ref.get('recipe_source') or 'Kho công thức Bếp Của Ngoại.')
            for i, url in enumerate(data['sources'], 1):
                if url.startswith('https://'):
                    st.markdown(f'[{i}. Nguồn thành phần]({url})')
            for note in data['assumptions']:
                st.markdown('- '+note)
        if on_adjust:
            st.button('Điều chỉnh công thức này', key=f'calo_adjust_{key}', icon=':material/tune:',
                      on_click=on_adjust, args=(ref['id'],))


def hien_noi_dung(text):
    paragraphs = re.split(r'\n\s*\n', text)
    sources = [p for p in paragraphs if p.lstrip().startswith('Nguồn thành phần năng lượng:')]
    if not sources:
        st.markdown(text)
        return
    st.markdown('\n\n'.join(p for p in paragraphs if p not in sources))
    with st.expander('Xem nguồn dinh dưỡng', expanded=False, icon=':material/menu_book:'):
        for source in sources:
            st.markdown(source)
