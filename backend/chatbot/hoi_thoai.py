"""LCEL theo phiên: NLP → context → truy hồi/gợi ý → trích xuất/template."""
import copy
import re
import time
from functools import lru_cache
from langchain_core.runnables import RunnableLambda
from backend.chatbot.che_do_du_lieu import chon_kho
from backend.chatbot.intent import phan_tich
from backend.chatbot.sinh_cau_tra_loi import mo_ta_nguon
from backend.chatbot.trang_thai import lay_trang_thai, cap_nhat, chon_theo_so, la_cau_noi_tiep
from backend.chatbot.cong_thuc import danh_muc, tu_vung_nguyen_lieu, goi_y_theo_dieu_kien, quy_doi_khau_phan, ten_nguyen_lieu
from backend.chatbot.phan_hoi import chon_phan_hoi
from backend.chatbot.ngon_ngu import khoa_cau_hoi


def _empty(message, suggestions=()):
    return {'cau_tra_loi': message, 'loai':'khong_chac', 'nguon':[], 'goi_y':list(suggestions),
            'nhan_goi_y':'Chọn nội dung bạn muốn xem:', 'doan_truy_hoi':[], 'chu_de':None,
            'giai_thich':{}}


@lru_cache(maxsize=1)
def chuoi_hoi_thoai():
    def prepare(payload):
        kho, mode = chon_kho(payload['options'])
        parsed = phan_tich(payload['question'], tu_vung_nguyen_lieu(kho))
        previous = lay_trang_thai(payload['history'])
        if 'tinh_trang_suc_khoe' not in previous:
            from backend.chatbot.suc_khoe import cap_nhat as cap_nhat_suc_khoe
            for turn in payload['history']:
                previous['tinh_trang_suc_khoe'] = cap_nhat_suc_khoe(previous.get('tinh_trang_suc_khoe'),turn.get('cau_hoi',''))
        # Tương thích lịch sử trước phiên bản trạng thái có cấu trúc.
        if not previous.get('mon_hien_tai'):
            previous['mon_hien_tai'] = next((h['chu_de'] for h in reversed(payload['history']) if h.get('chu_de')), None)
        if not any(h.get('trang_thai') for h in payload['history']) and payload['history']:
            from backend.chatbot.ngon_ngu import dieu_kien
            from backend.chatbot.suc_khoe import cap_nhat as cap_nhat_suc_khoe
            previous['dieu_kien'] = dieu_kien('', payload['history'])
            for turn in payload['history']:
                previous['tinh_trang_suc_khoe'] = cap_nhat_suc_khoe(previous.get('tinh_trang_suc_khoe'),turn.get('cau_hoi',''))
        state = cap_nhat(previous, parsed)
        choice, error = chon_theo_so(payload['question'], previous)
        if choice:
            state['mon_hien_tai'] = choice
        return {**payload, 'started':time.perf_counter(), 'kho':kho, 'mode':mode, 'parsed':parsed, 'state':state,
                'previous':previous, 'choice':choice, 'error':error}

    def answer(payload):
        from backend.chatbot.sinh_cau_tra_loi import _tra_loi_truy_hoi, mo_ta_nguon, nhan_dien_xa_giao
        from backend.chatbot.doi_chieu import chi_muc_cau_hoi
        from backend.chatbot.fuzzy import de_nghi_ten_mon
        p, state, q, kho = payload['parsed'], payload['state'], payload['question'], payload['kho']
        from backend.chatbot.suc_khoe import id_co_bang_chung, thong_bao_thieu
        health = [] if nhan_dien_xa_giao(q) else state.get('tinh_trang_suc_khoe', [])
        food_request = not ('thong_tin' in p['intents'] and not set(p['intents']) & {'goi_y_mon','cong_thuc','che_bien','nguyen_lieu'})
        health_ids = id_co_bang_chung(kho,tuple(health),food_request) if health else None
        current = state.get('mon_hien_tai')
        if health and not health_ids:
            result = _empty(thong_bao_thieu(health))
        elif payload['error']:
            result = _empty(payload['error'])
        else:
            
            nau_nhanh = 'nau_nhanh' in p['intents']

            constrained = bool(
                state.get('nguyen_lieu_co')
                or state.get('thoi_gian_toi_da') is not None
                or state.get('khong_chien')
                or nau_nhanh
            )

            exact = bool(
                chi_muc_cau_hoi(kho).get(khoa_cau_hoi(q))
            )

            
            recommend = (
                ('goi_y_mon' in p['intents'] or nau_nhanh)
                and constrained
                and (not exact or nau_nhanh)
            )

            if recommend:
                options = goi_y_theo_dieu_kien(kho, state)
                if not options:
                    result = _empty('Mình chưa tìm được công thức có đủ dữ liệu để đáp ứng đồng thời các điều kiện này. Bạn có thể bổ sung nguyên liệu hoặc nới giới hạn thời gian không?')
                else:
                    
                    lines = [
                        "Mình gợi ý bạn một vài món có thời gian "
                        "chế biến ngắn trong kho công thức nhé!"
                        if nau_nhanh else
                        "Mình tìm được một vài món phù hợp "
                        "với yêu cầu của bạn:"
                    ]

                    
                    for i, (_, _, recipe, missing) in enumerate(options, 1):
                        ten_mon = recipe.cau_hoi.strip()

                        # Bỏ phần mở đầu của câu hỏi.
                        ten_mon = re.sub(
                            r'^(?:cách nấu|cách làm|hướng dẫn nấu|'
                            r'hướng dẫn làm|nấu|làm)\s+',
                            '',
                            ten_mon,
                            flags=re.IGNORECASE
                        )

                        # Bỏ phần hỏi ở cuối, giữ dấu tiếng Việt.
                        ten_mon = re.sub(
                            r'\s+(?:như thế nào|ra sao|làm sao|'
                            r'nấu thế nào|nấu sao)\s*[?!.]*$',
                            '',
                            ten_mon,
                            flags=re.IGNORECASE
                        )

                        ten_mon = ten_mon.strip(" ?!.").capitalize()

                        if recipe.tong_phut is not None:
                            lines.append(
                                f"{i}. **{ten_mon}** — {recipe.tong_phut} phút"
                            )
                        else:
                            lines.append(f"{i}. **{ten_mon}**")

                        if state.get("nguyen_lieu_co") and missing:
                            raw_missing = [
                                line.lstrip("- ")
                                for line in recipe.nguyen_lieu
                                if ten_nguyen_lieu(line) in missing
                            ]
                            lines.append(
                                "   Cần thêm theo nguồn: "
                                + ", ".join(raw_missing) + "."
                            )

                    lines.append(
                        "Bạn chọn món muốn nấu nhé, "
                        "mình sẽ hướng dẫn nguyên liệu "
                        "và cách làm chi tiết."
                    )

                    result = _empty(
                        "\n\n".join(lines),
                        [r[2].cau_hoi for r in options]
                    )

                    result["nguon"] = [
                        mo_ta_nguon(dict(r[2].metadata, diem=0.0))
                        for r in options
                    ]

            else:
                # Không fuzzy-sửa một câu có điều kiện tránh/dị ứng.
                dk = state['dieu_kien']
                protected = bool(dk['loai_tru'] or dk['chua_ro'] or dk['an_chay'])
                proposals = de_nghi_ten_mon(q, kho) if not protected and not la_cau_noi_tiep(q) and not payload['choice'] else []
                if proposals:
                    result = _empty('Tên món bạn nhập có thể bị gõ nhầm. Ý bạn là công thức nào dưới đây? Mình chờ bạn xác nhận để không đổi nhầm món.', proposals)
                else:
                    tc = {**payload['options'], 'kho':kho, 'dieu_kien':dk}
                    if current and (payload['choice'] or la_cau_noi_tiep(q)) and 'thay_the' not in p['intents']:
                        tc['id_chu_de'] = current['id_goc']
                    result = _tra_loi_truy_hoi(p['cau_chuan'], payload['history'], tc)
                    # Một công thức đúng món chưa chắc trả lời được bảo quản/thay thế.
                    # Không dùng ngữ cảnh để biến câu hỏi đó thành yêu cầu nấu lại.
                    aspects = set(p['intents']) & {'bao_quan','thay_the'}
                    if aspects and current and la_cau_noi_tiep(q) and result['loai'] == 'tra_loi':
                        from backend.chatbot.sinh_cau_tra_loi import noi_dung_day_du
                        from backend.chatbot.ngon_ngu import chuan_hoa
                        source_text = '\n'.join(noi_dung_day_du(kho,n['id_goc']) for n in result['nguon'])
                        support = {'bao_quan':r'\b(bao quan|tru dong|cap dong|tu lanh)\b',
                                   'thay_the':r'\b(thay bang|thay the|co the dung .+ thay)\b'}
                        if not all(re.search(support[a],chuan_hoa(source_text)) for a in aspects):
                            name = 'bảo quản' if 'bao_quan' in aspects else 'thay thế nguyên liệu'
                            result = _empty(f"Mình đang giữ món **{current['cau_hoi']}**, nhưng nguồn vừa tìm chưa có hướng dẫn {name} đủ rõ cho yêu cầu này. Bạn nêu cụ thể nguyên liệu hoặc cách bảo quản muốn hỏi để mình tìm tiếp nhé.")
                    if current and not aspects and tc.get('id_chu_de') is not None and result['loai'] == 'khong_chac' and not result['nguon']:
                        details = ', '.join(dk['loai_tru'])
                        reason = f' điều kiện tránh {details}' if details else ' các điều kiện đang giữ'
                        result['cau_tra_loi'] = (f"Mình vẫn đang giữ món **{current['cau_hoi']}**. "
                            f"Công thức trong nguồn chưa đáp ứng{reason}; mình chưa có phiên bản đã kiểm chứng để tự thay nguyên liệu. "
                            + (f"Mình đã ghi nhận khẩu phần {state['khau_phan']} người. " if state.get('khau_phan') else '')
                            + 'Bạn có thể chọn món khác hoặc điều chỉnh yêu cầu. Các điều kiện dị ứng vẫn được giữ.')
        if health and health_ids:
            # Áp dụng cho cả nhánh truy hồi, fuzzy, gợi ý nguyên liệu và nút phụ.
            if any(n['id_goc'] not in health_ids for n in result.get('nguon', [])):
                result = _empty(thong_bao_thieu(health))
            allowed_titles = chi_muc_cau_hoi(kho)
            result['goi_y'] = [title for title in result.get('goi_y', [])
                              if set(allowed_titles.get(khoa_cau_hoi(title), {})) & health_ids]
            if result['loai'] == 'khong_chac':
                result['cau_tra_loi'] = ('Mình tìm được các tài liệu cùng chủ đề sức khỏe dưới đây. Bạn chọn nội dung muốn xem nhé.'
                                        if result['goi_y'] else thong_bao_thieu(health))
                result['nhan_goi_y'] = 'Chọn tài liệu cùng chủ đề sức khỏe:'
        payload['result'] = result
        return payload

    def finish(payload):
        from backend.chatbot.doi_chieu import chi_muc_cau_hoi
        result, state, p = payload['result'], payload['state'], payload['parsed']
        kho = payload['kho']
        if result.get('chu_de'):
            state['mon_hien_tai'] = copy.deepcopy(result['chu_de'])
        if payload['choice'] and not result.get('chu_de'):
            state['mon_hien_tai'] = copy.deepcopy(payload['choice'])
        state['de_xuat'] = []
        for title in result.get('goi_y', []):
            rows = chi_muc_cau_hoi(kho).get(khoa_cau_hoi(title), {})
            if rows:
                d = next(iter(rows.values()))
                state['de_xuat'].append({'id_goc':d['id_goc'], 'cau_hoi':title, 'kho':kho})
        if state.get('khau_phan') and result['loai'] == 'tra_loi' and state.get('mon_hien_tai'):
            recipe = next((r for r in danh_muc(kho) if r.id_goc == state['mon_hien_tai']['id_goc']), None)
            if recipe:
                scaled = quy_doi_khau_phan(recipe, state['khau_phan'])
                if scaled and scaled['goc'] != scaled['dich']:
                    lines = [f"**Ước tính nguyên liệu cho {scaled['dich']} người** (nguồn gốc {scaled['goc']} người, hệ số {scaled['he_so']}):", *scaled['dong']]
                    if scaled['chua_quy_doi']:
                        lines += ['Các dòng chưa đủ định lượng để tự đổi:', *scaled['chua_quy_doi']]
                    lines.append('Không tự nhân thời gian nấu; gia vị và kích thước nguyên liệu cần điều chỉnh thực tế. Công thức gốc ở dưới để đối chiếu.')
                    result['cau_tra_loi'] = '\n\n'.join(lines)+'\n\n'+result['cau_tra_loi']
                elif not scaled:
                    result['cau_tra_loi'] = 'Nguồn chưa ghi rõ khẩu phần gốc nên mình chưa thể quy đổi định lượng chính xác.\n\n'+result['cau_tra_loi']
        result = chon_phan_hoi(result, payload['question'], p['intents'], payload['previous'].get('mau_phan_hoi'))
        state['can_lam_ro'] = result['loai'] == 'khong_chac'
        state['cau_hoi_can_lam_ro'] = payload['question'] if state['can_lam_ro'] else None
        state['mau_phan_hoi'] = result.get('mau_phan_hoi')
        result['trang_thai'] = state
        g = result.setdefault('giai_thich', {})
        from backend.chatbot.truy_hoi import nap_kho
        defaults = {'may_tim':nap_kho(kho)[2]['may_tim'], 'che_do_truy_hoi':'loc_cong_thuc',
                    'thoi_gian_giay':0.0, 'diem_cao_nhat':0.0, 'nguong_ngoai_pham_vi':None,
                    'nguong_tin_cay':None, 'cau_hoi_sach':p['cau_chuan'],
                    'cau_hoi_vao_mo_hinh':'', 'cau_hoi_viet_lai':None}
        for key,value in defaults.items():
            g.setdefault(key,value)
        g.update(framework='langchain', che_do_phan_hoi='trich_xuat_template', che_do_du_lieu=payload['mode'], intents=p['intents'], kho=kho)
        g['thoi_gian_giay'] = round(time.perf_counter()-payload['started'], 3)
        result['giai_thich'] = g
        if result.get('loai') in ('ngoai_pham_vi', 'khong_chac') or (g.get('diem_cao_nhat', 0) < 0.40 and not result.get('chu_de')):
            try:
                from backend.chatbot.tu_hoc import ghi_nhan_cau_hoi_cho_hoc
                ghi_nhan_cau_hoi_cho_hoc(payload['question'], result.get('loai', 'diem_thap'), g.get('diem_cao_nhat', 0), kho)
            except Exception:
                pass
        return result

    return RunnableLambda(prepare, name='nlp_va_trang_thai') | RunnableLambda(answer, name='chon_nguon_va_loc') | RunnableLambda(finish, name='response_selector')


def tra_loi_co_trang_thai(question, history=None, options=None):
    if not isinstance(question, str) or not question.strip():
        return _empty('Bạn nhập tên món hoặc nhu cầu ăn uống để mình tìm giúp nhé.')
    return chuoi_hoi_thoai().invoke({'question':question.strip(), 'history':history or [], 'options':options or {}}, config={'callbacks':[]})
