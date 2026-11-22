"""Build versioned offline knowledge in staging only; never promote production."""
import argparse
from collections import Counter
import csv
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import shutil
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CONFLICTS = {689, 799, 878, 906}
HEADER = ['ID', 'Nhóm', 'Tập', 'Câu hỏi', 'Câu trả lời', 'Nguồn']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f, delimiter=';'))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')


def write_csv(path, rows, fields=HEADER):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=';')
        writer.writeheader()
        writer.writerows(rows)


def protected_hashes():
    return {p.relative_to(ROOT).as_posix(): sha(p.read_bytes())
            for folder in ('data', 'kho_vector', 'cau_hinh', 'reports')
            for p in (ROOT / folder).rglob('*') if p.is_file()}


def culinary_excerpt(row):
    """Two explicitly inspected source spans, not a keyword-based medical rewrite."""
    assert int(row['ID']) in (214, 277)
    text = row['Câu trả lời']
    start = text.index('Nguyên liệu cần chuẩn bị')
    end = text.find('\n\n', text.index('Hoàn thành món ăn'))
    if end < 0:
        end = len(text)
    body = text[start:end]
    assert 'Sơ chế' in body and 'Cách chế biến' in body and 'Hoàn thành món ăn' in body
    assert body == text[start:end]
    return body, [start, end]


def export_candidates(destination):
    scopes = {int(r['id']): r for r in read_csv_comma(ROOT / 'audit/question_scope_review.csv')
              if r['record_role'] == 'ORIGINAL_QA'}
    original = []
    for path in sorted((ROOT / 'data/groups').glob('*/all.csv')):
        original.extend(dict(row, group_folder=path.parent.name) for row in read_csv(path))
    assert len(original) == 993 and {int(r['ID']) for r in original} == set(range(1, 994))
    assert len(scopes) == 993
    shutil.copytree(ROOT / 'data/groups', destination / 'archive/original_groups')
    shutil.copytree(ROOT / 'data/kiem_thu', destination / 'evaluation_only')
    shutil.copy2(ROOT / 'audit/question_scope_review.csv', destination / 'archive/question_scope_review.csv')
    for name in ('dataset.csv', 'dataset.jsonl'):
        shutil.copy2(ROOT / 'data/merged' / name, destination / ('archive/original_' + name))
    fixtures = []
    raw = ROOT / 'data/merged/dataset.jsonl'
    for number, line in enumerate(raw.read_text(encoding='utf-8').splitlines(), 1):
        row = json.loads(line)
        if (str(row.get('id')) == '2' and row.get('cau_hoi') == 'Cách nấu canh kiểm miền Tây'
                and row.get('cau_tra_loi') == 'Canh kiểm nấu với khoai lang, bí đỏ, nước cốt dừa.'
                and row.get('nguon') == 'Học chủ động (Active Learning)'):
            fixtures.append(dict(origin=raw.relative_to(ROOT).as_posix(), line=number, raw=line,
                                 raw_sha256=sha(line.encode()), reason='Exact legacy incremental-test fixture'))
    merged_csv = read_csv(ROOT / 'data/merged/dataset.csv')
    csv_fixtures = [(i, r) for i, r in enumerate(merged_csv, 1)
                    if r['ID'] == '2' and r['Câu hỏi'] == 'Cách nấu canh kiểm miền Tây'
                    and r['Câu trả lời'] == 'Canh kiểm nấu với khoai lang, bí đỏ, nước cốt dừa.'
                    and r['Nguồn'] == 'Học chủ động (Active Learning)']
    assert len(fixtures) == len(csv_fixtures) == 4
    assert len(merged_csv) == 997
    for fixture, (number, row) in zip(fixtures, csv_fixtures):
        fixture.update(csv_origin='data/merged/dataset.csv', csv_logical_record=number,
                       csv_fields=row, csv_fields_sha256=sha(json.dumps(row, sort_keys=True).encode()))
    write_jsonl(destination / 'archive/fixtures.jsonl', fixtures)
    master, ledger, active, review, nlp = [], [], [], [], []
    for row in sorted(original, key=lambda r: int(r['ID'])):
        idx = int(row['ID']); scope = scopes[idx]['classification']
        decision = 'ALLOW_CONVERSATION' if scope == 'CONVERSATIONAL' else ('ALLOW_UNVERIFIED_CANDIDATE' if scope == 'IN_SCOPE' else 'HOLD_REVIEW')
        body = row['Câu trả lời']; span = [0, len(body)]
        if idx in (214, 277):
            body, span = culinary_excerpt(row)
            decision = 'ALLOW_CULINARY_EXCERPT_UNVERIFIED'
        if idx in CONFLICTS:
            decision = 'HOLD_CONFLICT'
        allow = decision.startswith('ALLOW_')
        item = dict(id=idx, question=row['Câu hỏi'], group=row['Nhóm'], group_folder=row['group_folder'],
                    split=row['Tập'], scope=scope, decision=decision, source_verification='UNVERIFIED',
                    allowed_for_answer=allow, allowed_for_nlp_train=row['Tập'] == 'Train',
                    source=row['Nguồn'], original_answer_sha256=sha(row['Câu trả lời'].encode()),
                    allowed_span=span if allow else None, answer_text=body if allow else '',
                    answer_sha256=sha(body.encode()) if allow else '',
                    authorization_basis='User-authorized candidate/exact culinary span, not medical or source verification' if allow else 'Manual approval required')
        ledger.append(item)
        versions = [dict(origin='all.csv_candidate', raw=row)]
        if idx in CONFLICTS:
            folder = ROOT / 'data/groups' / row['group_folder']
            for split in ('train.csv', 'test.csv'):
                versions.extend(dict(origin=str(folder.relative_to(ROOT) / split), raw=r)
                                for r in read_csv(folder / split) if int(r['ID']) == idx)
            for line in (ROOT / 'data/merged/dataset.jsonl').read_text(encoding='utf-8').splitlines():
                r = json.loads(line)
                if int(r['id']) == idx:
                    versions.append(dict(origin='data/merged/dataset.jsonl', raw=r))
        master.append(dict(id=idx, immutable_split=row['Tập'], original=row, versions=versions,
                           selected_answer_version=None if idx in CONFLICTS else 'all.csv_candidate',
                           source_verification='UNVERIFIED'))
        if row['Tập'] == 'Train':
            nlp.append({k: row[k] for k in ('ID', 'Nhóm', 'Tập', 'Câu hỏi')})
        if allow:
            active.append(dict(id=idx, group=row['Nhóm'], group_folder=row['group_folder'], split=row['Tập'],
                               question=row['Câu hỏi'], answer=body, source=row['Nguồn']))
        else:
            review.append(item)
    write_jsonl(destination / 'master/records.jsonl', master)
    write_jsonl(destination / 'ledger.jsonl', ledger)
    write_jsonl(destination / 'review_queue.jsonl', review)
    write_jsonl(destination / 'merged/dataset.jsonl', active)
    csv_rows = [{'ID': r['id'], 'Nhóm': r['group'], 'Tập': r['split'], 'Câu hỏi': r['question'],
                 'Câu trả lời': r['answer'], 'Nguồn': r['source']} for r in active]
    write_csv(destination / 'merged/dataset.csv', csv_rows)
    write_csv(destination / 'nlp_train.csv', nlp, ['ID', 'Nhóm', 'Tập', 'Câu hỏi'])
    assert len(active) == 832 and sum(r['id'] == 2 for r in active) == 1
    assert len(nlp) == 795 and all(r['Tập'] == 'Train' for r in nlp)
    return original, ledger, active


def read_csv_comma(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def build(build_id, fail_at=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', build_id):
        raise ValueError('Invalid build ID')
    destination = ROOT / 'staging' / build_id
    destination.mkdir(parents=True, exist_ok=False)
    before = protected_hashes()
    try:
        original, ledger, active = export_candidates(destination)
        if fail_at == 'after_export':
            raise RuntimeError('Injected build failure; production untouched')
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
        import torch
        torch.set_num_threads(4)
        import faiss
        import numpy as np
        from backend.chatbot.mo_hinh_vector import nap_mo_hinh
        from scripts import tach_doan as chunks
        from transformers import AutoTokenizer
        chunks.nap_tokenizer = lambda name: AutoTokenizer.from_pretrained(name, local_files_only=True)
        bd = chunks.BoDem(); counter = Counter(); docs = []
        for row in active:
            source = dict(zip(HEADER, [row['id'], row['group'], row['split'], row['question'], row['answer'], row['source']]))
            cap = chunks.CapHoiDap(source, row['group_folder'], bd, counter)
            parts = chunks.tao_ban_ghi(cap, 'cau_truc', chunks.CAT['cau_truc'](cap))
            for part in parts:
                part['build_id'] = build_id
                part['content_version'] = sha(row['answer'].encode())
                n = len(bd.tok.encode(part['noi_dung_kem_tieu_de_tach_tu'], truncation=False))
                if n > 256:
                    raise ValueError('Chunk exceeds tokenizer limit: ' + part['chunk_id'])
                part['so_token'] = n
            assert re.sub(r'\s+', '', cap.tl) == re.sub(r'\s+', '', '\n'.join(p['noi_dung'] for p in parts))
            docs.extend(parts)
        assert len({r['chunk_id'] for r in docs}) == len(docs)
        write_jsonl(destination / 'doan/doan_cau_truc.jsonl', docs)
        model = nap_mo_hinh()
        vectors = model.encode([r['noi_dung_kem_tieu_de_tach_tu'] for r in docs], batch_size=32,
                               normalize_embeddings=True, show_progress_bar=False).astype('float32')
        stores = []
        for name, mask in [('answer_all', [True]*len(docs)), ('answer_Train', [d['tap']=='Train' for d in docs])]:
            chosen = [r for r, keep in zip(docs, mask) if keep]
            matrix = np.ascontiguousarray(vectors[np.array(mask)])
            index = faiss.IndexFlatIP(matrix.shape[1]); index.add(matrix)
            folder = destination / 'kho_vector' / name; folder.mkdir(parents=True)
            (folder / 'index.faiss').write_bytes(faiss.serialize_index(index).tobytes())
            write_jsonl(folder / 'sieu_du_lieu.jsonl', chosen)
            write_json(folder / 'thong_tin.json', dict(build_id=build_id, may_tim='faiss', so_doan=len(chosen),
                        so_chieu=index.d, ten_mo_hinh=chunks.CH['ten_mo_hinh'], tap='Train' if name.endswith('Train') else 'tat_ca'))
            loaded = faiss.deserialize_index(np.frombuffer((folder/'index.faiss').read_bytes(), dtype=np.uint8))
            assert loaded.ntotal == len(chosen) and loaded.d == 768
            restored = np.vstack([loaded.reconstruct(i) for i in range(loaded.ntotal)])
            assert np.array_equal(restored, matrix)
            assert np.isfinite(matrix).all() and np.allclose(np.linalg.norm(matrix, axis=1), 1, atol=1e-5)
            write_json(folder/'ordered_chunks.json', [dict(chunk_id=r['chunk_id'], text_sha256=sha(r['noi_dung_kem_tieu_de_tach_tu'].encode())) for r in chosen])
            stores.append(dict(name=name, vectors=loaded.ntotal, unique_ids=len({r['id_goc'] for r in chosen}), dimension=loaded.d))
        assert protected_hashes() == before
        recipe_ids = {r['id'] for r in active if re.search(r'(?im)^Nguyên liệu cần chuẩn bị', r['answer'])}
        validation = dict(original_records=993, archived_fixtures=4, allowed_records=len(active),
                          conversation_records=40, held_records=sum(not r['allowed_for_answer'] for r in ledger),
                          source_verified_records=0, culinary_excerpts=[214,277], recipe_ids=sorted(recipe_ids),
                          western_ids_preserved=list(range(41,191)), stores=stores, max_tokens=max(r['so_token'] for r in docs),
                          protected_unchanged=True, sealed_test_optimized=False, status='STRUCTURAL_BUILD_PASS')
        write_json(destination/'validation.json', validation)
        write_json(destination/'input_sha256.json', before)
        write_json(destination/'build_log.json', dict(build_id=build_id, time_utc=datetime.now(timezone.utc).isoformat(),
                   changes=['Excluded exactly four test fixtures from active export', 'Held conflict versions', 'Extracted exact culinary spans for214/277'], promoted=False))
        code_paths = [p for folder in ['backend','scripts','frontend'] for p in (ROOT/folder).rglob('*.py')]
        code_hashes = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in code_paths}
        write_json(destination/'code_sha256.json', code_hashes)
        model_name = chunks.CH['ten_mo_hinh']
        cache = Path.home()/'.cache/huggingface/hub'/('models--'+model_name.replace('/','--'))
        revision = (cache/'refs/main').read_text().strip()
        model_hashes = {p.relative_to(cache/'snapshots'/revision).as_posix(): sha(p.read_bytes())
                        for p in (cache/'snapshots'/revision).rglob('*') if p.is_file()}
        artifacts = {p.relative_to(destination).as_posix(): sha(p.read_bytes()) for p in destination.rglob('*') if p.is_file()}
        write_json(destination/'manifest.json', dict(build_id=build_id, status='VALIDATED_NOT_PROMOTED',
                   artifacts=artifacts, model=model_name, model_revision=revision, model_files=model_hashes,
                   tokenizer_revision=revision, max_tokens=256, configuration=chunks.CH,
                   dictionary_sha256=sha((ROOT/'cau_hinh/tu_dien_rieng.txt').read_bytes()),
                   dependencies={n:version(n) for n in ['torch','transformers','sentence-transformers','faiss-cpu','langchain-core','numpy']},
                   classification_source_sha256=sha((ROOT/'audit/question_scope_review.csv').read_bytes()),
                   source_verification='UNVERIFIED', production_promoted=False))
        return destination, validation
    except BaseException as exc:
        write_json(destination/'FAILED.json', dict(error=repr(exc), protected_unchanged=protected_hashes()==before,
                                                  production_promoted=False, rollback='No production pointer was changed; failed artifacts retained'))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--build-id', required=True); p.add_argument('--fail-at', choices=['after_export'])
    args = p.parse_args()
    folder, result = build(args.build_id, args.fail_at)
    print(json.dumps(dict(path=str(folder),validation=result), ensure_ascii=True))
