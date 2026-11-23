"""Bảng quản trị có dữ liệu thật; mọi truy cập đều kiểm tra quyền phía máy chủ."""
import html
import base64
import csv
import io
import json
import re
from collections import Counter
from datetime import date, timedelta
from functools import lru_cache
import streamlit as st
from backend.chatbot import tai_khoan
from backend.chatbot.cau_hinh import ROOT


def esc(value):
    return html.escape(str(value))


@lru_cache(maxsize=1)
def tai_tai_lieu():
    from backend.chatbot.knowledge_policy import active_build
    build = active_build()
    path = build/'merged/dataset.jsonl' if build else ROOT/'data/merged/dataset.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def trang_thai_neo4j():
    """Check in a clean process so partial scientific-library imports cannot hide connectivity."""
    import subprocess
    import sys
    try:
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts/kiem_tra_neo4j_ui.py")],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
            timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        lines = result.stdout.strip().splitlines()
        return json.loads(lines[-1]) if lines else {"ok": False, "error": "Không nhận được kết quả kiểm tra."}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Kết nối quá thời gian chờ."}
    except (OSError, ValueError):
        return {"ok": False, "error": "Không chạy được phép kiểm tra kết nối."}


@st.cache_resource(show_spinner=False)
def _neo4j_background():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Lock
    return {"executor": ThreadPoolExecutor(max_workers=1, thread_name_prefix="neo4j-health"),
            "lock": Lock(), "future": None, "result": None, "checked": 0.0}


@st.fragment(run_every="2s")
def hien_thi_ket_noi_neo4j():
    from time import monotonic
    state = _neo4j_background()
    refresh = st.button("Kiểm tra Neo4j", width="stretch", key="neo4j_health_refresh")
    with state["lock"]:
        future = state["future"]
        if future is not None and future.done():
            try:
                state["result"] = future.result()
            except Exception:
                state["result"] = {"ok": False, "error": "Không chạy được phép kiểm tra kết nối."}
            state["checked"] = monotonic()
            state["future"] = None
        if state["future"] is None and (refresh or state["result"] is None or monotonic() - state["checked"] > 60):
            state["future"] = state["executor"].submit(trang_thai_neo4j)
        result = state["result"]
        pending = state["future"] is not None
    if result is None:
        st.caption("Đang kiểm tra Neo4j… Bạn có thể chuyển mục ngay.")
    elif result.get("ok"):
        st.success("Neo4j đã kết nối")
    else:
        st.info("Neo4j chưa kết nối")
        st.caption(result.get("error", "Chưa xác định được lỗi kết nối."))
    if pending and result is not None:
        st.caption("Đang cập nhật trạng thái…")


def chuyen(muc):
    if st.session_state.get('admin_muc') != muc:
        st.session_state.admin_reset_scroll = True
    st.session_state.admin_muc = muc


def _hieu_ung_chuyen_muc():
    if not st.session_state.pop('admin_reset_scroll', False):
        return
    import streamlit.components.v1 as components
    components.html("""<script>
    const page = window.parent;
    function resetPage() {
        const main = page.document.querySelector('[data-testid="stMain"]');
        if (main) main.scrollTo({top: 0, left: 0, behavior: 'instant'});
        page.scrollTo({top: 0, left: 0, behavior: 'instant'});
    }
    resetPage();
    [100, 300].forEach(delay => setTimeout(resetPage, delay));
    const content = page.document.querySelector('[data-testid="stMainBlockContainer"]');
    if (content && !page.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        content.animate([{opacity: .75, transform: 'translateY(4px)'},
                         {opacity: 1, transform: 'translateY(0)'}],
                        {duration: 160, easing: 'ease-out'});
    }
    </script>""", height=0, scrolling=False)


@st.cache_data(ttl=15, show_spinner=False)
def _du_lieu_tong_quan(actor, backend):
    # Cached display data only. Access and all mutations still check current permissions.
    return tai_khoan.danh_sach_nguoi_dung(actor), tai_khoan.nhat_ky_quan_tri(actor)


CSS_ADMIN = ROOT/'frontend/assets/admin/dashboard.css'


@lru_cache(maxsize=1)
def style_admin(_mtime=None):
    """Khóa cache theo thời điểm sửa file CSS → sửa CSS là thấy ngay, không cần khởi động lại."""
    css=CSS_ADMIN.read_text(encoding='utf-8')
    # Serve images once through the browser cache rather than embedding megabytes on every rerun.
    asset_root = ROOT / 'static/admin'
    photo = f"/app/static/admin/food-reference.png?v={(asset_root / 'food-reference.png').stat().st_mtime_ns}"
    decor = f"/app/static/admin/sidebar-kitchen.png?v={(asset_root / 'sidebar-kitchen.png').stat().st_mtime_ns}"
    css += f'\n.stApp:has(.bmt-admin) [data-testid="stSidebar"]{{background-image:linear-gradient(#fffaf333,#fffaf333),url("{decor}");background-size:100% 100%;background-repeat:no-repeat;background-position:center;}}'
    return css + f'\n.dish-photo{{background-image:url("{photo}")!important;background-size:620% 620%!important;}} .dish-0{{background-position:24% 85%!important}}.dish-1{{background-position:44% 85%!important}}.dish-2{{background-position:63% 85%!important}}'



def _svg(path, size=18):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>')


ICON_BANG = {
    'cau_hoi': _svg('<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.6 8.6 0 0 1-3.8-.9L3 20.5l1.5-4.6A8.4 8.4 0 0 1 12 3.1a8.4 8.4 0 0 1 9 8.4z"/>'),
    'noi_dung': _svg('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8M8 9h2"/>'),
    'nguon': _svg('<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>'),
    'link': _svg('<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>', 14),
    'mo': _svg('<path d="M9 6l6 6-6 6"/>', 16),
}
ICON_TIEU_DE = {
    'Kho tri thức': _svg('<path d="M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z"/>'
                         '<path d="M5 8h3M5 11h3M16 8h3M16 11h3"/>', 34),
    'Món ăn': _svg('<path d="M3 11h18a9 9 0 0 1-18 0zM12 3v4M8 5v2M16 5v2"/>', 34),
    'spark': _svg('<path d="M8 9 7 3M12 13l5-4M13 18h6"/>', 24),
}
ICON_TIEU_DE['Kiểm thử & phản hồi'] = _svg(
    '<path d="M21 11.5a8.5 8.5 0 0 1-9 8.5 9 9 0 0 1-4-.9L3 21l1.5-4.5A8.5 8.5 0 1 1 21 11.5z"/>'
    '<circle cx="8" cy="11" r=".7"/><circle cx="12" cy="11" r=".7"/><circle cx="16" cy="11" r=".7"/>', 34)
URL = re.compile(r'https?://[^\s<>"\']+')


def _o_nguon(text):
    """Thẻ nguồn: bấm được nếu nguồn có đường dẫn; nhãn là chữ của nguồn (hoặc chính đường dẫn)."""
    text = ' '.join(str(text or '').split())
    url = (URL.search(text) or [None])[0]
    if url:
        url = url.rstrip('.,);]')
        if not url.lower().startswith(('http://', 'https://')):
            url = None
    if not text:
        return '<td class="dl-src"></td><td class="dl-go"></td>'
    chip = f'{ICON_BANG["link"]}<span>{esc(text)}</span>'
    if url:
        href = esc(url)
        return (f'<td class="dl-src"><a class="src-chip" href="{href}" target="_blank" rel="noopener" title="{esc(text)}">{chip}</a></td>'
                f'<td class="dl-go"><a href="{href}" target="_blank" rel="noopener" aria-label="Mở nguồn">{ICON_BANG["mo"]}</a></td>')
    # không có đường dẫn (vd. "Không áp dụng"): thẻ nhạt, không icon link để khỏi trông như bấm được
    return f'<td class="dl-src"><span class="src-chip src-none" title="{esc(text)}"><span>{esc(text)}</span></span></td><td class="dl-go"></td>'


def _an_toan_csv(value):
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def _csv(rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Câu hỏi', 'Nội dung', 'Nguồn'])
    w.writerows(
        [_an_toan_csv(d.get('question', '')), _an_toan_csv(d.get('answer', '')), _an_toan_csv(d.get('source', ''))]
        for d in rows
    )
    return buf.getvalue().encode('utf-8-sig')  # có BOM để Excel đọc đúng tiếng Việt


def _dao(key):
    st.session_state[key] = not st.session_state.get(key, False)


def bang_du_lieu(muc, source):
    """Bảng dữ liệu nguồn (Món ăn / Kho tri thức): ô tìm kiếm + nút công cụ, bảng HTML có thẻ nguồn."""
    day_du, mo_rong = st.session_state.get('dl_day_du', False), st.session_state.get('dl_mo_rong', False)
    with st.container(key='dl_cong_cu'):
        tim, nut = st.columns([1, 0.16], vertical_alignment='center', gap='small')
        query = tim.text_input('Tìm trong dữ liệu', placeholder='Nhập món ăn hoặc từ khóa...',
                               key='admin_tim_du_lieu', label_visibility='collapsed')
        q = ' '.join(query.split()).casefold()
        filtered = [d for d in source if q in (d.get('question', '') + ' ' + d.get('answer', '')).casefold()]
        with nut.container(horizontal=True, key='dl_nut', horizontal_alignment='right', gap='small'):
            st.button('', icon=':material/visibility_off:' if day_du else ':material/visibility:', key='dl_xem',
                      type='primary' if day_du else 'secondary', on_click=_dao, args=('dl_day_du',),
                      help='Thu gọn nội dung' if day_du else 'Hiện đầy đủ nội dung')
            st.download_button('', data=_csv(filtered), icon=':material/download:', key='dl_tai',
                               file_name=('mon_an' if muc == 'Món ăn' else 'kho_tri_thuc') + '.csv', mime='text/csv',
                               help='Tải các mục đang hiển thị (CSV)')
            st.button('', icon=':material/fullscreen_exit:' if mo_rong else ':material/fullscreen:', key='dl_rong',
                      type='primary' if mo_rong else 'secondary', on_click=_dao, args=('dl_mo_rong',),
                      help='Thu bảng lại' if mo_rong else 'Mở rộng bảng')
    st.caption(f'{len(filtered)} / {len(source)} mục - Dữ liệu nguồn của chatbot')
    if not filtered:
        st.markdown('<div class="dl-card dl-empty">Không tìm thấy mục nào khớp từ khóa.</div>', unsafe_allow_html=True)
        return
    gioi_han = None if day_du else 220  # thu gọn: cắt bớt chữ để trang nhẹ, CSS hiện dấu “…”
    rows = []
    for d in filtered:
        q_txt = ' '.join(str(d.get('question', '')).split())
        a_txt = ' '.join(str(d.get('answer', '')).split())
        a_ngan = a_txt if gioi_han is None or len(a_txt) <= gioi_han else a_txt[:gioi_han] + '…'
        rows.append(f'<tr><td class="dl-q" title="{esc(q_txt)}">{esc(q_txt)}</td>'
                    f'<td class="dl-a" title="{esc(a_txt[:400])}">{esc(a_ngan)}</td>{_o_nguon(d.get("source"))}</tr>')
    lop = 'dl-card' + (' dl-full' if day_du else '') + (' dl-wide' if mo_rong else '')
    st.markdown(f'<div class="{lop}"><table class="dl-table"><colgroup><col class="c-q"><col class="c-a"><col class="c-s"><col class="c-go"></colgroup>'
                f'<thead><tr><th>{ICON_BANG["cau_hoi"]}Câu hỏi</th><th>{ICON_BANG["noi_dung"]}Nội dung</th>'
                f'<th colspan="2">{ICON_BANG["nguon"]}Nguồn</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>',
                unsafe_allow_html=True)


def hien_tu_hoc_va_nlp(actor):
    from frontend.kiem_thu_admin import hien_thi_kiem_thu
    hien_thi_kiem_thu(actor, tai_tai_lieu())


def hien_thi(actor, dang_xuat):
    if not tai_khoan.la_admin(actor):
        st.error('Bạn không có quyền quản trị.')
        st.stop()
    current_page = st.session_state.get('admin_muc', 'Tổng quan')
    need_accounts = current_page in ('Tổng quan', 'Nhật ký hệ thống')
    from backend.chatbot.co_so_du_lieu import BACKEND
    users, logs = _du_lieu_tong_quan(actor, BACKEND) if need_accounts else ([], [])
    docs = tai_tai_lieu()
    recipes = [d for d in docs if d.get('group_folder') in ('02_huong_dan_nau_an', '03_huong_dan_nau_mon_mien_tay')]
    st.markdown('<style>' + style_admin(CSS_ADMIN.stat().st_mtime) + '</style><span class="bmt-admin"></span>', unsafe_allow_html=True)
    _hieu_ung_chuyen_muc()
    with st.sidebar:
        pot = (ROOT/'frontend/assets/login/brand-pot.svg').read_text(encoding='utf-8')
        st.markdown(f'<div class="admin-brand">{pot}<div>Bếp Miền Tây</div><small>Trang quản trị</small></div>', unsafe_allow_html=True)
        st.session_state.setdefault('admin_muc', 'Tổng quan')
        for label, icon in [
            ('Tổng quan', 'home'),
            ('Tài khoản', 'person'),
            ('Món ăn', 'soup_kitchen'),
            ('Quản lý dinh dưỡng', 'nutrition'),
            ('Quy tắc điều chỉnh', 'tune'),
            ('Quản lý chatbot', 'psychology'),
            ('Kiểm thử & phản hồi', 'fact_check'),
            ('Cài đặt hệ thống', 'settings'),
        ]:
            st.button(label, icon=f':material/{icon}:', key='admin_nav_'+icon, width='stretch',
                      type='primary' if st.session_state.admin_muc==label else 'secondary', on_click=chuyen,args=(label,))
        with st.container(key='admin_logout_footer'):
            st.button('Đăng xuất', icon=':material/logout:', key='admin_logout',width='stretch',on_click=dang_xuat)
    profile=tai_khoan.doc_ho_so(actor)
    name=profile.get('ten_hien_thi') or actor
    muc=st.session_state.admin_muc
    tieu_de = 'Tổng quan hệ thống' if muc=='Tổng quan' else esc(muc)
    if muc == 'Tổng quan':
        tieu_de += f'<span class="h-spark">{ICON_TIEU_DE["spark"]}</span>'
    if muc in ICON_TIEU_DE:  # Món ăn / Kho tri thức: icon trước tiêu đề + tia sáng cam phía sau
        tieu_de = f'<span class="h-ico">{ICON_TIEU_DE[muc]}</span>{tieu_de}<span class="h-spark">{ICON_TIEU_DE["spark"]}</span>'
    loi_chao = f'Chào <b>{esc(name)}</b>, cùng chăm sóc căn bếp hôm nay!'
    if muc == 'Món ăn':
        tieu_de = 'Quản lý món ăn'
        loi_chao = 'Quản lý kho công thức món ăn miền Tây.'
    if muc == 'Quản lý dinh dưỡng':
        loi_chao = 'Quản lý thông tin dinh dưỡng của món ăn, nguyên liệu và nguồn tham khảo.'
    if muc == 'Kiểm thử & phản hồi':
        loi_chao = f'Chào <b>{esc(name)}</b>, cùng kiểm thử và đánh giá chất lượng chatbot nhé!'
    if muc == 'Tài khoản':
        tieu_de = 'Quản lý tài khoản'
        loi_chao = 'Quản lý người dùng, phân quyền và bảo mật hệ thống.'
    if muc == 'Nhật ký hệ thống':
        tieu_de = f'<span class="h-ico">{ICON_BANG["noi_dung"]}</span>{tieu_de}'
        loi_chao = 'Theo dõi các thao tác quản trị trong căn bếp của bạn.'
    st.markdown(f'<div class="admin-heading"><div><h1>{tieu_de}</h1><p>{loi_chao}</p></div><div class="admin-profile"><span>{esc(name[:1].upper())}</span><div><b>{esc(name)}</b><br><em>Admin</em></div></div></div>',unsafe_allow_html=True)
    if muc=='Tổng quan' and st.session_state.get('thong_bao_quan_tri'):
        st.success(st.session_state.pop('thong_bao_quan_tri'))
    if muc=='Tài khoản':
        from frontend.quan_tri import hien_quan_tri
        hien_quan_tri(actor)
        return
    if muc=='Nhật ký hệ thống':
        from frontend.nhat_ky import hien_nhat_ky
        hien_nhat_ky(logs, users)
        return
    if muc=='Tự học & NLP':
        hien_tu_hoc_va_nlp(actor)
        return
    if muc == 'Món ăn':
        from frontend.mon_an_admin import hien_thi_mon_admin

        hien_thi_mon_admin(actor)
        return
    if muc == 'Quản lý dinh dưỡng':
        from frontend.dinh_duong_admin import hien_thi_dinh_duong

        hien_thi_dinh_duong(actor, docs)
        return
    if muc == 'Quy tắc điều chỉnh':
        from frontend.quy_tac_admin import hien_thi_quy_tac

        hien_thi_quy_tac(actor, docs)
        return
    if muc in ('Món ăn', 'Quản lý dinh dưỡng', 'Quy tắc điều chỉnh'):
        from frontend.noi_dung_quan_tri import noi_dung_bien_tap

        fields = {
            'Món ăn': ('Nguyên liệu', 'Cách nấu', 'Thời gian và khẩu phần', 'Nguồn tham khảo'),
            'Quản lý dinh dưỡng': ('Kcal', 'Đạm (g)', 'Béo (g)', 'Carbohydrate (g)', 'Natri (mg)', 'Nguồn tham khảo'),
            'Quy tắc điều chỉnh': ('Giảm, bỏ hoặc thay nguyên liệu', 'Điều kiện áp dụng', 'Căn cứ áp dụng'),
        }
        source, edit = st.tabs(['Dữ liệu đang dùng', 'Biên tập và duyệt'])
        with source:
            if muc == 'Món ăn':
                bang_du_lieu(muc, recipes)
            elif muc == 'Quản lý dinh dưỡng':
                bang_du_lieu(muc, [d for d in docs if d.get('group_folder') in
                                   ('08_dinh_duong', '09_goi_y_mon_theo_dinh_duong')])
            else:
                bang_du_lieu(muc, [d for d in docs if d.get('group_folder') in
                                   ('06_thay_the_nguyen_lieu', '07_dieu_chinh_cong_thuc')])
        with edit:
            noi_dung_bien_tap(actor, muc, fields[muc])
        return
    if muc == 'Quản lý chatbot':
        from frontend.chatbot_admin import hien_thi_chatbot_admin

        hien_thi_chatbot_admin(actor, docs)
        return
    if muc in ('Quản lý chatbot', 'Kho tri thức'):
        questions, tools = st.tabs(['Bộ câu hỏi và trả lời', 'Từ khóa, ý định và NLP'])
        with questions:
            bang_du_lieu(muc, docs)
        with tools:
            hien_tu_hoc_va_nlp(actor)
        return
    if muc == 'Kiểm thử & phản hồi':
        hien_tu_hoc_va_nlp(actor)
        return
    if muc == 'Cài đặt hệ thống':
        from frontend.cai_dat_admin import hien_thi_cai_dat
        hien_thi_cai_dat(actor)
        return
    from backend.chatbot.co_so_du_lieu import ket_noi

    cutoff = (date.today() - timedelta(days=6)).isoformat()
    new_users = sum((u.get("ngay_tao") or "") >= cutoff for u in users)
    with ket_noi() as con:
        new_chats = con.execute(
            "SELECT COUNT(*) AS total FROM cuoc_tro_chuyen WHERE tao_luc>=?", (cutoff,)
        ).fetchone()["total"]
    counts = (
        ('groups', 'Tài khoản người dùng', len(users)),
        ('sms', 'Cuộc trò chuyện', sum(u['so_cuoc_tro_chuyen'] for u in users)),
        ('skillet', 'Công thức món ăn', len(recipes)),
        ('database', 'Dữ liệu dinh dưỡng', sum(
            d.get('group_folder') in ('08_dinh_duong', '09_goi_y_mon_theo_dinh_duong') for d in docs
        )),
    )
    tiles = []
    for (icon, label, value), added in zip(counts, (new_users, new_chats, None, None)):
        if added is None:
            detail = '<span>Chưa có lịch sử 7 ngày</span>'
        elif added:
            detail = f'<span class="admin-metric-gain">↑ +{added:,}</span><span>mới trong 7 ngày qua</span>'
        else:
            detail = '<span>Không có mục mới trong 7 ngày qua</span>' 
        number = f"{value:,}".replace(",", ".")
        tiles.append(
            f'<div class="admin-metric"><i class="material-symbols-rounded" aria-hidden="true">{icon}</i>'
            f'<div><small>{label}</small><strong>{number}</strong>{detail}</div></div>'
        )
    st.markdown('<div class="admin-metrics">' + ''.join(tiles) + '</div>', unsafe_allow_html=True)
    usage, topics, quick = st.columns([2, 1.4, 1.2], gap="small")
    with usage, st.container(key="admin_usage", border=True):
        title, period = st.columns([3, 1], vertical_alignment="center", gap="small")
        title.markdown("### :material/bar_chart: Thống kê lượt sử dụng chatbot")
        days = period.selectbox("Khoảng thời gian", [7, 30], format_func=lambda n: f"{n} ngày qua",
                                label_visibility="collapsed",
                                help="Lượt hỏi đã lưu, nhóm theo ngày cập nhật cuộc trò chuyện.")
        daily, categories = thong_ke_luot_hoi(days)
        st.vega_lite_chart(spec=bieu_do_luot_hoi(daily), width="stretch")
    with topics, st.container(key="admin_topics", border=True):
        st.markdown("### :material/person: Chủ đề người dùng quan tâm")
        total = sum(categories.values())
        if total:
            palette = ("#ff861e", "#ffb15b", "#ffd171", "#8dca53", "#ccc9c5")
            entries = []
            stops = []
            start = 0
            for (label, count), color in zip(categories.most_common(), palette):
                end = start + count
                stops.append(f"{color} {start / total:.8%} {end / total:.8%}")
                percent = f"{count / total:.1%}".replace(".", ",")
                entries.append(
                    f'<li><i style="background:{color}"></i><span>{esc(label)}</span><b>{percent}</b></li>'
                )
                start = end
            number = f"{total:,}".replace(",", ".")
            st.html(
                '<div class="admin-topic-layout">'
                f'<div class="admin-topic-ring" style="background:conic-gradient({", ".join(stops)})">'
                f'<div><strong>{number}</strong><span>lượt hỏi</span></div></div>'
                '<ul class="admin-topic-legend">' + ''.join(entries) + '</ul></div>'
            )
        else:
            st.caption("Chưa có lượt hỏi trong khoảng thời gian này.")
    with quick, st.container(key="admin_quick", border=True):
        st.markdown("### Thao tác nhanh")
        actions = (
            ("Quản lý món ăn", "Món ăn", "soup_kitchen"),
            ("Dinh dưỡng", "Quản lý dinh dưỡng", "database"),
            ("Kiểm thử chatbot", "Kiểm thử & phản hồi", "psychology"),
            ("Quản lý tài khoản", "Tài khoản", "person_add"),
        )
        for offset in (0, 2):
            for col, (label, target, icon) in zip(st.columns(2, gap="small"), actions[offset:offset+2]):
                col.button(f":material/{icon}: {label}", on_click=chuyen, args=(target,),
                           key=f"admin_quick_{icon}", width="stretch")

    with st.container(key="admin_accounts", border=True):
        title, add = st.columns([2, 1])
        title.markdown("### Tài khoản gần đây")
        add.button("Thêm tài khoản", icon=":material/add:", type="primary", on_click=chuyen,
                   args=("Tài khoản",), width="stretch")
        recent = sorted(users, key=lambda user: user.get("ngay_tao") or "", reverse=True)[:5]
        rows = []
        for user in recent:
            login = esc(user["ten_dang_nhap"])
            email = esc(user.get("email") or "")
            role = "Admin" if user["vai_tro"] == "admin" else "User"
            status_text = "Hoạt động" if user["kich_hoat"] else "Đã khóa"
            status_class = "active" if user["kich_hoat"] else "locked"
            joined = esc((user.get("ngay_tao") or "")[:10])
            rows.append(f'<tr><td><b>{login}</b><small>{email}</small></td>'
                        f'<td><span class="admin-role-pill">{role}</span></td>'
                        f'<td><span class="status {status_class}">{status_text}</span></td><td>{joined}</td></tr>')
        st.markdown('<div class="admin-recent-table"><table><thead><tr><th>Tài khoản</th><th>Vai trò</th>'
                    '<th>Trạng thái</th><th>Ngày đăng ký</th></tr></thead><tbody>'
                    + ''.join(rows) + '</tbody></table></div>', unsafe_allow_html=True)
        st.button("Xem tất cả tài khoản", on_click=chuyen, args=("Tài khoản",), type="tertiary")
    activity, status = st.columns([1.4, 1], gap="small")
    with activity, st.container(key="admin_activity", border=True):
        st.markdown("### Hoạt động gần đây")
        for entry in logs[:5]:
            st.markdown(f'<div class="activity"><b>{esc(entry["hanh_dong"].replace("_", " ").capitalize())}: '
                        f'{esc(entry["doi_tuong"])}</b><small>{esc(entry["tao_luc"])}</small></div>',
                        unsafe_allow_html=True)
        if not logs:
            st.caption("Chưa có hoạt động quản trị.")
        st.button("Xem nhật ký hệ thống", on_click=chuyen, args=("Nhật ký hệ thống",))
    with status, st.container(key="admin_connections", border=True):
        st.markdown("### Tình trạng hệ thống")
        from backend.chatbot.co_so_du_lieu import BACKEND

        st.success(f"{'MySQL' if BACKEND == 'mysql' else 'SQLite'} đã kết nối")
        st.caption(f"Kho tri thức: {len(docs):,} mục")
        hien_thi_ket_noi_neo4j()

        from backend.chatbot.cau_hoi_cho_hoc import lay_danh_sach_cau_hoi_chua_biet

        unresolved = len(lay_danh_sach_cau_hoi_chua_biet())
        if unresolved:
            st.warning(f"{unresolved} câu hỏi chưa trả lời cần xem lại.")
            st.button("Xem câu hỏi chưa trả lời", on_click=chuyen, args=("Kiểm thử & phản hồi",))
        else:
            st.caption("Chưa ghi nhận câu hỏi chưa trả lời.")



def bieu_do_luot_hoi(daily):
    """Plain Vega-Lite spec: avoids Altair schema construction during a rerun."""
    records = [{"day": str(day), "count": int(count)} for day, count in daily.items()]
    dates = [str(day) for day in list(daily)[::max(1, len(daily) // 7)]]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
        "data": {"values": records},
        "encoding": {
            "x": {"field": "day", "type": "temporal", "title": None,
                  "axis": {"format": "%d/%m", "labelAngle": 0, "values": dates, "grid": False}},
            "y": {"field": "count", "type": "quantitative", "title": None,
                  "scale": {"domainMin": 0, "domainMax": max(1, max(daily.values(), default=0))},
                  "axis": {"tickCount": 5, "format": "d", "gridColor": "#eadfd2"}},
            "tooltip": [{"field": "day", "type": "temporal", "title": "Ngày", "format": "%d/%m/%Y"},
                        {"field": "count", "type": "quantitative", "title": "Lượt hỏi"}],
        },
        "layer": [
            {"mark": {"type": "area", "opacity": .48, "color": {
                "gradient": "linear", "x1": 0, "x2": 0, "y1": 1, "y2": 0,
                "stops": [{"color": "#ff8515", "offset": 0}, {"color": "#fff7ea", "offset": 1}]}}},
            {"mark": {"type": "line", "color": "#ff790b", "strokeWidth": 2.5,
                      "point": {"filled": True, "fill": "#fffaf1", "stroke": "#ff790b", "strokeWidth": 2, "size": 46}}},
        ],
        "height": 145, "config": {"view": {"stroke": None}},
    }


@st.cache_data(ttl=30, show_spinner=False)
def thong_ke_luot_hoi(days):
    """Summarize saved user messages and their topics without displaying message text."""
    from backend.chatbot.co_so_du_lieu import ket_noi
    from backend.chatbot.ngon_ngu import chuan_hoa

    today = date.today()
    start = today - timedelta(days=days - 1)
    daily = {(start + timedelta(days=i)).isoformat(): 0 for i in range(days)}
    categories = Counter()
    with ket_noi() as con:
        rows = con.execute(
            """SELECT c.cap_nhat AS tao_luc, t.du_lieu_json
               FROM cuoc_tro_chuyen c JOIN tin_nhan t
               ON c.ten_dang_nhap=t.ten_dang_nhap AND c.ma=t.ma_cuoc
               WHERE c.cap_nhat>=?""",
            (start.isoformat(),),
        ).fetchall()
    for row in rows:
        day = row["tao_luc"][:10]
        message = json.loads(row["du_lieu_json"])
        if day not in daily or message.get("vai") != "user":
            continue
        daily[day] += 1
        question = chuan_hoa(message.get("noi_dung", ""))
        for label, pattern in (
            ("Điều chỉnh công thức", r"\b(dieu chinh|thay the|khau phan)\b"),
            ("Dinh dưỡng", r"\b(dinh duong|du chat|calo)\b"),
            ("Gợi ý món ăn", r"\b(goi y|nau gi|an gi)\b"),
            ("Hướng dẫn nấu", r"\b(nau|cong thuc|che bien)\b"),
        ):
            if re.search(pattern, question):
                categories[label] += 1
                break
        else:
            categories["Khác"] += 1
    return daily, categories
   