"""Giao diện web của chatbot nấu ăn (Streamlit).

Chatbot LCEL: truy hồi lai có lọc điều kiện, thêm tóm tắt trích xuất bằng Ollama cục bộ.
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

# Streamlit caches imported modules; refresh the configured account backend on rerun.
import os
from backend.chatbot import co_so_du_lieu
from backend.chatbot.cau_hinh import nap_env
nap_env()
co_so_du_lieu.BACKEND = os.environ.get('TAI_KHOAN_BACKEND', co_so_du_lieu.BACKEND).strip().lower()

st.set_page_config(page_title="Bếp Của Ngoại – Trợ lý nấu ăn", page_icon=str(Path(__file__).resolve().parents[1] / "static/chat/bep-cua-ngoai-logo.png"), layout="centered")

CAU_GOI_Y = [
    "Cách nấu canh chua cá lóc miền Tây",
    "Cách làm bánh xèo miền Tây",
    "Lẩu mắm cần nguyên liệu gì",
    "Bữa sáng nên ăn gì để giảm cân",
    "Không có me thì nấu canh chua bằng gì",
    "Bị cảm cúm nên ăn gì cho mau khỏi",
]
CAU_DINH_DUONG = [
    'Món nào ăn tối nhẹ bụng mà đủ chất',
    'Nấu gì cho bữa cơm chay đủ chất',
    'Món chay nào giàu đạm',
    'Người làm việc văn phòng nên ăn gì',
]
GIOI_HAN_DAM = "Trợ lý trả lời dựa trên tài liệu về dinh dưỡng từ Bộ Y tế / Viện Dinh dưỡng."
GIOI_HAN = ("Thông tin chỉ mang tính tham khảo, không thay thế tư vấn y tế, không chẩn đoán bệnh, "
            "không kê thuốc và không khẳng định món ăn có thể chữa bệnh.")

st.markdown("""
<style>
[data-testid="stHeaderActionElements"] {display:none!important;}
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
    return False  # Offline profile: Google OAuth is disabled.



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
    if ss.get("cookie_phien_da_ghi") != ss.ma_phien:
        ghi_cookie(ss.ma_phien, 30 * 24 * 3600)
        ss.cookie_phien_da_ghi = ss.ma_phien
    if st.query_params.get("phien") != ss.ma_phien:
        st.query_params["phien"] = ss.ma_phien

TEN = ss.nguoi_dung["ten_dang_nhap"]
ss.setdefault("tin_nhan", [])
ss.setdefault("ma_cuoc", None)   # mã cuộc trò chuyện đang mở (None = chưa lưu)


# ================================================================== tài nguyên

@st.cache_resource(show_spinner="Đang tải kho dữ liệu (chỉ lần đầu)...")
def khoi_dong():
    """Warm the search index. The embedding model loads only when vector search needs it."""
    from backend.chatbot.truy_hoi import nap_bm25, nap_kho
    ch = doc_cau_hinh()
    nap_kho(ch["kho_vector"])
    if ch["che_do_truy_hoi"] != "vector":
        nap_bm25(ch["kho_vector"])


# ================================================================== hành động

TRANG_THEO_MUC = {"nav_history": "history", "nav_fav": "fav", "nav_profile": "profile"}


def hoi(cau):
    """Đặt câu chờ; lượt chạy kế tiếp sẽ trả lời."""
    ss.cau_cho = cau
    ss.trang_chat = "chat"


def mo_goi_y_mon():
    chon_muc_chat("nav_suggest")
    ss.pop("cau_cho", None)
    ss.trang_chat = "meal_suggestions"


def mo_goi_y_dinh_duong():
    ss.pop("cau_cho", None)
    ss.chon_mon_nau = False
    ss.trang_chat = "nutrition"
    ss.muc_dang_chon = "nav_nutri"


def cuoc_moi():
    ss.tin_nhan, ss.ma_cuoc = [], None
    ss.muc_dang_chon = "nav_chat"
    ss.chon_mon_nau = False
    ss.trang_chat = "chat"
    ss.loi_chao = "chung"


def bo_tin_dieu_huong(tin_nhan):
    """Remove old navigation messages without an associated answer."""
    return [
        tin for i, tin in enumerate(tin_nhan)
        if not (
            tin.get("vai") == "user" and tin.get("noi_dung") == 'Hướng dẫn nấu ăn'
            and (i + 1 == len(tin_nhan) or tin_nhan[i + 1].get("vai") != "assistant")
        )
    ]


def mo_cuoc(cuoc):
    ss.tin_nhan, ss.ma_cuoc = cuoc["tin_nhan"], cuoc["ma"]
    ss.muc_dang_chon = "nav_chat"
    ss.chon_mon_nau = False
    ss.trang_chat = "chat"


def chon_muc_chat(muc, cau=None):
    if muc in TRANG_THEO_MUC:  # trang phụ: lịch sử, món yêu thích, hồ sơ
        ss.muc_dang_chon, ss.trang_chat, ss.chon_mon_nau = muc, TRANG_THEO_MUC[muc], False
        return
    if muc == 'nav_adjust':
        ss.pop('cau_cho', None)
        ss.pop('adjust_recipe_id', None)
        ss.pop('adjust_applied', None)
        ss.pop('adjust_target', None)
        ss.pop('adjust_salt_cut', None)
        ss.pop('adjust_oil_cut', None)
        ss.muc_dang_chon, ss.trang_chat, ss.chon_mon_nau = muc, 'adjust_recipe', False
        return
    if muc in ('nav_chat', 'nav_nutri'):
        cuoc_moi()
        ss.loi_chao = 'dinh_duong' if muc == 'nav_nutri' else 'chung'
    ss.trang_chat = 'chat'
    ss.muc_dang_chon = muc
    ss.chon_mon_nau = muc == 'nav_cook'
    if ss.chon_mon_nau:
        ss.pop('cau_cho', None)
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
        ss.tin_nhan, ss.ma_cuoc = [], None


def doi_yeu_thich(cau):
    from frontend import mon_yeu_thich
    mon_yeu_thich.doi(TEN, cau)


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

if ss.nguoi_dung.get('vai_tro') == 'admin' and ss.get('trang_hien_tai', 'Quản trị') != 'Trò chuyện':
    from frontend.bang_quan_tri import hien_thi
    hien_thi(TEN, dang_xuat)
    st.stop()

# Streamlit reruns this entrypoint but caches imported modules between runs.
# Reload the small view module so new image placeholders and assets take effect.
import importlib
from frontend import giao_dien_tro_chuyen
importlib.reload(giao_dien_tro_chuyen)
from frontend.giao_dien_tro_chuyen import (MUC_THANH_BEN, ap_dung, the_ho_so, thong_bao, thuong_hieu,
                                           tieu_de, tieu_de_trang, to_muc_chon)
from frontend import mon_yeu_thich
ap_dung()
ss.setdefault("trang_chat", "chat")
ss.setdefault("loi_chao", "chung")

with st.sidebar:
    thuong_hieu()
    for key, nhan, icon in MUC_THANH_BEN:
        callback = mo_goi_y_mon if key == 'nav_suggest' else chon_muc_chat
        args = () if key == 'nav_suggest' else (key,)
        st.button(nhan, key=key, icon=icon, width='stretch', on_click=callback, args=args)
    trang = (st.radio('Chức năng', ['Trò chuyện', 'Quản trị'], key='trang_hien_tai')
             if tai_khoan.la_admin(TEN) else 'Trò chuyện')

    # Preserve the selected menu through reruns and chatbot replies.
    to_muc_chon(ss.get('muc_dang_chon', 'nav_chat'))

    # chân thanh bên: luôn dính ở đáy (CSS .st-key-chan_trang)
    cac_cuoc_da_luu = tai_khoan.danh_sach_cuoc_tro_chuyen(TEN)
    recent = cac_cuoc_da_luu[:3]
    if recent:
        with st.container(key="chat_recent"):
            st.caption("Lịch sử gần đây")
            for c in recent:
                st.button(c["tieu_de"], key=f"recent_{c['ma']}", icon=":material/chat:", width="stretch",
                          on_click=mo_cuoc, args=(c,), help=c["tieu_de"], wrap=True)
            if len(cac_cuoc_da_luu) > len(recent):
                st.button(f"Xem tất cả ({len(cac_cuoc_da_luu)})", key="recent_all",
                          on_click=chon_muc_chat, args=("nav_history",), width="stretch")

    with st.container(key="chan_trang"):
        st.button("Đăng xuất", key="dang_xuat", icon=":material/arrow_forward:", width="stretch", on_click=dang_xuat)

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
    if not kq["nguon"]:
        return
    with st.expander("Nguồn tham khảo", expanded=False, icon=":material/menu_book:"):
        for n in kq["nguon"]:
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


def hien_tra_loi(kq, vi_tri, cuoi, cau_hoi=None, yeu_thich=frozenset()):
    from backend.chatbot.knowledge_policy import render_result
    kq = render_result(kq, doc_cau_hinh()['kho_vector'])
    if kq.get('reason_code') == 'COMFORT_MEAL_OPTIONS':
        st.caption('Kho hiện tại chưa có câu trả lời sức khỏe được duyệt cho tình trạng bạn nêu. '
                   'Các món dưới đây chỉ là gợi ý món mềm hoặc có nước, không phải kết luận món phù hợp để điều trị. '
                   'Bạn vẫn có thể hỏi riêng cách nấu một món.')
    from frontend.ollama_local import cache_key
    llm = ss.get('ollama_summaries', {}).get(cache_key(cau_hoi or '', kq), {})
    if llm.get('status') == 'ok':
        st.markdown(llm['text'])
        st.markdown('**Nội dung đầy đủ và căn cứ**')
    elif cuoi and llm.get('status') in ('unavailable', 'model_missing', 'no_selection'):
        st.caption('Ollama chưa tạo được tóm tắt. Bạn vẫn có thể xem nội dung và nguồn bên dưới.')
    from frontend.noi_dung_tra_loi import calo_kem_cong_thuc
    cooking_calories = calo_kem_cong_thuc(kq, doc_cau_hinh()['kho_vector'])
    if cooking_calories:
        reference = cooking_calories['reference']
        st.markdown(f"**Calo ước tính:** ≈ {reference['energy_total_kcal']:,.0f} kcal cả công thức · "
                    f"≈ {reference['energy_per_serving_kcal']:,.0f} kcal/khẩu phần "
                    f"(quy ước chia {reference['servings']:g} phần).")
    from frontend.noi_dung_tra_loi import hien_noi_dung, hien_calo_truc_tiep
    if not hien_calo_truc_tiep(kq):
        hien_noi_dung(kq["cau_tra_loi"])
    from frontend.noi_dung_tra_loi import hien_calo_cong_thuc
    hien_calo_cong_thuc(kq, doc_cau_hinh()['kho_vector'], key=vi_tri, on_adjust=dieu_chinh_mon_da_luu)
    hien_nguon(kq)
    cooking_options = []
    if cuoi and cau_hoi:
        from frontend.huong_dan_sau_goi_y import cong_thuc_goi_y, hien_huong_dan
        cooking_options = cong_thuc_goi_y(cau_hoi, kq, doc_cau_hinh()['kho_vector'])
        from backend.chatbot.knowledge_policy import active_build
        legacy_comfort = kq.get('reason_code') == 'COMFORT_MEAL_OPTIONS' and not active_build()
        hien_huong_dan(cooking_options, vi_tri=vi_tri, on_chon=chon_mon_huong_dan if legacy_comfort else hoi)
    if giai_thich and {"kho", "che_do_truy_hoi", "thoi_gian_giay", "diem_cao_nhat", "nguong_ngoai_pham_vi", "nguong_tin_cay", "cau_hoi_sach", "cau_hoi_vao_mo_hinh"}.issubset(kq.get("giai_thich", {})):  # history may be blocked or omit diagnostics
        hien_giai_thich(kq)
    if cau_hoi and kq.get("loai") == "tra_loi":  # chỉ lưu món khi trợ lý trả lời được từ dữ liệu
        da_luu = cau_hoi in yeu_thich
        st.button("Đã lưu vào món yêu thích" if da_luu else "Lưu vào món yêu thích",
                  icon=":material/heart_check:" if da_luu else ":material/heart_plus:",
                  key=f"yt_{vi_tri}", type="tertiary", on_click=doi_yeu_thich, args=(cau_hoi,),
                  help="Bấm lần nữa để bỏ khỏi danh sách" if da_luu else "Lưu để xem lại trong mục Món yêu thích")
    cooking_questions = {item['question'] for item in cooking_options}
    other_suggestions = [q for q in kq['goi_y'] if q not in cooking_questions]
    if other_suggestions and cuoi:  # nút câu hỏi gợi ý chỉ bấm được ở câu trả lời mới nhất
        nhan_goi_y = kq.get("nhan_goi_y") or ("👉 Gợi ý công thức món ăn bạn có thể nấu:" if kq["loai"] == "tra_loi" else "👉 Chọn món bạn muốn xem công thức:")
        st.caption(nhan_goi_y)
        for j, cau in enumerate(other_suggestions):
            st.button(f"{j+1}. {cau}", key=f"lq_{vi_tri}_{j}", on_click=hoi, args=(cau,))
    if cuoi and cau_hoi:
        from backend.chatbot.goi_y_lien_quan import related
        suggestions = related(cau_hoi, doc_cau_hinh()['kho_vector'], kq)
        if suggestions:
            with st.container(border=True, key='related_questions'):
                st.caption('Bạn có thể hỏi tiếp về nội dung liên quan:')
                columns = st.columns(2)
                for j,item in enumerate(suggestions):
                    columns[j % 2].button(item['question'], key=f'related_{vi_tri}_{item["id"]}',
                        icon=':material/arrow_forward:', width='stretch', on_click=hoi, args=(item['question'],))


# ================================================================== các trang phụ

def trang_lich_su():
    tieu_de_trang("history", "Lịch sử trò chuyện", "Mở lại hoặc xóa các cuộc trò chuyện đã lưu.")
    st.button("Cuộc trò chuyện mới", key="cuoc_moi", icon=":material/edit_square:", on_click=cuoc_moi)
    cac_cuoc = tai_khoan.danh_sach_cuoc_tro_chuyen(TEN)
    if not cac_cuoc:
        st.info("Chưa có cuộc trò chuyện nào.", icon=":material/chat_bubble:")
        return
    hom_nay = datetime.now().date().isoformat()
    moc_truoc = None
    for c in cac_cuoc:
        moc = "Hôm nay" if c["cap_nhat"][:10] == hom_nay else "Trước đó"
        if moc != moc_truoc:
            st.markdown(f"<div class='nhan-muc'>{moc}</div>", unsafe_allow_html=True)
            moc_truoc = moc
        so_cau = sum(1 for t in c["tin_nhan"] if t.get("vai") == "user")
        cot_ten, cot_xoa = st.columns([12, 1], vertical_alignment="center")
        cot_ten.button(c["tieu_de"], key=f"ls_{c['ma']}", icon=":material/chat_bubble:", width="stretch",
                       on_click=mo_cuoc, args=(c,),
                       help=f"Cập nhật {c['cap_nhat'][:16].replace('T', ' ')} · {so_cau} câu hỏi")
        cot_xoa.button("", icon=":material/delete:", key=f"xoa_{c['ma']}", on_click=xoa_cuoc, args=(c["ma"],),
                       help="Xóa cuộc trò chuyện này")


def mo_yeu_thich(cau):
    cuoc_moi()
    hoi(cau)


def dieu_chinh_mon_da_luu(recipe_id):
    chon_muc_chat("nav_adjust")
    ss.adjust_recipe_id = recipe_id


def trang_yeu_thich():
    from frontend.danh_sach_mon_da_luu import hien_thi_mon_da_luu

    hien_thi_mon_da_luu(
        doc_cau_hinh()["kho_vector"], TEN, mo_yeu_thich, dieu_chinh_mon_da_luu, chon_muc_chat
    )


def trang_ho_so():
    with st.container(key="profile_page"):
        tieu_de_trang("person", "Hồ sơ cá nhân", "Quản lý thông tin tài khoản, tùy chọn ăn uống và hoạt động của bạn.")
        cac_cuoc = tai_khoan.danh_sach_cuoc_tro_chuyen(TEN)
        so_cau = sum(1 for c in cac_cuoc for t in c["tin_nhan"] if t.get("vai") == "user")
        the_ho_so(ss.nguoi_dung, len(cac_cuoc), so_cau, len(mon_yeu_thich.danh_sach(TEN)))

        from frontend.tuy_chon_ho_so import hien_thi_tuy_chon

        hien_thi_tuy_chon(TEN, ss.nguoi_dung)


# ================================================================== màn hình trò chuyện

cau_hoi = None
tieu_de(ss.nguoi_dung)
with st.container(key="chat_canvas"):
    if ss.trang_chat == "history":
        trang_lich_su()
    elif ss.trang_chat == "fav":
        trang_yeu_thich()
    elif ss.trang_chat == "profile":
        trang_ho_so()
    elif ss.trang_chat == "adjust_recipe":
        from frontend.dieu_chinh_cong_thuc import hien_thi_dieu_chinh

        with st.container(key="adjust_page"):
            hien_thi_dieu_chinh(doc_cau_hinh()["kho_vector"], TEN, hoi)
    elif ss.trang_chat == 'cook_detail':
        from frontend.chi_tiet_cong_thuc import hien_thi_chi_tiet
        hien_thi_chi_tiet(ss.get('cook_detail_result', {}), doc_cau_hinh()['kho_vector'], TEN,
            lambda: chon_muc_chat('nav_cook'), dieu_chinh_mon_da_luu, hoi)
    elif ss.trang_chat == "meal_suggestions":
        from frontend.chon_mon_nau import hien_thi_chon_mon

        with st.container(key="meal_suggestions_page"):
            with st.chat_message("user"):
                st.markdown(next(label for key, label, _ in MUC_THANH_BEN if key == "nav_suggest"))
            hien_thi_chon_mon(doc_cau_hinh()["kho_vector"], chon_mon_huong_dan, theo_nhom=True)
    elif ss.trang_chat == "nutrition":
        with st.chat_message("user"):
            st.markdown('Món ăn dinh dưỡng')
        with st.chat_message("assistant", avatar="🍲"):
            st.markdown("**Món ăn dinh dưỡng**")
            st.write("Bạn muốn hỏi câu nào?")
            for i, cau in enumerate(CAU_DINH_DUONG):
                st.button(cau, key=f"nutrition_{i}", on_click=hoi, args=(cau,))
    else:
        yeu_thich = {m["cau_hoi"] for m in mon_yeu_thich.danh_sach(TEN)}
        ss.tin_nhan = bo_tin_dieu_huong(ss.tin_nhan)
        so_tin = len(ss.tin_nhan)
        tin_hien_thi = [] if ss.get("chon_mon_nau") else ss.tin_nhan
        for vi_tri, tn in enumerate(tin_hien_thi):
            with st.chat_message(tn["vai"], avatar="🍲" if tn["vai"] == "assistant" else None):
                if tn["vai"] == "assistant":
                    hien_tra_loi(tn["ket_qua"], vi_tri, cuoi=vi_tri == so_tin - 1,
                                 cau_hoi=tn.get("cau_hoi"), yeu_thich=yeu_thich)
                else:
                    st.markdown(tn["noi_dung"])

        if ss.get("chon_mon_nau"):
            from frontend.chon_mon_nau import hien_thi_chon_mon
            with st.container(key="cook_picker_page"):
                with st.chat_message("user"):
                    st.markdown(dict((key, label) for key, label, _ in MUC_THANH_BEN)["nav_cook"])
                hien_thi_chon_mon(doc_cau_hinh()["kho_vector"], chon_mon_huong_dan)

        if not ss.tin_nhan and not ss.get("chon_mon_nau") and not ss.get("cau_cho"):
            if ss.loi_chao in ("dinh_duong", "dieu_chinh"):
                muc = "nav_nutri" if ss.loi_chao == "dinh_duong" else "nav_adjust"
                with st.container(key=f"topic_badge_{muc}"), st.chat_message("user"):
                    st.markdown(next(label for key, label, _ in MUC_THANH_BEN if key == muc))
            with st.chat_message("assistant", avatar="🍲"):
                if ss.loi_chao == "dinh_duong":
                    with st.container(key="nutrition_prompt"):
                        st.markdown("Bạn muốn hỏi gì về dinh dưỡng?")
                    for j, cau in enumerate(CAU_DINH_DUONG):
                        st.button(cau, key=f"dd_{j}", icon=":material/arrow_right:", type="tertiary",
                                  on_click=hoi, args=(cau,))
                elif ss.loi_chao == "dieu_chinh":
                    st.markdown("Bạn muốn thay nguyên liệu hay điều chỉnh khẩu phần? Hãy nhập tên món và thay đổi bạn cần.")
                    cau = "Không có me thì nấu canh chua bằng gì"
                    st.button(cau, key="adjust_example", on_click=hoi, args=(cau,))
                else:
                    with st.container(key="chat_welcome_copy"):
                        st.markdown("**Chào bạn!** Hôm nay mình gợi ý cho bạn một số món miền Tây thơm ngon, dễ nấu nhé:\n\n"
                                    "- **Cá kho tộ** – đậm đà, đưa cơm.\n"
                                    "- **Canh cá nấu lá giang** – vị chua thanh, giải nhiệt.\n"
                                    "- **Thịt kho nước dừa** – mềm, béo nhẹ, hợp bữa cơm gia đình.\n\n"
                                    "Bạn muốn mình hướng dẫn cách nấu món nào trong các món trên ạ?")

        cho_tin_nhan_moi = st.empty()

        with st.container(key="chat_actions"):
            cot = st.columns(4)
            for i, (nhan, cau) in enumerate([
                ('Gợi ý món ăn', 'Gợi ý món ăn miền Tây cho bữa cơm gia đình'),
                ('Hướng dẫn nấu ăn', 'Hướng dẫn nấu ăn'),
                ('Món ăn dinh dưỡng', None),
                ('Món nấu nhanh', 'Gợi ý món ăn nấu nhanh trong 25 phút'),
            ]):
                icon = ("restaurant", "soup_kitchen", "ecg_heart", "bolt")[i]
                label = f":material/{icon}: {nhan}"
                if i == 0:
                    cot[i].button(label, key=f"chat_quick_{i}",
                                  on_click=mo_goi_y_mon, width="stretch")
                elif i == 1:
                    cot[i].button(label, key=f'chat_quick_{i}', on_click=chon_muc_chat, args=('nav_cook',), width='stretch')
                elif i == 2:
                    cot[i].button(label, key=f'chat_quick_{i}', on_click=mo_goi_y_dinh_duong, width='stretch')
                else:
                    cot[i].button(label, key=f'chat_quick_{i}', on_click=hoi, args=(cau,), width='stretch')

        if not ss.get("chon_mon_nau"):
            with st.container(key="chat_features"):
                st.markdown('<h2 class="chat-features-title">✦ Bạn có thể làm gì với Bếp Của Ngoại?</h2>', unsafe_allow_html=True)
                cards = [
                    ('Gợi ý món theo nhu cầu', 'Theo nguyên liệu, thời gian, khẩu phần và tình trạng sức khỏe.', 'mon-ca-kho.jpg', mo_goi_y_mon, ()),
                    ('Hướng dẫn nấu chi tiết', 'Có nguyên liệu, khẩu phần, thời gian và các bước nấu.', 'mon-canh.jpg', chon_muc_chat, ('nav_cook',)),
                    ('Phân tích & điều chỉnh công thức', 'Kiểm tra thành phần, cảnh báo và gợi ý thay thế phù hợp.', 'mon-dinh-duong.jpg', chon_muc_chat, ('nav_adjust',)),
                    ('Thông tin dinh dưỡng', 'Tra cứu kiến thức dinh dưỡng và nguồn tham khảo.', 'mon-nhanh.jpg', chon_muc_chat, ('nav_nutri',)),
                ]
                for i, (column, card) in enumerate(zip(st.columns(4), cards)):
                    title, description, image, callback, args = card
                    with column, st.container(key=f"chat_feature_{i}"):
                        st.html(f'<img class="chat-feature-image" src="/app/static/chat/{image}" alt="">')
                        st.button(title, key=f"feature_open_{i}", on_click=callback, args=args, width="stretch")
                        st.markdown(f'<p class="chat-feature-description">{description}</p>', unsafe_allow_html=True)

        with st.container(key="chat_composer"):
            with st.form("chat_message_form", clear_on_submit=True, border=False):
                cot_nhap, cot_gui = st.columns([8, 1], vertical_alignment="bottom")
                tin_nhap = cot_nhap.text_input(
                    "Tin nhắn", key="chat_message_text", label_visibility="collapsed",
                    placeholder="Hỏi mình về món ăn, nguyên liệu, dinh dưỡng...",
                )
                da_gui = cot_gui.form_submit_button("Gửi", icon=":material/send:", width="stretch")
            cau_cho = ss.pop("cau_cho", None)
            cau_hoi = (tin_nhap.strip() if da_gui else "") or cau_cho

    with st.container(key="chat_footer"):
        thong_bao(GIOI_HAN_DAM, GIOI_HAN)

if cau_hoi:
    from frontend.hoi_thoai import tra_loi

    # hiện ngay câu vừa hỏi và bong bóng trợ lý có ba chấm nhấp nháy trong lúc tìm câu trả lời
    with cho_tin_nhan_moi.container():
        with st.chat_message("user"):
            st.markdown(cau_hoi)
        with st.chat_message("assistant", avatar="🍲"):
            st.markdown("<div class='dang-nghi'><span></span><span></span><span></span></div>", unsafe_allow_html=True)

    lich_su = [{"cau_hoi": tn["cau_hoi"], "cau_tra_loi": tn["ket_qua"]["cau_tra_loi"], "chu_de": tn["ket_qua"]["chu_de"],
                "trang_thai": tn["ket_qua"].get("trang_thai")}
               for tn in ss.tin_nhan if tn["vai"] == "assistant"]
    mo_trang_cong_thuc = ss.pop('cong_thuc_vua_chon', False)
    if mo_trang_cong_thuc:
        lich_su = []
    ss.chon_mon_nau = False
    from frontend.huong_dan_sau_goi_y import cau_hoi_tim_cong_thuc
    cooking_question = cau_hoi_tim_cong_thuc(cau_hoi, doc_cau_hinh()['kho_vector'])
    kq = tra_loi(cooking_question, lich_su)
    from backend.chatbot.knowledge_policy import render_result
    from frontend.ollama_local import cache_key, summarize
    validated = render_result(kq, doc_cau_hinh()['kho_vector'])
    summaries = ss.setdefault('ollama_summaries', {})
    summary_key = cache_key(cau_hoi, validated)
    if summary_key not in summaries:
        with st.spinner('Ollama đang đọc tài liệu trên máy…'):
            summaries[summary_key] = summarize(cau_hoi, validated)
        while len(summaries) > 30:
            del summaries[next(iter(summaries))]
    ss.tin_nhan = ss.tin_nhan + [{"vai": "user", "noi_dung": cau_hoi},
                                 {"vai": "assistant", "cau_hoi": cau_hoi, "ket_qua": kq}]
    # lưu lịch sử bản rút gọn (bỏ nội dung các đoạn truy hồi), bản đầy đủ chỉ giữ trong phiên
    ban_luu = [t if t["vai"] == "user" else {**t, "ket_qua": tai_khoan.rut_gon_ket_qua(t["ket_qua"])}
               for t in ss.tin_nhan]
    ss.ma_cuoc = tai_khoan.luu_cuoc_tro_chuyen(TEN, ss.ma_cuoc, ban_luu)
    if mo_trang_cong_thuc and kq.get('loai') == 'tra_loi':
        ss.cook_detail_result = kq
        ss.trang_chat = 'cook_detail'
    st.rerun()  # vẽ lại từ lịch sử (thay ba chấm bằng câu trả lời, hiện nút câu hỏi liên quan)
