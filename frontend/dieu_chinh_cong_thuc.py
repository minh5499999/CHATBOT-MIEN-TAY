"""Recipe adjustment view backed by the active recipe catalog."""
import re

import streamlit as st

from backend.chatbot.cong_thuc import danh_muc, quy_doi_khau_phan
from frontend import mon_yeu_thich
from frontend.chon_mon_nau import ten_mon


def hien_thi_dieu_chinh(kho, ten_tai_khoan, hoi):
    recipes = {r.id_goc: r for r in danh_muc(kho) if r.khau_phan}
    st.markdown("### Phân tích và điều chỉnh công thức")
    if not recipes:
        st.info("Kho hiện chưa có công thức ghi rõ số khẩu phần.")
        return

    controls = st.columns([3, 1])
    recipe_id = controls[0].selectbox(
        "Chọn món", list(recipes), format_func=lambda i: ten_mon(recipes[i].cau_hoi), key="adjust_recipe_id"
    )
    recipe = recipes[recipe_id]
    target = controls[1].number_input("Khẩu phần", min_value=1, max_value=30, value=2)
    result = quy_doi_khau_phan(recipe, target)

    with st.chat_message("user"):
        st.write(f"Điều chỉnh công thức {ten_mon(recipe.cau_hoi)} cho {target} khẩu phần.")
    with st.chat_message("assistant", avatar="🍲"):
        st.write(f"Mình đã quy đổi các nguyên liệu có định lượng từ {recipe.khau_phan} xuống hoặc lên {target} khẩu phần.")

    main, aside = st.columns([2, 1], gap="medium")
    with main, st.container(key="adjust_main", border=True):
        st.markdown("#### So sánh nguyên liệu")
        original, adjusted = st.columns(2)
        original.markdown("**Công thức gốc**")
        original.markdown("\n".join(f"- {line.lstrip('-• ')}" for line in recipe.nguyen_lieu))
        adjusted.markdown("**Công thức đã điều chỉnh**")
        adjusted.markdown("\n".join(result["dong"]) or "Chưa có định lượng để quy đổi.")
        if result["chua_quy_doi"]:
            adjusted.caption("Cần tự cân chỉnh các mục sau:")
            adjusted.markdown("\n".join(result["chua_quy_doi"]))

        cooking, full = st.tabs(["Cách nấu", "Công thức gốc đầy đủ"])
        steps = re.search(r"(?im)^\s*(?:sơ chế|cách chế biến|cách làm|các bước)\b", recipe.noi_dung)
        with cooking:
            st.markdown(recipe.noi_dung[steps.start():] if steps else recipe.noi_dung)
            st.caption("Các bước và thời gian lấy từ công thức gốc. Dùng định lượng đã quy đổi ở trên.")
        with full:
            st.markdown(recipe.noi_dung)
        da_luu = mon_yeu_thich.da_luu(ten_tai_khoan, recipe.cau_hoi)
        if da_luu:
            st.button("Đã lưu", icon=":material/check:", key="adjust_recipe_saved", disabled=True)
        else:
            st.button("Lưu món", icon=":material/favorite:", key="adjust_recipe_save",
                      on_click=mon_yeu_thich.them, args=(ten_tai_khoan, recipe.cau_hoi))

    with aside, st.container(key="adjust_aside"):
        with st.container(border=True):
            st.markdown("#### So sánh dinh dưỡng")
            st.caption("Chưa có số liệu dinh dưỡng đã xác minh cho hai phiên bản công thức.")
        with st.container(border=True):
            st.markdown("#### Giải thích điều chỉnh")
            st.write(f"Định lượng được nhân với tỷ lệ {target}/{recipe.khau_phan}.")
        with st.container(border=True):
            st.markdown("#### Nguồn tham khảo")
            st.write(recipe.metadata.get("nguon") or "Kho công thức Bếp Miền Tây.")

    question = st.chat_input("Hỏi thêm về món ăn hoặc yêu cầu điều chỉnh khác…", key="adjust_followup")
    if question:
        hoi(question)
        st.rerun()
