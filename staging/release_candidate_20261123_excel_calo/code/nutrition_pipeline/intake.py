import hashlib,json,shutil
from pathlib import Path
from nutrition_import import intake
from offline_nutrition.trust import NutritionError,require
from offline_nutrition.engine import NUTRIENTS

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_new(p,value):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,default=str)

def import_draft(filename,incoming,queue,destination):
    """Reuse the existing importer; export only an unapproved engine-shaped bundle."""
    package,receipt=intake(filename,incoming,queue)
    bad=[dict(row=r['row_index'],issues=r['issues']) for r in package['records'] if r['issues']]
    bad += [dict(row=r['row_index'],issues=['MISSING_FOOD_IDENTITY']) for r in package['records'] if not isinstance(r['input_record'],dict) or not isinstance(r['input_record'].get('identity_key'),str) or not r['input_record']['identity_key'].strip()]
    if bad:return dict(status='BLOCKED',issues=bad,queue_file=str(receipt),dataset=None)
    destination=Path(destination);require(not destination.exists(),'OUTPUT_EXISTS','Never replace an existing draft')
    # Recheck all local source bytes before creating a bundle.
    incoming=Path(incoming).resolve();sources={}
    for item in package['records']:
        row=item['input_record'];p=(incoming/row['source_path']).resolve()
        require(p.is_relative_to(incoming) and sha(p)==row['source_sha256'],'EVIDENCE_DIGEST_MISMATCH','Source changed since intake')
        sources[row['source_sha256']]=p
    foods={}
    for item in package['records']:
        r=item['input_record']
        foods[r['food_id']]=dict(name=r['name'],identity_key=r['identity_key'],food_state=r['food_state'],dataset_version=r['dataset_version'],source_locator=r['source_locator'],reuse_basis=r['reuse_basis'],carbohydrate_basis=r['carbohydrate_basis'],energy_basis=r['energy_basis'],nutrients_per_100g={k:str(r[k]) for k in NUTRIENTS},citations=[dict(path='evidence/'+r['source_sha256']+'.txt',sha256=r['source_sha256'],passage=r['passage'],document_version=r['document_version'],collected_at=r['collected_at'])])
    dataset=dict(schema_version=1,basis_mass_g='100',foods=foods,status='IMPORTED_UNVERIFIED',approval_granted=False,input_sha256=package['input_sha256'])
    destination.mkdir(parents=True);(destination/'evidence').mkdir()
    for digest,p in sources.items():shutil.copyfile(p,destination/'evidence'/f'{digest}.txt')
    write_new(destination/'dataset.json',dataset)
    write_new(destination/'intake_receipt.json',dict(source_package_sha256=sha(receipt),input_sha256=package['input_sha256'],status='IMPORTED_UNVERIFIED',registry_modified=False))
    return dict(status='IMPORTED_UNVERIFIED',food_count=len(foods),queue_file=str(receipt),dataset=str(destination/'dataset.json'),approved=False)

def merge_drafts(datasets):
    """Conflicting identities/values/bases/provenance never select a newest winner."""
    foods={};conflicts=[]
    for dataset in datasets:
        require(dataset.get('schema_version')==1 and str(dataset.get('basis_mass_g'))=='100','DATASET_SCHEMA','Only normalized per100g drafts can merge')
        for fid,food in dataset.get('foods',{}).items():
            if fid in foods and foods[fid]!=food:conflicts.append(dict(food_id=fid,code='SOURCE_CONFLICT'))
            elif fid not in foods:foods[fid]=food
    if conflicts:return dict(status='BLOCKED',issues=conflicts,foods={})
    return dict(schema_version=1,basis_mass_g='100',status='IMPORTED_UNVERIFIED',approval_granted=False,foods=foods)
