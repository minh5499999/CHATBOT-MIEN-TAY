"""Offline CSV/JSON review intake. Successful validation never means APPROVED."""
import argparse,csv,hashlib,io,json,re,unicodedata
from datetime import datetime,timezone
from pathlib import Path
from offline_nutrition.trust import read_json,NutritionError,require,iso_date
from offline_nutrition.engine import NUTRIENTS,STATES,number

REQUIRED=('food_id','name','food_state','basis_mass_g','dataset_version','source_path',
          'source_sha256','passage','document_version','collected_at','source_locator',
          'reuse_basis','carbohydrate_basis','energy_basis',*NUTRIENTS)
def normalized(s):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD',s.lower().replace('đ','d')) if unicodedata.category(c)!='Mn').split())

def intake(path,source_root,queue):
    """Append-only review package, no registry writes or automatic mapping."""
    path=Path(path).resolve();root=Path(source_root).resolve();queue=Path(queue).resolve()
    require(path.is_relative_to(root),'PATH_ESCAPE','Import must be inside incoming source root')
    raw=path.read_bytes();require(len(raw)<=8*1024*1024,'INPUT_TOO_LARGE','Use bounded imports')
    digest=hashlib.sha256(raw).hexdigest()
    if path.suffix.lower()=='.csv':
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        require(reader.fieldnames and len(reader.fieldnames)==len(set(reader.fieldnames)),'DUPLICATE_COLUMN','CSV columns must be unique')
        rows=list(reader)
    else:
        require(path.suffix.lower()=='.json','UNSUPPORTED_FORMAT','Only UTF-8 CSV/JSON intake supported; PDF requires reviewed extraction')
        rows=read_json(raw)
    require(isinstance(rows,list) and bool(rows),'IMPORT_SCHEMA','Nonempty record array required')
    ids=set();names={};results=[]
    for index,row in enumerate(rows):
        issues=[];evidence=None
        try:
            require(isinstance(row,dict),'IMPORT_SCHEMA','Record must be object')
            require(None not in row and all(row.get(k) is not None and str(row[k]).strip() for k in REQUIRED),'MISSING_FIELD','Missing explicit required fields; missing is not zero')
            require(re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}',str(row['food_id'])),'INVALID_FOOD_ID','Use traceable stable food ID')
            require(row['food_id'] not in ids,'DUPLICATE_FOOD_ID','Duplicate food ID')
            ids.add(row['food_id'])
            require(row['food_state'] in STATES,'FOOD_STATE_MISMATCH','State must be explicit')
            require(number(row['basis_mass_g'],'basis_mass_g',positive=True)==100,'UNSUPPORTED_NUTRIENT_BASIS','Only per100g accepted')
            require(row.get('energy_unit')=='kcal' and row.get('macro_unit')=='g' and row.get('sodium_unit')=='mg','NUTRIENT_UNIT_MISMATCH','Explicit kcal / g / mg units required')
            require(row['carbohydrate_basis'] in ('TOTAL','AVAILABLE','BY_DIFFERENCE') and row['energy_basis'] in ('METABOLIZABLE','GROSS','OTHER_REVIEWED'),'INCOMPATIBLE_NUTRIENT_BASES','Definitions required')
            for key in NUTRIENTS:number(row[key],key,code='INVALID_NUTRIENT_VALUE')
            name=row['source_path']
            require(isinstance(name,str) and ':' not in name and not name.startswith(('/','\\')) and all(s not in ('','.','..') for s in name.replace('\\','/').split('/')),'INVALID_LOCAL_PATH','Local relative evidence path required')
            source=(root/name).resolve();require(source.is_relative_to(root),'PATH_ESCAPE','Evidence escapes source root')
            data=source.read_bytes();require(len(data)<=8*1024*1024,'INPUT_TOO_LARGE','Evidence too large')
            require(hashlib.sha256(data).hexdigest()==row['source_sha256'],'EVIDENCE_DIGEST_MISMATCH','Source bytes differ')
            require(row['passage'] in data.decode('utf-8-sig'),'PASSAGE_NOT_FOUND','Exact source passage missing')
            iso_date(row['collected_at'],'collected_at')
            evidence=dict(sha256=row['source_sha256'],document_version=row['document_version'],passage=row['passage'],source_path=name)
            # Name/state collisions are review flags, never fuzzy merged into one food.
            key=normalized(str(row['name']))
            if key in names and names[key]!=(row['food_id'],row['food_state']):issues.append('AMBIGUOUS_NAME_OR_STATE')
            names[key]=(row['food_id'],row['food_state'])
        except NutritionError as exc:issues.append(exc.code)
        except (OSError,UnicodeError,TypeError,ValueError):issues.append('LOCAL_INPUT_INVALID')
        results.append(dict(row_index=index,input_record=row,status='NEEDS_REVIEW' if not issues else 'UNVERIFIED',issues=issues,evidence=evidence,approved=False))
    # Also flag the earlier side of a collision; no preferential first match.
    for item in results:
        row=item['input_record']
        if isinstance(row,dict) and isinstance(row.get('name'),str):
            peers=[r['input_record'] for r in results if isinstance(r['input_record'],dict) and normalized(str(r['input_record'].get('name','')))==normalized(row['name'])]
            if len({(str(r.get('food_id')),str(r.get('food_state'))) for r in peers})>1:
                if 'AMBIGUOUS_NAME_OR_STATE' not in item['issues']:item['issues'].append('AMBIGUOUS_NAME_OR_STATE')
                item['status']='UNVERIFIED'
    package=dict(schema_version=1,status='NEEDS_MANUAL_REVIEW',input_sha256=digest,
                 collected_at=datetime.now(timezone.utc).isoformat(),source_file=path.name,
                 records=results,approved_records=0,
                 review_instructions='Validate every value against local source/page, units, state, rights and scopes. Intake cannot approve or modify the release registry.')
    queue.mkdir(parents=True,exist_ok=True)
    target=queue/(digest+'.json')
    # Decimal JSON numbers retain exact spelling as strings.
    with target.open('x',encoding='utf-8') as f:json.dump(package,f,ensure_ascii=False,indent=2,default=str)
    return package,target

def main():
    p=argparse.ArgumentParser();p.add_argument('filename');a=p.parse_args()
    build=Path(__file__).resolve().parents[1]
    package,target=intake(build/'nutrition_sources/incoming'/a.filename,build/'nutrition_sources/incoming',build/'nutrition_sources/review_queue')
    print(json.dumps(dict(queue_file=str(target),records=len(package['records']),approved_records=0)))
if __name__=='__main__':main()
