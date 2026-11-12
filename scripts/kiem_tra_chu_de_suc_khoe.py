"""Regression lỗi gợi ý lệch chủ đề sức khỏe, đọc kho thực tế không thêm đáp án."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend',choices=['faiss','neo4j'],default='faiss')
    args=parser.parse_args()
    import torch
    torch.set_num_threads(4)
    from backend.chatbot.cau_hinh import doc_cau_hinh
    from backend.chatbot.sinh_cau_tra_loi import tra_loi
    from backend.chatbot.suc_khoe import id_co_bang_chung
    ch=doc_cau_hinh()
    ch.update(kho_tim_kiem=args.backend,ghi_nhat_ky=False)
    ids=sorted(id_co_bang_chung(ch['kho_vector'],('tiểu đường',),True))
    rows=[]
    history=[]
    for q in ('bị tiểu đường thì nấu được món gì',
              'mình bị tiểu đường thì nấu ăn món nào được',
              'bi tieu duong thi nau duoc mon gi',
              'Gợi ý món ăn cho người đái tháo đường',
              'Tôi bị tiểu đường, có cá lóc thì nấu món nào?',
              'vậy nấu cho 3 người thì sao?'):
        r=tra_loi(q,history)
        # Với kho hiện tại chưa có tài liệu chuyên biệt: phải báo thiếu dữ liệu.
        passed=(not ids and r['loai']=='khong_chac' and not r['nguon'] and not r['goi_y']
                and 'tiểu đường' in r['cau_tra_loi'] and r['giai_thich']['may_tim']==args.backend)
        rows.append({'cau_hoi':q,'dat':passed,'backend':r['giai_thich']['may_tim'],
                     'tra_loi':r['cau_tra_loi'],'goi_y':r['goi_y'],'nguon':r['nguon']})
        history.append({'cau_hoi':q,'cau_tra_loi':r['cau_tra_loi'],'chu_de':r['chu_de'],'trang_thai':r['trang_thai']})
    output={'backend':args.backend,'id_chuyen_biet_tieu_duong':ids,'so_dat':sum(r['dat'] for r in rows),
            'so_ca':len(rows),'la_test_kin':False,'chi_tiet':rows}
    (ROOT/'reports'/f'sua_chu_de_suc_khoe_{args.backend}.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False,indent=2))
    return 0 if all(r['dat'] for r in rows) else 1


if __name__=='__main__':
    sys.exit(main())
