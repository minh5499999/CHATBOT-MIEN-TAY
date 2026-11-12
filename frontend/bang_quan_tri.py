"""Bảng quản trị có dữ liệu thật; mọi truy cập đều kiểm tra quyền phía máy chủ."""
import html
import base64
import csv
import io
import json
import re
from functools import lru_cache
import streamlit as st
from backend.chatbot import tai_khoan
from backend.chatbot.cau_hinh import ROOT


def esc(value):
    return html.escape(str(value))


@lru_cache(maxsize=1)
def tai_tai_lieu():
    path = ROOT / 'data/merged/dataset.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


@st.cache_data(ttl=30, show_spinner=False)
def trang_thai_neo4j():
    try:
        from backend.chatbot.kho_neo4j import chay
        chay('RETURN 1 AS ok')
        return True
    except Exception:
        return False


def chuyen(muc):
    st.session_state.admin_muc = muc


CSS_ADMIN = ROOT/'frontend/assets/admin/dashboard.css'


@lru_cache(maxsize=1)
def style_admin(_mtime=None):
    """Khóa cache theo thời điểm sửa file CSS → sửa CSS là thấy ngay, không cần khởi động lại."""
    css=CSS_ADMIN.read_text(encoding='utf-8')
    photo=base64.b64encode((ROOT/'frontend/assets/admin/food-reference.png').read_bytes()).decode('ascii')
    decor=base64.b64encode((ROOT/'frontend/assets/admin/sidebar-kitchen.png').read_bytes()).decode('ascii')
    css+='\n.stApp:has(.bmt-admin) [data-testid="stSidebar"]{background-image:linear-gradient(#fffaf333,#fffaf333),url(data:image/png;base64,'+decor+');background-size:100% 100%;background-repeat:no-repeat;background-position:center;}'
    return css+'\n.dish-photo{background-image:url(data:image/png;base64,'+photo+')!important;background-size:620% 620%!important;} .dish-0{background-position:24% 85%!important}.dish-1{background-position:44% 85%!important}.dish-2{background-position:63% 85%!important}'


def _svg(path, size=18):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>')


ICON_BANG = {
    'cau_hoi': _svg('<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.6 8.6 0 0 1-3.8-.9L3 20.5l1.5-4.6A8.4 8.4 0 0 1 12 3.1a8.4 8.4 0 0 1 9 8.4z"/>'),
    'noi_dung': _svg('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8M8 9h2"/>'),
    'nguon': _svg('<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>'),
    'link': _svg('<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>', 14),
    'mo': _svg('<path d="M9 6l6 6-6 6"/>', 16),
}
ICON_TIEU_DE = {
    'Kho tri thức': _svg('<path d="M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z"/>'
                         '<path d="M5 8h3M5 11h3M16 8h3M16 11h3"/>', 34),
    'Món ăn': _svg('<path d="M3 11h18a9 9 0 0 1-18 0zM12 3v4M8 5v2M16 5v2"/>', 34),
    'spark': _svg('<path d="M8 9 7 3M12 13l5-4M13 18h6"/>', 24),
}
URL = re.compile(r'https?://\S+')


def _o_nguon(text):
    """Thẻ nguồn: bấm được nếu nguồn có đường dẫn; nhãn là chữ của nguồn (hoặc chính đường dẫn)."""
    text = ' '.join(str(text or '').split())
    url = (URL.search(text) or [None])[0]
    if not text:
        return '<td class="dl-src"></td><td class="dl-go"></td>'
    chip = f'{ICON_BANG["link"]}<span>{esc(text)}</span>'
    if url:
        href = esc(url)
        return (f'<td class="dl-src"><a class="src-chip" href="{href}" target="_blank" rel="noopener" title="{esc(text)}">{chip}</a></td>'
                f'<td class="dl-go"><a href="{href}" target="_blank" rel="noopener" aria-label="Mở nguồn">{ICON_BANG["mo"]}</a></td>')
    # không có đường dẫn (vd. "Không áp dụng"): thẻ nhạt, không icon link để khỏi trông như bấm được
    return f'<td class="dl-src"><span class="src-chip src-none" title="{esc(text)}"><span>{esc(text)}</span></span></td><td class="dl-go"></td>'


def _csv(rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Câu hỏi', 'Nội dung', 'Nguồn'])
    w.writerows([d.get('question', ''), d.get('answer', ''), d.get('source', '')] for d in rows)
    return buf.getvalue().encode('utf-8-sig')  # có BOM để Excel đọc đúng tiếng Việt


def _dao(key):
    st.session_state[key] = not st.session_state.get(key, False)


def bang_du_lieu(muc, source):
    """Bảng dữ liệu nguồn (Món ăn / Kho tri thức): ô tìm kiếm + nút công cụ, bảng HTML có thẻ nguồn."""
    day_du, mo_rong = st.session_state.get('dl_day_du', False), st.session_state.get('dl_mo_rong', False)
    with st.container(key='dl_cong_cu'):
        tim, nut = st.columns([1, 0.16], vertical_alignment='center', gap='small')
        query = tim.text_input('Tìm trong dữ liệu', placeholder='Nhập món ăn hoặc từ khóa...',
                               key='admin_tim_du_lieu', label_visibility='collapsed')
        q = ' '.join(query.split()).casefold()
        filtered = [d for d in source if q in (d.get('question', '') + ' ' + d.get('answer', '')).casefold()]
        with nut.container(horizontal=True, key='dl_nut', horizontal_alignment='right', gap='small'):
            st.button('', icon=':material/visibility_off:' if day_du else ':material/visibility:', key='dl_xem',
                      type='primary' if day_du else 'secondary', on_click=_dao, args=('dl_day_du',),
                      help='Thu gọn nội dung' if day_du else 'Hiện đầy đủ nội dung')
            st.download_button('', data=_csv(filtered), icon=':material/download:', key='dl_tai',
                               file_name=('mon_an' if muc == 'Món ăn' else 'kho_tri_thuc') + '.csv', mime='text/csv',
                               help='Tải các mục đang hiển thị (CSV)')
            st.button('', icon=':material/fullscreen_exit:' if mo_rong else ':material/fullscreen:', key='dl_rong',
                      type='primary' if mo_rong else 'secondary', on_click=_dao, args=('dl_mo_rong',),
                      help='Thu bảng lại' if mo_rong else 'Mở rộng bảng')
    st.caption(f'{len(filtered)} / {len(source)} mục - Dữ liệu nguồn của chatbot')
    if not filtered:
        st.markdown('<div class="dl-card dl-empty">Không tìm thấy mục nào khớp từ khóa.</div>', unsafe_allow_html=True)
        return
    gioi_han = None if day_du else 220  # thu gọn: cắt bớt chữ để trang nhẹ, CSS hiện dấu “…”
    rows = []
    for d in filtered:
        q_txt = ' '.join(str(d.get('question', '')).split())
        a_txt = ' '.join(str(d.get('answer', '')).split())
        a_ngan = a_txt if gioi_han is None or len(a_txt) <= gioi_han else a_txt[:gioi_han] + '…'
        rows.append(f'<tr><td class="dl-q" title="{esc(q_txt)}">{esc(q_txt)}</td>'
                    f'<td class="dl-a" title="{esc(a_txt[:400])}">{esc(a_ngan)}</td>{_o_nguon(d.get("source"))}</tr>')
    lop = 'dl-card' + (' dl-full' if day_du else '') + (' dl-wide' if mo_rong else '')
    st.markdown(f'<div class="{lop}"><table class="dl-table"><colgroup><col class="c-q"><col class="c-a"><col class="c-s"><col class="c-go"></colgroup>'
                f'<thead><tr><th>{ICON_BANG["cau_hoi"]}Câu hỏi</th><th>{ICON_BANG["noi_dung"]}Nội dung</th>'
                f'<th colspan="2">{ICON_BANG["nguon"]}Nguồn</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>',
                unsafe_allow_html=True)


def hien_tu_hoc_va_nlp(actor):
    from backend.chatbot.tu_hoc import (
        lay_danh_sach_cau_hoi_chua_biet,
        gom_cum_cau_hoi,
        them_cau_hoi_moi,
    )
    from backend.chatbot.trich_xuat_thuc_the import (
        phan_tich_chuyen_sau,
        lay_bo_tach_tu,
    )

    st.markdown("### 🧠 Quản trị Tự học (Active Learning) & Tối ưu NLP")
    st.caption("Mở rộng tri thức và tối ưu khả năng hiểu ngôn ngữ tiếng Việt hoàn toàn không cần gọi API LLM.")

    tab_active, tab_them, tab_nlp = st.tabs([
        "💡 Khai phá & Gom cụm câu hỏi chưa biết",
        "➕ Thêm câu hỏi & Công thức mới (FAISS Hot-reload)",
        "🧪 Thử nghiệm Tách từ & Trích xuất NLP"
    ])

    with tab_active:
        st.markdown("#### 1. Phát hiện khoảng trống tri thức từ lịch sử hỏi đáp")
        st.info("Hệ thống tự động ghi nhận các câu hỏi mà bot chưa trả lời được (ngoài phạm vi hoặc điểm tin cậy < ngưỡng), sau đó dùng vector embedding + DBSCAN để gom cụm theo chủ đề.")

        chua_biet = lay_danh_sach_cau_hoi_chua_biet()
        if st.button("🔍 Quét & Gom cụm câu hỏi", type="primary", key="btn_gom_cum"):
            st.session_state.cum_da_gom = gom_cum_cau_hoi(eps=0.35, min_samples=1)

        cum_list = st.session_state.get("cum_da_gom")
        if cum_list is None and chua_biet:
            st.session_state.cum_da_gom = gom_cum_cau_hoi(eps=0.35, min_samples=1)
            cum_list = st.session_state.cum_da_gom

        if cum_list:
            st.success(f"Phát hiện **{len(cum_list)}** cụm chủ đề người dùng đang quan tâm:")
            for c in cum_list:
                with st.expander(f"📌 Chủ đề: **{c['chu_de']}** ({c['so_cau_hoi']} câu hỏi)"):
                    st.write(f"- **Câu hỏi tiêu biểu:** `{c['cau_hoi_dai_dien']}`")
                    st.write("- **Các câu hỏi thành viên:**")
                    for q in c['danh_sach_cau_hoi']:
                        st.markdown(f"  * {q}")
                    if st.button("✨ Dạy bot câu trả lời cho cụm này", key=f"day_bot_{c['cum_id']}"):
                        st.session_state.form_cau_hoi = c['cau_hoi_dai_dien']
                        st.rerun()
        else:
            st.write("Hiện tại chưa ghi nhận câu hỏi ngoài phạm vi nào cần giải quyết. Hệ thống đang hoạt động ổn định!")

    with tab_them:
        st.markdown("#### 2. Thêm trực tiếp câu hỏi & công thức vào FAISS Index")
        st.caption("Cập nhật vector gia tăng (Incremental Indexing) trong vài mili-giây, không cần build lại toàn bộ kho tri thức.")

        default_q = st.session_state.get("form_cau_hoi", "")
        with st.form("form_them_tri_thuc"):
            q_in = st.text_input("Câu hỏi của người dùng", value=default_q, placeholder="Ví dụ: Cách làm lạp xưởng tươi Mai Quế Lộ miền Tây")
            nhom_in = st.selectbox("Nhóm tri thức", [
                "Hướng dẫn nấu món ăn miền Tây",
                "Món ăn miền Tây",
                "Giải thích nguyên liệu, gia vị",
                "Thay thế nguyên liệu",
                "Dinh dưỡng, lượng calo, chất đạm, chất béo",
                "Bảo quản và chế biến thực phẩm",
                "Gợi ý khi ốm, mệt mỏi, phục hồi",
            ])
            a_in = st.text_area("Câu trả lời / Công thức chuẩn", height=180, placeholder="Nhập nguyên liệu, các bước thực hiện hoặc lưu ý...")
            nguon_in = st.text_input("Nguồn tham khảo", value="Admin cập nhật trực tiếp")
            submitted = st.form_submit_button("🚀 Lưu & Cập nhật FAISS tức thì", type="primary")

            if submitted:
                if not q_in.strip() or not a_in.strip():
                    st.error("Vui lòng nhập đầy đủ câu hỏi và nội dung câu trả lời.")
                else:
                    nhom_folder_map = {
                        "Hướng dẫn nấu món ăn miền Tây": "02_huong_dan_nau_an",
                        "Món ăn miền Tây": "03_huong_dan_nau_mon_mien_tay",
                        "Giải thích nguyên liệu, gia vị": "04_giai_thich_nguyen_lieu",
                        "Thay thế nguyên liệu": "06_thay_the_nguyen_lieu",
                        "Dinh dưỡng, lượng calo, chất đạm, chất béo": "08_dinh_duong",
                        "Bảo quản và chế biến thực phẩm": "10_bao_quan",
                        "Gợi ý khi ốm, mệt mỏi, phục hồi": "12_goi_y_khi_om_met",
                    }
                    folder = nhom_folder_map.get(nhom_in, "02_huong_dan_nau_an")
                    try:
                        res = them_cau_hoi_moi(
                            cau_hoi=q_in,
                            cau_tra_loi=a_in,
                            nhom=nhom_in,
                            nhom_folder=folder,
                            nguon=nguon_in,
                            actor=actor,
                        )
                        st.success(f"🎉 Đã thêm thành công vào FAISS Index! Tổng số vector hiện tại: {res['tong_so_vector']}. Người dùng có thể hỏi câu này ngay lập tức.")
                        st.session_state.pop("form_cau_hoi", None)
                    except Exception as e:
                        st.error(f"Lỗi khi thêm vào kho tri thức: {e}")

    with tab_nlp:
        st.markdown("#### 3. Thử nghiệm Tách từ (BiMM), Keyword (TextRank) & Intent (ML)")
        st.caption("Xem cách hệ thống NLP cổ điển phân rã và hiểu câu hỏi người dùng.")

        q_test = st.text_input("Nhập câu hỏi để thử nghiệm", value="Tôi muốn nấu canh chua cá lóc không dùng me, cần nhiều đạm")
        if q_test.strip():
            analysis = phan_tich_chuyen_sau(q_test)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**1. Tách từ hai chiều (BiMM Tokenizer):**")
                tach = lay_bo_tach_tu()
                tokens_str = tach.tach_cau_hoi(analysis['cau_chuan'])
                st.code(tokens_str, language="text")

                st.markdown("**2. Từ khóa Đồ thị (TextRank / PageRank):**")
                for kw, score in analysis['tu_khoa_textrank']:
                    st.write(f"- `{kw}`: điểm PageRank `{score}`")

                st.markdown("**3. Phân loại Ý định (Classical ML - TF-IDF + LogisticRegression):**")
                ml_res = analysis['phan_loai_ml']
                st.write(f"- Dự đoán: **{ml_res['nhom']}** (Độ tin cậy: `{ml_res['diem']*100:.1f}%`)")
                for grp, p in ml_res.get('top_nhom', []):
                    st.write(f"  * {grp}: {p*100:.1f}%")

            with col2:
                st.markdown("**4. Cụm cú pháp thực thể (POS Grammar Chunker):**")
                chunks = analysis['cum_cu_phap']
                st.write("- **Cụm món ăn:**", chunks.get('cum_mon_an') or "Không có")
                st.write("- **Ràng buộc dinh dưỡng:**", chunks.get('rang_buoc_dinh_duong') or "Không có")
                st.write("- **Dị ứng / Kiêng khem:**", chunks.get('di_ung_kieng') or "Không có")

                st.markdown("**5. Tách phạm vi phủ định (Negation Scope):**")
                st.write("- ✅ **Positive (cần tìm):**", analysis['positive_keywords'] or "Không có")
                st.write("- ❌ **Negative (loại trừ):**", analysis['negative_keywords'] or "Không có")


def hien_thi(actor, dang_xuat):
    if not tai_khoan.la_admin(actor):
        st.error('Bạn không có quyền quản trị.')
        st.stop()
    users = tai_khoan.danh_sach_nguoi_dung(actor)
    logs = tai_khoan.nhat_ky_quan_tri(actor)
    docs = tai_tai_lieu()
    recipes = [d for d in docs if d.get('group_folder') in ('02_huong_dan_nau_an', '03_huong_dan_nau_mon_mien_tay')]
    st.markdown('<style>' + style_admin(CSS_ADMIN.stat().st_mtime) + '</style><span class="bmt-admin"></span>', unsafe_allow_html=True)
    with st.sidebar:
        pot = (ROOT/'frontend/assets/login/brand-pot.svg').read_text(encoding='utf-8')
        st.markdown(f'<div class="admin-brand">{pot}<div>Bếp Miền Tây</div></div>', unsafe_allow_html=True)
        st.session_state.setdefault('admin_muc', 'Tổng quan')
        for label, icon in [
            ('Tổng quan', 'home'),
            ('Tài khoản', 'person'),
            ('Món ăn', 'soup_kitchen'),
            ('Kho tri thức', 'menu_book'),
            ('Tự học & NLP', 'psychology'),
            ('Nhật ký hệ thống', 'description'),
        ]:
            st.button(label, icon=f':material/{icon}:', key='admin_nav_'+icon, width='stretch',
                      type='primary' if st.session_state.admin_muc==label else 'secondary', on_click=chuyen,args=(label,))
        st.divider()
        st.button('Đăng xuất', icon=':material/logout:', key='admin_logout',width='stretch',on_click=dang_xuat)
        st.markdown('<div class="sidebar-garden">🌿 🪴 🌿</div>',unsafe_allow_html=True)
    profile=tai_khoan.doc_ho_so(actor)
    name=profile.get('ten_hien_thi') or actor
    muc=st.session_state.admin_muc
    tieu_de = 'Tổng quan hệ thống' if muc=='Tổng quan' else esc(muc)
    if muc in ICON_TIEU_DE:  # Món ăn / Kho tri thức: icon trước tiêu đề + tia sáng cam phía sau
        tieu_de = f'<span class="h-ico">{ICON_TIEU_DE[muc]}</span>{tieu_de}<span class="h-spark">{ICON_TIEU_DE["spark"]}</span>'
    loi_chao = f'Chào <b>{esc(name)}</b>, cùng chăm sóc căn bếp hôm nay!'
    if muc == 'Nhật ký hệ thống':
        tieu_de = f'<span class="h-ico">{ICON_BANG["noi_dung"]}</span>{tieu_de}'
        loi_chao = 'Theo dõi các thao tác quản trị trong căn bếp của bạn.'
    st.markdown(f'<div class="admin-heading"><div><h1>{tieu_de}</h1><p>{loi_chao}</p></div><div class="admin-profile"><span>{esc(name[:1].upper())}</span><div><b>{esc(name)}</b><br><em>Admin</em></div></div></div>',unsafe_allow_html=True)
    if muc=='Tổng quan' and st.session_state.get('thong_bao_quan_tri'):
        st.success(st.session_state.pop('thong_bao_quan_tri'))
    if muc=='Tài khoản':
        from frontend.quan_tri import hien_quan_tri
        hien_quan_tri(actor)
        return
    if muc=='Nhật ký hệ thống':
        from frontend.nhat_ky import hien_nhat_ky
        hien_nhat_ky(logs, users)
        return
    if muc=='Tự học & NLP':
        hien_tu_hoc_va_nlp(actor)
        return
    if muc in ('Món ăn','Kho tri thức'):
        bang_du_lieu(muc, recipes if muc=='Món ăn' else docs)
        if muc=='Kho tri thức':
            st.info('Sau khi sửa dữ liệu nguồn, chạy quy trình tạo chunk/vector và nạp Neo4j để đồng bộ kho tìm kiếm.')
            st.code('python scripts/nap_neo4j.py',language='powershell')
        return
    counts=[('♙','Tài khoản',len(users)),('☏','Cuộc trò chuyện',sum(u['so_cuoc_tro_chuyen'] for u in users)),('♨','Mục hướng dẫn nấu ăn',len(recipes)),('▤','Tài liệu tri thức',len(docs))]
    st.markdown('<div class="admin-metrics">'+''.join(f'<div class="admin-metric"><i>{icon}</i><div><small>{label}</small><strong>{value}</strong></div></div>' for icon,label,value in counts)+'</div>',unsafe_allow_html=True)
    workspace=st.container(key='admin_workspace')
    left,right=workspace.columns([1.8,1],gap='medium')
    with left:
        with st.container(key='admin_accounts',border=True):
            title,action=st.columns([2,1])
            title.markdown('### ♙ Quản lý tài khoản')
            action.button('＋ Thêm tài khoản',type='primary',width='stretch',on_click=chuyen,args=('Tài khoản',))
            search,role=st.columns([1.4,1])
            q=search.text_input('Tìm tài khoản',placeholder='Tìm tên đăng nhập...',label_visibility='collapsed')
            r=role.selectbox('Lọc vai trò',['Tất cả vai trò','Admin','User'],label_visibility='collapsed')
            shown=[u for u in users if q.casefold() in u['ten_dang_nhap'].casefold() and (r=='Tất cả vai trò' or u['vai_tro']==r.lower())]
            from frontend.quan_tri import bang_tai_khoan
            bang_tai_khoan(shown,actor,'overview')
            st.button('Quản lý quyền / khóa tài khoản',icon=':material/manage_accounts:',on_click=chuyen,args=('Tài khoản',))
        with st.container(key='admin_dishes',border=True):
            st.markdown('### ♨ Món ăn trong kho tri thức')
            cols=st.columns(3)
            for idx,(col,(emoji,title,term)) in enumerate(zip(cols,[('🍲','Cá kho tộ','cá kho'),('🥬','Canh cá lá giang','lá giang'),('🥘','Thịt kho hột vịt','thịt kho')])):
                with col:
                    st.markdown(f'<div class="dish-card"><div class="dish-photo dish-{idx}" role="img" aria-label="{title}"></div><b>{title}</b><small>Món miền Tây</small></div>',unsafe_allow_html=True)
                    if st.button('Xem dữ liệu',key='dish_'+term,width='stretch'):
                        st.session_state.admin_tim_du_lieu=term
                        chuyen('Món ăn'); st.rerun()
    with right:
        with st.container(key='admin_connections',border=True):
            st.markdown('### ▱ Kết nối dữ liệu')
            from backend.chatbot.co_so_du_lieu import BACKEND
            ok=trang_thai_neo4j()
            for title,connected in [(('MySQL' if BACKEND=='mysql' else 'SQLite')+' · Tài khoản',True),('Neo4j · Tri thức',ok)]:
                st.markdown(f'<div class="connection-row"><b>{esc(title)}</b><span class="status {"active" if connected else "locked"}">{"Đã kết nối" if connected else "Chưa kết nối"}</span></div>',unsafe_allow_html=True)
            if st.button('Kiểm tra lại kết nối',icon=':material/refresh:',width='stretch'):
                trang_thai_neo4j.clear(); st.rerun()
            st.button('Quản lý dữ liệu',width='stretch',on_click=chuyen,args=('Kho tri thức',))
        with st.container(key='admin_activity',border=True):
            st.markdown('### ◷ Hoạt động gần đây')
            names={'tao_tai_khoan':'Tạo tài khoản','cap_nhat_quyen':'Cập nhật quyền','dat_lai_mat_khau':'Đặt lại mật khẩu'}
            for entry in logs[:4]:
                st.markdown(f'<div class="activity"><b>{esc(names.get(entry["hanh_dong"],entry["hanh_dong"]))}: {esc(entry["doi_tuong"])}</b><small>{esc(entry["tao_luc"])}</small></div>',unsafe_allow_html=True)
            if not logs: st.caption('Chưa có hoạt động quản trị.')
    st.caption('Bếp Miền Tây · Bảng quản trị · Dữ liệu thực tế của hệ thống')
