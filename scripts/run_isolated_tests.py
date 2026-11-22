"""Run existing tests only in a disposable project copy, with write/network guards."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for name in ('data', 'kho_vector', 'cau_hinh', 'du_lieu_nguoi_dung', 'logs')
            for p in (root / name).rglob('*') if p.is_file()}


CHILD = r'''
import sys, os, socket, unittest, io, json, ipaddress
from pathlib import Path
root=Path.cwd().resolve()
def guard(event,args):
    paths=[]
    if event=='open':
        path,mode,flags=args
        if not isinstance(path,(str,bytes,os.PathLike)): return
        if (isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            paths=[path]
    elif event in ('os.remove','os.rmdir','os.mkdir','os.chmod'): paths=[args[0]]
    elif event in ('os.rename','os.link','os.symlink'): paths=list(args[:2])
    elif event in ('socket.connect','socket.getaddrinfo'):
        address=args[1] if event=='socket.connect' else args[0]
        host=address[0] if isinstance(address,tuple) else address
        try: allowed=ipaddress.ip_address(host).is_loopback
        except ValueError: allowed=host in ('localhost',None)
        if not allowed: raise PermissionError('TEST: external network denied')
    for path in paths:
        p=Path(os.fsdecode(path)).resolve()
        if not p.is_relative_to(root): raise PermissionError('TEST: write outside sandbox: '+str(p))
sys.addaudithook(guard)
class Result(unittest.TextTestResult):
    def __init__(self,*a,**k): super().__init__(*a,**k); self.passed=0
    def addSuccess(self,t): self.passed+=1; super().addSuccess(t)
result=unittest.TextTestRunner(stream=io.StringIO(),resultclass=Result).run(unittest.defaultTestLoader.discover('tests',pattern=sys.argv[1]))
print(json.dumps(dict(run=result.testsRun,passed=result.passed,failed=len(result.failures),error=len(result.errors),skipped=len(result.skipped),errors=[(str(t),s) for t,s in result.errors],failures=[(str(t),s) for t,s in result.failures],skips=[(str(t),s) for t,s in result.skipped]),ensure_ascii=True))
sys.exit(0 if result.wasSuccessful() else 1)
'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pattern',default='test_*.py')
    parser.add_argument('--report',default='audit/isolated_test_results.json')
    args=parser.parse_args()
    before=snapshot(ROOT)
    with tempfile.TemporaryDirectory(prefix='mien_tay_tests_') as folder:
        sandbox=Path(folder)/'project'
        shutil.copytree(ROOT,sandbox,ignore=shutil.ignore_patterns('.venv','.git','audit','__pycache__','.offline_wheels'))
        scratch=sandbox/'temp';scratch.mkdir()
        env=dict(os.environ,TMP=str(scratch),TEMP=str(scratch),PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false',CHAY_KIEM_THU_MYSQL='0')
        result=subprocess.run([sys.executable,'-B','-X','utf8','-c',CHILD,args.pattern],cwd=sandbox,env=env,capture_output=True,text=True,encoding='utf-8')
        after=snapshot(ROOT)
        output=dict(command=sys.argv,python=sys.executable,returncode=result.returncode,protected_unchanged=before==after,protected_files=len(before),stdout=result.stdout,stderr=result.stderr)
        try: output['results']=json.loads(result.stdout.strip().splitlines()[-1])
        except (ValueError,IndexError): pass
        (ROOT/args.report).write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in output.items() if k not in ('stdout','stderr','results')},ensure_ascii=True))
        if 'results' in output:print({k:v for k,v in output['results'].items() if k not in ('errors','failures','skips')})
        if before!=after: raise RuntimeError('Protected project files changed')
        return result.returncode


if __name__=='__main__':
    sys.exit(main())
