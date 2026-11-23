"""Adapter DB-API MySQL cho dich vu tai khoan; tham so duoc bind boi PyMySQL."""
from contextlib import contextmanager
import hashlib
import os
import sqlite3

import pymysql
from backend.chatbot.cau_hinh import nap_env


def cau_hinh():
    nap_env()
    return {'host':os.environ.get('MYSQL_HOST','127.0.0.1'),
            'port':int(os.environ.get('MYSQL_PORT','3306')),
            'user':os.environ.get('MYSQL_USER','bep_mien_tay_app'),
            'password':os.environ.get('MYSQL_PASSWORD',''),
            'database':os.environ.get('MYSQL_DATABASE','bep_mien_tay')}


class Hang(dict):
    """Tuong thich sqlite3.Row: ho tro ca row['cot'] va row[0]."""
    def __getitem__(self,key):
        return tuple(self.values())[key] if isinstance(key,int) else super().__getitem__(key)


class KetQua:
    def __init__(self, rows=()):
        self._rows = [Hang(row) for row in rows]
        self._pos = 0

    def fetchone(self):
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return row

    def fetchall(self):
        rest = self._rows[self._pos:]
        self._pos = len(self._rows)
        return rest

    def __iter__(self):
        return iter(self.fetchall())


def doi_tham_so(sql):
    """Doi ? ngoai literal thanh %s; khong noi gia tri nguoi dung vao SQL."""
    result=[]
    quote=None
    escaped=False
    for char in sql:
        if quote:
            result.append('%%' if char=='%' else char)
            if escaped:
                escaped=False
            elif char=='\\':
                escaped=True
            elif char==quote:
                quote=None
        elif char in ("'",'"','`'):
            quote=char
            result.append(char)
        else:
            result.append('%s' if char=='?' else '%%' if char=='%' else char)
    return ''.join(result)


class KetNoi:
    def __init__(self,con):
        self.con=con

    def execute(self,sql,params=()):
        cursor=self.con.cursor()
        try:
            cursor.execute(doi_tham_so(sql),params)
            rows = cursor.fetchall() if cursor.description is not None else ()
            return KetQua(rows)
        except pymysql.IntegrityError as exc:
            raise sqlite3.IntegrityError('Vi pham rang buoc du lieu MySQL.') from exc
        finally:
            cursor.close()

    def executemany(self,sql,params):
        cursor=self.con.cursor()
        try:
            cursor.executemany(doi_tham_so(sql),params)
            rows = cursor.fetchall() if cursor.description is not None else ()
            return KetQua(rows)
        except pymysql.IntegrityError as exc:
            raise sqlite3.IntegrityError('Vi pham rang buoc du lieu MySQL.') from exc
        finally:
            cursor.close()


@contextmanager
def ket_noi(ghi=False):
    config=cau_hinh()
    try:
        con=pymysql.connect(**config,charset='utf8mb4',autocommit=False,
                            connect_timeout=5,read_timeout=15,write_timeout=15,
                            cursorclass=pymysql.cursors.DictCursor)
    except pymysql.MySQLError:
        raise RuntimeError('Không kết nối được database tài khoản MySQL. Kiểm tra dịch vụ MySQL và cấu hình MYSQL_*.') from None
    adapter=KetNoi(con)
    lock_name='bmt_auth_'+hashlib.sha256(config['database'].encode()).hexdigest()[:20]
    locked=False
    try:
        if ghi:
            # Tuong duong BEGIN IMMEDIATE cua SQLite: tranh hai admin cung
            # ha quyen va vo tinh de lai he thong khong con admin.
            locked=adapter.execute('SELECT GET_LOCK(?,10) AS da_khoa',(lock_name,)).fetchone()[0]==1
            if not locked:
                raise TimeoutError('Database đang có thao tác ghi khác. Bạn thử lại sau nhé.')
        con.begin()
        yield adapter
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        try:
            if locked:
                adapter.execute('SELECT RELEASE_LOCK(?)',(lock_name,))
        finally:
            con.close()
