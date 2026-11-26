"""Export exact explicitly approved bytes; never select food identities or sign a review."""
import shutil
from pathlib import Path
from offline_nutrition.engine import PLAN_SCOPES,DATA_SCOPES
from offline_nutrition.trust import require
from nutrition_levels import A_SCOPES
from .review import ReviewQueue,local
from .intake import sha,write_new

def export_reviewed_bundle(review_root,entries,destination,*,math_fixtures=False):
    root=Path(review_root).resolve();queue=ReviewQueue(root)
    import json
    policy=json.loads((root/'reviewer_policy.json').read_text(encoding='utf-8'))
    scope='SYNTHETIC_MATH_TESTS' if math_fixtures else 'PRODUCTION'
    require(policy.get('scope')==scope,'REGISTRY_SCOPE_MISMATCH','Cannot export test approvals as real food')
    require(isinstance(entries,dict) and set(entries)=={'plans','datasets','evidence'},'EXPORT_SCHEMA','All three registry categories required')
    registry=dict(schema_version=1,scope=scope,plans={},datasets={},evidence={});copies=[]
    for kind,items in entries.items():
        require(isinstance(items,dict) and bool(items),'EXPORT_SCHEMA','No partial/empty production bundle')
        for target,subject in items.items():
            require(isinstance(target,str) and target.startswith(kind+'/') and ':' not in target and all(p not in ('','.','..') for p in target.split('/')),'INVALID_LOCAL_PATH','Export path must be category-relative')
            value,event=queue.approved(subject,{'source_text','reuse_rights'} if kind=='evidence' else DATA_SCOPES|{'reuse_rights'} if kind=='datasets' else {'recipe_mapping','mass','completeness'},parse_json=kind!='evidence')
            if kind=='plans':
                value,event=queue.approved(subject,A_SCOPES if value.get('calculation_level','B')=='A' else PLAN_SCOPES)
            entry=dict(sha256=sha(local(root,subject)),status='APPROVED',reviewed_by=event['actor'],reviewed_at=event['recorded_at'],review_scope=event['review_scope'],review_subject_path=subject)
            if kind=='plans':entry['recipe_id']=value['recipe_id']
            if kind=='evidence':entry['document_version']=event.get('document_version')
            registry[kind][target]=entry;copies.append((local(root,subject),target))
    destination=Path(destination);require(not destination.exists(),'OUTPUT_EXISTS','Use a new bundle/version')
    destination.mkdir(parents=True)
    for source,target in copies:
        p=destination/target;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,p)
    write_new(destination/'approval_registry.json',registry)
    # Assembly is not a nutrition test or publication. Existing engine validation
    # and manifest pinning are still mandatory before this bundle can be activated.
    return dict(status='REVIEWED_BYTES_EXPORTED_ENGINE_VALIDATION_REQUIRED',scope=scope,counts={k:len(v) for k,v in entries.items()},registry_sha256=sha(destination/'approval_registry.json'),activated=False)
