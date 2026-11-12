"""Backup MySQL bang mysqldump voi defaults-file rieng; khong de mat khau trong argv/log."""
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from backend.chatbot.co_so_du_lieu_mysql import cau_hinh
    config=cau_hinh()
    executable=shutil.which('mysqldump') or r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe'
    if not Path(executable).is_file():
        raise RuntimeError('Chua tim thay mysqldump. Cai MySQL client hoac them vao PATH.')
    folder=ROOT/'du_lieu_nguoi_dung/sao_luu_mysql'
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/('bep_mien_tay_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.sql')
    def quote(value):
        return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r')+'"'
    with tempfile.TemporaryDirectory(dir=ROOT/'du_lieu_nguoi_dung',prefix='mysql_backup_') as temp:
        defaults=Path(temp)/'client.cnf'
        defaults.write_text('[client]\n'+''.join(f'{k}={quote(v)}\n' for k,v in config.items() if k!='database'),encoding='utf-8')
        command=[executable,'--defaults-extra-file='+str(defaults),'--single-transaction','--no-tablespaces',
                 '--skip-lock-tables','--set-gtid-purged=OFF','--column-statistics=0','--databases',config['database']]
        with target.open('wb') as output:
            result=subprocess.run(command,stdout=output,stderr=subprocess.PIPE,check=False)
        if result.returncode:
            target.unlink(missing_ok=True)
            raise RuntimeError('mysqldump khong thanh cong; kiem tra dich vu MySQL va quyen backup.')
    print('Da sao luu MySQL: '+str(target.relative_to(ROOT)))


if __name__=='__main__':
    main()
