"""Trang dang nhap Bep Mien Tay: asset cuc bo, hieu ung CSS, form Streamlit that."""
from functools import lru_cache
from pathlib import Path
import streamlit as st

from backend.chatbot import tai_khoan
from backend.chatbot.cau_hinh import ROOT

ASSETS=ROOT/'frontend/assets/login'


def tai_giao_dien():
    # Truyen thoi diem sua file vao cache de sua login.css la thay ngay, khong can tat server.
    return _tai_giao_dien((ASSETS/'login.css').stat().st_mtime)


@lru_cache(maxsize=1)
def _tai_giao_dien(_mtime):
    # Anh nen la file tinh (static/), khong nhung base64: CSS nhe nen ap dung ngay khi tai lai trang.
    background='/app/static/login/bep_mien_tay_background.png'
    css=(ASSETS/'login.css').read_text(encoding='utf-8').replace('__BACKGROUND__',background)
    pot=(ASSETS/'brand-pot.svg').read_text(encoding='utf-8')
    return css,pot


# Than mui ten net dut (chay ve phia mon an), dau mui ten net lien.
ARROW='''<svg viewBox="0 0 90 80" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path class="than" d="M15 5 Q5 58 70 66"/><path d="M57 57L70 66 57 72"/></svg>'''
ARROW_LEFT='''<svg viewBox="0 0 90 80" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path class="than" d="M72 5 Q77 52 16 65"/><path d="M28 54L16 65 33 69"/></svg>'''
HAT='''<svg class="bmt-hat" viewBox="0 0 64 52" aria-hidden="true"><path d="M18 36C8 36 4 26 10 19c4-5 10-5 13-3 2-8 9-12 16-10 6 2 8 6 8 9 6-3 14 1 13 9-1 7-6 11-12 12v12H18Z" fill="#fff8ec" stroke="#e8590c" stroke-width="3" stroke-linejoin="round"/><path d="M18 41h30" stroke="#e8590c" stroke-width="3"/><circle cx="28" cy="24" r="2" fill="#e8590c"/><circle cx="39" cy="24" r="2" fill="#e8590c"/><path d="M29 29q5 4 10 0" stroke="#e8590c" stroke-width="2.4" stroke-linecap="round" fill="none"/></svg>'''


def hien_thi(vao_bang_mat_khau,google_da_cau_hinh):
    css,pot=tai_giao_dien()
    # CSS va phan trang tri cung mot lan ve: khong bao gio hien chu/mui ten tran khi chua co CSS.
    # Phai xuong dong sau </style>: neu viet lien, Markdown coi cac dong thut le phia sau la khoi code.
    st.markdown('<style>'+css+'</style>\n'+'''<div class="bmt-login-scene" aria-hidden="true">
      <div class="bmt-note bmt-note-canh">Canh cá<br>nấu lá giang'''+ARROW+'''</div>
      <div class="bmt-note bmt-note-com">Cơm trắng'''+ARROW_LEFT+'''</div>
      <div class="bmt-note bmt-note-mam">Nước mắm ớt'''+ARROW_LEFT+'''</div>
      <div class="bmt-note bmt-note-ca">Cá kho tộ'''+ARROW_LEFT+'''</div>
      <div class="bmt-steam bmt-steam-canh"><i></i><i></i><i></i></div>
      <div class="bmt-steam bmt-steam-ca"><i></i><i></i><i></i></div>
      <i class="bmt-gleam bmt-gleam-ca"></i><i class="bmt-gleam bmt-gleam-mam"></i>
      <i class="bmt-glint g1"></i><i class="bmt-glint g2"></i><i class="bmt-glint g3"></i>
      <i class="bmt-glint g4"></i><i class="bmt-glint g5"></i><i class="bmt-glint g6"></i>
      <i class="bmt-glow"></i>
      <div class="bmt-dust"><i></i><i class="b"></i><i></i><i></i><i class="b"></i><i></i><i></i><i class="b"></i><i></i><i></i></div>
      <i class="bmt-leaf bmt-leaf-one"></i><i class="bmt-leaf bmt-leaf-two"></i>
    </div>''',unsafe_allow_html=True)
    with st.container(key='login_coluna'):
        st.markdown('<div class="bmt-brand"><div class="bmt-pot">'+pot+
                    '</div><div class="bmt-wordmark"><h1>Bếp <span>Miền'+HAT+'</span> Tây</h1>'
                    '<p>Trợ lý hướng dẫn nấu ăn, ưu tiên món miền Tây</p>'
                    '<span class="bmt-stroke"></span></div></div>',unsafe_allow_html=True)
        with st.container(key='the_dn'):
            tab_vao,tab_moi=st.tabs(['Đăng nhập','Tạo tài khoản'])
            with tab_vao,st.form('dang_nhap',border=False):
                ten=st.text_input('Tên đăng nhập',placeholder='Nhập tên đăng nhập của bạn',
                                  icon=':material/person:',autocomplete='username')
                mk=st.text_input('Mật khẩu',type='password',placeholder='Nhập mật khẩu của bạn',
                                 icon=':material/lock:',autocomplete='current-password')
                if st.form_submit_button('Đăng nhập',type='primary',width='stretch',
                                         icon=':material/arrow_forward:',icon_position='right'):
                    nd=tai_khoan.dang_nhap(ten,mk)
                    if nd:
                        vao_bang_mat_khau(nd)
                    st.error('Sai tên đăng nhập hoặc mật khẩu.')
            with tab_moi,st.form('dang_ky',border=False):
                c1,c2=st.columns(2)
                display=c1.text_input('Tên của bạn',placeholder='Ví dụ: Bảo Trâm',icon=':material/badge:')
                ten=c2.text_input('Tên đăng nhập',placeholder='vd: baotram',icon=':material/person:',autocomplete='username')
                c1,c2=st.columns(2)
                mk=c1.text_input('Mật khẩu',type='password',placeholder='ít nhất 8 ký tự',autocomplete='new-password')
                confirm=c2.text_input('Nhập lại mật khẩu',type='password',placeholder='Nhập lại mật khẩu',autocomplete='new-password')
                if st.form_submit_button('Tạo tài khoản',type='primary',width='stretch',
                                         icon=':material/arrow_forward:',icon_position='right'):
                    if mk!=confirm:
                        st.error('Hai mật khẩu chưa khớp.')
                    else:
                        ok,message=tai_khoan.dang_ky(ten,display,mk)
                        if ok:
                            vao_bang_mat_khau(tai_khoan.dang_nhap(ten,mk))
                        st.error(message)
            st.markdown('<div class="bmt-or">hoặc</div>',unsafe_allow_html=True)
            if google_da_cau_hinh():
                st.button('Đăng nhập bằng Gmail',key='nut_google',width='stretch',on_click=st.login,args=('google',))
            else:
                st.button('Đăng nhập bằng Gmail',key='nut_google',width='stretch',disabled=True,
                          help='Đăng nhập bằng Google hiện chưa được bật.')
            st.caption('Tài khoản và lịch sử trò chuyện chỉ lưu trên máy chạy backend.chatbot.')
