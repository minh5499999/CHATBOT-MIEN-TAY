"""Ingredient alias catalog, with editorial changes separate from active rules."""
from html import escape

import streamlit as st

from backend.chatbot.ngon_ngu import ALIASES, chuan_hoa
from frontend.noi_dung_quan_tri import noi_dung_bien_tap



def loc_nguyen_lieu(aliases, query, status):
    normalized = chuan_hoa(query.strip())
    return [{"name": name, "aliases": list(dict.fromkeys(values))} for name, values in aliases.items()
            if normalized in chuan_hoa(" ".join([name, *values])) and status != "Ngừng sử dụng"]


def _text(column, value, center=False):
    column.html(f'<div style="font:500 15px/28px Segoe UI,Arial,sans-serif;color:#49291f;'
                f'text-align:{"center" if center else "left"};">{escape(str(value))}</div>')


def _select_visible(names):
    selected = st.session_state.get("keyword_select_all", False)
    for name in names:
        st.session_state[f"keyword_selected_{name}"] = selected


def hien_thi_tu_khoa(actor):
    from backend.chatbot import tai_khoan
    if not tai_khoan.la_admin(actor):
        st.error("Bạn không có quyền quản trị.")
        st.stop()
    with st.container(key="keyword_listing", border=True):
        search, status, space, add = st.columns([3, 1.15, .9, 1.2], gap="small", vertical_alignment="center")
        query = search.text_input("Tìm nguyên liệu hoặc từ đồng nghĩa", placeholder="Tìm nguyên liệu hoặc từ đồng nghĩa...",
                                  icon=":material/search:", key="keyword_search", label_visibility="collapsed")
        selected = status.selectbox("Trạng thái từ khóa", ["Tất cả trạng thái", "Đang sử dụng", "Ngừng sử dụng"],
                                    key="keyword_status", label_visibility="collapsed")
        if add.button("Thêm nguyên liệu", icon=":material/add:", type="primary", width="stretch"):
            st.session_state["editor_Từ khóa chatbot"] = ""
            _bien_tap(actor)
        matches = loc_nguyen_lieu(ALIASES, query, selected)
        filters = (query, selected)
        if st.session_state.get("keyword_filters") != filters:
            st.session_state.keyword_page = 1
            st.session_state.keyword_filters = filters
        pages = max(1, (len(matches)+7)//8)
        page = min(max(1, st.session_state.get("keyword_page", 1)), pages)
        st.session_state.keyword_page = page
        visible = matches[(page-1)*8:page*8]
        names = [row["name"] for row in visible]
        st.session_state.keyword_select_all = bool(names) and all(st.session_state.get(f"keyword_selected_{name}", False) for name in names)
        widths = [.3, .3, 1.4, 2.8, .65, 1.1, 1]
        with st.container(key="keyword_table_frame"):
            with st.container(key="keyword_table_header"):
                cols = st.columns(widths, gap=None, vertical_alignment="center")
                cols[0].checkbox("Chọn tất cả trên trang", key="keyword_select_all", label_visibility="collapsed",
                                 on_change=_select_visible, args=(names,))
                for column, title in zip(cols[1:], ["#", "Nguyên liệu", "Từ khóa & đồng nghĩa", "Số từ khóa", "Trạng thái", "Thao tác"]):
                    column.markdown(f"**{title}**")
            for index, row in enumerate(visible, (page-1)*8+1):
                name = row["name"]
                with st.container(key=f"keyword_table_row_{index}"):
                    cols = st.columns(widths, gap=None, vertical_alignment="center")
                    cols[0].checkbox(f"Chọn {name}", key=f"keyword_selected_{name}", label_visibility="collapsed")
                    _text(cols[1], index, True)
                    cols[2].html(f'<div style="font:650 15px/28px Segoe UI,Arial,sans-serif;color:#542515;">{escape(name)}</div>')
                    chips, plus = cols[3].columns([4, 1], gap="small", vertical_alignment="center")
                    chips.html('<div style="display:flex;flex-wrap:wrap;align-items:center;gap:5px;min-height:28px;">' + ''.join(
                        '<span style="display:inline-block;padding:2px 9px;border:1px solid #f7e2cc;border-radius:14px;'
                        f'background:#fff1df;color:#583824;font:500 13px/20px Segoe UI,Arial,sans-serif;">{escape(value)}</span>'
                        for value in row["aliases"]) + '</div>')
                    if plus.button("Thêm", icon=":material/add:", key=f"keyword_add_{name}", help="Biên tập từ đồng nghĩa"):
                        st.session_state["editor_Từ khóa chatbot"] = ""
                        _bien_tap(actor, row)
                    _text(cols[4], len(row["aliases"]), True)
                    cols[5].html('<span style="display:inline-block;border-radius:20px;padding:3px 10px;background:#e5fac7;color:#248c00;'
                                 'font:600 13px/22px Segoe UI,Arial,sans-serif;white-space:nowrap;">● Đang sử dụng</span>')
                    view, edit, delete = cols[6].columns(3, gap=None)
                    if view.button("", icon=":material/visibility:", key=f"keyword_view_{name}", help="Xem từ khóa"):
                        _xem(row)
                    if edit.button("", icon=":material/edit:", key=f"keyword_edit_{name}", help="Biên tập nguyên liệu"):
                        st.session_state["editor_Từ khóa chatbot"] = ""
                        _bien_tap(actor, row)
                    delete.button("", icon=":material/delete:", key=f"keyword_delete_{name}", disabled=True,
                                  help="Từ khóa đang sử dụng cần được xóa qua quy trình cập nhật kho tri thức.")
            if not visible:
                st.info("Không tìm thấy nguyên liệu phù hợp.")
        with st.container(key="keyword_pagination"):
            footer, nav = st.columns([2.4, 1.6], vertical_alignment="center")
            footer.caption(f"Hiển thị {(page-1)*8+1 if visible else 0} – {min(page*8,len(matches))} / {len(matches)} nguyên liệu")
            numbers = sorted({1, pages, *range(max(1,page-1),min(pages,max(3,page+1))+1)})
            targets = [("«",1),("‹",page-1)]
            previous = 0
            for number in numbers:
                if previous and number-previous>1:
                    targets.append(("…",None))
                targets.append((str(number),number))
                previous=number
            targets.append(("›",page+1))
            for index,(column,(label,target)) in enumerate(zip(nav.columns(len(targets),gap="small"),targets)):
                if column.button(label,key=f"keyword_nav_{index}",width="stretch",
                                 type="primary" if target==page and index>=2 else "secondary",
                                 disabled=target is None or target<1 or target>pages or (index==0 and page==1)):
                    st.session_state.keyword_page=target
                    st.rerun()


@st.dialog("Chi tiết từ khóa", width="large")
def _xem(row):
    st.subheader(row["name"])
    st.caption(f'{len(row["aliases"])} từ khóa · Đang sử dụng')
    for value in row["aliases"]:
        st.write(f"• {value}")


@st.dialog("Biên tập từ khóa & đồng nghĩa", width="small")
def _bien_tap(actor, row=None):
    with st.container(key="keyword_editor_compact"):
        noi_dung_bien_tap(actor, "Từ khóa chatbot", ("Nguyên liệu", "Từ khóa & đồng nghĩa", "Nguồn tham khảo"),
                          initial={"Nguyên liệu":row["name"],"Từ khóa & đồng nghĩa":"\n".join(row["aliases"])} if row else None,
                          compact=True)
