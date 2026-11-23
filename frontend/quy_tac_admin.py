"""Rules catalog and editorial workflow."""
import json
import streamlit as st
from backend.chatbot import co_so_du_lieu
from backend.chatbot.co_so_du_lieu import ket_noi
from backend.chatbot.ngon_ngu import chuan_hoa
from frontend.noi_dung_quan_tri import noi_dung_bien_tap


def phan_loai(title):
    text = chuan_hoa(title)
    if any(word in text for word in ("khau phan", "nguoi an")):
        return "Điều chỉnh khẩu phần"
    if any(word in text for word in ("thay", "khong co", "het thi")):
        return "Thay thế nguyên liệu"
    if any(word in text for word in ("khong dung", "bo ", "loai bo")):
        return "Bỏ nguyên liệu"
    if "giam" in text:
        return "Giảm lượng"
    return "Chưa phân loại"


def nhom_dinh_duong(title):
    text = chuan_hoa(title)
    for keywords, label in ((("muoi", "natri", "nuoc mam"), "Giảm natri"),
                             (("duong",), "Kiểm soát đường"),
                             (("dau", "beo", "nuoc cot dua"), "Giảm chất béo")):
        if any(word in text for word in keywords):
            return label
    return "Chưa phân loại"


def chon_loai_quy_tac(label):
    st.session_state.rule_type_filter = label


def hien_thi_quy_tac(actor, docs):
    from backend.chatbot import tai_khoan
    if not tai_khoan.la_admin(actor):
        st.error("Bạn không có quyền quản trị.")
        st.stop()
    from frontend.bang_quan_tri import esc

    with st.container(key="admin_rules_page"):
        # Initialize the same editorial table used by the other admin pages.
        with ket_noi() as con:
            if co_so_du_lieu.BACKEND == "sqlite":
                con.execute("""CREATE TABLE IF NOT EXISTS noi_dung_quan_tri (
                    ma VARCHAR(32) PRIMARY KEY, nhom VARCHAR(40) NOT NULL,
                    tieu_de VARCHAR(255) NOT NULL, noi_dung TEXT NOT NULL,
                    trang_thai VARCHAR(20) NOT NULL)""")
            edited = con.execute("SELECT * FROM noi_dung_quan_tri WHERE nhom=?",
                                 ("Quy tắc điều chỉnh",)).fetchall()
        source = [d for d in docs if d.get("group_folder") in
                  ("06_thay_the_nguyen_lieu", "07_dieu_chinh_cong_thuc")]
        items = [{"title": d["question"], "body": d.get("answer", ""), "status": "Trong kho",
                  "source": d.get("source") or "Chưa ghi nguồn"} for d in source]
        for row in edited:
            data = json.loads(row["noi_dung"])
            items.append({"title": row["tieu_de"], "body": data.get("Giảm, bỏ hoặc thay nguyên liệu", ""),
                          "status": row["trang_thai"], "source": data.get("Căn cứ áp dụng", "")})
        metrics = (("tune", "Tổng quy tắc / tài liệu", len(items)),
                   ("check", "Trong kho trả lời", len(source)),
                   ("schedule", "Chờ duyệt", sum(r["status"] == "Chờ duyệt" for r in items)),
                   ("edit_note", "Bản nháp", sum(r["status"] == "Nháp" for r in items)))
        st.html('<div class="admin-metrics">' + ''.join(
            f'<div class="admin-metric"><i class="material-symbols-rounded">{icon}</i>'
            f'<div><small>{title}</small><strong>{count}</strong></div></div>' for icon, title, count in metrics
        ) + '</div>')
        kinds = ["Tất cả quy tắc", "Thay thế nguyên liệu", "Giảm lượng", "Bỏ nguyên liệu", "Điều chỉnh khẩu phần"]
        kind = st.session_state.get("rule_type_filter", kinds[0])
        with st.container(key="rule_category_buttons"):
            for col, label in zip(st.columns([1, 1.3, .9, 1.1, 1.4], gap="small"), kinds):
                col.button(label, key=f"rule_category_{kinds.index(label)}", width="stretch",
                           type="primary" if kind == label else "secondary",
                           on_click=chon_loai_quy_tac, args=(label,))
        listing, edit = st.tabs(["Tất cả quy tắc", "Thêm / sửa quy tắc"])
        with listing, st.container(key="admin_rules_listing", border=True):
            search, nutrition, status, add = st.columns([2.5, 1.2, 1.2, 1], gap="small")
            query = search.text_input("Tìm quy tắc", placeholder="Ví dụ: nước mắm, giảm muối…", label_visibility="collapsed")
            group = nutrition.selectbox("Nhóm dinh dưỡng", ["Tất cả nhóm dinh dưỡng", "Giảm natri", "Kiểm soát đường", "Giảm chất béo", "Chưa phân loại"], label_visibility="collapsed")
            if add.button("Thêm quy tắc", icon=":material/add:", type="primary", width="stretch"):
                st.session_state.rule_add_notice = True
            if st.session_state.get("rule_add_notice"):
                st.caption("Mở tab Thêm / sửa quy tắc để nhập nội dung và căn cứ áp dụng.")
            state = status.selectbox("Trạng thái", ["Tất cả trạng thái", "Trong kho", "Nháp", "Chờ duyệt", "Đã duyệt"],
                                      label_visibility="collapsed")
            matches = [r for r in items if query.casefold() in (r["title"] + r["body"]).casefold()
                       and (state == "Tất cả trạng thái" or state == r["status"])
                       and (not kind or kind == kinds[0] or phan_loai(r["title"]) == kind)
                       and (group == "Tất cả nhóm dinh dưỡng" or nhom_dinh_duong(r["title"]) == group)]
            slot = st.container()
            pages = max(1, (len(matches) + 4) // 5)
            page = st.selectbox("Trang quy tắc", range(1, pages+1), key=f"rules_page_{pages}")
            with slot:
                for col, label in zip(st.columns([.3, 2, 1.2, 1.2, 3, 1]), ["#", "Quy tắc điều chỉnh", "Loại điều chỉnh", "Nhóm dinh dưỡng", "Mô tả / Nội dung", "Trạng thái"]):
                    col.markdown(f"**{label}**")
                for i, row in enumerate(matches[(page-1)*5:page*5], (page-1)*5+1):
                    with st.container(key=f"rule_row_{i}"):
                        cols = st.columns([.3, 2, 1.2, 1.2, 3, 1], vertical_alignment="center")
                        cols[0].write(str(i))
                        cols[1].markdown(f'**{row["title"]}**')
                        rule_type = phan_loai(row["title"])
                        color = {"Thay thế nguyên liệu": "purple", "Giảm lượng": "orange", "Bỏ nguyên liệu": "red"}.get(rule_type, "neutral")
                        cols[2].html(f'<span class="rule-type {color}">{esc(rule_type)}</span>')
                        cols[3].write(nhom_dinh_duong(row["title"]))
                        cols[4].write(row["body"][:230] + ("…" if len(row["body"]) > 230 else ""))
                        cols[5].html(f'<span class="role-badge">{esc(row["status"])}</span>')
                        with st.expander("Xem nội dung và căn cứ"):
                            st.write(row["body"])
                            st.caption(row["source"])
            st.caption(f"Hiển thị {len(matches[(page-1)*5:page*5])} / {len(matches)} mục")
        with edit:
            noi_dung_bien_tap(actor, "Quy tắc điều chỉnh",
                             ("Giảm, bỏ hoặc thay nguyên liệu", "Điều kiện áp dụng", "Căn cứ áp dụng"))
