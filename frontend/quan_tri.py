"""Trang quản trị Streamlit; mỗi thao tác kiểm tra quyền lại ở tầng SQLite."""
import streamlit as st
from backend.chatbot import tai_khoan


def _thong_bao(result):
    ok,message=result
    if ok:
        st.session_state.pop('admin_dialog',None)
        st.session_state['thong_bao_quan_tri']=message
        st.rerun()
    st.error(message)


def dong_dialog():
    st.session_state.pop('admin_dialog',None)


def sua_tai_khoan(actor, target):
    st.session_state.pop("admin_dialog", None)
    st.session_state.qt_doi_tuong = target
    st.session_state.account_default_tab = "Phân quyền / khóa tài khoản"


@st.dialog('Xác nhận xóa tài khoản',on_dismiss=dong_dialog)
def xoa_tai_khoan(actor,target):
    users=tai_khoan.danh_sach_nguoi_dung(actor)
    if not any(u['ten_dang_nhap']==target for u in users):
        st.error('Tài khoản không còn tồn tại.'); return
    st.warning(f'Xóa vĩnh viễn tài khoản **{target}**, toàn bộ phiên đăng nhập và lịch sử trò chuyện của tài khoản này. Không thể hoàn tác.')
    with st.form('xoa_tai_khoan_dialog'):
        confirm=st.text_input('Nhập đúng tên đăng nhập để xác nhận')
        if st.form_submit_button('Xác nhận xóa vĩnh viễn',type='primary'):
            if confirm.strip()!=target: st.error('Tên xác nhận chưa khớp.')
            else:
                result=tai_khoan.admin_xoa_tai_khoan(actor,target)
                if result[0] and st.session_state.get('qt_doi_tuong')==target:
                    st.session_state.pop('qt_doi_tuong',None)
                _thong_bao(result)


def bang_tai_khoan(users,actor,key):
    """Các nút thật theo từng dòng, không dùng liên kết HTML để thực hiện thao tác."""
    from frontend.bang_quan_tri import esc
    widths = [1.7, 1.8, .8, 1.1, 1.05, 1.05]
    head = st.columns(widths, gap="small")
    for col, label in zip(head, ["Tài khoản", "Email", "Vai trò", "Trạng thái", "Ngày đăng ký", "Thao tác"]):
        col.markdown(f"**{label}**")
    with st.container(key=f"account_rows_{key}"):
        for u in users:
            name = u["ten_dang_nhap"]
            cols = st.columns(widths, gap="small", vertical_alignment="center")
            cols[0].html(f'<div class="account-name"><i>{esc(name[:1].upper())}</i><b>{esc(name)}</b></div>')
            cols[1].text(u.get("email") or "—")
            cols[2].html(f'<span class="role-badge">{esc(u["vai_tro"].title())}</span>')
            status = "active" if u["kich_hoat"] else "locked"
            label = "Hoạt động" if u["kich_hoat"] else "Đã khóa"
            cols[3].html(f'<span class="status {status}">● {label}</span>')
            cols[4].text((u.get("ngay_tao") or "")[:10])
            with cols[5]:
                edit, delete = st.columns(2, gap=None)
                if edit.button("", icon=":material/edit:", key=f"edit_{key}_{name}"):
                    sua_tai_khoan(actor, name)
                if delete.button("", icon=":material/delete:", key=f"delete_{key}_{name}",
                                 disabled=name == actor):
                    st.session_state.admin_dialog = ("xoa", name)
        if not users: st.caption('Không tìm thấy tài khoản phù hợp.')
    pending=st.session_state.get('admin_dialog')
    if pending:
        action,target=pending
        if action == 'sua':
            sua_tai_khoan(actor, target)
        elif action=='xoa': xoa_tai_khoan(actor,target)


def _editer(actor, users=None):
    st.markdown('### :material/settings: Quản trị tài khoản')
    try:
        if users is None:
            users=tai_khoan.danh_sach_nguoi_dung(actor)
        notice=st.session_state.pop('thong_bao_quan_tri',None)
        if notice:
            st.success(notice)
        manage,create,password=st.tabs(['Phân quyền / khóa tài khoản','Tạo tài khoản','Đặt lại mật khẩu'],
                                        default=st.session_state.pop('account_default_tab', None),
                                        key='account_editor_tabs', on_change='rerun')
        if manage.open:
            with manage:
                target=st.selectbox('Tài khoản cần cập nhật',[u['ten_dang_nhap'] for u in users],key='qt_doi_tuong')
                profile=next(u for u in users if u['ten_dang_nhap']==target)
                with st.form(f'quan_tri_quyen_{target}'):
                    display = st.text_input('Tên hiển thị', value=profile['ten_hien_thi'], max_chars=80)
                    role=st.selectbox('Vai trò',['user','admin'],index=0 if profile['vai_tro']=='user' else 1, format_func=str.title)
                    active=st.checkbox('Cho phép đăng nhập',value=bool(profile['kich_hoat']))
                    if st.form_submit_button('Lưu quyền và trạng thái',icon=':material/save:',type='primary',width='stretch'):
                        _thong_bao(tai_khoan.admin_cap_nhat(actor,target,role,active,ten_hien_thi=display))
                st.markdown(
                    '<div class="account-permission-note"><b>ⓘ Lưu ý</b><ul>'
                    '<li>Admin quản trị toàn bộ hệ thống.</li>'
                    '<li>User sử dụng chatbot, xem và lưu công thức.</li>'
                    '<li>Tài khoản bị khóa không thể đăng nhập.</li></ul></div>',
                    unsafe_allow_html=True,
                )
        if create.open:
            with create, st.form('quan_tri_tao',clear_on_submit=True):
                name=st.text_input('Tên đăng nhập mới')
                display=st.text_input('Tên hiển thị mới')
                secret=st.text_input('Mật khẩu ban đầu',type='password',help='Từ 8 đến 64 ký tự.')
                confirm=st.text_input('Nhập lại mật khẩu ban đầu',type='password')
                role=st.selectbox('Vai trò tài khoản mới',['user','admin'])
                if st.form_submit_button('Tạo tài khoản mới'):
                    if secret!=confirm:
                        st.error('Hai mật khẩu chưa khớp.')
                    else:
                        _thong_bao(tai_khoan.admin_tao_tai_khoan(actor,name,display,secret,role))
        if password.open:
            with password:
                local=[u['ten_dang_nhap'] for u in users if not u['google']]
                if local:
                    with st.form('quan_tri_mat_khau',clear_on_submit=True):
                        target=st.selectbox('Tài khoản đặt lại mật khẩu',local)
                        secret=st.text_input('Mật khẩu mới',type='password')
                        confirm=st.text_input('Nhập lại mật khẩu mới',type='password')
                        if st.form_submit_button('Đặt lại mật khẩu'):
                            if secret!=confirm:
                                st.error('Hai mật khẩu chưa khớp.')
                            else:
                                _thong_bao(tai_khoan.admin_dat_lai_mat_khau(actor,target,secret))
        history = st.expander('Nhật ký quản trị gần đây', key='account_history', on_change='rerun')
        if history.open:
            with history:
                st.dataframe(tai_khoan.nhat_ky_quan_tri(actor),hide_index=True,width='stretch')
    except PermissionError as exc:
        st.error(str(exc))
        st.stop()


def hien_quan_tri(actor):
    users=tai_khoan.danh_sach_nguoi_dung(actor)
    stats=[('groups','Tổng tài khoản',len(users)),('workspace_premium','Admin đang hoạt động',sum(u['vai_tro']=='admin' and u['kich_hoat'] for u in users)),('lock','Tài khoản bị khóa',sum(not u['kich_hoat'] for u in users)),('sms','Cuộc trò chuyện',sum(u['so_cuoc_tro_chuyen'] for u in users))]
    st.markdown('<div class="admin-metrics">'+''.join(f'<div class="admin-metric"><i class="material-symbols-rounded" aria-hidden="true">{icon}</i><div><small>{label}</small><strong>{value}</strong></div></div>' for icon,label,value in stats)+'</div>',unsafe_allow_html=True)
    listing,editor=st.columns([1.65,1],gap='small')
    with listing, st.container(key="account_listing", border=True):
        title, add = st.columns([2, 1], vertical_alignment="center")
        title.markdown("### :material/list: Danh sách tài khoản")
        if add.button("Thêm tài khoản", icon=":material/add:", type="primary", width="stretch"):
            st.session_state.account_default_tab = "Tạo tài khoản"

        search, role, status = st.columns([1.7, 1, 1], gap="small")
        query = search.text_input("Tìm tài khoản", placeholder="Tìm tên tài khoản, email…", label_visibility="collapsed")
        selected = role.selectbox("Vai trò", ["Tất cả vai trò", "Admin", "User"], label_visibility="collapsed")
        active = status.selectbox("Trạng thái", ["Tất cả trạng thái", "Hoạt động", "Đã khóa"], label_visibility="collapsed")
        filtered = [
            u for u in users
            if query.strip().casefold() in " ".join(
                u.get(field) or "" for field in ("ten_dang_nhap", "ten_hien_thi", "email")
            ).casefold()
            and (selected == "Tất cả vai trò" or selected.lower() == u["vai_tro"])
            and (active == "Tất cả trạng thái" or bool(u["kich_hoat"]) == (active == "Hoạt động"))
        ]
        size = 8
        pages = max(1, (len(filtered) + size - 1) // size)
        table = st.container()
        page = st.selectbox("Trang tài khoản", range(1, pages + 1),
                            key=f"account_page_{pages}") if pages > 1 else 1
        shown = filtered[(page - 1) * size:page * size]
        with table:
            bang_tai_khoan(shown, actor, "accounts")
        st.caption(f"Hiển thị {len(shown)} / {len(filtered)} tài khoản phù hợp")
    with editor:
        with st.container(key='account_editor',border=True):
            _editer(actor, users)
