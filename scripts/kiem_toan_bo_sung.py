"""Bộ diễn đạt lại phát triển và hội thoại nối tiếp có sẵn, qua luồng trả lời thật.

Đã dùng nhiều lần để phát triển; không coi đây là Test kín chưa từng sử dụng.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def doc_tsv(name):
    with (ROOT/'data/kiem_thu'/name).open(encoding='utf-8') as stream:
        return list(csv.DictReader((x for x in stream if x.strip() and not x.startswith('#')), delimiter='\t'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=['faiss', 'neo4j'], default='faiss')
    args = parser.parse_args()
    import torch
    torch.set_num_threads(4)
    from backend.chatbot.cau_hinh import doc_cau_hinh
    from backend.chatbot.sinh_cau_tra_loi import tra_loi
    ch = doc_cau_hinh()
    ch.update(kho_tim_kiem=args.backend, ghi_nhat_ky=False)
    rows = []

    def record(kind, question, expected, history=None):
        r = tra_loi(question, history)
        ids = [d['id_goc'] for d in r['nguon']]
        from backend.chatbot.ngon_ngu import khoa_cau_hoi
        from backend.chatbot.doi_chieu import chi_muc_cau_hoi
        suggested = {i for q in r['goi_y'] for i in chi_muc_cau_hoi(r['giai_thich']['kho']).get(khoa_cau_hoi(q), {})}
        status = 'tra_loi_dung_id' if expected in ids else ('goi_y_dung' if expected in suggested else 'chua_dat')
        rows.append({'bo': kind, 'cau_hoi': question, 'id_mong_doi': expected, 'ket_qua': status,
                     'loai': r['loai'], 'nguon': ids, 'goi_y': r['goi_y'], 'may_tim': r['giai_thich']['may_tim']})
        return r

    for d in doc_tsv('dien_dat_lai.tsv'):
        record('dien_dat_lai_doc_lap', d['cau_hoi'], int(d['id_goc']))
    for d in doc_tsv('noi_tiep.tsv'):
        first = tra_loi(d['cau_truoc'], tuy_chon={})
        history = [{'cau_hoi': d['cau_truoc'], 'cau_tra_loi': first['cau_tra_loi'], 'chu_de': first['chu_de']}]
        record('noi_tiep', d['cau_noi_tiep'], int(d['id_goc']), history)
    from collections import Counter
    summary = {kind: dict(Counter(r['ket_qua'] for r in rows if r['bo'] == kind)) for kind in {r['bo'] for r in rows}}
    output = {'backend': args.backend, 'backend_thuc_te':dict(Counter(r['may_tim'] for r in rows)),
              'la_test_kin':False, 'so_luot': len(rows), 'tom_tat': summary, 'chi_tiet': rows}
    (ROOT/'reports'/f'kiem_toan_bo_sung_{args.backend}.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
