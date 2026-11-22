"""Probe real FAISS/model and Streamlit in a disposable copy; no production writes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from run_isolated_tests import ROOT, snapshot

GUARD = '''
import sys,ipaddress
def guard(event,args):
    if event=='socket.connect':
        address=args[1]
        if isinstance(address,tuple):
            try: allowed=ipaddress.ip_address(address[0]).is_loopback
            except ValueError: allowed=address[0]=='localhost'
            if not allowed: raise PermissionError('External network denied')
sys.addaudithook(guard)
'''


def main():
    before=snapshot(ROOT)
    output={}
    with tempfile.TemporaryDirectory(prefix='offline_probe_') as folder:
        root=Path(folder)/'project'
        shutil.copytree(ROOT,root,ignore=shutil.ignore_patterns('.venv','audit','.offline_wheels','__pycache__','.git'))
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false')
        code=GUARD+'''
import json
import torch
torch.set_num_threads(4)
from backend.chatbot.sinh_cau_tra_loi import tra_loi
from backend.chatbot.mo_hinh_vector import vector_cau_hoi
from backend.chatbot.truy_hoi import nap_kho
v,_,_=vector_cau_hoi('cách nấu canh chua cá lóc')
r=tra_loi('cách nấu canh chua cá lóc')
from streamlit.testing.v1 import AppTest
app=AppTest.from_file('app.py',default_timeout=60).run()
print(json.dumps(dict(vector_shape=list(v.shape),backend=nap_kho('kho_vector/cau_truc_tat_ca')[2]['may_tim'],answer_type=r['loai'],sources=len(r['nguon']),ui_exceptions=[str(e.value) for e in app.exception]),ensure_ascii=True))
'''
        p=subprocess.run([sys.executable,'-B','-X','utf8','-c',code],cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',timeout=180)
        output['integration']={'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
        # Explicit localhost server and HTTP health probe; no browser claim.
        code=GUARD+"\nimport runpy,sys\nsys.argv=['streamlit','run','app.py','--server.address','127.0.0.1','--server.port','18529','--server.headless','true']\nrunpy.run_module('streamlit',run_name='__main__')"
        with (root/'server.log').open('w',encoding='utf-8') as log:
            server=subprocess.Popen([sys.executable,'-B','-X','utf8','-c',code],cwd=root,env=env,stdout=log,stderr=log)
            try:
                for _ in range(40):
                    if server.poll() is not None:break
                    try:
                        with urllib.request.urlopen('http://127.0.0.1:18529/_stcore/health',timeout=1) as response:
                            output['localhost_health']={'status':response.status,'body':response.read().decode()};break
                    except OSError:time.sleep(.5)
            finally:
                server.terminate()
                server.wait(timeout=15)
        output['server_log']=(root/'server.log').read_text(encoding='utf-8')
    output['protected_unchanged']=before==snapshot(ROOT)
    (ROOT/'audit/offline_runtime_probe.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=True))
    assert output['protected_unchanged']


if __name__=='__main__':main()
