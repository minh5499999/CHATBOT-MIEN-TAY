"""System settings and backup guidance, styled to match the administration area."""
import streamlit as st
from backend.chatbot.co_so_du_lieu import BACKEND


def hien_thi_cai_dat(actor):
    from frontend.bang_quan_tri import chuyen
    with st.container(key='admin_settings_page'):
        system, audit = st.tabs([':material/database: Cấu hình và sao lưu', ':material/receipt_long: Nhật ký thao tác'],
                                key='settings_tabs', on_change='rerun')
        if system.open:
            with system:
                left, right = st.columns(2, gap='medium')
                with left, st.container(key='settings_database_card', border=True):
                    st.markdown('### :material/database: Cơ sở dữ liệu tài khoản')
                    st.markdown(f'<div class="settings-db-value"><strong>{BACKEND}</strong><span aria-label="Đã cấu hình">✓</span></div>', unsafe_allow_html=True)
                    st.divider()
                    st.markdown('### :material/key: Quản lý quyền và khóa tài khoản')
                    st.write('Mở trang quản lý để phân quyền, cấp khóa truy cập và cấu hình tài khoản.')
                    st.button('Mở quản lý tài khoản', icon=':material/group:', on_click=chuyen,
                              args=('Tài khoản',), key='settings_open_accounts')
                with right, st.container(key='settings_backup_card', border=True):
                    st.markdown('### :material/code: Lệnh hỗ trợ thao tác')
                    st.write('Sử dụng lệnh sau để xem hướng dẫn sao lưu dữ liệu:')
                    backup = 'scripts/sao_luu_mysql.py' if BACKEND == 'mysql' else 'scripts/sao_luu_sqlite.py'
                    st.code(f'python {backup} --help', language='powershell')
                with st.container(key='settings_tip', border=True):
                    st.markdown('### :material/info: Gợi ý')
                    st.write('Bạn nên sao lưu dữ liệu định kỳ để đảm bảo an toàn và có thể khôi phục khi cần thiết.')
        if audit.open:
            with audit:
                from frontend.nhat_ky import hien_nhat_ky
                from backend.chatbot import tai_khoan
                hien_nhat_ky(tai_khoan.nhat_ky_quan_tri(actor), tai_khoan.danh_sach_nguoi_dung(actor))
