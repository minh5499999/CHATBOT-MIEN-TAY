"""Kiểm toán mọi câu gốc và biến thể qua luồng trả lời thật (không ghi log, không dùng mô hình sinh).

python scripts/kiem_toan_toan_bo.py --tag truoc --backend faiss
Không khẳng định nội dung dinh dưỡng đúng; đối chiếu ID và gợi ý với nhãn nguồn.
"""
import argparse
import hashlib
from collections import Counter
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', default='sau')
    parser.add_argument('--backend', choices=['faiss', 'neo4j'], default='faiss')
    parser.add_argument('--chi-goc', action='store_true')
    args = parser.parse_args()
    source_hashes = {name: hashlib.sha256((ROOT/'chatbot'/name).read_bytes()).hexdigest()
                     for name in ('ngon_ngu.py', 'doi_chieu.py', 'nhan_dien_mon.py', 'sinh_cau_tra_loi.py', 'chuoi_langchain.py',
                                  'hoi_thoai.py','intent.py','trang_thai.py','cong_thuc.py','fuzzy.py','phan_hoi.py','che_do_du_lieu.py')}
    import torch
    torch.set_num_threads(4)
    from backend.chatbot.cau_hinh import doc_cau_hinh
    from backend.chatbot.ngon_ngu import chuan_hoa, khoa_cau_hoi
    from backend.chatbot.doi_chieu import ten_mon_tu_cau_hoi
    from backend.chatbot.sinh_cau_tra_loi import tra_loi
    ch = doc_cau_hinh()
    ch.update(kho_tim_kiem=args.backend, ghi_nhat_ky=False)
    raw = [json.loads(s) for s in (ROOT/ch['kho_vector']/'sieu_du_lieu.jsonl').read_text(encoding='utf-8').splitlines()]
    by_id = {r['id_goc']: r for r in raw}
    title_ids = {}
    for r in by_id.values():
        title_ids.setdefault(khoa_cau_hoi(r['cau_hoi']), set()).add(r['id_goc'])
    cases = []
    for row in by_id.values():
        q = row['cau_hoi']
        expected = sorted(title_ids[khoa_cau_hoi(q)])
        cases.append(('goc', q, expected))
        if not args.chi_goc:
            cases.append(('khong_dau', chuan_hoa(q), expected))
            if row['nhom_folder'] != '01_chao_hoi':
                cases.append(('loi_dan', 'Bạn ơi, cho mình hỏi: '+q+' nhé', expected))
    # Nhãn kiểm thử vùng miền viết trước, đối chiếu với tên món trong kho.
    if not args.chi_goc:
        short_names = {}
        for r in by_id.values():
            if r['nhom_folder'] in ('02_huong_dan_nau_an', '03_huong_dan_nau_mon_mien_tay'):
                name = ten_mon_tu_cau_hoi(r['cau_hoi'])
                if 2 <= len(name.split()) <= 14:
                    short_names.setdefault(name, set()).add(r['id_goc'])
        for name, ids in sorted(short_names.items()):
            cases.append(('ten_mon_ngan', name, sorted(ids)))
            cases.append(('yeu_cau_cong_thuc', 'Mình muốn nấu '+name+' thì cần nguyên liệu và các bước?', sorted(ids)))
        for filename, label in [('ngoai_pham_vi.txt', 'ngoai_pham_vi'), ('khong_co_du_lieu.txt', 'khong_co_du_lieu')]:
            for line in (ROOT/'data/kiem_thu'/filename).read_text(encoding='utf-8').splitlines():
                if line.strip() and not line.startswith('#'):
                    cases.append((label, line.strip(), []))
        for question, terms in [
            ('thịt kho hột vịt', ('thit kho trung',)),
            ('thit kho hot vit', ('thit kho trung',)),
            ('chỉ mình làm thịt kho hột vịt với', ('thit kho trung',)),
            ('hướng dẫn tôi làm món thịt kho đi', ('thit kho',)),
            ('thịt kho', ('thit kho',)),
            ('cách nấu khổ qua nhồi thịt', ('kho qua nhoi',)),
            ('cách nấu mướp đắng nhồi thịt', ('kho qua nhoi',)),
            ('cách nấu đậu phụ sốt cà chua', ('dau hu sot ca', 'dau phu sot ca')),
        ]:
            expected = sorted(r['id_goc'] for r in by_id.values()
                              if any(t in chuan_hoa(r['cau_hoi']) for t in terms))
            if 'hột vịt' in question or 'hot vit' in question:
                expected = [59]  # Đã đối chiếu: công thức kho rệu có trứng vịt trong nguyên liệu.
            if expected:
                cases.append(('thu_cong', question, expected))
    records = []
    started = time.perf_counter()
    for i, (kind, q, expected) in enumerate(cases, 1):
        try:
            answer = tra_loi(q, tuy_chon={})
            source = [s['id_goc'] for s in answer['nguon']]
            suggestions = {idx for title in answer['goi_y'] for idx in title_ids.get(khoa_cau_hoi(title), ())}
            if kind in ('ngoai_pham_vi', 'khong_co_du_lieu'):
                status = 'tra_loi_khi_khong_co_dap_an' if answer['loai'] == 'tra_loi' else 'khong_tra_loi_bua'
            elif answer['loai'] == 'chao_hoi':
                status = 'xa_giao' if all(by_id[j]['nhom_folder'] == '01_chao_hoi' for j in expected) else 'sai'
            elif answer['loai'] == 'tra_loi':
                status = 'tra_loi_dung_id' if set(source) & set(expected) else 'tra_loi_sai_id'
            elif suggestions & set(expected):
                status = 'goi_y_dung'
            else:
                status = 'chua_giai_dap'
            records.append({'bo': kind, 'cau_hoi': q, 'id_mong_doi': expected, 'ket_qua': status,
                            'loai': answer['loai'], 'nguon_id': source, 'goi_y': answer['goi_y'],
                            'tra_loi': answer['cau_tra_loi'][:400]})
        except Exception as exc:
            records.append({'bo': kind, 'cau_hoi': q, 'id_mong_doi': expected,
                            'ket_qua': 'exception', 'loi': type(exc).__name__+': '+str(exc)})
        if i % 100 == 0:
            print(f'{i}/{len(cases)} | {time.perf_counter()-started:.1f}s', flush=True)
    summary = {kind: dict(Counter(r['ket_qua'] for r in records if r['bo'] == kind))
               for kind in sorted({r['bo'] for r in records})}
    output = {'so_cau_goc': len(by_id), 'so_luot': len(records), 'backend': args.backend,
              'ma_bam_ma_nguon': source_hashes,
              'giay': round(time.perf_counter()-started, 2), 'tom_tat': summary, 'chi_tiet': records,
              'gioi_han': 'Câu gốc có trong kho; biến thể tự sinh không phải đánh giá độc lập. Không thẩm định nội dung y khoa hoặc sinh tự do.'}
    report = ROOT/'reports'/f'kiem_toan_{args.tag}.json'
    report.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    print(report, flush=True)


if __name__ == '__main__':
    main()
