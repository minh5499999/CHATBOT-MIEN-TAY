"""Chuyển dữ liệu JSON sang SQLite, kiểm tra toàn vẹn và tùy chọn cấp admin đầu tiên."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admin',help='Tên tài khoản hiện có được chủ máy chỉ định làm admin đầu tiên.')
    args=parser.parse_args()
    from backend.chatbot.co_so_du_lieu import khoi_tao,ket_noi,FILE_DB,BACKEND
    if BACKEND!='sqlite':
        print('Cong cu SQLite cu khong dung khi backend tai khoan la MySQL. Dung scripts/kiem_tra_mysql.py.')
        return 1
    from backend.chatbot.tai_khoan_sqlite import khoi_tao_admin_cuc_bo
    khoi_tao()
    if args.admin:
        ok,message=khoi_tao_admin_cuc_bo(args.admin)
        print(message)
        if not ok:
            return 1
    with ket_noi() as con:
        integrity=con.execute('PRAGMA integrity_check').fetchone()[0]
        fk=con.execute('PRAGMA foreign_key_check').fetchall()
        counts={table:con.execute('SELECT count(*) FROM '+table).fetchone()[0]
                for table in ('nguoi_dung','phien','cuoc_tro_chuyen','tin_nhan','nhat_ky_quan_tri')}
        roles=dict(con.execute('SELECT vai_tro,count(*) FROM nguoi_dung GROUP BY vai_tro').fetchall())
        migration=json.loads(con.execute("SELECT gia_tri FROM cau_hinh_db WHERE khoa='chuyen_json_v1'").fetchone()[0])
    output={'database':str(FILE_DB.relative_to(ROOT)),'kiem_tra_toan_ven':integrity,
            'loi_khoa_ngoai':len(fk),'so_ban_ghi':counts,'vai_tro':roles,'chuyen_doi':migration}
    (ROOT/'reports/chuyen_tai_khoan_sqlite.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False,indent=2))
    return 0 if integrity=='ok' and not fk else 2


if __name__=='__main__':
    sys.exit(main())
