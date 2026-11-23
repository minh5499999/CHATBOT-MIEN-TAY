"""Account preference form backed by the account database."""
import streamlit as st

from frontend.luu_tuy_chon_ho_so import doc_tuy_chon, luu_tuy_chon


def hien_thi_tuy_chon(tai_khoan, nguoi_dung):
    state_key = f"profile_settings_{tai_khoan}"
    version_key = f"{state_key}_version"
    saved = doc_tuy_chon(tai_khoan)
    version = st.session_state.get(version_key, 0)

    if st.session_state.pop(f"{state_key}_feedback", False):
        st.success("Đã lưu thay đổi vào tài khoản.")

    with st.form(f"{state_key}_{version}", border=False, enter_to_submit=False):
        left, right = st.columns(2)
        with left:
            with st.expander("Thông tin cá nhân", icon=":material/person:", expanded=False):
                name = st.text_input("Họ và tên", value=nguoi_dung["ten_hien_thi"], max_chars=80)
                email = st.text_input("Email", value=saved.get("email", ""))
                phone = st.text_input("Số điện thoại", value=saved.get("phone", ""))
                birthday = st.date_input("Ngày sinh", value=saved.get("birthday"), min_value=None)
            with st.expander("Tùy chọn ăn uống", icon=":material/restaurant:", expanded=False):
                goals = ["Ăn uống cân bằng", "Ăn chay", "Ăn ít muối", "Ăn ít dầu"]
                goal = st.selectbox("Mục tiêu ăn uống", goals, index=goals.index(saved.get("goal", goals[0])))
                servings = st.number_input("Khẩu phần mặc định", 1, 30, saved.get("servings", 2))
                avoid = st.text_input("Nguyên liệu cần tránh", value=saved.get("avoid", ""))
                allergies = st.text_input("Dị ứng thực phẩm", value=saved.get("allergies", ""))
        with right:
            with st.expander("Tiền sử sức khỏe", icon=":material/ecg_heart:", expanded=False):
                health = st.multiselect("Tình trạng sức khỏe hiện tại", ["Cảm", "Ho", "Sốt", "Đang hành kinh"],
                                        default=saved.get("health", []), placeholder="Không có")
                notes = st.text_area("Lưu ý khác", value=saved.get("notes", ""), max_chars=200)
            with st.expander("Cài đặt thông báo", icon=":material/notifications:", expanded=False):
                alerts = {
                    label: st.toggle(label, value=saved.get("alerts", {}).get(label, default))
                    for label, default in (
                        ("Gợi ý món ăn theo nhu cầu", True),
                        ("Nhắc nấu món đã lưu", True),
                        ("Cập nhật công thức mới", False),
                        ("Tin tức dinh dưỡng", True),
                    )
                }

        save, reset = st.columns(2)
        do_save = save.form_submit_button("Lưu thay đổi", type="primary", width="stretch")
        do_reset = reset.form_submit_button("Đặt lại", width="stretch")

    if do_reset:
        st.session_state[version_key] = version + 1
        st.rerun()
    if do_save:
        name = name.strip()
        if not name:
            st.error("Vui lòng nhập họ và tên.")
            return
        settings = dict(email=email, phone=phone, birthday=birthday, goal=goal,
                        servings=servings, avoid=avoid, allergies=allergies, health=health,
                        notes=notes, alerts=alerts)
        try:
            ok = luu_tuy_chon(tai_khoan, name, settings)
        except ValueError as exc:
            st.error(str(exc))
            return
        if not ok:
            st.error("Tài khoản không còn hoạt động.")
            return
        st.session_state["nguoi_dung"] = {**nguoi_dung, "ten_hien_thi": name}
        st.session_state[f"{state_key}_feedback"] = True
        st.rerun()
