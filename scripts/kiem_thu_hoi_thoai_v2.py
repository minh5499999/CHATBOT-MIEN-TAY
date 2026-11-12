"""Kiểm thử phát triển trên backend thật; không biến fallback thành kết quả Neo4j."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

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
    from backend.chatbot.cong_thuc import danh_muc
    from backend.chatbot.ngon_ngu import vi_pham, chuan_hoa
    doc_cau_hinh().update(kho_tim_kiem=args.backend,ghi_nhat_ky=False)
    rows=[]
    def check(q,predicate,history=None):
        started=time.perf_counter()
        r=tra_loi(q,history)
        try:
            passed=bool(predicate(r))
        except (KeyError,IndexError,TypeError):
            passed=False
        backend=r['giai_thich']['may_tim']
        rows.append({'cau_hoi':q,'dat':passed and backend==args.backend,
                     'backend_thuc_te':backend,'loai':r['loai'],
                     'nguon':[n['id_goc'] for n in r['nguon']], 'goi_y':r['goi_y'],
                     'intents':r['giai_thich']['intents'],
                     'giay':round(time.perf_counter()-started,4),
                     'cau_tra_loi':r['cau_tra_loi']})
        return r
    for q in ['Chỉ tui nấu thịt kho hột vịt.','Chi tui nau thit kho hot vit.',
              'Cách làm thịt kho trứng vịt?','Nấu thịt kho hột vịt sao cho ngon?',
              'Mình muốn làm thịt kho có trứng vịt.']:
        check(q,lambda r:r['loai']=='tra_loi' and r['nguon'][0]['id_goc']==59 and 'Trứng vịt 10 quả' in r['cau_tra_loi'])
    check('Cho tôi nguyên liệu và cách nấu canh chua cá lóc.',lambda r:
          r['nguon'][0]['id_goc']==41 and all(s in r['cau_tra_loi'] for s in ('Nguyên liệu','Sơ chế','Cách chế biến')))
    check('canh chua ca locc',lambda r:r['loai']=='khong_chac' and bool(r['goi_y']) and not r['nguon'])
    check('Gợi ý món dưới 400 kcal',lambda r:not r['nguon'] and 'chưa có bảng dưỡng chất' in r['cau_tra_loi'])
    check('Tôi chỉ có cá lóc, gợi ý món ăn',lambda r:not r['nguon'])
    def valid_time(r):
        recipes={x.id_goc:x for x in danh_muc(r['giai_thich']['kho'])}
        return bool(r['nguon']) and all(recipes[n['id_goc']].tong_phut<=30 and
               'chien' not in chuan_hoa(recipes[n['id_goc']].noi_dung) for n in r['nguon'])
    check('Gợi ý món không chiên trong 30 phút',valid_time)
    def valid_allergy(r):
        recipes={x.id_goc:x for x in danh_muc(r['giai_thich']['kho'])}
        dk=r['trang_thai']['dieu_kien']
        return bool(r['nguon']) and set(r['trang_thai']['di_ung'])=={'tôm','đậu phộng'} and all(
            not vi_pham(recipes[n['id_goc']].noi_dung,dk) for n in r['nguon'])
    check('Tôi dị ứng tôm và đậu phộng, gợi ý món ăn từ cá lóc',valid_allergy)
    history=[]
    def add(q,r):
        history.append({'cau_hoi':q,'cau_tra_loi':r['cau_tra_loi'],'chu_de':r['chu_de'],'trang_thai':r['trang_thai']})
    q='Gợi ý món ăn từ cá lóc.'
    r=check(q,lambda r:len(r['trang_thai']['de_xuat'])>=2,history)
    selected=r['trang_thai']['de_xuat'][1]['id_goc']
    add(q,r)
    q='Món thứ hai nấu sao?'
    r=check(q,lambda r:r['loai']=='tra_loi' and r['nguon'][0]['id_goc']==selected,history)
    add(q,r)
    q='Không dùng ớt nha.'
    r=check(q,lambda r:r['trang_thai']['mon_hien_tai']['id_goc']==selected and
            'ớt' in r['trang_thai']['dieu_kien']['loai_tru'] and not r['nguon'],history)
    add(q,r)
    q='Nấu cho 3 người thì sao?'
    check(q,lambda r:r['trang_thai']['khau_phan']==3 and r['trang_thai']['mon_hien_tai']['id_goc']==selected and not r['nguon'],history)
    latencies=[r['giay'] for r in rows]
    output={'backend_yeu_cau':args.backend,'backend_thuc_te':dict(Counter(r['backend_thuc_te'] for r in rows)),
            'la_test_kin':False,'so_luot':len(rows),'so_dat':sum(r['dat'] for r in rows),
            'do_tre_p50_giay':statistics.median(latencies),'do_tre_lon_nhat_giay':max(latencies),
            'sha256_ma_nguon':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'chatbot').glob('*.py')},
            'chi_tiet':rows}
    path=ROOT/'reports'/f'hoi_thoai_v2_{args.backend}.json'
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in output.items() if k not in ('chi_tiet','sha256_ma_nguon')},ensure_ascii=False,indent=2))
    return 0 if output['so_dat']==len(rows) else 1


if __name__=='__main__':
    sys.exit(main())
