"""Editorial records kept apart from the validated chatbot knowledge build."""
import json
from uuid import uuid4

import streamlit as st

from backend.chatbot import tai_khoan
from backend.chatbot.co_so_du_lieu import ket_noi


def noi_dung_bien_tap(actor, group, fields, initial=None, compact=False):
    if not tai_khoan.la_admin(actor):
        st.stop()
    with ket_noi() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS noi_dung_quan_tri (
            ma VARCHAR(32) PRIMARY KEY, nhom VARCHAR(40) NOT NULL,
            tieu_de VARCHAR(255) NOT NULL, noi_dung TEXT NOT NULL,
            trang_thai VARCHAR(20) NOT NULL
        )""")
        rows = con.execute(
            "SELECT * FROM noi_dung_quan_tri WHERE nhom=? ORDER BY tieu_de", (group,)
        ).fetchall()

    st.caption("Bản biên tập lưu riêng. Duyệt ở đây chưa đưa nội dung vào kho trả lời.")
    entries = {row["ma"]: row for row in rows}
    selected = st.selectbox("Bản biên tập", [""] + list(entries),
                            format_func=lambda key: entries[key]["tieu_de"] if key else "Thêm bản mới",
                            key=f"editor_{group}")
    current = entries.get(selected)
    data = json.loads(current["noi_dung"]) if current else (initial or {})
    with st.form(f"editor_form_{group}_{selected}"):
        title = st.text_input("Tên mục", value=current["tieu_de"] if current else (initial or {}).get(fields[0], ""), max_chars=200)
        values = {}
        for index, field in enumerate(fields):
            if compact and index == 0:
                values[field] = st.text_input(field, value=data.get(field, ""), max_chars=2500)
            else:
                values[field] = st.text_area(field, value=data.get(field, ""), max_chars=2500,
                                             height=68 if compact else 116)
        status = st.selectbox("Trạng thái", ["Nháp", "Chờ duyệt", "Đã duyệt"],
                              index=["Nháp", "Chờ duyệt", "Đã duyệt"].index(current["trang_thai"]) if current else 0)
        remove = st.checkbox("Xác nhận xóa bản này") if current else False
        save = st.form_submit_button("Lưu bản biên tập", type="primary")
        delete = st.form_submit_button("Xóa", disabled=not current)
    if not (save or delete):
        return
    if not tai_khoan.la_admin(actor):
        st.stop()
    if delete and not remove:
        st.warning("Hãy xác nhận trước khi xóa.")
        return
    if save and (not title.strip() or not values[fields[-1]].strip()):
        st.warning("Nhập tên mục và nguồn hoặc căn cứ áp dụng.")
        return
    with ket_noi(ghi=True) as con:
        if delete:
            con.execute("DELETE FROM noi_dung_quan_tri WHERE ma=? AND nhom=?", (selected, group))
        elif current:
            con.execute(
                "UPDATE noi_dung_quan_tri SET tieu_de=?,noi_dung=?,trang_thai=? WHERE ma=? AND nhom=?",
                (title.strip(), json.dumps(values, ensure_ascii=False), status, selected, group),
            )
        else:
            con.execute("INSERT INTO noi_dung_quan_tri VALUES (?,?,?,?,?)",
                        (uuid4().hex, group, title.strip(), json.dumps(values, ensure_ascii=False), status))
    st.rerun()
