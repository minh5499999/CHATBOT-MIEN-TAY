"""Chatbot knowledge administration overview."""
import streamlit as st
from frontend.noi_dung_quan_tri import noi_dung_bien_tap


def _trang_thai_cau_hoi(row):
    status = str(row.get("trang_thai", row.get("status", ""))).strip().casefold()
    if status in {"cần kiểm tra", "chờ duyệt", "nháp", "pending", "draft", "needs_review", "rejected"}:
        return "Cần kiểm tra"
    if not str(row.get("question", "")).strip() or not str(row.get("answer", "")).strip():
        return "Cần kiểm tra"
    return "Đã duyệt"


def hien_thi_chatbot_admin(actor, docs):
    from backend.chatbot import tai_khoan
    if not tai_khoan.la_admin(actor):
        st.error("Bạn không có quyền quản trị.")
        st.stop()
    from frontend.bang_quan_tri import esc
    from backend.chatbot.cau_hoi_cho_hoc import lay_danh_sach_cau_hoi_chua_biet
    from backend.chatbot.intent import phan_tich

    unknown = lay_danh_sach_cau_hoi_chua_biet()
    with st.container(key="admin_chatbot_page"):
        stats = (("sms", "Tổng câu hỏi", str(len(docs))),
                 ("check", "Tỷ lệ trả lời đúng", "—"),
                 ("forum", "Câu hỏi chưa hiểu", str(len(unknown))),
                 ("star", "Đánh giá tích cực", "—"))
        st.html('<div class="admin-metrics">' + ''.join(
            f'<div class="admin-metric"><i class="material-symbols-rounded">{icon}</i>'
            f'<div><small>{label}</small><strong>{value}</strong></div></div>'
            for icon, label, value in stats) + '</div>')
        from frontend.du_lieu_tim_kiem_admin import hien_thi_thong_ke_tim_kiem
        hien_thi_thong_ke_tim_kiem()
        questions, intents, keywords, retrieval = st.tabs(
            [":material/chat_bubble_outline: Quản lý câu hỏi", ":material/psychology: Quản lý ý định",
             ":material/account_tree: Từ khóa & đồng nghĩa", ":material/database: Dữ liệu tìm kiếm"], key="chatbot_tabs", on_change="rerun")
        if questions.open:
            with questions, st.container(key="chatbot_questions_table", border=True):
                search, group, status, add = st.columns([2.3, 1.2, 1.2, 1], gap="small", vertical_alignment="center")
                query = search.text_input("Tìm câu hỏi", placeholder="Tìm kiếm câu hỏi, ý định...",
                                          icon=":material/search:", label_visibility="collapsed")
                groups = ["Tất cả danh mục"] + sorted({d.get("group", "") for d in docs})
                category = group.selectbox("Danh mục", groups, label_visibility="collapsed")
                selected_status = status.selectbox("Trạng thái", ["Tất cả trạng thái", "Đã duyệt", "Cần kiểm tra"], label_visibility="collapsed")
                if add.button("Thêm câu hỏi", icon=":material/add:", type="primary", width="stretch"):
                    st.session_state["editor_Quản lý chatbot"] = ""
                    _bien_tap_cau_hoi(actor)
                matched = [d for d in docs if query.casefold() in (d.get("question", "") + d.get("group", "")).casefold()
                           and (category == groups[0] or d.get("group") == category)
                           and (selected_status == "Tất cả trạng thái" or _trang_thai_cau_hoi(d) == selected_status)]
                page_key = "chatbot_question_page"
                filters = (query, category, selected_status)
                if st.session_state.get("chatbot_question_filters") != filters:
                    st.session_state[page_key] = 1
                    st.session_state.chatbot_question_filters = filters
                pages = max(1, (len(matched) + 4) // 5)
                page = min(max(1, st.session_state.get(page_key, 1)), pages)
                st.session_state[page_key] = page
                widths = [.4, 1.5, 1.2, 1.9, 1.05, 1.05]
                cell_style = "font:400 16px/28px 'Segoe UI',Arial,sans-serif;color:#49262a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:0;"
                visible = matched[(page - 1)*5:page*5]
                with st.container(key="chatbot_table_frame"):
                    with st.container(key="chatbot_table_header"):
                        for col, title in zip(st.columns(widths, gap=None),
                                              ["STT", "Câu hỏi", "Ý định", "Trả lời mẫu", "Trạng thái", "Thao tác"]):
                            col.markdown(f"**{title}**")
                    for index, row in enumerate(visible, (page - 1)*5 + 1):
                        with st.container(key=f"chatbot_question_row_{index}"):
                            cols = st.columns(widths, gap=None, vertical_alignment="center")
                            cols[0].html(f'<div class="chatbot-cell" style="{cell_style}">{index}</div>')
                            for col, field in zip(cols[1:4], ["question", "group", "answer"]):
                                text = esc(row.get(field, ""))
                                col.html(f'<div class="chatbot-cell" style="{cell_style}" title="{text}">{text}</div>')
                            label = _trang_thai_cau_hoi(row)
                            background, color = ("#e5fac7", "#299500") if label == "Đã duyệt" else ("#fff0cc", "#a96400")
                            cols[4].html(f'<div style="display:flex;align-items:center;justify-content:center;min-height:28px;">'
                                         f'<span style="display:inline-block;padding:4px 12px;border-radius:20px;background:{background};'
                                         f'color:{color};font:600 14px/22px Segoe UI,Arial,sans-serif;white-space:nowrap;">{label}</span></div>')
                            view, edit, delete = cols[5].columns(3, gap=None)
                            if view.button("", icon=":material/visibility:", key=f"chatbot_view_{index}", help="Xem câu trả lời"):
                                _xem_cau_hoi(row)
                            if edit.button("", icon=":material/edit:", key=f"chatbot_edit_{index}", help="Tạo bản biên tập"):
                                st.session_state["editor_Quản lý chatbot"] = ""
                                _bien_tap_cau_hoi(actor, row)
                            delete.button("", icon=":material/delete:", key=f"chatbot_delete_{index}", disabled=True,
                                          help="Câu hỏi trong kho đã kiểm duyệt cần được xóa qua quy trình cập nhật kho tri thức.")
                    if not visible:
                        st.info("Không tìm thấy câu hỏi phù hợp.")
                with st.container(key="chatbot_pagination"):
                    numbers = sorted({1, pages, *range(max(1, min(page-1, pages-2)), min(pages, max(3, page+1))+1)})
                    items = []
                    for number in numbers:
                        if items and number - items[-1] > 1:
                            items.append("…")
                        items.append(number)
                    footer, nav = st.columns([1.4, 2], vertical_alignment="center")
                    first = (page-1)*5+1 if visible else 0
                    footer.caption(f"Hiển thị {first} – {min(page*5, len(matched))} / {len(matched):,} câu hỏi".replace(",", "."))
                    buttons = nav.columns(len(items)+3, gap="small")
                    targets = [("«", 1), ("‹", page-1)] + [(str(n), n) for n in items] + [("›", page+1)]
                    for position, (col, (label, target)) in enumerate(zip(buttons, targets)):
                        disabled = target == "…" or (position < 2 and page == 1) or (position == len(targets)-1 and page == pages)
                        if col.button(label, key=f"chatbot_nav_{position}", disabled=disabled,
                                      type="primary" if target == page and position >= 2 else "secondary", width="stretch"):
                            st.session_state[page_key] = target
                            st.rerun()
        if intents.open:
            with intents:
                from frontend.y_dinh_admin import hien_thi_y_dinh
                hien_thi_y_dinh(actor, docs)
        if keywords.open:
            with keywords:
                from frontend.tu_khoa_admin import hien_thi_tu_khoa
                hien_thi_tu_khoa(actor)
        if retrieval.open:
            with retrieval:
                from frontend.du_lieu_tim_kiem_admin import hien_thi_du_lieu_tim_kiem
                hien_thi_du_lieu_tim_kiem(actor)


@st.dialog("Chi tiết câu hỏi", width="large")
def _xem_cau_hoi(row):
    st.subheader(row.get("question", ""))
    st.caption(row.get("group", ""))
    st.write(row.get("answer", ""))


@st.dialog("Biên tập câu hỏi", width="large")
def _bien_tap_cau_hoi(actor, row=None):
    noi_dung_bien_tap(actor, "Quản lý chatbot", ("Câu hỏi", "Ý định", "Trả lời mẫu", "Nguồn tham khảo"),
                      initial={"Câu hỏi": row.get("question", ""), "Ý định": row.get("group", ""),
                               "Trả lời mẫu": row.get("answer", "")} if row else None)
