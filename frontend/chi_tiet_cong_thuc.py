"""Cooking detail page: source recipe, reference nutrients, native actions."""
import html
import re
from pathlib import Path
import streamlit as st
from frontend import mon_yeu_thich
from frontend.noi_dung_tra_loi import calo_kem_cong_thuc

STATIC = Path(__file__).resolve().parents[1]/'static/chat'

def ten_hien_thi(question):
    name = re.sub(r'^(?:chỉ mình|hướng dẫn mình|hướng dẫn|giúp mình|cách)\s*(?:cách\s*)?(?:nấu|làm|chế biến|trộn|đổ)?\s*', '', question, flags=re.I)
    name = re.split(r'\s+(?:làm sao|nấu sao|làm thế nào|nấu thế nào|sao cho)\b', name, flags=re.I)[0]
    return re.sub(r'\s+(?:với|đi|nhé|nha|ạ)$', '', name.strip(' ?'), flags=re.I).capitalize()

def cac_buoc(text):
    """Keep all source cooking lines; never invent steps or cooking times."""
    match = re.search(r'(?im)^\s*(?:sơ chế|cách chế biến|cách làm|các bước|chế biến)\b', text)
    if not match: return [('Cách thực hiện', text)]
    body = re.split(r'(?im)^\s*(?:nguồn|tham khảo)\s*:', text[match.start():])[0]
    result=[]; title='Cách thực hiện'; lines=[]
    for line in body.splitlines():
        line=line.strip()
        if not line: continue
        if re.match(r'^(?:sơ chế|cách chế biến|cách làm|các bước|chế biến|hoàn thành)\b',line,re.I) and not line.startswith(('-', '•')):
            if lines: result.append((title,'\n'.join(lines)));lines=[]
            title=line.rstrip(':')
        else: lines.append(line.lstrip('-• '))
    if lines: result.append((title,'\n'.join(lines)))
    return result

def hien_thi_chi_tiet(result, kho, user, on_back, on_adjust, on_ask):
    from backend.chatbot.knowledge_policy import render_result
    from backend.chatbot.cong_thuc import danh_muc
    result=render_result(result,kho)
    data=calo_kem_cong_thuc(result,kho)
    recipe=next((r for r in danh_muc(kho) if r.id_goc==(result.get('chu_de') or {}).get('id_goc')),None)
    if result.get('loai')!='tra_loi' or not recipe:
        st.info('Công thức này chưa sẵn sàng để hiển thị. Bạn chọn lại món nhé.')
        st.button('Danh sách món ăn',on_click=on_back,key='recipe_back_unavailable')
        return
    # Require the entire source recipe, not an ingredient-only answer.
    from frontend.du_lieu_dieu_chinh import clean
    if clean(recipe.noi_dung) not in clean(result.get('cau_tra_loi','')):
        st.markdown(result['cau_tra_loi'])
        st.button('Danh sách món ăn',on_click=on_back,key='recipe_back_partial')
        return
    name=ten_hien_thi(recipe.cau_hoi)
    with st.container(key='recipe_detail'):
        st.button('Danh sách món ăn',icon=':material/arrow_back:',type='tertiary',on_click=on_back,key='recipe_back')
        title, actions=st.columns([1.5,1],vertical_alignment='center')
        with title:
            st.markdown(f'## {name}')
            if result.get('reason_code') == 'SOURCE_UNVERIFIED':
                st.caption('Công thức tham khảo trong kho; nguồn chưa được xác minh lại.')
            bits=[]
            if recipe.tong_phut: bits.append(f':material/schedule: Khoảng {recipe.tong_phut} phút')
            if recipe.khau_phan: bits.append(f':material/restaurant: {recipe.khau_phan} khẩu phần')
            if bits: st.markdown('　 ·　 '.join(bits))
        with actions,st.container(horizontal=True,horizontal_alignment='right'):
            saved=mon_yeu_thich.da_luu(user,recipe.cau_hoi)
            st.button('Đã lưu món' if saved else 'Lưu món',icon=':material/favorite:',key='detail_save',disabled=saved,
                on_click=mon_yeu_thich.them,args=(user,recipe.cau_hoi))
            st.download_button('Tải công thức',recipe.noi_dung,file_name=f'cong_thuc_{recipe.id_goc}.txt',
                mime='text/plain',icon=':material/download:',key='detail_download')
        left,right=st.columns([1,2.1],gap='medium')
        with left:
            image='mon-ca-kho.jpg' if 'kho' in name.casefold() and 'cá' in name.casefold() else 'mon-canh.jpg' if 'canh' in name.casefold() else None
            if image:
                st.image(str(STATIC/image),width='stretch',alt='Ảnh minh họa nhóm món '+name)
                st.caption('Ảnh minh họa nhóm món')
            else:
                with st.container(border=True):
                    st.markdown('## 🍲')
                    st.caption(name)
            with st.container(border=True,key='recipe_nutrients'):
                st.markdown('#### :material/nutrition: Giá trị dinh dưỡng')
                st.caption('Ước tính / 1 khẩu phần')
                if data:
                    ref=data['reference']
                    st.metric('Năng lượng',f"≈ {ref['energy_per_serving_kcal']:,.0f} kcal")
                    labels=[('protein_g','Đạm','g'),('fat_g','Chất béo','g'),('carbohydrate_available_g','Carbohydrate','g'),('sodium_mg','Natri','mg')]
                    st.table([{'Thành phần':label,'Giá trị':f"≈ {ref['per_serving'][key]:,.1f} {unit}"} for key,label,unit in labels],hide_index=True,alt='Bốn chỉ số dinh dưỡng mỗi khẩu phần')
                    st.caption(f"Cả công thức: ≈ {ref['energy_total_kcal']:,.0f} kcal • {ref['servings']:g} phần. Không gồm cơm/món ăn kèm ngoài công thức.")
                else: st.caption('Chưa có số liệu đúng phiên bản và khẩu phần cho công thức này.')
        with right:
            with st.container(border=True,key='recipe_ingredients'):
                st.markdown('#### :material/grocery: Nguyên liệu')
                a,b=st.columns(2)
                lines=recipe.nguyen_lieu
                midpoint=(len(lines)+1)//2
                for column,items in [(a,lines[:midpoint]),(b,lines[midpoint:])]:
                    with column: st.markdown('\n'.join('- '+x.lstrip('-• ') for x in items))
            with st.container(border=True,key='recipe_steps'):
                st.markdown('#### :material/skillet: Cách chế biến')
                steps=cac_buoc(recipe.noi_dung)
                cards=[]
                for i,(heading,body) in enumerate(steps,1):
                    paragraphs=''.join('<p>'+html.escape(line)+'</p>' for line in body.splitlines())
                    cards.append(f'<article class="recipe-step"><span class="recipe-step-number">{i}</span><h5>{html.escape(heading)}</h5>{paragraphs}</article>')
                st.html('<div class="recipe-step-grid">'+''.join(cards)+'</div>')
            with st.container(border=True,key='recipe_nutrition_note'):
                st.markdown(':material/eco: **Thông tin dinh dưỡng**')
                st.write('Giá trị hiển thị là ước tính theo định lượng và thực phẩm tham chiếu. Khi đổi khẩu phần, dầu hoặc gia vị, hãy xem lại bảng so sánh trước–sau.')
            with st.container(horizontal=True):
                st.button('Điều chỉnh công thức',type='primary',icon=':material/tune:',key='detail_adjust',on_click=on_adjust,args=(recipe.id_goc,))
                st.button('Hỏi thêm về món',icon=':material/chat:',key='detail_ask',on_click=on_ask,args=(f'Mình muốn hỏi thêm về công thức {recipe.cau_hoi}',))
        with st.expander('Nguồn công thức và cách tính dinh dưỡng',expanded=False,icon=':material/menu_book:'):
            st.write(recipe.metadata.get('nguon') or 'Kho công thức Bếp Của Ngoại.')
            if data:
                st.caption(data['reference']['note'])
                for i,url in enumerate(data['sources'],1):
                    if url.startswith('https://'): st.markdown(f'[{i}. Nguồn thành phần]({url})')
                for note in data['assumptions']: st.markdown('- '+note)
