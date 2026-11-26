"""Browse and act on the signed-in account's saved dishes."""
import streamlit as st

from backend.chatbot.cong_thuc import danh_muc
from backend.chatbot.ngon_ngu import chuan_hoa, khoa_cau_hoi
from frontend import mon_yeu_thich
from frontend.chon_mon_nau import ten_mon
from frontend.giao_dien_tro_chuyen import tieu_de_trang


def hien_thi_mon_da_luu(kho, account, on_open, on_adjust, on_browse):
    saved = mon_yeu_thich.danh_sach(account)
    with st.container(key="saved_dishes"):
        heading, add = st.columns([4, 1], vertical_alignment="center")
        with heading:
            tieu_de_trang("favorite", "Món yêu thích",
                          "Xem lại công thức đã lưu hoặc điều chỉnh khẩu phần.")
        add.button("Thêm món yêu thích", icon=":material/add:", on_click=on_browse,
                   args=("nav_cook",), width="stretch")
        if not saved:
            st.info("Bạn chưa lưu món nào. Mở một công thức rồi bấm Lưu vào món yêu thích.")
            return

        search, filters = st.columns([4, 1])
        query = search.text_input("Tìm món yêu thích", placeholder="Ví dụ: canh chua, cá kho…")
        groups = {"Tất cả món": "", "Món canh": "canh", "Món kho": "kho", "Món xào": "xao",
                  "Món hấp": "hap", "Món chiên": "chien"}
        group = groups[filters.selectbox("Nhóm món", list(groups))]
        recipes = {khoa_cau_hoi(r.cau_hoi): r for r in danh_muc(kho)}
        found = False
        for i, item in enumerate(saved):
            question = item["cau_hoi"]
            normalized = chuan_hoa(question)
            if chuan_hoa(query) not in normalized or (group and group not in normalized.split()):
                continue
            found = True
            recipe = recipes.get(khoa_cau_hoi(question))
            with st.container(key=f"saved_dish_{i}", border=True):
                picture, info, view, adjust, remove = st.columns(
                    [2, 4, 2, 1.65, .65], vertical_alignment="center"
                )
                with picture:
                    photos = {
                        "ca kho to": "mon-ca-kho.jpg",
                        "canh chua ca loc": "mon-canh.jpg",
                        "thit kho trung": "mon-nhanh.jpg",
                    }
                    photo = next((image for name, image in photos.items() if name in normalized), None)
                    if photo:
                        st.html(f'<img class="saved-dish-photo" src="/app/static/chat/{photo}" alt="">')
                    else:
                        st.image("/app/static/chat/avatar-bep.svg", width=72)
                with info:
                    st.markdown("**" + ten_mon(question) + "**")
                    details = []
                    if recipe and recipe.tong_phut is not None:
                        details.append(f"{recipe.tong_phut} phút")
                    if recipe and recipe.khau_phan:
                        details.append(f"{recipe.khau_phan} người")
                    if details:
                        st.caption(" · ".join(details))
                view.button("Xem công thức", key=f"yt_mo_{i}", icon=":material/skillet:",
                            type="primary", width="stretch", on_click=on_open, args=(question,))
                adjust.button("Điều chỉnh", key=f"yt_adjust_{i}", icon=":material/tune:",
                              disabled=not (recipe and recipe.khau_phan), on_click=on_adjust,
                              args=(recipe.id_goc,) if recipe else (), width="stretch",
                              help="Cần công thức có số khẩu phần gốc để quy đổi.")
                remove.button("", key=f"yt_xoa_{i}", icon=":material/delete:",
                              on_click=mon_yeu_thich.xoa, args=(account, question),
                              help="Bỏ khỏi món yêu thích")
        if not found:
            st.info("Không tìm thấy món phù hợp với bộ lọc.")
