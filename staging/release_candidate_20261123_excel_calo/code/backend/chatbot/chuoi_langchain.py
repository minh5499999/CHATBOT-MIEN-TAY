"""LCEL chain chạy trong tiến trình Python; không endpoint hay cloud tracing."""
import os
import copy
import json
from functools import lru_cache

# Tắt cả tên biến cũ lẫn mới, kể cả khi môi trường máy đã bật tracing.
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from backend.chatbot.ngon_ngu import mo_rong_keyword


def _scoped_options(options):
    from backend.chatbot.che_do_du_lieu import chon_kho

    kho, mode = chon_kho(options)
    return {**options,'kho':kho,'che_do_du_lieu':mode}


@lru_cache(maxsize=1)
def chuoi_truy_hoi():
    from backend.chatbot.truy_hoi import truy_hoi

    def chuan_bi(state):
        return {**state, "truy_van": mo_rong_keyword(state["cau_hoi"])}

    def tim(state):
        from backend.chatbot.doi_chieu import doi_chieu_cau_goc, chi_muc_cau_hoi, chi_muc_ten_mon, ten_mon_tu_cau_hoi
        from backend.chatbot.ngon_ngu import khoa_cau_hoi
        from backend.chatbot.cau_hinh import doc_cau_hinh
        from backend.chatbot.knowledge_policy import check_rows, policy
        from backend.chatbot.truy_hoi import nap_kho
        from backend.chatbot.y_dinh_an_uong import chon_cau_hoi_cung_y_dinh
        options = _scoped_options(state.get('tuy_chon', {}))
        kho = options['kho']
        options.pop('che_do_du_lieu')
        groups, splits = options.get('loc_nhom'), options.get('loc_tap')
        scoped = policy(kho) if splits else None
        ledger = scoped[1] if scoped else None

        def eligible(row):
            return ((not groups or row['nhom_folder'] in groups)
                    and (not splits or row['tap'] in splits)
                    and (ledger is None or ledger.get(row['id_goc'], {}).get('split') == row['tap']))

        question = state['cau_hoi']
        exact = chi_muc_cau_hoi(kho).get(khoa_cau_hoi(question), {})
        matches = {i:row for i,row in exact.items() if eligible(row)}
        if not matches:
            named = chi_muc_ten_mon(kho).get(ten_mon_tu_cau_hoi(question), {})
            matches = {i:row for i,row in named.items() if eligible(row)}
        matched_intent = False
        if not matches:
            _, metadata, _ = nap_kho(kho)
            matches = chon_cau_hoi_cung_y_dinh(question, [row for row in metadata if eligible(row)], groups)
            matched_intent = bool(matches)
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
        result = doi_chieu_cau_goc(result, question, groups)
        # Cross-checking can promote exact rows from the full store catalog.
        result['doan'] = [row for row in result['doan'] if eligible(row)]
        visible = {row['id_goc'] for row in result['doan']}
        for field in ('id_khop_chinh_xac','id_khop_ten_mon'):
            result[field] = [rid for rid in result[field] if rid in visible]
        check_rows(kho,result['doan'])
        result["documents"] = [Document(page_content=d["noi_dung"],
                                        metadata={k: v for k, v in d.items() if k != "noi_dung"})
                               for d in result["doan"]]
        return result

    return RunnableLambda(chuan_bi, name="chuan_hoa_keyword") | RunnableLambda(tim, name="truy_hoi_lai")


@lru_cache(maxsize=256)
def _ket_qua_truy_hoi(cau_hoi, tuy_chon_json, cau_hinh_json, phien_ban_kho):
    # Cache key includes the selected store, filters and validated build.
    return chuoi_truy_hoi().invoke({'cau_hoi': cau_hoi, 'tuy_chon': json.loads(tuy_chon_json)},
                                  config={'callbacks': []})


def truy_hoi_langchain(cau_hoi, **kwargs):
    from backend.chatbot.cau_hinh import doc_cau_hinh
    from backend.chatbot.knowledge_policy import digest, policy

    options = _scoped_options(kwargs)
    knowledge = policy(options['kho'])
    revision = digest(json.dumps(knowledge[0],sort_keys=True).encode('utf-8')) if knowledge else None
    result = _ket_qua_truy_hoi(cau_hoi,json.dumps(options,sort_keys=True,default=str),
                             json.dumps(doc_cau_hinh(),sort_keys=True),revision)
    # Tầng trả lời sắp xếp/lọc các đoạn. Mỗi lượt cần bản sao riêng để tránh
    # làm hỏng cache và làm điều kiện của người trước ảnh hưởng người sau.
    return copy.deepcopy(result)
