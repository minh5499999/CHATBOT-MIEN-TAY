"""Trang trí trang trò chuyện; các thao tác vẫn dùng widget Streamlit thật."""
import html
from pathlib import Path
import streamlit as st

ASSETS = Path(__file__).parent / 'assets'


def ap_dung():
    css = (ASSETS / 'chat.css').read_text(encoding='utf-8')
    scene = ASSETS / 'chat-scene-v2.png'
    css = css.replace('__CHAT_SCENE__', f'/app/static/chat/chat-scene-v2.png?v={scene.stat().st_mtime_ns}')
    st.markdown('<style>' + css + '</style>', unsafe_allow_html=True)


def thuong_hieu():
    pot = (ASSETS / 'login/brand-pot.svg').read_text(encoding='utf-8')
    st.markdown('<div class="chat-brand"><div>' + pot + '</div><h2>Bếp Miền Tây</h2>'
                '<p>Trợ lý hướng dẫn nấu ăn<br>ưu tiên món miền Tây</p></div>', unsafe_allow_html=True)


def tieu_de(nguoi_dung):
    name = html.escape(nguoi_dung['ten_hien_thi'])
    role = 'Admin' if nguoi_dung.get('vai_tro') == 'admin' else 'Thành viên'
    pot = (ASSETS / 'login/brand-pot.svg').read_text(encoding='utf-8')
    st.markdown(f'<div class="chat-heading"><div class="chat-logo">{pot}</div>'
                '<div class="chat-heading-copy"><h1>Trò chuyện cùng Bếp Miền Tây</h1>'
                '<p>Bạn có thể hỏi gợi ý món ăn, cách nấu, dinh dưỡng hoặc thay thế nguyên liệu nhé!</p></div>'
                f'<div class="chat-account"><span>{name[:1].upper()}</span><div><b>{name}</b><small>{role}</small></div></div></div>',
                unsafe_allow_html=True)


def to_muc_chon(muc):
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]+', str(muc)):
        muc = 'nav_chat'
    sidebar = 'section[data-testid="stSidebar"][data-testid="stSidebar"]'
    keys = ['nav_chat', 'nav_suggest', 'nav_cook', 'cuoc_moi']
    reset = ','.join(f'{sidebar} .st-key-{key} button{state}' for key in keys for state in ('', ':hover', ':focus', ':active'))
    labels = ','.join(f'{sidebar} .st-key-{key} button p' for key in keys)
    selected = f'{sidebar} .st-key-{muc} button'
    css = f"""
    {reset} {{background:transparent!important;color:#96320e!important;box-shadow:none!important;border:1px solid transparent!important;}}
    {labels} {{color:#96320e!important;}}
    {selected}, {selected}:hover, {selected}:focus {{
        background:linear-gradient(110deg,#ffad12,#ff5900)!important;
        color:#fff!important;border-color:#ff890b!important;
        box-shadow:0 3px 8px #cc73152a!important;
    }}
    {selected} p {{color:#fff!important;font-weight:700!important;}}
    """
    st.markdown('<style>'+css+'</style>', unsafe_allow_html=True)
