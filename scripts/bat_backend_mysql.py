"""Chi kich hoat MySQL sau khi moc doi chieu du lieu chuyen doi da ton tai."""
import json
from datetime import datetime
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from chuyen_sqlite_mysql import chuan_bi_ket_noi
    from backend.chatbot.co_so_du_lieu_mysql import ket_noi
    from dotenv import dotenv_values
    config=chuan_bi_ket_noi()
    with ket_noi() as con:
        marker=con.execute("SELECT gia_tri FROM cau_hinh_db WHERE khoa='chuyen_sqlite_mysql_v1'").fetchone()
        if not marker or not json.loads(marker[0]).get('doi_chieu_tat_ca_ban_ghi'):
            raise RuntimeError('Chua co doi chieu chuyen doi thanh cong; khong doi backend.')
        admin=con.execute("SELECT vai_tro,kich_hoat FROM nguoi_dung WHERE ten_dang_nhap=?",('baotram',)).fetchone()
        if not admin or admin['vai_tro']!='admin' or not admin['kich_hoat']:
            raise RuntimeError('Chua xac nhan quyen admin cua tai khoan duoc chi dinh.')
    env_path=ROOT/'.env'
    original=env_path.read_text(encoding='utf-8')
    backup=ROOT/'du_lieu_nguoi_dung/sao_luu_cau_hinh'
    backup.mkdir(exist_ok=True)
    (backup/('env_truoc_mysql_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.txt')).write_text(original,encoding='utf-8')
    updated=original
    for key,value in {**config,'TAI_KHOAN_BACKEND':'mysql'}.items():
        if not re.fullmatch(r'[A-Za-z0-9_.:-]+',value):
            raise ValueError('Gia tri staging khong hop le.')
        line=f'{key}={value}'
        pattern=r'(?m)^'+re.escape(key)+r'\s*=.*$'
        updated=re.sub(pattern,lambda _:line,updated) if re.search(pattern,updated) else updated.rstrip()+'\n'+line+'\n'
    # Ghi cung inode khi chatbot dang dung: tranh loi Windows khoa os.replace.
    env_path.write_text(updated,encoding='utf-8')
    if dotenv_values(env_path).get('TAI_KHOAN_BACKEND')!='mysql':
        raise RuntimeError('Chua xac nhan duoc cau hinh backend vua ghi.')
    print('Da kich hoat MySQL bep_mien_tay cho tai khoan, phien va lich su. Khong hien thong tin bi mat.')


if __name__=='__main__':
    main()
