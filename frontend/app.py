"""Giao diện web của chatbot nấu ăn (Streamlit).

Chatbot LCEL: truy hồi lai có lọc điều kiện; chỉ dùng trích xuất và template có nguồn, không LLM.
Có đăng nhập và lịch sử trò chuyện riêng từng tài khoản (lưu trên máy).
Các chủ đề (nhóm dữ liệu) chỉ dùng bên trong cho việc tìm và định tuyến câu trả lời, không hiện trên giao diện.
Chạy: python -m streamlit run app.py   (hoặc bấm đúp chay_web.bat)
Mở trình duyệt: http://localhost:8501
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from datetime import datetime

import streamlit as st

from backend.chatbot import tai_khoan
from backend.chatbot.cau_hinh import doc_cau_hinh

st.set_page_config(page_title="Bếp Miền Tây – Trợ lý nấu ăn", page_icon="🍲", layout="centered")

CAU_GOI_Y = [
    "Cách nấu canh chua cá lóc miền Tây",
    "Cách làm bánh xèo miền Tây",
    "Lẩu mắm cần nguyên liệu gì",
    "Bữa sáng nên ăn gì để giảm cân",
    "Không có me thì nấu canh chua bằng gì",
    "Bị cảm cúm nên ăn gì cho mau khỏi",
]
GIOI_HAN = ("Trợ lý trả lời về nấu ăn và ăn uống dựa trên tài liệu của đồ án · có thể chọn nhầm câu, "
            "hãy xem nguồn · không thay lời khuyên của bác sĩ hay chuyên gia dinh dưỡng · không dùng cho dị ứng nặng "
            "hay bệnh cần điều trị · không tra cứu thông tin mới trên mạng · đừng nhập thông tin cá nhân.")

st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 760px;}
/* khối chỉ chứa <style> (và iframe ghi cookie) không chiếm chỗ → không tạo khoảng trống đầu trang */
.stElementContainer:has(> .stMarkdown style):not(:has([data-testid="stMarkdownContainer"] > :not(style):not(span:empty))) {display: none;}
[data-testid="stLayoutWrapper"]:has(> .st-key-o_cookie) {position: absolute; width: 0; height: 0; overflow: hidden; margin: 0;}
div[data-testid="stChatMessage"] {border-radius: 14px;}
.stButton > button {border-radius: 999px; text-align: left;}
/* thanh bên: nút lịch sử dạng dòng danh sách, căn trái */
section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {
    justify-content: flex-start; border: none; background: transparent; border-radius: 10px;
    padding: 0.25rem 0.6rem; min-height: 2rem;}
section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover {background: rgba(200,102,30,0.12);}
section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] p {
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.92rem;}
/* Keep every history icon and title at the same left edge, even for short titles. */
section[data-testid="stSidebar"] .stElementContainer[class*="st-key-ls_"] button {
    display: flex; justify-content: flex-start; text-align: left; width: 100%;}
section[data-testid="stSidebar"] .stElementContainer[class*="st-key-ls_"] button > div {
    flex: 1; min-width: 0; justify-content: flex-start;}
section[data-testid="stSidebar"] .stElementContainer[class*="st-key-ls_"] button [data-testid="stMarkdownContainer"] {
    flex: 1; min-width: 0; text-align: left;}
section[data-testid="stSidebar"] .stElementContainer[class*="st-key-xoa_"] button {
    width: 100%; justify-content: center;}
/* thanh bên: bỏ khoảng trống lớn phía trên tên ứng dụng */
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {height: 2.2rem; min-height: 0; padding: 0.4rem 1rem 0 1rem;}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {padding-top: 0;}
section[data-testid="stSidebar"] h3 {padding-top: 0; margin-top: 0;}
/* tên ứng dụng ở đầu thanh bên: chữ to, kéo lên ngang hàng nút thu gọn thanh bên */
.ten-app {font-size: 1.75rem; font-weight: 800; line-height: 1.2; margin: -2.4rem 0 0.2rem 0; color: #8A3F0C;}
/* thanh bên cao đủ một màn hình → chân thanh bên (margin-top: auto) luôn nằm sát đáy, kể cả khi ít nội dung */
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {display: flex; flex-direction: column;}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] > * {flex-shrink: 0;}  /* nội dung dài: cuộn, không co đầu thanh bên */
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    flex: 1 0 auto; display: flex; flex-direction: column; padding-bottom: 0;}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div {flex: 1; display: flex; flex-direction: column;}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {flex: 1;}
/* sticky đặt ở lớp bọc stLayoutWrapper: lớp này chỉ cao bằng chân trang nên sticky đặt trong nó không có tác dụng */
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:has(> .st-key-chan_trang) {
    position: sticky; bottom: 0; z-index: 2; margin-top: auto;}
section[data-testid="stSidebar"] .st-key-chan_trang {
    padding: 0.6rem 0 0.8rem 0;
    background: var(--secondary-background-color, #F7E6D3); border-top: 1px solid rgba(59,42,30,0.15);}
/* ẩn nút Deploy và menu ⋮ của Streamlit (chỉ dành cho người lập trình); giữ thanh trên để còn nút mở lại thanh bên */
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"] {display: none !important;}
/* nút Đăng xuất: có khung, không trong suốt như các dòng danh sách */
section[data-testid="stSidebar"] .st-key-dang_xuat button {
    justify-content: center; background: #FFFFFF; border: 1px solid rgba(169,80,15,0.45); border-radius: 12px;
    min-height: 2.6rem;}
section[data-testid="stSidebar"] .st-key-dang_xuat button:hover {background: rgba(200,102,30,0.12); border-color: #A9500F;}
section[data-testid="stSidebar"] .st-key-dang_xuat button p {font-weight: 600;}
.nhan-muc {font-size: 0.78rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; opacity: 0.6;
           margin: 0.8rem 0 0.2rem 0.6rem;}
.the-dang-nhap {text-align: center; margin: 1.5rem 0 1rem 0;}
.the-dang-nhap .logo {font-size: 3.2rem; line-height: 1;}
.the-dang-nhap h1 {margin: 0.4rem 0 0.2rem 0; padding: 0;}
/* ba chấm nhấp nháy trong bong bóng trợ lý khi đang tìm câu trả lời */
.dang-nghi {display: inline-flex; gap: 0.35rem; padding: 0.55rem 0.2rem;}
.dang-nghi span {width: 0.55rem; height: 0.55rem; border-radius: 50%; background: #A9500F;
                 animation: nhay 1.2s infinite ease-in-out;}
.dang-nghi span:nth-child(2) {animation-delay: 0.2s;}
.dang-nghi span:nth-child(3) {animation-delay: 0.4s;}
@keyframes nhay {0%, 80%, 100% {opacity: 0.25; transform: translateY(0);}
                 40% {opacity: 1; transform: translateY(-0.3rem);}}
</style>
""", unsafe_allow_html=True)

ss = st.session_state
ss.setdefault("nguoi_dung", None)

# Không tin vai trò/phiên đã lưu trong bộ nhớ: tài khoản có thể vừa bị khóa,
# đổi quyền hoặc thu hồi phiên ở một cửa sổ quản trị khác.
if ss.nguoi_dung is not None:
    nd = (tai_khoan.nguoi_dung_theo_phien(ss.ma_phien) if ss.get('ma_phien')
          else tai_khoan.doc_ho_so(ss.nguoi_dung['ten_dang_nhap']))
    if nd:
        ss.nguoi_dung = nd
    else:
        ss.nguoi_dung = None
        ss.ma_phien = None
        ss.tin_nhan = []
        ss.ma_cuoc = None
        ss.pop('cau_cho', None)


# ================================================================== đăng nhập

def google_da_cau_hinh():
    """Đăng nhập Gmail chỉ bật khi .streamlit/secrets.toml có [auth.google] với client_id thật."""
    try:
        return bool(st.secrets["auth"]["google"]["client_id"].strip())
    except Exception:  # chưa có secrets.toml / chưa có mục [auth.google]
        return False


# đã đăng nhập Google (cookie còn hạn 30 ngày) → vào thẳng, không cần đăng nhập lại khi tải lại trang
if ss.nguoi_dung is None and google_da_cau_hinh() and st.user.is_logged_in:
    ss.nguoi_dung = tai_khoan.dang_nhap_google(st.user.email, st.user.get("name"))

# đăng nhập bằng mật khẩu: mã phiên (hạn 30 ngày) giữ ở cả cookie COOKIE_PHIEN lẫn đường dẫn trang (?phien=...)
# → tải lại trang (F5, Ctrl+F5) không phải đăng nhập lại, kể cả khi trình duyệt chặn cookie; chỉ Đăng xuất mới xóa
COOKIE_PHIEN = "bmt_phien"
if ss.nguoi_dung is None:
    for ma in (st.context.cookies.get(COOKIE_PHIEN), st.query_params.get("phien")):
        nd = tai_khoan.nguoi_dung_theo_phien(ma)
        if nd:
            ss.nguoi_dung, ss.ma_phien = nd, ma
            break


def ghi_cookie(gia_tri, so_giay):
    """Streamlit không tự ghi cookie được → chạy JS trong khung ẩn (cùng nguồn) để ghi lên trang cha."""
    with st.container(key="o_cookie"):
        st.iframe(f"<script>window.parent.document.cookie = '{COOKIE_PHIEN}={gia_tri}; path=/; "
                  f"max-age={so_giay}; SameSite=Lax';</script>", height=1)
    st.markdown("<style>.st-key-o_cookie {position: absolute; width: 0; height: 0; overflow: hidden;}</style>",
                unsafe_allow_html=True)


def vao_bang_mat_khau(nd):
    ss.nguoi_dung, ss.ma_phien = nd, tai_khoan.tao_phien(nd["ten_dang_nhap"])
    ss.trang_hien_tai = 'Quản trị' if nd.get('vai_tro') == 'admin' else 'Trò chuyện'
    ss.admin_muc = 'Tổng quan'
    st.rerun()


def man_hinh_dang_nhap():
    from frontend.giao_dien_dang_nhap import hien_thi
    hien_thi(vao_bang_mat_khau, google_da_cau_hinh)


if ss.nguoi_dung is None:
    if ss.get("xoa_cookie"):  # vừa đăng xuất
        ghi_cookie("", 0)
    man_hinh_dang_nhap()
    st.stop()
if ss.get("ma_phien"):
    ghi_cookie(ss.ma_phien, 30 * 24 * 3600)
    if st.query_params.get("phien") != ss.ma_phien:
        st.query_params["phien"] = ss.ma_phien

TEN = ss.nguoi_dung["ten_dang_nhap"]
ss.setdefault("tin_nhan", [])
ss.setdefault("ma_cuoc", None)   # mã cuộc trò chuyện đang mở (None = chưa lưu)


# ================================================================== tài nguyên

@st.cache_resource(show_spinner="Đang tải kho dữ liệu (chỉ lần đầu)...")
def khoi_dong():
    """Nạp kho và mô hình sinh vector (nếu cách tìm trong cấu hình cần) một lần cho mọi phiên."""
    from backend.chatbot.truy_hoi import nap_bm25, nap_kho
    ch = doc_cau_hinh()
    nap_kho(ch["kho_vector"])
    if ch["che_do_truy_hoi"] != "bm25":
        from backend.chatbot.mo_hinh_vector import nap_mo_hinh
        nap_mo_hinh()
    if ch["che_do_truy_hoi"] != "vector":
        nap_bm25(ch["kho_vector"])


# ================================================================== hành động

def hoi(cau):
    """Đặt câu chờ; lượt chạy kế tiếp sẽ trả lời."""
    ss.cau_cho = cau


def cuoc_moi():
    ss.tin_nhan, ss.ma_cuoc = [], None
    ss.muc_dang_chon = "cuoc_moi"
    ss.chon_mon_nau = False


def mo_cuoc(cuoc):
    ss.tin_nhan, ss.ma_cuoc = cuoc["tin_nhan"], cuoc["ma"]
    ss.muc_dang_chon = f"ls_{cuoc['ma']}"
    ss.chon_mon_nau = False


def chon_muc_chat(muc, cau=None):
    if muc == 'nav_chat':
        cuoc_moi()
    ss.muc_dang_chon = muc
    ss.chon_mon_nau = muc == 'nav_cook'
    if ss.chon_mon_nau:
        ss.pop('cau_cho', None)
        message = {'vai': 'user', 'noi_dung': 'Hướng dẫn nấu ăn'}
        if not ss.tin_nhan or ss.tin_nhan[-1] != message:
            ss.tin_nhan = ss.tin_nhan + [message]
    elif cau:
        hoi(cau)


def chon_mon_huong_dan(cau):
    ss.chon_mon_nau = False
    ss.muc_dang_chon = 'nav_cook'
    ss.cong_thuc_vua_chon = True
    hoi(cau)


def xoa_cuoc(ma):
    tai_khoan.xoa_cuoc_tro_chuyen(TEN, ma)
    if ss.ma_cuoc == ma:
        cuoc_moi()


def dang_xuat():
    la_google = ss.nguoi_dung.get("google")
    tai_khoan.xoa_phien(ss.get("ma_phien"))  # mã trong cookie hết giá trị dù cookie chưa kịp xóa
    for k in list(ss.keys()):
        del ss[k]
    ss.xoa_cookie = True
    st.query_params.pop("phien", None)
    if la_google:
        st.logout()  # xóa cookie Google, nếu không lần tải trang sau sẽ tự đăng nhập lại


# ================================================================== thanh bên

if tai_khoan.la_admin(TEN) and ss.get('trang_hien_tai', 'Quản trị') != 'Trò chuyện':
    from frontend.bang_quan_tri import hien_thi
    hien_thi(TEN, dang_xuat)
    st.stop()

# Streamlit reruns this entrypoint but caches imported modules between runs.
# Reload the small view module so new image placeholders and assets take effect.
import importlib
from frontend import giao_dien_tro_chuyen
importlib.reload(giao_dien_tro_chuyen)
from frontend.giao_dien_tro_chuyen import ap_dung, thuong_hieu, tieu_de
ap_dung()

with st.sidebar:
    thuong_hieu()
    st.button('Trò chuyện', key='nav_chat', icon=':material/chat_bubble:', width='stretch', on_click=chon_muc_chat, args=('nav_chat',))
    st.button('Gợi ý món ăn', key='nav_suggest', icon=':material/ramen_dining:', width='stretch', on_click=chon_muc_chat, args=('nav_suggest', 'Gợi ý món ăn miền Tây cho bữa cơm gia đình'))
    st.button('Hướng dẫn nấu ăn', key='nav_cook', icon=':material/skillet:', width='stretch', on_click=chon_muc_chat, args=('nav_cook',))
    trang = (st.radio('Chức năng',['Trò chuyện','Quản trị'],key='trang_hien_tai')
             if tai_khoan.la_admin(TEN) else 'Trò chuyện')
    if trang == 'Trò chuyện':
        st.button("Cuộc trò chuyện mới", key="cuoc_moi", icon=":material/edit_square:", width="stretch", on_click=cuoc_moi)

    # Preserve the selected menu through reruns and chatbot replies.
    muc_chon = ss.get('muc_dang_chon', 'nav_chat')
    from frontend.giao_dien_tro_chuyen import to_muc_chon
    to_muc_chon(muc_chon)

    cac_cuoc = tai_khoan.danh_sach_cuoc_tro_chuyen(TEN) if trang == 'Trò chuyện' else []
    if trang == 'Trò chuyện':
        st.markdown("<div class='nhan-muc'>Lịch sử</div>", unsafe_allow_html=True)
    if not cac_cuoc and trang == 'Trò chuyện':
        st.caption("Chưa có cuộc trò chuyện nào.")
    hom_nay = datetime.now().date().isoformat()
    moc_truoc = None
    for c in cac_cuoc[:30]:
        moc = "Hôm nay" if c["cap_nhat"][:10] == hom_nay else "Trước đó"
        if moc != moc_truoc:
            st.caption(moc)
            moc_truoc = moc
        cot_ten, cot_xoa = st.columns([6, 1], vertical_alignment="center")
        cot_ten.button(c["tieu_de"], key=f"ls_{c['ma']}", icon=":material/chat_bubble:", width="stretch",
                       on_click=mo_cuoc, args=(c,), help=c["tieu_de"])
        cot_xoa.button("", icon=":material/delete:", key=f"xoa_{c['ma']}", on_click=xoa_cuoc, args=(c["ma"],), help="Xóa cuộc trò chuyện này")

    # chân thanh bên: luôn dính ở đáy (CSS .st-key-chan_trang), lịch sử dài thì cuộn phía trên
    with st.container(key="chan_trang"):
        st.button("Đăng xuất", key="dang_xuat", icon=":material/logout:", width="stretch", on_click=dang_xuat)

if trang == 'Quản trị':
    st.rerun()

try:
    khoi_dong()
except Exception as e:
    st.error(f"Không khởi động được chatbot: {e}")
    st.stop()

# chế độ giải thích (câu hỏi sau tiền xử lý / tách từ, câu hỏi viết lại, top-k, ngưỡng): không có nút trên giao diện,
# bật bằng cách thêm &giai_thich=1 vào đường dẫn trang
giai_thich = st.query_params.get("giai_thich") == "1"


# ================================================================== hiển thị câu trả lời

def hien_nguon(kq):
    for n in kq["nguon"]:
        with st.expander("Nguồn tham khảo", icon=":material/menu_book:"):
            dong = f"**ID {n['id_goc']} – {n['cau_hoi']}**  \nNhóm: {n['nhom']} · độ khớp {n['diem']:.3f}"
            if n["nguon"]:
                dong += f"  \n[Mở bài viết gốc]({n['nguon']})"
            st.markdown(dong)


def hien_giai_thich(kq):
    g = kq["giai_thich"]
    with st.expander("Giải thích (cho vấn đáp)", icon=":material/manage_search:"):
        st.markdown(
            f"- Loại xử lý: `{kq['loai']}` · kho `{g['kho']}` trên **{g.get('may_tim', 'faiss')}** · cách tìm `{g['che_do_truy_hoi']}` · {g['thoi_gian_giay']} giây\n"
            f"- Điểm cao nhất **{g['diem_cao_nhat']:.3f}** · ngưỡng ngoài phạm vi {g['nguong_ngoai_pham_vi']} "
            f"· ngưỡng tin cậy {g['nguong_tin_cay']}\n"
            f"- Sau tiền xử lý: `{g['cau_hoi_sach']}`\n- Sau tách từ: `{g['cau_hoi_vao_mo_hinh']}`"
            + (f"\n- Câu hỏi viết lại (ghép chủ đề lượt trước): **{g['cau_hoi_viet_lai']}**" if g["cau_hoi_viet_lai"] else ""))
        st.dataframe([{"#": d["xep_hang"], "điểm": d["diem"], **({"RRF": d["diem_rrf"]} if "diem_rrf" in d else {}),
                       "ID": d["id_goc"], "nhóm": d["nhom_folder"], "câu hỏi gốc": d["cau_hoi"],
                       "tên mục": d["ten_muc"]} for d in kq["doan_truy_hoi"]],
                     hide_index=True, width="stretch")


def hien_tra_loi(kq, vi_tri, cuoi):
    st.markdown(kq["cau_tra_loi"])
    hien_nguon(kq)
    if giai_thich and "giai_thich" in kq:  # tin nhắn mở từ lịch sử không còn phần giải thích
        hien_giai_thich(kq)
    if kq["goi_y"] and cuoi:  # nút câu hỏi gợi ý chỉ bấm được ở câu trả lời mới nhất
        nhan_goi_y = kq.get("nhan_goi_y") or ("👉 Gợi ý công thức món ăn bạn có thể nấu:" if kq["loai"] == "tra_loi" else "👉 Chọn món bạn muốn xem công thức:")
        st.caption(nhan_goi_y)
        for j, cau in enumerate(kq["goi_y"]):
            st.button(f"{j+1}. {cau}", key=f"lq_{vi_tri}_{j}", on_click=hoi, args=(cau,))


# ================================================================== màn hình trò chuyện

tieu_de(ss.nguoi_dung)

with st.container(key="chat_canvas"):
    so_tin = len(ss.tin_nhan)
    for vi_tri, tn in enumerate(ss.tin_nhan[-1:] if ss.get("chon_mon_nau") else ss.tin_nhan):
        with st.chat_message(tn["vai"], avatar="🍲" if tn["vai"] == "assistant" else None):
            if tn["vai"] == "assistant":
                hien_tra_loi(tn["ket_qua"], vi_tri, cuoi=vi_tri == so_tin - 1)
            else:
                st.markdown(tn["noi_dung"])

    if ss.get("chon_mon_nau"):
        from frontend.chon_mon_nau import hien_thi_chon_mon
        hien_thi_chon_mon(doc_cau_hinh()["kho_vector"], chon_mon_huong_dan)

    if not ss.tin_nhan and not ss.get("chon_mon_nau"):
        with st.chat_message("assistant", avatar="🍲"):
            st.markdown("Chào bạn! Hôm nay mình gợi ý cho bạn một số món miền Tây thơm ngon, dễ nấu nhé:\n\n"
                        "- **Cá kho tộ** – đậm đà, đưa cơm.\n"
                        "- **Canh cá nấu lá giang** – vị chua thanh, giải nhiệt.\n"
                        "- **Thịt kho nước dừa** – mềm, béo nhẹ, hợp bữa cơm gia đình.\n\n"
                        "Bạn muốn mình hướng dẫn cách nấu món nào trong các món trên ạ?")

    with st.container(key="chat_actions"):
        cot = st.columns(4)
        for i, (nhan, icon, cau) in enumerate([
            ('Gợi ý món ăn', ':material/restaurant:', 'Gợi ý món ăn miền Tây cho bữa cơm gia đình'),
            ('Hướng dẫn nấu ăn', ':material/skillet:', 'Hướng dẫn nấu ăn'),
            ('Món ăn dinh dưỡng', ':material/eco:', 'Gợi ý bữa ăn đủ dinh dưỡng'),
            ('Món nấu nhanh', ':material/schedule:', 'Gợi ý món ăn dễ nấu trong 20 phút'),
        ]):
            if i == 1:
                cot[i].button(nhan, icon=icon, key=f'chat_quick_{i}', on_click=chon_muc_chat, args=('nav_cook',), width='stretch')
            else:
                cot[i].button(nhan, icon=icon, key=f'chat_quick_{i}', on_click=hoi, args=(cau,), width='stretch')

    with st.container(key="chat_composer"):
        cau_hoi = st.chat_input("Hỏi mình về món ăn, nguyên liệu, dinh dưỡng...") or ss.pop("cau_cho", None)

if cau_hoi:
    from backend.chatbot.sinh_cau_tra_loi import tra_loi

    # hiện ngay câu vừa hỏi và bong bóng trợ lý có ba chấm nhấp nháy trong lúc tìm câu trả lời
    with st.chat_message("user"):
        st.markdown(cau_hoi)
    with st.chat_message("assistant", avatar="🍲"):
        st.markdown("<div class='dang-nghi'><span></span><span></span><span></span></div>", unsafe_allow_html=True)

    lich_su = [{"cau_hoi": tn["cau_hoi"], "cau_tra_loi": tn["ket_qua"]["cau_tra_loi"], "chu_de": tn["ket_qua"]["chu_de"],
                "trang_thai": tn["ket_qua"].get("trang_thai")}
               for tn in ss.tin_nhan if tn["vai"] == "assistant"]
    if ss.pop('cong_thuc_vua_chon', False):
        lich_su = []
    ss.chon_mon_nau = False
    kq = tra_loi(cau_hoi, lich_su)
    ss.tin_nhan = ss.tin_nhan + [{"vai": "user", "noi_dung": cau_hoi},
                                 {"vai": "assistant", "cau_hoi": cau_hoi, "ket_qua": kq}]
    # lưu lịch sử bản rút gọn (bỏ nội dung các đoạn truy hồi), bản đầy đủ chỉ giữ trong phiên
    ban_luu = [t if t["vai"] == "user" else {**t, "ket_qua": tai_khoan.rut_gon_ket_qua(t["ket_qua"])}
               for t in ss.tin_nhan]
    ss.ma_cuoc = tai_khoan.luu_cuoc_tro_chuyen(TEN, ss.ma_cuoc, ban_luu)
    st.rerun()  # vẽ lại từ lịch sử (thay ba chấm bằng câu trả lời, hiện nút câu hỏi liên quan)

with st.container(key="chat_notice"):
    st.caption(f"ℹ️ {GIOI_HAN}")
