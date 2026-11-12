"""Chay regression/MySQL AppTest tren schema kiem thu, khong ghi vao production."""
import argparse
import json
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))


def main():
    from dotenv import dotenv_values
    config=dict(dotenv_values(ROOT/'du_lieu_nguoi_dung/mysql_ket_noi.env'))
    config['MYSQL_DATABASE']='bep_mien_tay_kiem_thu'
    os.environ.update(config)
    os.environ['CHAY_KIEM_THU_MYSQL']='1'
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_mysql_*.py')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    output={'database':'bep_mien_tay_kiem_thu','so_tests':result.testsRun,
            'bo_qua':len(result.skipped),'loi':len(result.errors),'that_bai':len(result.failures),
            'thanh_cong':result.wasSuccessful(),'ghi_production':False}
    (ROOT/'reports/kiem_thu_mysql.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    sys.exit(main())
