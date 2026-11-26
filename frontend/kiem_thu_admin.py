"""Feedback and active-learning dashboard; expensive tools run on demand."""
from html import escape
import streamlit as st
from backend.chatbot.cau_hoi_cho_hoc import lay_danh_sach_cau_hoi_chua_biet

LABELS = [":material/layers: Khai phá & Gom cụm câu hỏi", ":material/add: Thêm câu hỏi & Công thức mới",
          ":material/settings: Thử nghiệm Tách từ & Trích xuất NLP"]


def _teach(cluster):
    st.session_state.form_cau_hoi = cluster['cau_hoi_dai_dien']
    st.session_state.feedback_tabs = LABELS[1]


@st.dialog('Chi tiết cụm câu hỏi', width='small')
def _view(cluster):
    st.subheader(cluster['chu_de'])
    st.caption(f"{cluster['so_cau_hoi']} câu hỏi trong cụm")
    for question in cluster['danh_sach_cau_hoi']:
        st.write('• '+question)
    st.button('Biên tập câu trả lời', icon=':material/edit:', on_click=_teach, args=(cluster,), type='primary')


def hien_thi_kiem_thu(actor, docs):
    # The outer container is a stable CSS hook shared with the other admin pages.
    with st.container(key='admin_feedback_page'):
        _noi_dung(actor, docs)


def _noi_dung(actor, docs):
    pending = lay_danh_sach_cau_hoi_chua_biet()
    st.markdown('<div class="feedback-banner"><span class="feedback-banner-icon">'
                '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round">'
                '<path d="m12 2 10 5-10 5L2 7zM2 12l10 5 10-5M2 17l10 5 10-5"/></svg></span>'
                '<div><strong>Quản trị Tự học (Active Learning) &amp; Tối ưu NLP</strong>'
                '<p>Mở rộng tri thức và tối ưu khả năng hiểu ngôn ngữ tiếng Việt, không cần gọi API LLM.</p></div></div>', unsafe_allow_html=True)
    tab_active, tab_them, tab_nlp = st.tabs(LABELS, key='feedback_tabs', on_change='rerun')
    stats = [('chat_bubble', 'Tổng câu hỏi', str(len(docs))), ('check', 'Tỷ lệ trả lời đúng', '—'),
             ('help', 'Câu hỏi chưa hiểu', str(len(pending))), ('star', 'Đánh giá tích cực', '—')]
    selected_tab = next(tab for tab in (tab_active, tab_them, tab_nlp) if tab.open)
    with selected_tab:
        st.markdown('<div class="admin-metrics feedback-metrics">'+''.join(
            f'<div class="admin-metric"><i class="material-symbols-rounded">{icon}</i>'
            f'<div><small>{label}</small><strong>{value}</strong></div></div>' for icon,label,value in stats)+'</div>', unsafe_allow_html=True)
    if tab_active.open:
        with tab_active:
            st.markdown('#### 1. Phát hiện khoảng trống tri thức từ lịch sử hỏi đáp')
            st.info('Hệ thống ghi nhận câu hỏi bot chưa trả lời được hoặc có độ tin cậy thấp. '
                    'Bấm quét để dùng vector embedding và DBSCAN gom các câu hỏi theo chủ đề.', icon=':material/info:')
            if st.button('Quét & Gom cụm câu hỏi', icon=':material/search:', type='primary', key='btn_gom_cum'):
                try:
                    with st.spinner('Đang phân tích và gom cụm câu hỏi…'):
                        from backend.chatbot.tu_hoc import gom_cum_cau_hoi
                        st.session_state.cum_da_gom = gom_cum_cau_hoi(eps=.35, min_samples=1)
                except Exception:
                    st.error('Chưa gom cụm được. Kiểm tra mô hình embedding cục bộ và thử lại.')
            st.markdown('#### :material/layers: Kết quả gom cụm chủ đề')
            clusters = st.session_state.get('cum_da_gom')
            if clusters:
                widths = [.4, 1.5, .7, 3, 1.6]
                with st.container(key='feedback_cluster_table'):
                    with st.container(key='feedback_cluster_header'):
                        for col,label in zip(st.columns(widths,gap=None),['STT','Chủ đề (cụm câu hỏi)','Số câu hỏi','Ví dụ câu hỏi','Thao tác']):
                            col.markdown(f'**{label}**')
                    for index,cluster in enumerate(clusters,1):
                        with st.container(key=f'feedback_cluster_row_{index}'):
                            cols=st.columns(widths,gap=None,vertical_alignment='center')
                            for column,value in zip(cols[:4],[index,cluster['chu_de'],cluster['so_cau_hoi'], '; '.join(cluster['danh_sach_cau_hoi'][:2])]):
                                column.markdown(escape(str(value)))
                            view,edit=cols[4].columns([1,1.3],gap='small')
                            if view.button('Xem',icon=':material/visibility:',key=f'feedback_view_{index}'):
                                _view(cluster)
                            edit.button('Chỉnh sửa',icon=':material/edit:',key=f'feedback_edit_{index}',on_click=_teach,args=(cluster,))
            elif clusters is not None:
                st.caption('Không có cụm câu hỏi phù hợp trong lần quét này.')
            elif pending:
                st.caption(f'Có {len(pending)} câu hỏi cần xem lại. Bấm “Quét & Gom cụm câu hỏi” để tạo kết quả.')
                with st.expander('Xem câu hỏi đang chờ'):
                    for row in pending:
                        st.write('• '+row.get('cau_hoi',''))
            else:
                st.caption('Chưa có câu hỏi cần gom cụm.')

    if tab_them.open:
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
                            from backend.chatbot.tu_hoc import them_cau_hoi_moi
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

    if tab_nlp.open:
        with tab_nlp:
            st.markdown("#### 3. Thử nghiệm Tách từ (BiMM), Keyword (TextRank) & Intent (ML)")
            st.caption("Xem cách hệ thống NLP cổ điển phân rã và hiểu câu hỏi người dùng.")

            q_test = st.text_input("Nhập câu hỏi để thử nghiệm", value="Tôi muốn nấu canh chua cá lóc không dùng me, cần nhiều đạm")
            if st.button("Phân tích câu hỏi", type="primary") and q_test.strip():
                from backend.chatbot.trich_xuat_thuc_the import phan_tich_chuyen_sau, lay_bo_tach_tu
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
