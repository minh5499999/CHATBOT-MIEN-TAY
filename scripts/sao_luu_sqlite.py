"""Sao lưu SQLite nhất quán kể cả khi đang dùng WAL; không in dữ liệu tài khoản."""
from datetime import datetime
from pathlib import Path
import sqlite3
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from backend.chatbot.co_so_du_lieu import FILE_DB
    folder=FILE_DB.parent/'sao_luu_sqlite'
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/('chatbot_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.sqlite3')
    dest=sqlite3.connect(target)
    try:
        source=sqlite3.connect(FILE_DB)
        try:
            source.backup(dest)
        finally:
            source.close()
        if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise RuntimeError('Bản sao không qua kiểm tra toàn vẹn.')
    finally:
        dest.close()
    print(f'Đã sao lưu SQLite và kiểm tra toàn vẹn: {target.relative_to(ROOT)}')


if __name__=='__main__':
    main()
