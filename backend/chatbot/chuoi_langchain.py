"""LCEL chain chạy trong tiến trình Python; không endpoint hay cloud tracing."""
import os
import copy
import json
from pathlib import Path
from functools import lru_cache

# Tắt cả tên biến cũ lẫn mới, kể cả khi môi trường máy đã bật tracing.
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from backend.chatbot.ngon_ngu import mo_rong_keyword


@lru_cache(maxsize=1)
def chuoi_truy_hoi():
    from backend.chatbot.truy_hoi import truy_hoi

    def chuan_bi(state):
        return {**state, "truy_van": mo_rong_keyword(state["cau_hoi"])}

    def tim(state):
        from backend.chatbot.doi_chieu import doi_chieu_cau_goc, chi_muc_cau_hoi, chi_muc_ten_mon, ten_mon_tu_cau_hoi
        from backend.chatbot.ngon_ngu import khoa_cau_hoi
        from backend.chatbot.cau_hinh import ROOT, doc_cau_hinh
        from backend.chatbot.truy_hoi import nap_kho, thu_muc_kho
        from backend.chatbot.y_dinh_an_uong import chon_cau_hoi_cung_y_dinh
        options = state.get('tuy_chon', {})
        kho = options.get('kho') or thu_muc_kho()
        kho_path = Path(kho)
        kho = kho_path.relative_to(ROOT).as_posix() if kho_path.is_absolute() else kho_path.as_posix()
        matches = chi_muc_cau_hoi(kho).get(khoa_cau_hoi(state['cau_hoi']), {})
        if not matches:
            matches = chi_muc_ten_mon(kho).get(ten_mon_tu_cau_hoi(state['cau_hoi']), {})
        matched_intent = False
        if not matches:
            _, metadata, _ = nap_kho(kho)
            matches = chon_cau_hoi_cung_y_dinh(state['cau_hoi'], metadata, options.get('loc_nhom'))
            matched_intent = bool(matches)
        if options.get('loc_nhom'):
            matches = {i:d for i,d in matches.items() if d['nhom_folder'] in options['loc_nhom']}
        if matches:
            index, _, info = nap_kho(kho)
            ch = doc_cau_hinh()
            mode = options.get('che_do') or ch['che_do_truy_hoi']
            thresholds = ch['nguong'][mode if mode in ('bm25', 'khong_dau') else 'vector']
            result = {'doan': [dict(d, diem=0.0, khop_y_dinh=matched_intent) for d in matches.values()],
                      'kho': kho, 'che_do_truy_hoi': mode, 'ngoai_pham_vi': False,
                      'diem_cao_nhat': 0.0, 'nguong': thresholds['ngoai_pham_vi'],
                      'nguong_tin_cay': thresholds['tin_cay'], 'cau_hoi_sach': state['truy_van'],
                      'cau_hoi_vao_mo_hinh': '(Khớp câu/tên món: không cần gọi mô hình embedding)',
                      'may_tim': getattr(index, 'may_tim', info['may_tim'])}
        else:
            result = truy_hoi(state["truy_van"], **options)
        result = doi_chieu_cau_goc(result, state['cau_hoi'], state.get('tuy_chon', {}).get('loc_nhom'))
        result["documents"] = [Document(page_content=d["noi_dung"],
                                        metadata={k: v for k, v in d.items() if k != "noi_dung"})
                               for d in result["doan"]]
        return result

    return RunnableLambda(chuan_bi, name="chuan_hoa_keyword") | RunnableLambda(tim, name="truy_hoi_lai")


@lru_cache(maxsize=256)
def _ket_qua_truy_hoi(cau_hoi, tuy_chon_json, cau_hinh_json):
    # Cấu hình tham gia khóa cache. Dữ liệu được nạp lại khi restart chatbot,
    # giống cache kho/vector hiện có. Không lưu lịch sử hay đáp án cá nhân.
    return chuoi_truy_hoi().invoke({'cau_hoi': cau_hoi, 'tuy_chon': json.loads(tuy_chon_json)},
                                  config={'callbacks': []})


def truy_hoi_langchain(cau_hoi, **kwargs):
    from backend.chatbot.cau_hinh import doc_cau_hinh
    result = _ket_qua_truy_hoi(cau_hoi, json.dumps(kwargs, sort_keys=True, default=str),
                             json.dumps(doc_cau_hinh(), sort_keys=True))
    # Tầng trả lời sắp xếp/lọc các đoạn. Mỗi lượt cần bản sao riêng để tránh
    # làm hỏng cache và làm điều kiện của người trước ảnh hưởng người sau.
    return copy.deepcopy(result)
