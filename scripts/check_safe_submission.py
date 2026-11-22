"""Smoke test the actual ZIP after extracting it beside no project data."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import zipfile

from build_safe_submission import TOP, verify

WORKER = r'''
import ipaddress, json, os, socket, sys
from pathlib import Path
root = Path.cwd().resolve()
socket_events = []
def hook(event, args):
    if event == 'socket.connect':
        _, address = args
        if isinstance(address, tuple):
            if not ipaddress.ip_address(address[0]).is_loopback:
                raise PermissionError('External connections forbidden')
            socket_events.append('loopback')
    if event == 'socket.getaddrinfo' and args[0] not in (None, 'localhost', '127.0.0.1', '::1'):
        raise PermissionError('External name resolution forbidden')
    if event == 'open':
        path, _, flags = args
        if not isinstance(path, int) and isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
            if not Path(os.fsdecode(path)).resolve().is_relative_to(root):
                raise PermissionError('Write outside extracted demo')
sys.addaudithook(hook)
from streamlit.testing.v1 import AppTest
assert not list(root.rglob('*.sqlite3'))
assert not (root/'.env').exists()
app = AppTest.from_file(str(root/'app_demo.py'), default_timeout=120).run()
assert not app.exception
assert app.button(key='nut_google').disabled
for i, value in enumerate(('Demo Test', 'demo_check', 'TemporaryDemo!456', 'TemporaryDemo!456'), 2):
    app.text_input[i].set_value(value)
next(b for b in app.button if b.label=='Tạo tài khoản').click().run()
assert not app.exception and not app.error
app.button(key='dang_xuat').click().run()
app.text_input[0].set_value('demo_check')
app.text_input[1].set_value('TemporaryDemo!456')
next(b for b in app.button if b.label=='Đăng nhập').click().run()
assert not app.exception and not app.error, [str(x.value) for x in app.exception]
app.chat_input[0].set_value('Cách nấu canh chua cá lóc?').run()
assert not app.exception and not app.error
assert any('Nguyên liệu' in m.value for m in app.markdown)
if next(root.glob('staging/*/code/backend/chatbot/demo_food_safety.py'), None):
    for question in ('Dầu ăn dùng chiên đi chiên lại có hại không?', 'dau chien lai duoc may lan', 'Bảo quản dầu đã chiên thế nào?'):
        app.chat_input[0].set_value(question).run()
        assert not app.exception and not app.error
        bubbles = [m for m in app.chat_message if m.name == 'assistant']
        shown = bubbles[-1].markdown[0].value
        assert all(term in shown for term in ('Không có một số lần', 'lọc hết cặn', 'tủ lạnh', 'nổi bọt dai', 'ask.fsis.usda.gov', 'cfs.gov.hk')), shown
    app.chat_input[0].set_value('Dầu chiên lại có chữa ho không?').run()
    assert not app.exception and not app.error
    bubbles = [m for m in app.chat_message if m.name == 'assistant']
    assert 'lọc hết cặn' not in bubbles[-1].markdown[0].value
    print('Food-safety FAQ: three positive cases and one medical-boundary case passed')
if (root/'data/nutrition/recipe_structure_inventory.jsonl').is_file():
    from offline_nutrition import KnowledgeCatalog
    assert not (root/'audit').exists()
    binding = json.loads(next(root.glob('staging/*/nutrition_binding.json')).read_text(encoding='utf-8'))
    catalog = KnowledgeCatalog(root, binding)
    assert len(catalog.recipe_ids()) == 250
from backend.chatbot.co_so_du_lieu import FILE_DB, BACKEND
assert BACKEND=='sqlite' and FILE_DB.is_file() and FILE_DB.is_relative_to(root)
print(json.dumps({'sqlite_created_locally':True,'registered_and_logged_in':True,'recipe_answer_rendered':True,'google_disabled':True,'food_safety_faq':bool(next(root.glob('staging/*/code/backend/chatbot/demo_food_safety.py'), None)),'loopback_observed':bool(socket_events)}))
'''

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('zip_path',type=Path)
    args=parser.parse_args()
    count=verify(args.zip_path)
    with tempfile.TemporaryDirectory(prefix='bep_demo_verify_') as temp:
        root=Path(temp)/TOP
        with zipfile.ZipFile(args.zip_path) as archive:
            archive.extractall(temp)
        scratch=(root/'_test_temp').resolve()
        scratch.mkdir()
        env=dict(os.environ,TEMP=str(scratch),TMP=str(scratch),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        result=subprocess.run([sys.executable,'-B','-X','utf8','-c',WORKER],cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',timeout=200)
        if result.returncode:
            sys.stderr.write(result.stderr)
            sys.stderr.write(result.stdout)
            raise SystemExit(result.returncode)
        print(json.dumps({'zip_entries':count,**json.loads(result.stdout.strip().splitlines()[-1])}))
