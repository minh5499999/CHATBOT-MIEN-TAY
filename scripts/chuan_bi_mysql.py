"""Chuan bi SQL rieng cho Workbench va cau hinh staging; khong in mat khau."""
import json
from pathlib import Path
import secrets
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    from dotenv import dotenv_values
    folder=ROOT/'du_lieu_nguoi_dung'
    folder.mkdir(exist_ok=True)
    config_file=folder/'mysql_ket_noi.env'
    if config_file.exists():
        config=dict(dotenv_values(config_file))
    else:
        config={'MYSQL_HOST':'127.0.0.1','MYSQL_PORT':'3306','MYSQL_USER':'bep_mien_tay_app',
                'MYSQL_PASSWORD':secrets.token_hex(24),'MYSQL_DATABASE':'bep_mien_tay'}
        config_file.write_text('\n'.join(f'{k}={v}' for k,v in config.items())+'\n',encoding='utf-8')
    ddl=(ROOT/'sql/bep_mien_tay.sql').read_text(encoding='utf-8')
    secret=config['MYSQL_PASSWORD']
    # Chi dung chuoi hex da sinh de khong chen gia tri SQL tu input nguoi dung.
    if not secret or any(c not in '0123456789abcdef' for c in secret):
        raise ValueError('Cau hinh staging khong phai mat khau duoc script sinh.')
    script=ddl+'\n'+ddl.replace('bep_mien_tay','bep_mien_tay_kiem_thu')
    script+=f"\nCREATE USER IF NOT EXISTS 'bep_mien_tay_app'@'127.0.0.1' IDENTIFIED BY '{secret}';\n"
    for name in ('bep_mien_tay','bep_mien_tay_kiem_thu'):
        script+=f"GRANT SELECT, INSERT, UPDATE, DELETE ON {name}.* TO 'bep_mien_tay_app'@'127.0.0.1';\n"
    script+='USE bep_mien_tay;\n'
    target=folder/'khoi_tao_mysql_rieng.sql'
    target.write_text(script,encoding='utf-8')
    print('SQL setup (chua thong tin ket noi rieng): '+str(target))
    print('Da chuan bi schema production/test va tai khoan chi co quyen du lieu tren hai schema nay.')


if __name__=='__main__':
    main()
