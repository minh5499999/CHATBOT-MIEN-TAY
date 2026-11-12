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


@st.dialog('Sửa tài khoản',on_dismiss=dong_dialog)
def sua_tai_khoan(actor,target):
    users=tai_khoan.danh_sach_nguoi_dung(actor)
    profile=next((u for u in users if u['ten_dang_nhap']==target),None)
    if profile is None:
        st.error('Tài khoản không còn tồn tại.'); return
    st.caption(f'Tên đăng nhập: {target}')
    with st.form('sua_tai_khoan_dialog'):
        display=st.text_input('Tên hiển thị',value=profile['ten_hien_thi'],max_chars=100)
        role=st.selectbox('Vai trò tài khoản',['user','admin'],index=int(profile['vai_tro']=='admin'))
        active=st.checkbox('Tài khoản hoạt động',value=bool(profile['kich_hoat']))
        if st.form_submit_button('Lưu thay đổi',type='primary'):
            if not display.strip(): st.error('Vui lòng nhập tên hiển thị.')
            else: _thong_bao(tai_khoan.admin_cap_nhat(actor,target,role,active,display))


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
    head=st.columns([2,1,1.4,1.7])
    for c,t in zip(head,['Tài khoản','Vai trò','Trạng thái','Thao tác']): c.markdown(f'**{t}**')
    with st.container(height=245,border=False,key='account_rows_'+key):
        for u in users:
            name=u['ten_dang_nhap']
            cols=st.columns([2,1,1.4,1.7],vertical_alignment='center')
            cols[0].markdown(f'<b>{esc(name)}</b>',unsafe_allow_html=True)
            cols[1].markdown(f'<span class="role-badge">{esc(u["vai_tro"].title())}</span>',unsafe_allow_html=True)
            cols[2].markdown(f'<span class="status {"active" if u["kich_hoat"] else "locked"}">● {"Hoạt động" if u["kich_hoat"] else "Đã khóa"}</span>',unsafe_allow_html=True)
            with cols[3]:
                edit,delete=st.columns(2,gap='small')
                if edit.button('Sửa',key=f'edit_{key}_{name}',help=f'Sửa tài khoản {name}',width='stretch'):
                    st.session_state.admin_dialog=('sua',name)
                if delete.button('Xóa',key=f'delete_{key}_{name}',help=f'Xóa tài khoản {name}',disabled=name==actor,width='stretch'):
                    st.session_state.admin_dialog=('xoa',name)
        if not users: st.caption('Không tìm thấy tài khoản phù hợp.')
    pending=st.session_state.get('admin_dialog')
    if pending:
        action,target=pending
        if action=='sua': sua_tai_khoan(actor,target)
        elif action=='xoa': xoa_tai_khoan(actor,target)


def _editer(actor):
    st.title('Quản trị tài khoản')
    try:
        users=tai_khoan.danh_sach_nguoi_dung(actor)
        notice=st.session_state.pop('thong_bao_quan_tri',None)
        if notice:
            st.success(notice)
        manage,create,password=st.tabs(['Phân quyền / khóa tài khoản','Tạo tài khoản','Đặt lại mật khẩu'])
        with manage:
            target=st.selectbox('Tài khoản cần cập nhật',[u['ten_dang_nhap'] for u in users],key='qt_doi_tuong')
            profile=next(u for u in users if u['ten_dang_nhap']==target)
            with st.form('quan_tri_quyen'):
                role=st.selectbox('Vai trò',['user','admin'],index=0 if profile['vai_tro']=='user' else 1)
                active=st.checkbox('Cho phép đăng nhập',value=bool(profile['kich_hoat']))
                if st.form_submit_button('Lưu quyền và trạng thái',type='primary'):
                    _thong_bao(tai_khoan.admin_cap_nhat(actor,target,role,active))
            st.caption('Không thể khóa hoặc hạ quyền admin cuối cùng đang hoạt động.')
        with create, st.form('quan_tri_tao',clear_on_submit=True):
            name=st.text_input('Tên đăng nhập mới')
            display=st.text_input('Tên hiển thị mới')
            secret=st.text_input('Mật khẩu ban đầu',type='password',help='Từ 8 đến 128 ký tự.')
            confirm=st.text_input('Nhập lại mật khẩu ban đầu',type='password')
            role=st.selectbox('Vai trò tài khoản mới',['user','admin'])
            if st.form_submit_button('Tạo tài khoản mới'):
                if secret!=confirm:
                    st.error('Hai mật khẩu chưa khớp.')
                else:
                    _thong_bao(tai_khoan.admin_tao_tai_khoan(actor,name,display,secret,role))
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
        with st.expander('Nhật ký quản trị gần đây'):
            st.dataframe(tai_khoan.nhat_ky_quan_tri(actor),hide_index=True,width='stretch')
    except PermissionError as exc:
        st.error(str(exc))
        st.stop()


def hien_quan_tri(actor):
    from frontend.bang_quan_tri import esc
    users=tai_khoan.danh_sach_nguoi_dung(actor)
    stats=[('♙','Tài khoản',len(users)),('♔','Admin đang hoạt động',sum(u['vai_tro']=='admin' and u['kich_hoat'] for u in users)),('▣','Tài khoản bị khóa',sum(not u['kich_hoat'] for u in users)),('☏','Cuộc trò chuyện',sum(u['so_cuoc_tro_chuyen'] for u in users))]
    st.markdown('<div class="admin-metrics">'+''.join(f'<div class="admin-metric"><i>{icon}</i><div><small>{label}</small><strong>{value}</strong></div></div>' for icon,label,value in stats)+'</div>',unsafe_allow_html=True)
    listing,editor=st.columns([1.35,1],gap='medium')
    with listing:
        with st.container(key='account_listing',border=True):
            st.markdown('### ♙ Danh sách tài khoản')
            search,role=st.columns([1.4,1])
            query=search.text_input('Tìm tên đăng nhập',placeholder='Tìm tên đăng nhập...',label_visibility='collapsed')
            selected=role.selectbox('Lọc tài khoản',['Tất cả vai trò','Admin','User'],label_visibility='collapsed')
            filtered=[u for u in users if query.casefold() in (u['ten_dang_nhap']+' '+u['ten_hien_thi']).casefold() and (selected=='Tất cả vai trò' or selected.lower()==u['vai_tro'])]
            bang_tai_khoan(filtered,actor,'accounts')
            st.caption(f'Hiển thị {len(filtered)} / {len(users)} tài khoản')
        with st.container(key='account_notes',border=True):
            st.markdown('### ◷ Hoạt động quản trị')
            logs=tai_khoan.nhat_ky_quan_tri(actor)
            names={'tao_tai_khoan':'Tạo tài khoản','cap_nhat_quyen':'Cập nhật quyền','dat_lai_mat_khau':'Đặt lại mật khẩu','xoa_tai_khoan':'Xóa tài khoản'}
            for row in logs[:3]:
                st.markdown(f'<div class="activity"><b>{esc(names.get(row["hanh_dong"],row["hanh_dong"]))} · {esc(row["doi_tuong"])}</b><small>{esc(row["tao_luc"])}</small></div>',unsafe_allow_html=True)
            if not logs: st.caption('Chưa có thao tác quản trị được ghi nhận.')
    with editor:
        with st.container(key='account_editor',border=True):
            _editer(actor)
