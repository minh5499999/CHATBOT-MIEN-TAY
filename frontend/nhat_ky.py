"""Nhật ký quản trị: diễn giải dữ liệu thật và bộ lọc cho trang quản trị."""
from datetime import datetime, timedelta, timezone
from html import escape
import json
import unicodedata

import streamlit as st


HANH_DONG = {
    'khoi_tao_admin': ('Cấp quyền quản trị', 'neutral'),
    'tao_tai_khoan': ('Tạo tài khoản', 'neutral'),
    'cap_nhat_quyen': ('Cập nhật tài khoản', 'changed'),
    'dat_lai_mat_khau': ('Đặt lại mật khẩu', 'changed'),
    'xoa_tai_khoan': ('Xóa tài khoản', 'removed'),
}
MOI_TRANG = 6

# Dữ liệu minh họa (theo bản mẫu giao diện): hiện kèm nhãn "Dữ liệu minh họa" ở tiêu đề bảng.
# Đổi thành False để bảng chỉ còn nhật ký thật.
HIEN_MINH_HOA = False
MINH_HOA = [
    # (người dùng, mục liên quan, việc đã làm, sắc thái nhãn, nội dung cụ thể, thời gian)
    ('Baotram', 'Kho tri thức', 'Sửa hướng dẫn', 'soft', 'Bổ sung bước nêm canh chua', '2026-11-05 09:20'),
    ('Baotram', 'Món ăn', 'Sửa công thức', 'changed', 'Cá kho tộ: đổi lượng nước mắm từ 3 xuống 2 muỗng', '2026-11-05 09:05'),
    ('Baotram', 'Món ăn', 'Thêm món ăn', 'added', 'Thêm công thức bánh xèo miền Tây', '2026-11-04 15:40'),
    ('Baotram', 'Trang quản trị', 'Đăng nhập', 'neutral', 'Đăng nhập thành công', '2026-11-04 08:30'),
    ('Baotram', 'Kho tri thức', 'Thêm hướng dẫn', 'lime', 'Thêm bài hướng dẫn chọn cá tươi', '2026-11-03 14:15'),
]


def dong_minh_hoa():
    rows = []
    for user, section, action, tone, detail, when in MINH_HOA:
        date = datetime.fromisoformat(when)
        rows.append({'user': user, 'section': section, 'action': action, 'tone': tone, 'detail': detail,
                     'date': date, 'time': date.strftime('%d/%m/%Y %H:%M'), 'search': '', 'minh_hoa': True})
    return rows


def _svg(path, size=20):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>')


ICON = {
    'lop': _svg('<path d="M12 3 2 8l10 5 10-5z"/><path d="m2 12 10 5 10-5"/><path d="m2 16 10 5 10-5"/>'),
    'nguoi': _svg('<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>'),
    'lich': _svg('<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>'),
    'info': _svg('<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>', 18),
}


def thoi_gian(value):
    try:
        result = datetime.fromisoformat(str(value))
        if result.tzinfo:
            result = result.astimezone(timezone(timedelta(hours=7))).replace(tzinfo=None)
        return result
    except (ValueError, TypeError):
        return None


def tu_khoa(value):
    text = unicodedata.normalize('NFD', str(value).casefold().replace('đ', 'd'))
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).split())


def dien_giai(entry, names=None):
    names = names or {}
    actor = str(entry.get('nguoi_thuc_hien') or 'Không rõ')
    target = str(entry.get('doi_tuong') or 'Không rõ')
    code = str(entry.get('hanh_dong') or '')
    raw_detail = str(entry.get('chi_tiet') or '').strip()
    action, tone = HANH_DONG.get(code, (code.replace('_', ' ').capitalize() or 'Hoạt động khác', 'neutral'))
    detail = raw_detail or 'Không có nội dung bổ sung.'
    role_names = {'admin': 'quản trị', 'user': 'người dùng'}
    if code == 'khoi_tao_admin':
        detail = f'Cấp quyền quản trị ban đầu cho tài khoản {target}.'
    elif code == 'tao_tai_khoan':
        role = role_names.get(raw_detail)
        detail = f'Tạo tài khoản {target}' + (f' với quyền {role}.' if role else '.')
        if raw_detail and not role:
            detail += f' {raw_detail}'
    elif code == 'cap_nhat_quyen':
        try:
            data = json.loads(raw_detail)
        except (ValueError, TypeError):
            data = None
        if isinstance(data, dict):
            parts = [f'Cập nhật tài khoản {target}']
            if data.get('vai_tro') in role_names:
                parts.append('quyền ' + role_names[data['vai_tro']])
            if isinstance(data.get('kich_hoat'), bool):
                parts.append('đang hoạt động' if data['kich_hoat'] else 'đã khóa')
            detail = '; '.join(parts) + '.'
        else:
            detail = f'Cập nhật tài khoản {target}.' + (f' {raw_detail}' if raw_detail else '')
    elif code == 'dat_lai_mat_khau':
        detail = f'Đặt lại mật khẩu và đăng xuất các phiên của tài khoản {target}.'
    elif code == 'xoa_tai_khoan':
        detail = f'Xóa tài khoản {target} cùng lịch sử trò chuyện và phiên đăng nhập.'
    when = thoi_gian(entry.get('tao_luc'))
    return {
        'user': 'Hệ thống' if actor == 'thiet_lap_cuc_bo' else (names.get(actor) or actor),
        'section': 'Tài khoản' if code in HANH_DONG else target,
        'action': action, 'tone': tone, 'detail': detail, 'date': when,
        'time': when.strftime('%d/%m/%Y %H:%M') if when else 'Chưa rõ thời gian',
        'search': ' '.join((actor, names.get(actor) or '', target, raw_detail)),
    }


def loc_nhat_ky(rows, query='', action='Tất cả hoạt động', start=None, end=None):
    query = tu_khoa(query)
    return [row for row in rows
            if (not query or query in tu_khoa(' '.join(str(row[k]) for k in ('user', 'section', 'action', 'detail', 'search'))))
            and (action == 'Tất cả hoạt động' or row['action'] == action)
            and (start is None or (row['date'] is not None and row['date'].date() >= start))
            and (end is None or (row['date'] is not None and row['date'].date() <= end))]


def bang_html(rows, empty='Chưa có hoạt động quản trị được ghi nhận.'):
    body = []
    for row in rows:
        body.append('<tr>'
                    f'<td>{escape(row["user"])}</td><td>{escape(row["section"])}</td>'
                    f'<td><span class="log-badge {row["tone"]}">{escape(row["action"])}</span></td>'
                    f'<td>{escape(row["detail"])}</td><td>{escape(row["time"])}</td></tr>')
    if not body:
        body.append(f'<tr><td colspan="5" class="log-empty">{escape(empty)}</td></tr>')
    return ('<div class="log-table-scroll"><table class="log-table" aria-label="Lịch sử hoạt động quản trị">'
            '<colgroup><col style="width:15%"><col style="width:16%"><col style="width:19%">'
            '<col style="width:33%"><col style="width:17%"></colgroup>'
            '<thead><tr><th scope="col">Người dùng</th><th scope="col">Mục liên quan</th>'
            '<th scope="col">Việc đã làm</th><th scope="col">Nội dung cụ thể</th><th scope="col">Thời gian</th>'
            '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>')


def _doi_trang(delta):
    st.session_state.nk_trang = max(1, st.session_state.get('nk_trang', 1) + delta)


def hien_nhat_ky(logs, users):
    names = {u['ten_dang_nhap']: u.get('ten_hien_thi') or u['ten_dang_nhap'] for u in users}
    rows = [dien_giai(entry, names) for entry in logs]
    co_minh_hoa = HIEN_MINH_HOA
    if co_minh_hoa:  # trộn với nhật ký thật, mới nhất lên đầu
        rows = sorted(rows + dong_minh_hoa(), key=lambda r: r['date'] or datetime.min, reverse=True)
    dates = [r['date'] for r in rows if r['date']]
    latest = max(dates).strftime('%d/%m/%Y') if dates else 'chưa có'
    admins = sum(u.get('vai_tro') == 'admin' and bool(u.get('kich_hoat')) for u in users)
    st.markdown(f'<div class="log-summary"><span>{ICON["lop"]}{len(rows)} hoạt động</span><i>•</i>'
                f'<span>{ICON["nguoi"]}{admins} quản trị viên</span><i>•</i>'
                f'<span>{ICON["lich"]}Cập nhật gần nhất: {latest}</span></div>', unsafe_allow_html=True)
    with st.container(key='nhat_ky_panel'):
        nhan = ('<span class="log-demo" title="Bảng đang kèm các dòng mẫu để minh họa giao diện">Dữ liệu minh họa</span>'
                if co_minh_hoa else '')
        st.markdown(f'<div class="log-heading"><div class="log-title"><h2>Lịch sử hoạt động</h2>{nhan}</div>'
                    '<p>Xem ai đã làm gì, ở mục nào và vào lúc nào.</p></div>', unsafe_allow_html=True)
        with st.container(key='nk_filters'):
            search, actions, dates_col, refresh = st.columns([2.2, 1.4, 1.35, .8], gap='small', vertical_alignment='center')
            query = search.text_input('Tìm tên người hoặc nội dung', placeholder='Tìm tên người hoặc nội dung...',
                                      key='nk_tim', label_visibility='collapsed', icon=':material/search:')
            options = ['Tất cả hoạt động'] + sorted({r['action'] for r in rows})
            if st.session_state.get('nk_hanh_dong') not in options:
                st.session_state.nk_hanh_dong = options[0]
            action = actions.selectbox('Lọc hoạt động', options, key='nk_hanh_dong', label_visibility='collapsed')
            # Chưa chọn (None) = xem tất cả; ô hiện chữ gợi ý "Chọn thời gian" như bản mẫu.
            period = dates_col.selectbox('Chọn thời gian', ['Tất cả thời gian', 'Hôm nay', '7 ngày qua', '30 ngày qua', 'Chọn khoảng ngày'],
                                        index=None, placeholder='Chọn thời gian',
                                        key='nk_thoi_gian', label_visibility='collapsed')
            # Mỗi lần bấm, Streamlit chạy lại và tải nhật ký mới từ dịch vụ tài khoản.
            refresh.button('Làm mới', icon=':material/refresh:', key='nk_lam_moi', width='stretch')
        today = datetime.now(timezone(timedelta(hours=7))).date()
        start = end = None
        if period in ('Hôm nay', '7 ngày qua', '30 ngày qua'):
            end = today
            start = today - timedelta(days={'Hôm nay': 0, '7 ngày qua': 6, '30 ngày qua': 29}[period])
        elif period == 'Chọn khoảng ngày':
            selected = st.date_input('Khoảng thời gian', (today - timedelta(days=6), today),
                                     key='nk_khoang_ngay', format='DD/MM/YYYY')
            if len(selected) != 2:
                st.info('Chọn thêm ngày kết thúc để xem kết quả.')
                return
            start, end = selected
        filtered = loc_nhat_ky(rows, query, action, start, end)
        signature = (query, action, str(start), str(end))
        if st.session_state.get('nk_bo_loc') != signature:
            st.session_state.nk_trang = 1
            st.session_state.nk_bo_loc = signature
        pages = max(1, (len(filtered) + MOI_TRANG - 1) // MOI_TRANG)
        page = min(st.session_state.get('nk_trang', 1), pages)
        st.session_state.nk_trang = page
        offset = (page - 1) * MOI_TRANG
        st.markdown(bang_html(filtered[offset:offset + MOI_TRANG],
                             'Không có hoạt động phù hợp. Hãy thử từ khóa hoặc khoảng thời gian khác.' if rows
                             else 'Chưa có hoạt động quản trị được ghi nhận.'), unsafe_allow_html=True)
        with st.container(key='nk_footer', horizontal=True, vertical_alignment='center'):
            st.markdown(f'<span class="log-count">Hiển thị {offset + 1 if filtered else 0}–{min(offset + MOI_TRANG, len(filtered))}'
                        f' trong {len(filtered)} hoạt động</span>', unsafe_allow_html=True)
            with st.container(key='nk_pages', horizontal=True, horizontal_alignment='right', gap='small', width='content'):
                st.button('', icon=':material/chevron_left:', help='Trang trước', key='nk_truoc',
                          disabled=page <= 1, on_click=_doi_trang, args=(-1,))
                st.markdown(f'<span class="log-page" title="Trang {page} / {pages}">{page}</span>', unsafe_allow_html=True)
                st.button('', icon=':material/chevron_right:', help='Trang sau', key='nk_sau',
                          disabled=page >= pages, on_click=_doi_trang, args=(1,))
    st.markdown(f'<p class="log-note" title="Hiển thị tối đa 100 hoạt động gần nhất.">{ICON["info"]}'
                'Nhật ký giúp kiểm tra thay đổi và tra cứu hoạt động quản trị.</p>', unsafe_allow_html=True)
