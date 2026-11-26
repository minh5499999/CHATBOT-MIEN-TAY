"""Read-only, digest-bound local inputs. An input's VERIFIED label grants nothing."""
import hashlib,json,re
from datetime import datetime
from pathlib import Path

class NutritionError(ValueError):
    def __init__(self,code,message,path=''):
        super().__init__(message);self.code=code;self.message=message;self.path=path
    def issue(self):return {'code':self.code,'message':self.message,'path':self.path}

def fail(code,message,path=''):raise NutritionError(code,message,path)
def digest(data):return hashlib.sha256(data).hexdigest()
def require(condition,code,message,path=''):
    if not condition:fail(code,message,path)
def pairs(items):
    result={}
    for key,value in items:
        require(key not in result,'JSON_DUPLICATE_KEY','Duplicate JSON key',key);result[key]=value
    return result
def read_json(data):
    from decimal import Decimal
    try:return json.loads(data.decode('utf-8-sig'),object_pairs_hook=pairs,parse_float=Decimal,parse_constant=lambda value:fail('NON_FINITE_NUMBER','Non-finite JSON number'))
    except (UnicodeError,json.JSONDecodeError) as exc:raise NutritionError('INVALID_JSON','Invalid UTF-8 JSON') from exc
def iso_date(value,path):
    require(isinstance(value,str) and bool(value.strip()),'MISSING_REVIEW_METADATA','Missing date',path)
    try:datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError as exc:raise NutritionError('INVALID_REVIEW_DATE','Invalid date',path) from exc

class TrustStore:
    """Policy hash is supplied by the release manifest, never by a submitted plan."""
    def __init__(self,root,expected_registry_sha256,*,math_fixtures=False):
        self.root=Path(root).resolve();self.expected=expected_registry_sha256;self.math_fixtures=math_fixtures
        self._registry()
    def _path(self,name):
        require(isinstance(name,str) and 0<len(name)<=240,'INVALID_LOCAL_PATH','Expected relative local path')
        name=name.replace('\\','/')
        require(':' not in name and not name.startswith('/') and all(p not in ('','..','.') for p in name.split('/')),'INVALID_LOCAL_PATH','Absolute paths, URIs and traversal are forbidden')
        p=(self.root/name).resolve()
        require(p.is_relative_to(self.root),'PATH_ESCAPE','Symlink/path escapes local input bundle')
        require(p.is_file(),'LOCAL_FILE_MISSING','Local evidence/input file missing',name)
        require(p.stat().st_size<=8*1024*1024,'INPUT_TOO_LARGE','Input exceeds local safety limit',name)
        return name,p
    def _registry(self):
        data=(self.root/'approval_registry.json').read_bytes()
        require(digest(data)==self.expected,'REGISTRY_CHANGED','Approval registry differs from pinned release')
        r=read_json(data)
        require(isinstance(r,dict) and r.get('schema_version')==1,'REGISTRY_SCHEMA','Invalid registry schema')
        scope='SYNTHETIC_MATH_TESTS' if self.math_fixtures else 'PRODUCTION'
        require(r.get('scope')==scope,'REGISTRY_SCOPE_MISMATCH','Math fixtures cannot authorize real-food calculations')
        for kind in ('plans','datasets','evidence'):
            require(isinstance(r.get(kind),dict),'REGISTRY_SCHEMA','Missing approval category',kind)
            require(all(isinstance(k,str) and isinstance(v,dict) for k,v in r[kind].items()),'REGISTRY_SCHEMA','Invalid approval entry',kind)
        return r
    def approved(self,kind,name,scopes):
        r=self._registry();name,p=self._path(name);approval=r[kind].get(name)
        require(isinstance(approval,dict) and approval.get('status')=='APPROVED','INPUT_NOT_APPROVED','No digest-bound review for input',name)
        raw=p.read_bytes();require(digest(raw)==approval.get('sha256'),'INPUT_DIGEST_MISMATCH','Reviewed input changed',name)
        require(isinstance(approval.get('reviewed_by'),str) and bool(approval['reviewed_by'].strip()),'MISSING_REVIEW_METADATA','Reviewer missing',name)
        iso_date(approval.get('reviewed_at'),name)
        review_scope=approval.get('review_scope')
        require(isinstance(review_scope,list) and all(isinstance(s,str) for s in review_scope),'REGISTRY_SCHEMA','Review scope must be a string list',name)
        require(set(scopes)<=set(review_scope),'INSUFFICIENT_REVIEW_SCOPE','Required review scope missing',name)
        return raw,approval
    def load(self,kind,name,scopes):
        raw,approval=self.approved(kind,name,scopes);value=read_json(raw)
        require(isinstance(value,dict),'INPUT_SCHEMA','Expected JSON object',name)
        return value,{'path':name,'sha256':digest(raw),'reviewed_by':approval['reviewed_by'],'reviewed_at':approval['reviewed_at'],'review_scope':list(approval['review_scope'])}
    def citations(self,entries,path):
        require(isinstance(entries,list) and bool(entries),'MISSING_EVIDENCE','Local evidence references required',path)
        checked=[]
        for i,ref in enumerate(entries):
            loc=f'{path}[{i}]';require(isinstance(ref,dict),'MISSING_EVIDENCE','Invalid evidence reference',loc)
            raw,approval=self.approved('evidence',ref.get('path'),{'source_text'})
            require(digest(raw)==ref.get('sha256'),'EVIDENCE_DIGEST_MISMATCH','Evidence reference changed',loc)
            require(isinstance(ref.get('document_version'),str) and ref['document_version']==approval.get('document_version'),'EVIDENCE_VERSION_MISMATCH','Evidence version not reviewed',loc)
            iso_date(ref.get('collected_at'),loc)
            try:text=raw.decode('utf-8-sig')
            except UnicodeError as exc:raise NutritionError('EVIDENCE_TEXT_REQUIRED','Provide reviewed local UTF-8 extract bound to original document',loc) from exc
            quote=ref.get('passage')
            require(isinstance(quote,str) and bool(quote.strip()) and quote in text,'PASSAGE_NOT_FOUND','Exact evidence passage not present',loc)
            checked.append({'path':ref['path'],'sha256':ref['sha256'],'document_version':ref['document_version'],'passage':quote,'collected_at':ref['collected_at']})
        return checked
    def plan_path(self,recipe_id):
        r=self._registry();paths=[]
        for name,entry in r['plans'].items():
            if entry.get('recipe_id')==recipe_id and entry.get('status')=='APPROVED':paths.append(name)
        require(len(paths)==1,'NO_APPROVED_RECIPE_PLAN' if not paths else 'AMBIGUOUS_APPROVED_PLAN','Exactly one reviewed recipe plan is required')
        return paths[0]

class KnowledgeCatalog:
    """Bind permitted recipe versions/components to immutable v5; never unlock held."""
    def __init__(self,project_root,binding):
        self.root=Path(project_root).resolve();self.binding=dict(binding);self._load()
    def _load(self):
        build=(self.root/self.binding['parent_build']).resolve()
        require(build.is_relative_to(self.root/'staging'),'INVALID_PARENT_BUILD','Parent must be in staging')
        raw=(build/'manifest.json').read_bytes()
        require(digest(raw)==self.binding['parent_manifest_sha256'],'PARENT_BUILD_CHANGED','Parent manifest differs from bound v5')
        frozen=read_json((build/'REVIEW_FROZEN.json').read_bytes())
        require(frozen.get('manifest_sha256')==digest(raw),'PARENT_NOT_FROZEN','Parent review freeze mismatch')
        raw=(build/'ledger.jsonl').read_bytes()
        require(digest(raw)==self.binding['ledger_sha256'],'PARENT_LEDGER_CHANGED','Bound knowledge ledger changed')
        self.rows={r['id']:r for r in (read_json(s) for s in raw.splitlines() if s.strip())}
        inventory=(self.root/'audit/v5_recipe_structure_inventory.jsonl').read_bytes()
        require(digest(inventory)==self.binding['inventory_sha256'],'SOURCE_INVENTORY_CHANGED','Bound recipe component inventory changed')
        self.recipes={r['recipe_id']:r for r in (read_json(s) for s in inventory.splitlines() if s.strip())}
    def recipe_ids(self):self._load();return sorted(self.recipes)
    def check(self,recipe_id,version=None):
        self._load()
        require(type(recipe_id) is int and recipe_id in self.rows,'UNKNOWN_RECIPE','Unknown recipe ID')
        row=self.rows[recipe_id]
        require(row.get('allowed_for_answer') is True,'HELD_RECIPE','Recipe/answer is held; nutrition cannot unlock it')
        require(recipe_id in self.recipes,'NOT_A_RECIPE','Record is not a recipe')
        if version is not None:require(version==row['answer_sha256'],'RECIPE_VERSION_MISMATCH','Plan uses a different recipe version')
        item=self.recipes[recipe_id]
        require(item['recipe_version']==row['answer_sha256'],'RECIPE_VERSION_MISMATCH','Inventory version mismatch')
        components={f"span:{x['source_span']['start']}:{x['source_span']['end']}" for x in item['ingredients']}
        return {'recipe_id':recipe_id,'recipe_version':row['answer_sha256'],'components':components,'source_verification':row['source_verification']}
