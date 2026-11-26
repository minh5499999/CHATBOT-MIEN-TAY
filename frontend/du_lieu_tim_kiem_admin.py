"""Search-store administration using actual index metadata."""
import json
import base64
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

from backend.chatbot.cau_hinh import ROOT, doc_cau_hinh
from frontend.noi_dung_quan_tri import noi_dung_bien_tap

MODES = {"lai": "Kết hợp Vector + BM25", "vector": "Chỉ Vector", "bm25": "Chỉ BM25"}


def danh_sach_kho(root, current):
    directory = root / current
    rows = []
    for path in sorted(directory.parent.glob('*/thong_tin.json')):
        try:
            info = json.loads(path.read_text(encoding='utf-8'))
            metadata = path.parent/'sieu_du_lieu.jsonl'
            count = 0
            if metadata.is_file():
                with metadata.open(encoding='utf-8') as source:
                    count = sum(1 for line in source if line.strip())
            updated = max(p.stat().st_mtime for p in (path, metadata) if p.is_file())
            active = path.parent.resolve() == directory.resolve()
            method = {"cau_truc": "cấu trúc", "co_dinh": "độ dài cố định", "de_quy": "đệ quy"}.get(info.get('cach_cat'), info.get('cach_cat', ''))
            rows.append({'name': path.parent.name, 'description': f'Kho tìm kiếm chia đoạn theo {method} · {info.get("tap", "")}',
                         'count': count, 'updated': updated, 'active': active,
                         'info': info, 'path': path.parent.relative_to(root).as_posix()})
        except (OSError, ValueError, TypeError):
            continue
    return rows


def _cap_nhat_che_do(actor):
    from backend.chatbot import tai_khoan
    from backend.chatbot.cau_hinh import CAU_HINH_PATH
    if not tai_khoan.la_admin(actor):
        st.error('Bạn không có quyền thay đổi chế độ tìm kiếm.')
        return
    config = json.loads(CAU_HINH_PATH.read_text(encoding='utf-8'))
    config['che_do_truy_hoi'] = st.session_state.retrieval_mode
    temporary = CAU_HINH_PATH.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(CAU_HINH_PATH)
    doc_cau_hinh.cache_clear()


def _date(timestamp):
    return datetime.fromtimestamp(timestamp, ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%d/%m/%Y %H:%M')


def _cell(column, value, bold=False, center=False):
    text = escape(str(value))
    column.html(f'<div title="{text}" style="font:{600 if bold else 400} 15px/28px Segoe UI,Arial,sans-serif;'
                f'color:#49291f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:{"center" if center else "left"};">{text}</div>')


def _icon(kind, size=25):
    paths = {
        'folder': '<path d="M3 7h18v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l3 4"/>',
        'file': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 12h8M8 16h6"/>',
        'check': '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
        'sync': '<path d="M20 7v5h-5M4 17v-5h5M6 6a8 8 0 0 1 13 2M18 18A8 8 0 0 1 5 16"/>',
    }
    color = '#219b08' if kind == 'check' else '#ff8a00'
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{paths[kind]}</svg>')
    encoded = base64.b64encode(svg.encode('utf-8')).decode('ascii')
    return (f'<img src="data:image/svg+xml;base64,{encoded}" width="{size}" height="{size}" '
            f'alt="" style="display:block;flex-shrink:0;width:{size}px;height:{size}px;">')


def hien_thi_thong_ke_tim_kiem():
    config = doc_cau_hinh()
    rows = danh_sach_kho(ROOT, config['kho_vector'])
    latest = max((row['updated'] for row in rows), default=None)
    stats = [('folder','Tổng kho dữ liệu',str(len(rows))),('file','Tổng bản ghi',f'{sum(row["count"] for row in rows):,}'.replace(',','.')),
             ('check','Đang sử dụng',str(sum(row['active'] for row in rows))),('sync','Cập nhật gần nhất',_date(latest) if latest else '—')]
    with st.container(key="retrieval_top_metrics"):
        st.html('<div class="admin-metrics search-metrics">' + ''.join(
            '<div class="admin-metric">'
            f'<i style="display:grid;place-items:center;font-style:normal;background:{"#e5f8d2" if index == 2 else "#fff0d8"};">{_icon(icon)}</i>'
            f'<div><small>{escape(label)}</small><strong{chr(32) + "class=search-metric-date" if index == 3 else ""}>{escape(value)}</strong></div></div>'
            for index, (icon, label, value) in enumerate(stats)) + '</div>')



def hien_thi_du_lieu_tim_kiem(actor):
    config = doc_cau_hinh()
    rows = danh_sach_kho(ROOT, config['kho_vector'])
    with st.container(key='retrieval_listing'):
        with st.container(key='retrieval_mode_bar', border=True):
            title, modes = st.columns([1.3,5],vertical_alignment='center')
            title.markdown('**⚙ Chế độ tìm kiếm:**')
            if 'retrieval_mode' not in st.session_state:
                st.session_state.retrieval_mode = config.get('che_do_truy_hoi','lai')
            modes.radio('Chế độ tìm kiếm', list(MODES), format_func=lambda mode: MODES[mode] + ('  ·  Đề xuất' if mode == 'lai' else ''), horizontal=True,
                        label_visibility='collapsed',key='retrieval_mode',on_change=_cap_nhat_che_do,args=(actor,),
                        help='Kết hợp Vector + BM25 là chế độ đề xuất. Lựa chọn được lưu cho chatbot.')
        with st.container(key='retrieval_toolbar'):
            search,status,space,sync,add=st.columns([2.5,1.2,.8,1,1],gap='small',vertical_alignment='center')
            query=search.text_input('Tìm tên dữ liệu',placeholder='Tìm tên dữ liệu...',icon=':material/search:',label_visibility='collapsed',key='retrieval_search')
            selected=status.selectbox('Trạng thái dữ liệu',['Tất cả trạng thái','Đang sử dụng','Chưa sử dụng'],label_visibility='collapsed',key='retrieval_status')
            if sync.button('Đồng bộ dữ liệu',icon=':material/sync:',width='stretch',help='Đọc lại danh sách và thống kê kho trên ổ đĩa; không xây lại chỉ mục.'):
                doc_cau_hinh.cache_clear()
                st.rerun()
            if add.button('Thêm dữ liệu',icon=':material/add:',type='primary',width='stretch'):
                st.session_state['editor_Dữ liệu tìm kiếm']=''
                _bien_tap(actor)
        matches=[row for row in rows if query.casefold() in (row['name']+' '+row['description']).casefold()
                 and (selected=='Tất cả trạng thái' or (selected=='Đang sử dụng')==row['active'])]
        widths=[.4,1.6,2.3,.8,1.35,1.3,1]
        with st.container(key='retrieval_table_frame'):
            with st.container(key='retrieval_table_header'):
                for column,label in zip(st.columns(widths,gap=None),['STT','Tên dữ liệu','Mô tả','Số bản ghi','Ngày cập nhật','Trạng thái','Thao tác']):
                    column.markdown(f'**{label}**')
            for index,row in enumerate(matches,1):
                with st.container(key=f'retrieval_table_row_{index}'):
                    cols=st.columns(widths,gap=None,vertical_alignment='center')
                    _cell(cols[0],index,center=True)
                    cols[1].html('<div style="display:flex;align-items:center;gap:10px;color:#ff8a00;">'
                                 +_icon('file',22)+f'<strong title="{escape(row["name"])}" style="font:650 15px/28px Segoe UI,Arial,sans-serif;color:#651d12;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{escape(row["name"])}</strong></div>')
                    _cell(cols[2],row['description'])
                    _cell(cols[3],row['count'],center=True)
                    _cell(cols[4],_date(row['updated']),center=True)
                    label='Đang sử dụng' if row['active'] else 'Chưa sử dụng'
                    cols[5].html(f'<div style="display:flex;align-items:center;justify-content:center;min-height:28px;"><span style="display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:20px;background:{"#e5fac7" if row["active"] else "#fff0d7"};color:{"#248c00" if row["active"] else "#9c6500"};font:600 13px/22px Segoe UI,Arial,sans-serif;white-space:nowrap;">{_icon("check",15) if row["active"] else ""}{label}</span></div>')
                    view,edit,delete=cols[6].columns(3,gap=None)
                    if view.button('',icon=':material/visibility:',key=f'retrieval_view_{index}',help='Xem thông tin dữ liệu'):
                        _xem(row)
                    if edit.button('',icon=':material/edit:',key=f'retrieval_edit_{index}',help='Biên tập dữ liệu'):
                        st.session_state['editor_Dữ liệu tìm kiếm']=''
                        _bien_tap(actor,row)
                    delete.button('',icon=':material/delete:',key=f'retrieval_delete_{index}',disabled=True,
                                  help='Xóa kho cần qua quy trình cập nhật và kiểm định dữ liệu.')
            if not matches:
                st.info('Không tìm thấy dữ liệu phù hợp.')


@st.dialog('Thông tin dữ liệu tìm kiếm',width='large')
def _xem(row):
    st.subheader(row['name'])
    st.write(row['description'])
    st.caption(f'{row["count"]} bản ghi · Cập nhật {_date(row["updated"])}')
    st.json(row['info'])


@st.dialog('Biên tập dữ liệu tìm kiếm',width='large')
def _bien_tap(actor,row=None):
    noi_dung_bien_tap(actor,'Dữ liệu tìm kiếm',('Tên dữ liệu','Mô tả','Nguồn tham khảo'),
                      initial={'Tên dữ liệu':row['name'],'Mô tả':row['description'],'Nguồn tham khảo':row['path']} if row else None)
