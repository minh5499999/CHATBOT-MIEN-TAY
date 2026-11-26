"""Opt-in, immutable staging knowledge policy. No production pointer is changed."""
import copy
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
from functools import lru_cache, wraps

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 'Nội dung này đang chờ kiểm duyệt hoặc thuộc phiên bản cũ. Mình chưa thể dùng làm lời khuyên. Bạn có thể chọn một công thức khác trong danh mục hiện tại.'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def active_build():
    value = os.environ.get('CHATBOT_STAGING_BUILD')
    if not value:
        return None
    p = Path(value)
    p = (ROOT / p).resolve() if not p.is_absolute() else p.resolve()
    if not p.is_relative_to((ROOT / 'staging').resolve()):
        raise ValueError('Staging must remain under project/staging')
    if not (p / 'manifest.json').is_file():
        raise ValueError('Missing validated staging manifest')
    return p


def build_for_store(store):
    p = (ROOT / store).resolve()
    active = active_build()
    if active and not p.is_relative_to(active):
        raise ValueError('Cannot mix staging and legacy knowledge stores')
    for parent in (p, *p.parents):
        if parent == ROOT:
            break
        if (parent / 'manifest.json').is_file() and parent.parent == ROOT / 'staging':
            return parent
    if active:
        raise ValueError('Staging store has no policy')
    # A partial/failed build must never fall back to legacy permissive behavior.
    if p.is_relative_to(ROOT / 'staging'):
        raise ValueError('Unvalidated staging build')
    return None


@lru_cache(maxsize=8)
def _load(build, manifest_hash):
    p = Path(build)
    manifest = json.loads((p / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['status'] != 'VALIDATED_NOT_PROMOTED':
        raise ValueError('Build failed validation')
    for name, expected in manifest['artifacts'].items():
        target = (p / name).resolve()
        if not target.is_relative_to(p) or digest(target.read_bytes()) != expected:
            raise ValueError('Build checksum mismatch: ' + name)
    rows = [json.loads(s) for s in (p / 'ledger.jsonl').read_text(encoding='utf-8').splitlines()]
    return manifest, {int(r['id']): r for r in rows}


def policy(store):
    build = build_for_store(store)
    if build is None:
        return None
    signature = digest((build / 'manifest.json').read_bytes())
    manifest, ledger = _load(str(build), signature)
    # Verify selected live artifacts before using an already-cached index/catalog.
    directory = (ROOT / store).resolve()
    for file in ('index.faiss', 'sieu_du_lieu.jsonl', 'thong_tin.json'):
        name = (directory / file).relative_to(build).as_posix()
        if name not in manifest['artifacts'] or digest((directory / file).read_bytes()) != manifest['artifacts'][name]:
            raise ValueError('Live staging artifact changed: ' + name)
    if digest((build / 'ledger.jsonl').read_bytes()) != manifest['artifacts']['ledger.jsonl']:
        raise ValueError('Staging ledger changed')
    return manifest, ledger


def store_cache(maxsize=8):
    """Authorize the store before every cache lookup, including warm legacy caches."""
    def decorate(function):
        cached = lru_cache(maxsize=maxsize)(function)
        @wraps(function)
        def guarded(store, *args, **kwargs):
            policy(store)
            return cached(store, *args, **kwargs)
        guarded.cache_clear = cached.cache_clear
        guarded.cache_info = cached.cache_info
        return guarded
    return decorate


def allowed(ledger, idx):
    return ledger.get(int(idx), {}).get('allowed_for_answer', False)


def check_rows(store, rows):
    p = policy(store)
    if not p:
        return
    manifest, ledger = p
    for row in rows:
        if not allowed(ledger, row['id_goc']) or row.get('build_id') != manifest['build_id']:
            raise ValueError('Unauthorized knowledge row')


def limited(result=None):
    r = copy.deepcopy(result or {})
    r.update(cau_tra_loi=LIMIT, loai='khong_chac', nguon=[], goi_y=[], doan_truy_hoi=[], chu_de=None)
    r.setdefault('giai_thich', {})['policy_blocked'] = True
    return r


def enforce_result(result, store):
    p = policy(store)
    if not p:
        return result
    manifest, ledger = p
    r = copy.deepcopy(result)
    ids = [n['id_goc'] for n in r.get('nguon', [])] + [d['id_goc'] for d in r.get('doan_truy_hoi', [])]
    topic = r.get('chu_de')
    if topic:
        ids.append(topic['id_goc'])
    if any(not allowed(ledger, i) for i in ids) or (r.get('loai') == 'tra_loi' and not r.get('nguon')):
        return limited(r)
    titles = {v['question'] for v in ledger.values() if v['allowed_for_answer']}
    r['goi_y'] = [q for q in r.get('goi_y', []) if q in titles]
    # Re-compose displayed text exclusively from authorized source spans. Never
    # trust free-form prose from a cache/branch, even when it names an allowed ID.
    source_ids = list(dict.fromkeys(int(n['id_goc']) for n in r.get('nguon', [])))
    if r.get('loai') == 'tra_loi':
        r['cau_tra_loi'] = ('Nội dung tham khảo trong bản staging; nguồn chưa được xác minh độc lập.\n\n'
                            + '\n\n'.join(ledger[i]['answer_text'] for i in source_ids))
    elif source_ids or r['goi_y']:
        r['cau_tra_loi'] = 'Bạn có thể chọn nội dung trong danh mục đang được phép sử dụng.'
    elif r.get('loai') == 'chao_hoi':
        conversations = {v['answer_text'] for v in ledger.values()
                         if v['allowed_for_answer'] and v['scope'] == 'CONVERSATIONAL'}
        if r.get('cau_tra_loi') not in conversations:
            r['cau_tra_loi'] = 'Mình là trợ lý nấu ăn. Bạn muốn xem công thức món nào?'
    else:
        r['cau_tra_loi'] = LIMIT
    r.setdefault('giai_thich', {})['knowledge_build_id'] = manifest['build_id']
    return r


@lru_cache(maxsize=8)
def _seal_key(build_id):
    return secrets.token_bytes(32)


def _body(result):
    # Seal everything rendered, not only answer IDs. Historical unsigned text is untrusted.
    return json.dumps({k: result.get(k) for k in ('cau_tra_loi', 'loai', 'nguon', 'goi_y', 'chu_de')},
                      sort_keys=True, ensure_ascii=False).encode('utf-8')


def seal_result(result, store):
    if not policy(store):
        return result
    r = enforce_result(result, store)
    build_id = policy(store)[0]['build_id']
    r['policy_build_id'] = build_id
    r['policy_seal'] = hmac.new(_seal_key(build_id), _body(r), hashlib.sha256).hexdigest()
    return r


def render_result(result, store):
    p = policy(store)
    if not p:
        return result
    build_id = p[0]['build_id']
    expected = hmac.new(_seal_key(build_id), _body(result), hashlib.sha256).hexdigest()
    if result.get('policy_build_id') != build_id or not hmac.compare_digest(result.get('policy_seal', ''), expected):
        return limited(result)
    return enforce_result(result, store)


def sanitize_history(history, store):
    p = policy(store)
    if not p:
        return history
    _, ledger = p
    clean = copy.deepcopy(history)
    for turn in clean:
        turn['cau_tra_loi'] = ''  # Never feed historical answer prose back into answer selection.
        if turn.get('chu_de') and not allowed(ledger, turn['chu_de']['id_goc']):
            turn['chu_de'] = None
        state = turn.get('trang_thai') or {}
        if state.get('mon_hien_tai') and not allowed(ledger, state['mon_hien_tai']['id_goc']):
            state['mon_hien_tai'] = None
        state['de_xuat'] = [x for x in state.get('de_xuat', []) if allowed(ledger, x['id_goc'])]
    return clean
