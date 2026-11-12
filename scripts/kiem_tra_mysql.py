"""Kiem tra MySQL tai khoan: chi doc, khong hien mat khau/bam/ma phien."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staging',action='store_true')
    args=parser.parse_args()
    if args.staging:
        from chuyen_sqlite_mysql import chuan_bi_ket_noi
        chuan_bi_ket_noi()
    from backend.chatbot.co_so_du_lieu_mysql import ket_noi,cau_hinh
    from backend.chatbot.co_so_du_lieu import BACKEND
    with ket_noi() as con:
        info=con.execute('SELECT DATABASE() AS db,VERSION() AS version,CURRENT_USER() AS tai_khoan').fetchone()
        counts={name:con.execute('SELECT count(*) FROM '+name).fetchone()[0]
                for name in ('nguoi_dung','phien','cuoc_tro_chuyen','tin_nhan','nhat_ky_quan_tri','cau_hinh_db')}
        roles={r['vai_tro']:r['n'] for r in con.execute('SELECT vai_tro,count(*) AS n FROM nguoi_dung GROUP BY vai_tro')}
    report={'ket_noi':'thanh_cong','backend_cau_hinh':BACKEND,**dict(info),'so_ban_ghi':counts,'vai_tro':roles}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    (ROOT/'reports/kiem_tra_mysql.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
