"""Intent catalog derived from the active knowledge store."""
from collections import defaultdict
from html import escape

import streamlit as st

from frontend.noi_dung_quan_tri import noi_dung_bien_tap


def danh_sach_y_dinh(docs):
    groups = defaultdict(list)
    for doc in docs:
        groups[doc.get("group") or "Chưa phân nhóm"].append(doc)
    return [{"name": name, "docs": rows, "count": len(rows),
             "samples": len({str(row.get("answer", "")).strip() for row in rows if str(row.get("answer", "")).strip()}),
             "description": f"Nhóm câu hỏi về {name[:1].lower() + name[1:]}",
             "active": True} for name, rows in sorted(groups.items())]


def _cell(column, text, bold=False, center=False):
    value = escape(str(text))
    column.html(f'<div title="{value}" style="font:{600 if bold else 400} 15px/28px Segoe UI,Arial,sans-serif;'
                f'color:#49291f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'
                f'text-align:{"center" if center else "left"};">{value}</div>')


def hien_thi_y_dinh(actor, docs):
    from backend.chatbot import tai_khoan
    if not tai_khoan.la_admin(actor):
        st.error("Bạn không có quyền quản trị.")
        st.stop()
    catalog = danh_sach_y_dinh(docs)
    with st.container(key="intent_listing", border=True):
        search, status, sort, add = st.columns([3.1, 1.15, 1.5, 1], gap="small", vertical_alignment="center")
        query = search.text_input("Tìm kiếm ý định", placeholder="Tìm kiếm ý định (ví dụ: món ăn, dinh dưỡng, công thức...)",
                                  icon=":material/search:", label_visibility="collapsed", key="intent_search")
        selected = status.selectbox("Trạng thái ý định", ["Tất cả trạng thái", "Đang hoạt động", "Ngừng hoạt động"],
                                    label_visibility="collapsed", key="intent_status")
        order = sort.selectbox("Sắp xếp ý định", ["Sắp xếp: Số câu hỏi giảm dần", "Sắp xếp: Số câu hỏi tăng dần", "Sắp xếp: Tên A–Z"],
                               label_visibility="collapsed", key="intent_sort")
        if add.button("Thêm ý định", icon=":material/add:", type="primary", width="stretch"):
            st.session_state["editor_Ý định chatbot"] = ""
            _bien_tap(actor)
        matches = [row for row in catalog if query.strip().casefold() in (row["name"] + " " + row["description"]).casefold()
                   and (selected == "Tất cả trạng thái" or (selected == "Đang hoạt động") == row["active"])]
        matches.sort(key=(lambda row: row["name"].casefold()) if order.endswith("A–Z") else
                     (lambda row: (-row["count"] if order.endswith("giảm dần") else row["count"], row["name"])))
        filters = (query, selected, order)
        if st.session_state.get("intent_filters") != filters:
            st.session_state.intent_page = 1
            st.session_state.intent_filters = filters
        pages = max(1, (len(matches)+5)//6)
        page = min(max(1, st.session_state.get("intent_page", 1)), pages)
        st.session_state.intent_page = page
        visible = matches[(page-1)*6:page*6]
        widths = [.38, 1.7, 2.6, .8, .8, 1.5, 1.1]
        with st.container(key="intent_table_frame"):
            with st.container(key="intent_table_header"):
                for col, label in zip(st.columns(widths, gap=None),
                                      ["STT", "Ý định (Intent)", "Mô tả", "Số câu hỏi", "Số câu mẫu", "Trạng thái", "Thao tác"]):
                    col.markdown(f"**{label}**")
            for index, row in enumerate(visible, (page-1)*6+1):
                with st.container(key=f"intent_table_row_{index}"):
                    cols = st.columns(widths, gap=None, vertical_alignment="center")
                    _cell(cols[0], index, center=True)
                    name = escape(row["name"])
                    cols[1].html(f'<div title="{name}" style="display:flex;align-items:center;gap:10px;min-width:0;'
                                 'font:600 15px/28px Segoe UI,Arial,sans-serif;color:#49291f;">'
                                 '<span style="display:flex;align-items:center;justify-content:center;flex:0 0 32px;'
                                 'height:28px;border-radius:12px;background:#fff0d5;color:#ff8600;">'
                                 '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">'
                                 '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg></span>'
                                 f'<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{name}</span></div>')
                    _cell(cols[2], row["description"])
                    _cell(cols[3], row["count"], center=True)
                    _cell(cols[4], row["samples"], center=True)
                    badge, switch = cols[5].columns([3, 1], gap=None, vertical_alignment="center")
                    badge.html('<span style="display:inline-block;border-radius:20px;padding:3px 9px;background:#e5fac7;'
                               'color:#248c00;font:500 13px/22px Segoe UI,Arial,sans-serif;white-space:nowrap;">Đang hoạt động</span>')
                    switch.toggle("Hoạt động", value=True, disabled=True, label_visibility="collapsed", key=f"intent_active_{index}",
                                  help="Ý định đang có trong kho trả lời. Thay đổi trạng thái cần qua quy trình cập nhật kho.")
                    view, edit, delete = cols[6].columns(3, gap=None)
                    if view.button("", icon=":material/visibility:", key=f"intent_view_{index}", help="Xem ý định"):
                        _xem(row)
                    if edit.button("", icon=":material/edit:", key=f"intent_edit_{index}", help="Biên tập ý định"):
                        st.session_state["editor_Ý định chatbot"] = ""
                        _bien_tap(actor, row)
                    delete.button("", icon=":material/delete:", key=f"intent_delete_{index}", disabled=True,
                                  help="Xóa ý định trong kho cần qua quy trình cập nhật kho tri thức.")
            if not visible:
                st.info("Không tìm thấy ý định phù hợp.")
        with st.container(key="intent_pagination"):
            footer, nav = st.columns([2.2, 1.8], vertical_alignment="center")
            footer.caption(f"Hiển thị {(page-1)*6+1 if visible else 0} – {min(page*6, len(matches))} / {len(matches)} ý định")
            numbers = sorted({1, pages, *range(max(1, page-1), min(pages, max(3, page+1))+1)})
            targets = [("‹", page-1)]
            previous = 0
            for number in numbers:
                if previous and number-previous > 1:
                    targets.append(("…", None))
                targets.append((str(number), number))
                previous = number
            targets.append(("›", page+1))
            for index, (column, (label, target)) in enumerate(zip(nav.columns(len(targets), gap="small"), targets)):
                if column.button(label, key=f"intent_nav_{index}", width="stretch",
                                 type="primary" if target == page else "secondary",
                                 disabled=target is None or target < 1 or target > pages):
                    st.session_state.intent_page = target
                    st.rerun()
    with st.expander("Kiểm tra nhận diện ý định"):
        from backend.chatbot.intent import phan_tich
        question = st.text_input("Nhập câu hỏi để kiểm tra", key="intent_test_question")
        if question:
            st.json(phan_tich(question))


@st.dialog("Chi tiết ý định", width="small")
def _xem(row):
    with st.container(key="intent_detail_compact"):
        st.subheader(row["name"])
        st.write(row["description"])
        st.caption(f'{row["count"]} câu hỏi · {row["samples"]} câu trả lời mẫu khác nhau trong kho')
        st.dataframe([{"Câu hỏi": d.get("question", ""), "Trả lời mẫu": d.get("answer", "")} for d in row["docs"]],
                     hide_index=True, width="stretch", height=300)


@st.dialog("Biên tập ý định", width="large")
def _bien_tap(actor, row=None):
    noi_dung_bien_tap(actor, "Ý định chatbot", ("Tên ý định", "Mô tả", "Câu mẫu", "Nguồn tham khảo"),
                      initial={"Tên ý định": row["name"], "Mô tả": row["description"],
                               "Câu mẫu": "\n".join(d.get("question", "") for d in row["docs"][:6])} if row else None)
