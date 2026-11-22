"""Trang trí trang trò chuyện; các thao tác vẫn dùng widget Streamlit thật."""
import html
import re
from pathlib import Path
import streamlit as st

ASSETS = Path(__file__).parent / 'assets'
STATIC = Path(__file__).resolve().parents[1] / 'static/chat'

# Các mục thanh bên: (key, nhãn, icon). Thứ tự giống bản thiết kế.
MUC_THANH_BEN = [
    ('nav_chat', 'Trò chuyện', ':material/chat_bubble:'),
    ('nav_suggest', 'Gợi ý món ăn', ':material/restaurant_menu:'),
    ('nav_cook', 'Hướng dẫn nấu ăn', ':material/menu_book:'),
    ('nav_nutri', 'Dinh dưỡng & sức khỏe', ':material/ecg_heart:'),
    ('nav_adjust', 'Điều chỉnh công thức', ':material/tune:'),
    ('nav_fav', 'Món yêu thích', ':material/favorite:'),
    ('nav_profile', 'Hồ sơ cá nhân', ':material/person:'),
]

ICON_INFO = ('<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><circle cx="12" cy="12" r="10" '
             'fill="none" stroke="#f08a12" stroke-width="2"/><path d="M12 10.5v6" stroke="#f08a12" stroke-width="2.2" '
             'stroke-linecap="round"/><circle cx="12" cy="7.3" r="1.3" fill="#f08a12"/></svg>')


def _anh(ten):
    """Đường dẫn tĩnh kèm mốc sửa đổi để trình duyệt nạp ảnh mới khi ảnh thay đổi."""
    p = STATIC / ten
    v = p.stat().st_mtime_ns if p.exists() else 0
    return f'/app/static/chat/{ten}?v={v}'


def ap_dung():
    css = (ASSETS / 'chat.css').read_text(encoding='utf-8')
    for khoa, ten in [('__CHAT_SCENE__', 'chat-scene-v2.png'), ('__AVATAR_BEP__', 'avatar-bep.svg'),
                      ('__MON_CA_KHO__', 'mon-ca-kho.jpg'), ('__MON_CANH__', 'mon-canh.jpg'),
                      ('__MON_DINH_DUONG__', 'mon-dinh-duong.jpg'), ('__MON_NHANH__', 'mon-nhanh.jpg')]:
        css = css.replace(khoa, _anh(ten))
    st.markdown('<style>' + css + '</style>', unsafe_allow_html=True)


def thuong_hieu():
    pot = (ASSETS / 'login/brand-pot.svg').read_text(encoding='utf-8')
    st.markdown('<div class="chat-brand"><div>' + pot + '</div><h2>Bếp Miền Tây</h2>'
                '<p>Trợ lý hướng dẫn nấu ăn và dinh dưỡng món miền Tây</p></div>', unsafe_allow_html=True)


ICON_CHUONG = ('<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" '
               'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15Z"/>'
               '<path d="M10 20.5a2.2 2.2 0 0 0 4 0"/></svg>')
ICON_XUONG = ('<svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true" fill="none" stroke="currentColor" '
              'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>')


def tieu_de(nguoi_dung):
    name = html.escape(nguoi_dung['ten_hien_thi'])
    role = 'Admin' if nguoi_dung.get('vai_tro') == 'admin' else 'Thành viên'
    st.markdown(f'<div class="chat-heading"><div class="chat-logo"><img src="{_anh("header-basket.svg")}" alt=""></div>'
                '<div class="chat-heading-copy"><h1>Trò chuyện cùng Bếp Miền Tây</h1>'
                '<p>Bạn có thể hỏi gợi ý món ăn, cách nấu, dinh dưỡng hoặc thay thế nguyên liệu nhé!</p></div>'
                '<div class="chat-tools"><details class="chat-notifications">'
                f'<summary class="chat-bell" aria-label="Thông báo">{ICON_CHUONG}</summary>'
                '<div class="chat-notifications-panel"><strong>Thông báo</strong>'
                '<p>Bạn chưa có thông báo mới.</p></div></details>'
                f'<div class="chat-account"><span>{name[:1].upper()}</span><div><b>{name}</b>'
                f'<small>{role} {ICON_XUONG}</small></div></div></div></div>',
                unsafe_allow_html=True)


def thong_bao(dam, thuong):
    """Thẻ lưu ý cuối khung trò chuyện (biểu tượng i + câu in đậm + phần giải thích)."""
    st.markdown(f'<div class="chat-notice">{ICON_INFO}<p><b>{html.escape(dam)}</b> {html.escape(thuong)}</p></div>',
                unsafe_allow_html=True)


_NET = 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
ICON_TRANG = {
    'history': f'<circle cx="12" cy="12" r="9" {_NET}/><path d="M12 7v5l3 2" {_NET}/>',
    'favorite': f'<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" {_NET}/>',
    'person': f'<circle cx="12" cy="8" r="4" {_NET}/><path d="M4.5 20a7.5 7.5 0 0 1 15 0" {_NET}/>',
}


def tieu_de_trang(icon, ten, mo_ta):
    st.markdown(f'<div class="chat-page-title"><span><svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">'
                f'{ICON_TRANG.get(icon, "")}</svg></span>'
                f'<div><h3>{html.escape(ten)}</h3><p>{html.escape(mo_ta)}</p></div></div>', unsafe_allow_html=True)


def the_ho_so(nguoi_dung, so_cuoc, so_cau_hoi, so_yeu_thich):
    name = html.escape(nguoi_dung['ten_hien_thi'])
    user = html.escape(nguoi_dung['ten_dang_nhap'])
    role = 'Admin' if nguoi_dung.get('vai_tro') == 'admin' else 'Thành viên'
    cach = 'Tài khoản Google' if nguoi_dung.get('google') else 'Tên đăng nhập & mật khẩu'
    st.markdown(
        f'<div class="profile-card"><span class="profile-avatar">{name[:1].upper()}</span>'
        f'<div class="profile-info"><h3>{name}</h3><small>{role}</small>'
        f'<dl><dt>Tên đăng nhập</dt><dd>{user}</dd><dt>Cách đăng nhập</dt><dd>{cach}</dd></dl></div></div>'
        '<div class="profile-stats">' +
        ''.join(
            f'<div><i aria-hidden="true"><svg viewBox="0 0 24 24">{icon}</svg></i>'
            f'<div><b>{count}</b><span>{label}</span></div></div>'
            for count, label, icon in (
                (so_cuoc, 'Cuộc trò chuyện', f'<path d="M4 4h16v12H9l-5 4Z" {_NET}/><path d="M8 10h1m3 0h1m3 0h1" {_NET}/>'),
                (so_cau_hoi, 'Câu đã hỏi', f'<circle cx="12" cy="12" r="9" {_NET}/><path d="M9 9a3 3 0 1 1 4 3c-1 1-1 2-1 2m0 3h.01" {_NET}/>'),
                (so_yeu_thich, 'Món yêu thích', ICON_TRANG['favorite']),
            )
        ) + '</div>',
        unsafe_allow_html=True)


def to_muc_chon(muc):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', str(muc)):
        muc = 'nav_chat'
    sidebar = 'section[data-testid="stSidebar"][data-testid="stSidebar"]'
    keys = [k for k, _, _ in MUC_THANH_BEN]
    reset = ','.join(f'{sidebar} .st-key-{key} button{state}' for key in keys for state in ('', ':hover', ':focus', ':active'))
    labels = ','.join(f'{sidebar} .st-key-{key} button :is(p,span)' for key in keys)
    selected = f'{sidebar} .st-key-{muc} button'
    css = f"""
    {reset} {{background:transparent!important;color:#3B2A1E!important;box-shadow:none!important;border:1px solid transparent!important;}}
    {labels} {{color:#3B2A1E!important;}}
    {selected}, {selected}:hover, {selected}:focus {{
        background:#F08A24!important;
        color:#fff!important;border-color:#F08A24!important;
        box-shadow:0 6px 14px #f08a2445!important;
    }}
    {selected} :is(p,span) {{color:#fff!important;font-weight:700!important;}}
    """
    st.markdown('<style>'+css+'</style>', unsafe_allow_html=True)
