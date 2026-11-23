"""Nutrition overview of source records and editable nutrition entries."""
import json
import html

import streamlit as st

from backend.chatbot.cau_hinh import ROOT
from backend.chatbot.knowledge_policy import active_build
from frontend.noi_dung_quan_tri import noi_dung_bien_tap


def hien_thi_dinh_duong(actor, docs):
    from backend.chatbot import tai_khoan
    if not tai_khoan.la_admin(actor):
        st.error("Bạn không có quyền quản trị.")
        st.stop()
    from frontend.bang_quan_tri import esc

    build = active_build()
    dataset = build / "nutrition_data/datasets/dataset.json" if build else None
    foods = json.loads(dataset.read_text(encoding="utf8")).get("foods", {}) if dataset and dataset.exists() else {}
    nutrition = [d for d in docs if d.get("group_folder") in ("08_dinh_duong", "09_goi_y_mon_theo_dinh_duong")]
    sources = sorted({str(d.get("source")) for d in nutrition if d.get("source")})
    with st.container(key="admin_nutrition_page"):
        counts = (("database", "Tài liệu dinh dưỡng", len(nutrition)),
                  ("restaurant", "Món có định lượng", 0),
                  ("eco", "Nguyên liệu có số liệu", len(foods)),
                  ("menu_book", "Nguồn tài liệu", len(sources)))
        st.html('<div class="admin-metrics">' + ''.join(
            f'<div class="admin-metric"><i class="material-symbols-rounded">{icon}</i>'
            f'<div><small>{label}</small><strong>{count}</strong></div></div>'
            for icon, label, count in counts
        ) + '</div>')
        dishes, ingredients, references, edit = st.tabs(
            ["Dữ liệu món ăn", "Dữ liệu nguyên liệu", "Nguồn tham khảo", "Thêm dữ liệu"]
        )
        with dishes, st.container(key="nutrition_listing", border=True):
            query_col, source_col, status_col, add = st.columns([3, 1.2, 1.2, 1], gap="small")
            query = query_col.text_input("Tìm dữ liệu dinh dưỡng", placeholder="Tìm món (ví dụ: cá kho, canh chua…)",
                                        label_visibility="collapsed")
            source = source_col.selectbox("Nguồn", ["Tất cả nguồn"] + sources, label_visibility="collapsed")
            status_col.selectbox("Trạng thái", ["Tài liệu trong kho"], label_visibility="collapsed")
            if add.button("Thêm dữ liệu", icon=":material/add:", type="primary", width="stretch"):
                st.session_state.nutrition_edit_open = True
            matched = [d for d in nutrition if query.casefold() in (d.get("question", "") + " " + d.get("answer", "")).casefold()
                       and (source == "Tất cả nguồn" or str(d.get("source")) == source)]
            pages = max(1, (len(matched) + 4) // 5)
            key = "nutrition_list_page"
            st.session_state[key] = min(st.session_state.get(key, 1), pages)
            page = st.session_state[key]
            rows = []
            for i, row in enumerate(matched[(page-1)*5:page*5], (page-1)*5+1):
                title = html.escape(row.get("question", ""))
                ref = html.escape(str(row.get("source") or "Chưa ghi nguồn"))
                rows.append(f'<tr><td>{i}</td><td class="nutrition-dish">{title}</td>'
                            + '<td>—</td>' * 6
                            + f'<td><span class="nutrition-source">{ref}</span></td><td>—</td></tr>')
            st.html('<div class="nutrition-table-scroll"><table class="nutrition-table"><thead>'
                    '<tr><th rowspan="2">#</th><th rowspan="2">Món ăn / tài liệu</th>'
                    '<th colspan="6">Giá trị dinh dưỡng (trong 1 khẩu phần)</th>'
                    '<th rowspan="2">Nguồn tham khảo</th><th rowspan="2">Cập nhật</th></tr>'
                    '<tr><th>Năng lượng<br>(kcal)</th><th>Chất đạm<br>(g)</th><th>Chất béo<br>(g)</th>'
                    '<th>Carb<br>(g)</th><th>Chất xơ<br>(g)</th><th>Natri<br>(mg)</th></tr>'
                    '</thead><tbody>' + ''.join(rows) + '</tbody></table></div>')
            st.caption("Dấu — là giá trị chưa có trong dữ liệu nguồn.")
            summary, previous, current, following = st.columns([6, .5, .5, .5])
            summary.caption(f"Hiển thị {len(rows)} / {len(matched)} mục")
            if previous.button("‹", key="nutrition_previous", disabled=page == 1):
                st.session_state[key] = page - 1
                st.rerun()
            current.button(str(page), key="nutrition_current", disabled=True, type="primary")
            if following.button("›", key="nutrition_next", disabled=page == pages):
                st.session_state[key] = page + 1
                st.rerun()
            titles = {str(d["id"]): d for d in matched}
            selected = st.selectbox("Xem chi tiết tài liệu", [""] + list(titles),
                                    format_func=lambda i: titles[i]["question"] if i else "Chọn tài liệu")
            if selected:
                st.markdown(titles[selected].get("answer", ""))
            if st.session_state.get("nutrition_edit_open"):
                st.info("Mở tab Thêm dữ liệu để nhập thông tin và nguồn tham khảo.")
        with ingredients:
            records = []
            for key, food in foods.items():
                values = food.get("nutrients_per_100g", {})
                records.append({"Mã": key, "Nguyên liệu": food.get("name", ""),
                                "kcal": values.get("kcal"), "Đạm (g)": values.get("protein_g"),
                                "Béo (g)": values.get("lipid_g"), "Carb (g)": values.get("carbohydrate_g"),
                                "Natri (mg)": values.get("sodium_mg")})
            st.caption("Giá trị trên 100 g nguyên liệu theo dữ liệu nguồn.")
            st.dataframe(records, hide_index=True, width="stretch")
        with references:
            for source in sources:
                st.write(source)
            for food in foods.values():
                for citation in food.get("citations", []):
                    st.write(citation.get("document_version", ""))
                    st.caption(citation.get("passage", ""))
        with edit:
            noi_dung_bien_tap(actor, "Quản lý dinh dưỡng",
                             ("Kcal", "Đạm (g)", "Béo (g)", "Carbohydrate (g)", "Natri (mg)", "Nguồn tham khảo"))
