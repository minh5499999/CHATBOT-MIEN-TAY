"""Chuyen snapshot SQLite sang MySQL trong transaction; doi chieu tung ban ghi truoc khi commit."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TABLES=('cau_hinh_db','nguoi_dung','phien','cuoc_tro_chuyen','tin_nhan','nhat_ky_quan_tri')


def chuan_bi_ket_noi():
    from dotenv import dotenv_values
    config=dict(dotenv_values(ROOT/'du_lieu_nguoi_dung/mysql_ket_noi.env'))
    if config.get('MYSQL_DATABASE')!='bep_mien_tay':
        raise ValueError('Chi chuyen vao schema bep_mien_tay da chi dinh.')
    os.environ.update(config)
    return config


def chuyen():
    chuan_bi_ket_noi()
    from backend.chatbot.co_so_du_lieu_mysql import ket_noi
    source=ROOT/'du_lieu_nguoi_dung/chatbot.sqlite3'
    folder=source.parent/'sao_luu_sqlite'
    folder.mkdir(exist_ok=True)
    snapshot=folder/('truoc_mysql_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.sqlite3')
    original=sqlite3.connect(source)
    backup=sqlite3.connect(snapshot)
    try:
        original.backup(backup)
    finally:
        original.close()
        backup.close()
    snapshot_hash=hashlib.sha256(snapshot.read_bytes()).hexdigest()
    src=sqlite3.connect(snapshot)
    src.row_factory=sqlite3.Row
    payload={table:[dict(row) for row in src.execute('SELECT * FROM '+table)] for table in TABLES}
    src.close()
    def fingerprint(rows):
        return sorted(json.dumps(row,sort_keys=True,ensure_ascii=False) for row in rows)
    with ket_noi(ghi=True) as dst:
        marker=dst.execute("SELECT gia_tri FROM cau_hinh_db WHERE khoa='chuyen_sqlite_mysql_v1'").fetchone()
        if marker:
            previous=json.loads(marker[0])
            if previous.get('snapshot_sha256')==snapshot_hash:
                print('Snapshot nay da duoc chuyen; khong nhap trung.')
                return previous
            raise ValueError('MySQL da co moc chuyen SQLite. Khong ghi de du lieu dang dung.')
        if any(dst.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in TABLES):
            raise ValueError('Schema dich khong rong; da dung de bao toan du lieu hien co.')
        for table in TABLES:
            rows=payload[table]
            if rows:
                columns=list(rows[0])
                dst.executemany('INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',
                                [tuple(row[c] for c in columns) for row in rows])
        for table in TABLES:
            if fingerprint(payload[table])!=fingerprint([dict(row) for row in dst.execute('SELECT * FROM '+table).fetchall()]):
                raise ValueError('Doi chieu khong khop o bang '+table+'; rollback toan bo.')
        report={'database':'bep_mien_tay','backend':'mysql','doi_chieu_tat_ca_ban_ghi':True,
                'snapshot_sha256':snapshot_hash,'snapshot_sqlite':str(snapshot.relative_to(ROOT)),
                'so_ban_ghi':{table:len(rows) for table,rows in payload.items()},
                'vai_tro':{row['vai_tro']:row['so_luong'] for row in dst.execute('SELECT vai_tro,count(*) AS so_luong FROM nguoi_dung GROUP BY vai_tro')},
                'thoi_diem':datetime.now().isoformat(timespec='seconds')}
        dst.execute('INSERT INTO cau_hinh_db(khoa,gia_tri) VALUES (?,?)',('chuyen_sqlite_mysql_v1',json.dumps(report,ensure_ascii=False)))
    (ROOT/'reports/chuyen_mysql.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report


if __name__=='__main__':
    chuyen()
