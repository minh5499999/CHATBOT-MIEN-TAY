"""Export a standalone localhost demo from approved public project inputs only."""
import argparse
import csv
import io
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = 'release_candidate_20261116_p3d_v1'
BASE = f'staging/{BUILD}'
PARENT = 'staging/release_candidate_20261116_v5'
TOP = 'Bep-Mien-Tay-Demo'
EXCLUDED_QA_IDS = {689, 799, 878}
EXPECTED = '2672bba1efd9a11adb6969c0fd32a3b3d9e936c9edd30a7329818210d1358b1a'
BLOCKED_PARTS = {'.git','.venv','runtime','du_lieu_nguoi_dung','logs','backups','project_snapshots','__pycache__'}
SECRET_PATTERN = re.compile(rb'-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|\bhf_[A-Za-z0-9]{24,}\b|\bGOCSPX-[A-Za-z0-9_-]{16,}\b|\bsk-(?:proj-)?[A-Za-z0-9_-]{28,}\b')

LAUNCHER = r'''"""Entry for the sanitized localhost demo."""
from pathlib import Path
import os
import runpy

root = Path(__file__).resolve().parent
for key in tuple(os.environ):
    if key in {'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN', 'OPENAI_API_KEY', 'PYTHONPATH'} or key.startswith(('NEO4J_', 'MYSQL_', 'GOOGLE_', 'LANGSMITH_', 'LANGCHAIN_')):
        os.environ.pop(key, None)
for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY', 'PYTHON_DOTENV_DISABLED'):
    os.environ[key] = '1'
os.environ['LANGSMITH_TRACING'] = 'false'
os.environ['LANGCHAIN_TRACING_V2'] = 'false'
runpy.run_path(str(root/'staging/release_candidate_20261116_p3d_v1/code/app.py'), run_name='__main__')
'''

def sha(data):
    return hashlib.sha256(data).hexdigest()

def checked_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '\\' in name or ':' in name or '..' in path.parts:
        raise ValueError('Invalid archive path')
    for part in path.parts:
        key = part.casefold()
        if key in BLOCKED_PARTS or key.startswith(('.env','secrets.')) or key.endswith(('.db','.sqlite','.sqlite3','.db-wal','.db-shm','.sqlite3-wal','.sqlite3-shm','.zip','.pem','.key')):
            raise ValueError(f'Private or nested artifact excluded: {name}')

def source_bytes(name):
    checked_name(name)
    p = ROOT/name
    if p.resolve() != p.absolute() or not p.is_file():
        raise ValueError(f'Expected regular source file: {name}')
    data = p.read_bytes()
    if p.suffix.lower() in {'.py','.txt','.md','.json','.jsonl','.toml','.csv','.css','.svg'} and SECRET_PATTERN.search(data):
        raise ValueError(f'Possible embedded credential in {name}')
    return data

def json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2)+'\n').encode()

def apply_demo_scope(files, manifest):
    excluded_questions = set()
    for name in (f'{BASE}/ledger.jsonl', f'{BASE}/merged/dataset.jsonl', f'{PARENT}/ledger.jsonl'):
        kept = []
        removed = set()
        for line in files[name].splitlines(keepends=True):
            row = json.loads(line)
            if int(row['id']) in EXCLUDED_QA_IDS:
                removed.add(int(row['id']))
                excluded_questions.add(row['question'].strip().casefold())
            else:
                kept.append(line)
        if name.endswith('/ledger.jsonl') and removed != EXCLUDED_QA_IDS:
            raise ValueError(f'Unexpected scope rows in {name}')
        files[name] = b''.join(kept)

    name = f'{BASE}/nlp_train.csv'
    data = files[name]
    source = io.StringIO(data.decode('utf-8-sig'), newline='')
    output = io.StringIO(newline='')
    reader = csv.DictReader(source, delimiter=';')
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames, delimiter=';')
    writer.writeheader()
    writer.writerows(row for row in reader if int(row['ID']) not in EXCLUDED_QA_IDS)
    encoding = 'utf-8-sig' if data.startswith(b'\xef\xbb\xbf') else 'utf-8'
    files[name] = output.getvalue().encode(encoding)

    for group in ('answer_all', 'answer_Train'):
        name = f'{BASE}/kho_vector/{group}/sieu_du_lieu.jsonl'
        if any(int(json.loads(line)['id_goc']) in EXCLUDED_QA_IDS for line in files[name].splitlines()):
            raise ValueError(f'Excluded QA still indexed in {group}')

    parent_name = f'{PARENT}/manifest.json'
    parent = json.loads(files[parent_name])
    parent_digest = sha(files[parent_name])
    ledger_digest = sha(files[f'{PARENT}/ledger.jsonl'])
    parent['artifacts'] = {'ledger.jsonl': ledger_digest}
    parent['submission_parent_sha256'] = parent_digest
    files[parent_name] = json_bytes(parent)
    demo_parent_digest = sha(files[parent_name])
    freeze_name = f'{PARENT}/REVIEW_FROZEN.json'
    files[freeze_name] = json_bytes({'manifest_sha256': demo_parent_digest, 'status': 'LOCAL_SUBMISSION_DEMO'})

    name = f'{BASE}/nutrition_binding.json'
    binding = json.loads(files[name])
    if binding['parent_manifest_sha256'] != parent_digest:
        raise ValueError('Unexpected original nutrition parent')
    binding.update(parent_manifest_sha256=demo_parent_digest, ledger_sha256=ledger_digest)
    files[name] = json_bytes(binding)
    manifest['artifacts'] = {name: sha(files[f'{BASE}/{name}']) for name in manifest['artifacts']}

    for name, data in files.items():
        if PurePosixPath(name).suffix in {'.json', '.jsonl', '.csv', '.txt', '.md', '.py'}:
            contents = data.decode('utf-8-sig').casefold()
            if any(question and question in contents for question in excluded_questions):
                raise ValueError(f'Excluded question still present in {name}')


def add_demo_food_safety(files, manifest):
    prefix = f'{BASE}/code/backend/chatbot/'
    files[prefix+'demo_food_safety.py'] = source_bytes('scripts/demo_food_safety.py')
    patches = {
        'recipe_views_v5.py': (
            "    state['health_context_v5']=health['context']\n",
            "    from backend.chatbot.demo_food_safety import matches, response\n"
            "    if not (health['cure_question'] or health['health_need'] or health['context']['active'] "
            "or state.get('tinh_trang_suc_khoe')) and matches(payload['question']):\n"
            "        return response()\n",
        ),
        'knowledge_policy.py': (
            "    manifest, ledger = p\n    if manifest.get('nutrition_integration_version')",
            "    from backend.chatbot.demo_food_safety import REASON, response\n"
            "    if result.get('reason_code') == REASON:\n"
            "        return response(result)\n",
        ),
    }
    for filename, (anchor, addition) in patches.items():
        path = prefix+filename
        source = files[path].decode('utf-8').replace('\r\n', '\n')
        if source.count(anchor) != 1:
            raise ValueError(f'Unexpected runtime code in {filename}')
        first_line = anchor.index('\n') + 1
        files[path] = source.replace(anchor, anchor[:first_line]+addition+anchor[first_line:]).encode('utf-8')
    for name in (*patches, 'demo_food_safety.py'):
        rel = 'code/backend/chatbot/'+name
        manifest['artifacts'][rel] = sha(files[f'{BASE}/{rel}'])


def apply_demo_password_limit(files, manifest):
    replacements = {
        'code/backend/chatbot/tai_khoan_dich_vu.py': (
            (b'<=128:', b'<=64:', 2),
            ('8 đến 128'.encode(), '8 đến 64'.encode(), 2),
        ),
        'code/frontend/quan_tri.py': (
            ('8 đến 128'.encode(), '8 đến 64'.encode(), 1),
        ),
    }
    for name, changes in replacements.items():
        path = f'{BASE}/{name}'
        data = files[path]
        for old, new, count in changes:
            if data.count(old) != count:
                raise ValueError(f'Unexpected password policy in {name}')
            data = data.replace(old, new)
        files[path] = data
        manifest['artifacts'][name] = sha(data)


def build_payload():
    raw = source_bytes(f'{BASE}/manifest.json')
    if sha(raw)!=EXPECTED:
        raise ValueError('Unexpected staging manifest')
    manifest=json.loads(raw)
    if json.loads(source_bytes(f'{BASE}/REVIEW_FROZEN.json'))['manifest_sha256']!=EXPECTED:
        raise ValueError('Unexpected staging freeze')
    files={}
    for name in ('cau_hinh/chatbot.json','cau_hinh/tach_doan.json','cau_hinh/tu_dien_rieng.txt','scripts/tach_tu.py','.streamlit/config.toml','requirements.txt'):
        files[name]=source_bytes(name)
    for group in ('frontend/assets/admin','frontend/assets/login','static'):
        for path in sorted((ROOT/group).rglob('*')):
            if path.is_file() and path.suffix.lower() in {'.png','.svg','.css','.webp','.jpg','.jpeg'}:
                name=path.relative_to(ROOT).as_posix()
                files[name]=source_bytes(name)
    # Nutrition binding reads only these three immutable v5 files.
    for name in ('manifest.json','REVIEW_FROZEN.json','ledger.jsonl'):
        files[f'{PARENT}/{name}']=source_bytes(f'{PARENT}/{name}')
    keep={'ledger.jsonl','merged/dataset.jsonl','nlp_train.csv','nutrition_binding.json','nutrition_data/approval_registry.json','pipeline/reviewer_policy.json'}
    artifacts={}
    for name, digest in manifest['artifacts'].items():
        runtime_code=name.startswith('code/') and name.endswith('.py') and not PurePosixPath(name).name.startswith('test_')
        runtime_assets = name.startswith('code/frontend/assets/') and PurePosixPath(name).suffix.lower() in {'.png','.svg','.css','.webp','.jpg','.jpeg'}
        if name in keep or runtime_code or runtime_assets or name.startswith(('kho_vector/answer_all/','kho_vector/answer_Train/')):
            data=source_bytes(f'{BASE}/{name}')
            if sha(data)!=digest:
                raise ValueError(f'Candidate artifact changed: {name}')
            files[f'{BASE}/{name}']=data
            artifacts[name]=digest
    if not keep <= artifacts.keys():
        raise ValueError('Runtime input missing')
    # Freeze the demo's subset separately. Source manifests and working tree remain untouched.
    manifest['artifacts']=artifacts
    apply_demo_scope(files, manifest)
    add_demo_food_safety(files, manifest)
    apply_demo_password_limit(files, manifest)
    # The inventory is runtime data. Leave internal audit paths out of the submission.
    inventory_source = 'audit/v5_recipe_structure_inventory.jsonl'
    inventory_path = 'data/nutrition/recipe_structure_inventory.jsonl'
    files[inventory_path] = source_bytes(inventory_source)
    trust_path = 'code/offline_nutrition/trust.py'
    trust_code = files[f'{BASE}/{trust_path}']
    if trust_code.count(inventory_source.encode()) != 1:
        raise ValueError('Unexpected recipe inventory reference')
    trust_code = trust_code.replace(inventory_source.encode(), inventory_path.encode())
    files[f'{BASE}/{trust_path}'] = trust_code
    manifest['artifacts'][trust_path] = sha(trust_code)
    manifest['submission_parent_sha256']=EXPECTED
    files[f'{BASE}/manifest.json']=json_bytes(manifest)
    files[f'{BASE}/REVIEW_FROZEN.json']=json_bytes({'manifest_sha256':sha(files[f'{BASE}/manifest.json']), 'status':'LOCAL_SUBMISSION_DEMO'})
    files['app_demo.py']=LAUNCHER.encode()
    files['README.md']=source_bytes('HUONG_DAN_CHAY_DEMO.md')
    files['SHA256.json']=json_bytes({name:sha(data) for name,data in sorted(files.items())})
    return files

def verify(path):
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist()
        if len(names)!=len(set(n.casefold() for n in names)) or archive.testzip():
            raise ValueError('Duplicate entries or corrupt ZIP')
        if any(not n.startswith(TOP+'/') for n in names):
            raise ValueError('Unexpected archive root')
        for name in names:
            checked_name(name)
        recorded=json.loads(archive.read(TOP+'/SHA256.json'))
        if {TOP+'/'+n for n in recorded}|{TOP+'/SHA256.json'}!=set(names):
            raise ValueError('Unexpected archive entry')
        if any(sha(archive.read(TOP+'/'+n))!=h for n,h in recorded.items()):
            raise ValueError('Archive hash mismatch')
        return len(names)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('zip_path',type=Path)
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    if not args.verify:
        payload=build_payload()
        args.zip_path.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(args.zip_path,'x',zipfile.ZIP_DEFLATED) as archive:
            for name,data in sorted(payload.items()):
                archive.writestr(TOP+'/'+name,data)
    print(f'{verify(args.zip_path)} entries | SHA-256 {sha(args.zip_path.read_bytes())}')
