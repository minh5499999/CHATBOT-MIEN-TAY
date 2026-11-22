"""Recipe catalog management using the active knowledge store."""
import csv
import io
import re
import html

import streamlit as st

from backend.chatbot.cau_hinh import doc_cau_hinh
from backend.chatbot.cong_thuc import danh_muc
from backend.chatbot.ngon_ngu import chuan_hoa
from frontend.chon_mon_nau import ten_mon
from frontend.noi_dung_quan_tri import noi_dung_bien_tap


def nhom_mon(question):
    words = chuan_hoa(question).split()
    for word, label in (("canh", "Món canh"), ("lau", "Món lẩu"), ("kho", "Món kho"),
                        ("nuong", "Món nướng"), ("xao", "Món xào"), ("hap", "Món hấp")):
        if word in words:
            return label
    return "Món khác"


def do_kho(text):
    match = re.search(r"(?im)độ khó\s*[:：]\s*(dễ|trung bình|khó)", text)
    return match[1].capitalize() if match else "Chưa ghi rõ"


def hien_thi_mon_admin(actor):
    from frontend.bang_quan_tri import esc

    recipes = danh_muc(doc_cau_hinh()["kho_vector"])
    with st.container(key="admin_recipe_page"):
        stats = (
            ("restaurant", "Tổng số món ăn", str(len(recipes))),
            ("verified", "Trong kho trả lời", str(len(recipes))),
            ("schedule", "Chờ duyệt", "—"),
            ("cancel", "Từ chối", "—"),
        )
        st.html('<div class="admin-metrics">' + ''.join(
            f'<div class="admin-metric"><i class="material-symbols-rounded">{icon}</i>'
            f'<div><small>{label}</small><strong>{value}</strong></div></div>'
            for icon, label, value in stats
        ) + '</div>')
        listing, editor, categories, transfer = st.tabs(
            ["Danh sách món ăn", "Thêm món ăn", "Danh mục món", "Nhập / Xuất dữ liệu"]
        )
        with listing, st.container(key="admin_recipe_listing", border=True):
            search, group, status, difficulty, export = st.columns([2.5, 1.2, 1.2, 1.1, 1.1], gap="small")
            query = search.text_input("Tìm món", placeholder="Tìm món (ví dụ: cá kho, canh chua…)", label_visibility="collapsed")
            groups = ["Tất cả danh mục"] + sorted({nhom_mon(r.cau_hoi) for r in recipes})
            selected = group.selectbox("Danh mục", groups, label_visibility="collapsed")
            status.selectbox("Trạng thái", ["Trong kho trả lời"], label_visibility="collapsed")
            level = difficulty.selectbox("Độ khó", ["Tất cả độ khó", "Dễ", "Trung bình", "Khó", "Chưa ghi rõ"],
                                         label_visibility="collapsed")
            matches = [r for r in recipes if chuan_hoa(query) in chuan_hoa(r.cau_hoi)
                       and (selected == groups[0] or nhom_mon(r.cau_hoi) == selected)
                       and (level == "Tất cả độ khó" or do_kho(r.noi_dung) == level)]
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Tên món", "Danh mục", "Thời gian", "Khẩu phần"])
            for r in matches:
                writer.writerow([r.cau_hoi, nhom_mon(r.cau_hoi), r.tong_phut, r.khau_phan])
            export.download_button("Xuất dữ liệu", output.getvalue().encode("utf-8-sig"),
                                   file_name="mon_an.csv", icon=":material/download:", width="stretch")
            pages = max(1, (len(matches) + 4) // 5)
            page_key = "admin_dish_list_page"
            st.session_state[page_key] = min(st.session_state.get(page_key, 1), pages)
            page = st.session_state[page_key]
            widths = [.35, .35, 1, 3, 1.15, 1, 1, 1.2, .6]
            with st.container(key="recipe_table_header"):
                for col, title in zip(st.columns(widths, gap="small"),
                                      ["", "#", "Hình ảnh", "Tên món ăn", "Danh mục", "Thời gian", "Độ khó", "Trạng thái", "Xem"]):
                    col.markdown(f"**{title}**")
            for index, recipe in enumerate(matches[(page-1)*5:page*5], (page-1)*5+1):
                with st.container(key=f"admin_recipe_row_{recipe.id_goc}"):
                    cols = st.columns(widths, gap="small", vertical_alignment="center")
                    cols[0].checkbox("Chọn món", key=f"recipe_select_{recipe.id_goc}", label_visibility="collapsed")
                    cols[1].write(str(index))
                    name = chuan_hoa(recipe.cau_hoi)
                    photo = ("mon-canh.jpg" if "canh" in name else
                             "mon-nhanh.jpg" if "thit kho trung" in name else
                             "mon-ca-kho.jpg" if "ca" in name and "kho" in name else None)
                    image = photo or "avatar-bep.svg"
                    cols[2].html(f'<img class="admin-recipe-photo" src="/app/static/chat/{image}" alt="">')
                    description = re.split(r"\n\s*\n", recipe.noi_dung.strip())[0]
                    cols[3].html(f'<div class="admin-recipe-name"><b>{html.escape(ten_mon(recipe.cau_hoi))}</b>'
                                 f'<small>{html.escape(description[:100])}</small></div>')
                    category = nhom_mon(recipe.cau_hoi)
                    cols[4].html(f'<span class="recipe-category">{html.escape(category)}</span>')
                    cols[5].write(f"◷ {recipe.tong_phut} phút" if recipe.tong_phut is not None else "—")
                    cols[6].write(do_kho(recipe.noi_dung))
                    cols[7].html('<span class="status active">Trong kho</span>')
                    is_open = st.session_state.get("admin_recipe_view") == recipe.id_goc
                    if cols[8].button("", icon=":material/visibility_off:" if is_open else ":material/visibility:",
                                      key=f"recipe_view_{recipe.id_goc}"):
                        st.session_state.admin_recipe_view = None if is_open else recipe.id_goc
                        st.rerun()
                    if is_open:
                        with st.container(key=f"recipe_detail_{recipe.id_goc}", border=True):
                            st.markdown(f"#### {ten_mon(recipe.cau_hoi)}")
                            st.markdown(recipe.noi_dung)
            footer, previous, current, following = st.columns([6, .5, .5, .5])
            footer.caption(f"Hiển thị {len(matches[(page-1)*5:page*5])} / {len(matches)} món ăn")
            if previous.button("‹", disabled=page == 1):
                st.session_state[page_key] = page - 1
                st.rerun()
            current.button(str(page), type="primary", disabled=True)
            if following.button("›", disabled=page == pages):
                st.session_state[page_key] = page + 1
                st.rerun()
        with editor:
            noi_dung_bien_tap(actor, "Món ăn",
                             ("Nguyên liệu", "Cách nấu", "Thời gian và khẩu phần", "Nguồn tham khảo"))
        with categories:
            st.dataframe([{"Danh mục": group, "Số món": sum(nhom_mon(r.cau_hoi) == group for r in recipes)}
                          for group in groups[1:]], hide_index=True, width="stretch")
        with transfer:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["id", "Tên món", "Danh mục", "Thời gian (phút)", "Khẩu phần", "Nội dung"])
            for recipe in recipes:
                writer.writerow([recipe.id_goc, recipe.cau_hoi, nhom_mon(recipe.cau_hoi),
                                 recipe.tong_phut, recipe.khau_phan, recipe.noi_dung])
            st.download_button("Xuất dữ liệu CSV", output.getvalue().encode("utf-8-sig"),
                               file_name="mon_an.csv", mime="text/csv", icon=":material/download:")
            st.caption("Để thêm hoặc chỉnh nội dung, mở tab Thêm / sửa món ăn. Bản biên tập cần được đồng bộ vào kho trước khi chatbot sử dụng.")
