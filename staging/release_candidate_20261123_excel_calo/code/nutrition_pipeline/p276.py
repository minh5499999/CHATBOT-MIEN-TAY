"""Local reviewer workflow for the single 276-A-FDC89 packet."""
import argparse
from getpass import getpass
from pathlib import Path
import json
import os
import shutil
import tempfile
from uuid import uuid4

from nutrition_levels import A_SCOPES, LevelEngine
from offline_nutrition.engine import DATA_SCOPES
from offline_nutrition.trust import KnowledgeCatalog, NutritionError, read_json, require
from .bundle import export_reviewed_bundle
from .intake import sha, write_new
from .review import ReviewQueue
from .runtime_trust import ActionBoundTrustStore

BUILD = Path(__file__).resolve().parents[2]
ROOT = BUILD.parents[1]
PACKET = 'p276'
EVIDENCE = {'usda.txt', 'recipe.txt'}
SCOPES = {'plan.json': A_SCOPES, 'dataset.json': DATA_SCOPES | {'reuse_rights'},
          **{name: {'source_text', 'reuse_rights'} for name in EVIDENCE}}
ALL_SCOPES = set().union(*SCOPES.values())
ENTRIES = {'plans': {'plans/plan.json': f'{PACKET}/plan.json'},
           'datasets': {'datasets/dataset.json': f'{PACKET}/dataset.json'},
           'evidence': {f'evidence/{name}': f'{PACKET}/{name}' for name in sorted(EVIDENCE)}}


def verified_build():
    manifest = read_json((BUILD/'manifest.json').read_bytes())
    require(sha(BUILD/'manifest.json') == read_json((BUILD/'REVIEW_FROZEN.json').read_bytes())['manifest_sha256'],
            'MANIFEST_CHANGED', 'Candidate freeze mismatch')
    for name, expected in manifest['artifacts'].items():
        path = (BUILD/name).resolve()
        require(path.is_relative_to(BUILD) and sha(path) == expected, 'ARTIFACT_CHANGED', name)
    return manifest


class DerivedCatalog:
    def __init__(self, base, path, expected):
        self.base, self.path, self.expected = base, Path(path), expected

    def check(self, recipe_id, version=None):
        if type(recipe_id) is not int or recipe_id != 276:
            return self.base.check(recipe_id, version)
        raw = self.path.read_bytes()
        require(sha(self.path) == self.expected, 'CONTRACT_CHANGED', 'Derived version changed')
        contract = read_json(raw)
        require(contract['schema_version'] == 1 and contract['recipe_id'] == 276
                and contract['version'] == '276-A-FDC89' and contract['level'] == 'A',
                'DERIVED_CONTRACT_INVALID', 'Wrong derived contract')
        base = self.base.check(recipe_id, contract['base_sha256'])
        require(version is None or version == self.expected, 'RECIPE_VERSION_MISMATCH', 'Wrong derived version')
        return {**base, 'recipe_version': self.expected, 'components': {contract['component_id']}}


def authorize(policy, reviewer, authenticate):
    require(policy.get('scope') == 'PRODUCTION' and ALL_SCOPES <= set(policy.get('reviewers', {}).get(reviewer, [])),
            'REVIEWER_NOT_AUTHORIZED', 'Reviewer ID is not assigned all packet scopes')
    profile = authenticate(reviewer)
    require(profile and profile.get('ten_dang_nhap') == reviewer and profile.get('vai_tro') == 'admin',
            'REVIEWER_NOT_AUTHORIZED', 'An active local admin account with this reviewer ID is required')


def review_root():
    return BUILD/'runtime/nutrition_review'


def packet_evidence(folder):
    plan = read_json((folder/PACKET/'plan.json').read_bytes())
    refs = plan['citations'] + plan['ingredients'][0]['citations']
    return [{**ref, 'path': f"{PACKET}/{Path(ref['path']).name}"} for ref in refs]


def authorize_local(reviewer):
    from backend.chatbot.tai_khoan_dich_vu import dang_nhap
    # Enrollment is a separate local maintainer action. This CLI cannot create one.
    policy_file = BUILD/'runtime/reviewer_enrollment.json'
    require(policy_file.is_file(), 'REVIEWER_NOT_AUTHORIZED', 'No maintainer-approved reviewer enrollment on this candidate')
    policy = read_json(policy_file.read_bytes())
    authorize(policy, reviewer, lambda name: dang_nhap(name, getpass('Mật khẩu tài khoản admin cục bộ: ')))
    return policy


def record(folder, policy, reviewer, action, reason):
    require(action in {'APPROVED','REJECTED'} and reason.strip(), 'REVIEW_SCHEMA', 'Choose a decision and give a reason')
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder/'decision.lock'
    with lock.open('x', encoding='utf8'):
        pass
    try:
        if not (folder/'reviewer_policy.json').exists():
            shutil.copytree(BUILD/'pipeline'/PACKET, folder/PACKET, dirs_exist_ok=True)
            write_new(folder/'reviewer_policy.json',policy)
        require(read_json((folder/'reviewer_policy.json').read_bytes())==policy,
                'REVIEW_POLICY_CHANGED','Existing packet is bound to its original enrollment')
        for path in (BUILD/'pipeline'/PACKET).iterdir():
            require(sha(path)==sha(folder/PACKET/path.name),'SUBJECT_CHANGED','Review subjects differ from the frozen candidate')
        queue=ReviewQueue(folder)
        refs=packet_evidence(folder)
        batch_id = uuid4().hex
        for name,scopes in SCOPES.items():
            path=f'{PACKET}/{name}'
            decision=dict(batch_id=batch_id,action=action,actor=reviewer,reason=reason,review_scope=sorted(scopes),
                          subject_path=path,subject_sha256=sha(folder/path),evidence_checks=refs)
            if name in EVIDENCE:
                decision['document_version']=next(r['document_version'] for r in refs if Path(r['path']).name==name)
            queue.record(decision)
    finally:
        lock.unlink()


def pins(folder):
    names=['reviewer_policy.json', *(p.relative_to(folder).as_posix() for p in sorted((folder/'review_events').glob('*.json')))]
    return {n:sha(folder/n) for n in names}


def activate(manifest):
    folder=review_root()
    require(not (folder/'decision.lock').exists(), 'REVIEW_IN_PROGRESS', 'Finish the decision first')
    queue=ReviewQueue(folder)
    events=queue.events()
    latest={e['subject_path']:e for e in events}
    packet_events=[latest.get(f'{PACKET}/{name}', {}) for name in SCOPES]
    require(all(e.get('action')=='APPROVED' and e.get('batch_id') for e in packet_events)
            and len({e['batch_id'] for e in packet_events})==1,
            'INPUT_NOT_APPROVED','A complete authorized approval is required for all packet subjects')
    target=BUILD.with_name(BUILD.name+'_active')
    require(not target.exists(),'OUTPUT_EXISTS','Activation writes a new candidate')
    with tempfile.TemporaryDirectory(prefix='p276_',dir=BUILD.parent) as temporary:
        dest=Path(temporary)/'build'
        shutil.copytree(BUILD,dest,ignore=shutil.ignore_patterns('runtime','__pycache__','*.pyc','nutrition_data'))
        review_pins=pins(folder)
        export_reviewed_bundle(folder,ENTRIES,dest/'nutrition_data')
        registry='nutrition_data/approval_registry.json'
        store=ActionBoundTrustStore(dest/'nutrition_data',sha(dest/registry),folder,review_pins)
        contract=f'pipeline/{PACKET}/contract.json'
        binding=read_json((dest/'nutrition_binding.json').read_bytes())
        catalog=DerivedCatalog(KnowledgeCatalog(ROOT,binding),dest/contract,manifest['artifacts'][contract])
        result=LevelEngine(catalog,store).calculate_level(store.plan_path(276),expected_recipe_id=276)
        require(result['status']=='CALCULATED_APPROVED_INPUT_ESTIMATE' and result['calculation_level']=='A',
                'ENGINE_VALIDATION_FAILED', str(result.get('issues')))
        require(review_pins==pins(folder),'REVIEW_ACTION_CHANGED','Review changed during validation')
        manifest.update(build_id=target.name, parent_manifest_sha256=sha(BUILD/'manifest.json'),
                        nutrition_review_directory=folder.relative_to(ROOT).as_posix(),
                        nutrition_review_pins=review_pins,
                        nutrition_enrollment_sha256=sha(BUILD/'runtime/reviewer_enrollment.json'),
                        nutrition_derived_active=True,
                        real_nutrition_status='LEVEL_A_ENGINE_VALIDATED_ID_276')
        for p in (dest/'nutrition_data').rglob('*'):
            if p.is_file():manifest['artifacts'][p.relative_to(dest).as_posix()]=sha(p)
        (dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
        (dest/'REVIEW_FROZEN.json').write_text(json.dumps(dict(manifest_sha256=sha(dest/'manifest.json'),
                   status='ENGINE_VALIDATED_NOT_PROMOTED')),encoding='utf8')
        dest.rename(target)
    return target


def main():
    parser=argparse.ArgumentParser(description='Review 276-A-FDC89 locally')
    parser.add_argument('command',choices=('show','approve','reject','activate'))
    parser.add_argument('--reviewer')
    args=parser.parse_args()
    manifest=verified_build()
    if args.command=='show':
        for name in ('contract.json','usda.txt','recipe.txt','dataset.json','plan.json'):
            print(f'--- {name} ---\n'+(BUILD/'pipeline'/PACKET/name).read_text(encoding='utf8'))
        print('Trạng thái candidate: '+manifest['real_nutrition_status'])
        return
    reviewer=(args.reviewer or '').strip().lower()
    os.environ['CHATBOT_STAGING_BUILD']=str(BUILD)
    policy=authorize_local(reviewer)
    if args.command=='activate':
        if input('Nhập ACTIVATE 276-A-FDC89 để tạo candidate mới: ')!='ACTIVATE 276-A-FDC89':
            return
        print(activate(manifest))
        return
    print('Phạm vi: '+', '.join(sorted(ALL_SCOPES)))
    print('Chỉ 276-A-FDC89, FDC 169975, ước tính nguyên liệu đầu vào cấp A.')
    phrase=args.command.upper()+' 276-A-FDC89 CAP-A'
    if input(f'Nhập {phrase} để xác nhận: ')!=phrase:
        return
    reason=input('Lý do quyết định sau khi đã kiểm tra các chứng cứ: ')
    record(review_root(),policy,reviewer,'APPROVED' if args.command=='approve' else 'REJECTED',reason)
    print('Đã ghi quyết định cục bộ. Lệnh approve không tự kích hoạt hoặc promote.')


if __name__=='__main__':
    try:
        main()
    except NutritionError as exc:
        raise SystemExit(f'{exc.code}: {exc.message}')
