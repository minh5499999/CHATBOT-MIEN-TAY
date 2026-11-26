"""Read-only nutrition adapter inside LCEL; deterministic final-gate recomputation."""
import json,re
from fractions import Fraction
from offline_nutrition import KnowledgeCatalog,TrustStore,NutritionError
from offline_nutrition.engine import blocked,NUTRIENTS,packed
from nutrition_levels import LevelEngine

PATTERN=r'\b(kcal|calo|calorie|nang luong|protein|lipid|carbohydrate|carb|natri|chat dam|dam(?! da\b)|chat beo|dinh duong|duong chat)\b'
MISSING='nguồn công thức và bảng năm dưỡng chất được duyệt; mapping đúng thực phẩm/trạng thái; khối lượng phần ăn được và quy đổi; gia vị/hỗn hợp; cơ sở khẩu phần; đối với cấp B cần thêm yield, dầu/nước dùng tiêu thụ và hệ số giữ lại'

METRICS = {
    'kcal': r'kcal|calo|calorie|nang luong',
    'protein_g': r'protein|chat dam|dam(?! da\b)',
    'lipid_g': r'lipid|chat beo',
    'carbohydrate_g': r'carbohydrate|carb',
    'sodium_mg': r'natri',
}
LABELS = dict(kcal='Năng lượng', protein_g='Protein', lipid_g='Chất béo',
              carbohydrate_g='Carbohydrate', sodium_mg='Natri')
COUNTS = dict(zip('mot hai ba bon nam sau bay tam chin muoi'.split(), range(1, 11)))
COUNT = r'(\d+|' + '|'.join(COUNTS) + r')'
PORTION = r'\b' + COUNT + r'\s*(?:khau phan|nguoi|phan)\b'
PER_SERVING = r'\b(?:moi (?:khau phan|phan|nguoi)|mot (?:khau phan|phan)|mot nguoi an)\b'
SOURCE = r'\b(?:nguon|con so|so lieu|tai lieu|can cu|lay tu dau|gia dinh|thieu|tinh lai|(?:truoc|sau) (?:khi )?(?:luoc|nau))\b'


def serving_count(match):
    raw = match[1]
    return int(raw) if raw.isdecimal() and len(raw) <= 3 else COUNTS.get(raw, 0)


def components(values, metric=None):
    keys = (metric,) if metric else NUTRIENTS
    return ', '.join(f"{LABELS[key]}: {values[key]['display']} {values[key]['unit']}" for key in keys)


def build_path(manifest):
    from backend.chatbot.knowledge_policy import ROOT
    return ROOT/'staging'/manifest['build_id']

def recipe_version(manifest, row):
    if row.get('id') == 276 and manifest.get('nutrition_derived_active'):
        return manifest['artifacts']['pipeline/p276/contract.json']
    return row['answer_sha256']


def engine(manifest):
    from backend.chatbot.knowledge_policy import ROOT,digest
    build=build_path(manifest)
    for name in ('nutrition_binding.json','nutrition_data/approval_registry.json'):
        if digest((build/name).read_bytes())!=manifest['artifacts'][name]:raise NutritionError('NUTRITION_BUNDLE_CHANGED','Pinned nutrition inputs changed')
    binding=json.loads((build/'nutrition_binding.json').read_text(encoding='utf-8'))
    if manifest.get('data_pipeline_version')==1:
        from nutrition_pipeline.runtime_trust import ActionBoundTrustStore
        pinned={name.removeprefix('pipeline/'):value for name,value in manifest['artifacts'].items() if name=='pipeline/reviewer_policy.json' or name.startswith('pipeline/review_events/')}
        review_root = build/'pipeline'
        if manifest.get('nutrition_derived_active'):
            review_root = (ROOT/manifest['nutrition_review_directory']).resolve()
            if not review_root.is_relative_to(ROOT/'staging') or (review_root/'decision.lock').exists():
                raise NutritionError('REVIEW_ACTION_CHANGED','Review is unavailable or in progress')
            enrollment = review_root.parent/'reviewer_enrollment.json'
            if not enrollment.is_file() or digest(enrollment.read_bytes()) != manifest['nutrition_enrollment_sha256']:
                raise NutritionError('REVIEW_ACTION_CHANGED','Reviewer enrollment revoked or changed')
            pinned = manifest['nutrition_review_pins']
        store=ActionBoundTrustStore(build/'nutrition_data',manifest['artifacts']['nutrition_data/approval_registry.json'],review_root,pinned)
    else:
        store=TrustStore(build/'nutrition_data',manifest['artifacts']['nutrition_data/approval_registry.json'])
    catalog = KnowledgeCatalog(ROOT,binding)
    if manifest.get('nutrition_derived_active'):
        from nutrition_pipeline.p276 import DerivedCatalog
        contract = 'pipeline/p276/contract.json'
        catalog = DerivedCatalog(catalog,build/contract,manifest['artifacts'][contract])
    return LevelEngine(catalog,store)

def evaluate(request,manifest,ledger):
    rid=request.get('recipe_id')
    try:
        required = {'recipe_id', 'recipe_version', 'target_servings'}
        if not required <= request.keys() <= required | {'metric', 'view', 'division'} or type(rid) is not int:
            raise NutritionError('INVALID_NUTRITION_REQUEST', 'Invalid request descriptor')
        metric, view, division = request.get('metric'), request.get('view'), request.get('division')
        if metric is not None and metric not in NUTRIENTS or view not in (None, 'serving', 'division'):
            raise NutritionError('INVALID_NUTRITION_REQUEST', 'Invalid nutrient or view')
        if (view == 'division' and (type(division) is not int or not 1 <= division <= 100)) or (view != 'division' and division is not None):
            raise NutritionError('INVALID_NUTRITION_REQUEST', 'Invalid batch division')
        row=ledger.get(rid)
        if not row or not row['allowed_for_answer']:raise NutritionError('HELD_RECIPE','Held or unknown recipe')
        if request['recipe_version'] != recipe_version(manifest, row):raise NutritionError('RECIPE_VERSION_MISMATCH','Wrong recipe version')
        target=request['target_servings']
        if target is not None and (type(target) is not int or not 1<=target<=100):raise NutritionError('INVALID_TARGET_SERVINGS','Target must be 1..100')
        e=engine(manifest);e.catalog.check(rid,request['recipe_version'])
        result=e.calculate_level(e.store.plan_path(rid),expected_recipe_id=rid,target_servings=target)
        if result.get('status')=='MATH_TEST_ONLY' or result.get('input_review_scope')=='SYNTHETIC_MATH_TESTS':raise NutritionError('TEST_DATA_FORBIDDEN','Test fixtures cannot be displayed as food')
        return result
    except NutritionError as exc:return blocked(exc,rid)
    except (OSError,KeyError,TypeError,ValueError):return blocked(NutritionError('LOCAL_INPUT_INVALID','Nutrition input unavailable'),rid)

def render(request,manifest,ledger):
    from backend.chatbot.recipe_views_v5 import document
    result=evaluate(request,manifest,ledger);row=ledger.get(request.get('recipe_id'),{})
    name=row.get('question','Món chưa xác định')
    if result['status']=='BLOCKED':
        issue = result['issues'][0]['code']
        doc = document(row) if row.get('answer_text') else {}
        if issue == 'NO_APPROVED_RECIPE_PLAN':
            text = f'**{name}**\n\nMình chưa có hồ sơ dinh dưỡng đã duyệt cho món này.'
            if not doc.get('base_portions'):
                text += ' Khẩu phần gốc chưa xác định.'
            text += ' Thiếu: nguồn dưỡng chất và lượng phần ăn được đã đối chiếu, kể cả gia vị.'
            if doc.get('base_range'):
                text += ' Nguồn chỉ ghi khẩu phần dạng khoảng.'
        else:
            text = f'**{name}**\n\nMình chưa thể tính dinh dưỡng từ hồ sơ hiện tại. Cần kiểm tra lại dữ liệu và nguồn.'
        return result,text
    level=result['calculation_level']
    if manifest.get('nutrition_derived_active') and request['recipe_id'] == 276:
        name = 'Bắp cải luộc · 276-A-FDC89 · 89 g nguyên liệu đầu vào · 1 khẩu phần'
    lines=[f'**{name} — cấp {level}**',result['warning']]
    metric, view = request.get('metric'), request.get('view')
    if view == 'division':
        count = request['division']
        values = {key: packed(Fraction(result['totals'][key]['exact']) / count, key) for key in NUTRIENTS}
        lines.append(f'Chia cùng mẻ gốc thành {count} phần bằng nhau, giữ nguyên nguyên liệu. Mỗi phần: '+components(values, metric))
    elif view == 'serving':
        lines.append('Mỗi phần theo mốc nguồn: '+components(result['per_serving'], metric))
    else:
        lines.append(('Tổng nguyên liệu đầu vào: ' if level == 'A' else 'Tổng mẻ đã duyệt: ')+components(result['totals']))
        lines.append('Mỗi phần theo mốc nguồn: '+components(result['per_serving']))
    if view is None and result.get('scaled_batch'):
        scale=result['scaled_batch'];lines.append('Kịch bản tỷ lệ cho '+scale['target_servings_exact']+' phần: '+', '.join(f"{k}: {scale['totals'][k]['display']} {scale['totals'][k]['unit']}" for k in NUTRIENTS))
    prov=result['provenance'];lines.append('Nguồn công thức và bảng thành phần (local, checksum, phiên bản, đoạn chứng cứ):')
    for ref in prov['plan_citations']+sum((c['citations'] for c in result['ingredient_contributions']),[]):
        lines.append(f"- {ref['path']} | {ref['document_version']} | SHA-256 {ref['sha256']} | {ref['passage']}")
    lines+=['Không tự xác minh nguồn hay phê duyệt chuyên môn. Giá trị theo dữ liệu/định lượng đã duyệt; không phải phép đo trực tiếp của món bạn nấu hoặc lời khuyên điều trị.']
    return result,'\n\n'.join(lines)

def route(payload,manifest,ledger,recipe):
    from backend.chatbot.recipe_views_v5 import normalize, limitation, named_recipe_ids
    from backend.chatbot.cong_thuc import danh_muc
    q = normalize(payload['question'])
    state = payload['state']
    old = state.get('nutrition_context')
    portion = re.search(r'\b(?:nau|lam|doi|tang|giam|sang)?\s*(?:cho|sang|thanh|con)\s+' + PORTION, q)
    # A bare "còn một phần?" asks for the existing serving rather than scaling the recipe.
    if re.fullmatch(r'con mot (?:khau phan|phan|nguoi)(?: thi sao)?[?.!]*', q):
        portion = None
    division = re.search(r'\bchia(?:\s+cung me)?(?:\s+thanh)?\s+' + PORTION, q)
    per_serving = bool(re.search(PER_SERVING, q))
    asks = bool(re.search(PATTERN, q))
    recipe_source = bool(re.search(r'\b(?:nguon cong thuc|cong thuc (?:goc )?(?:lay|tu) (?:o )?dau|bai cong thuc)\b',q))
    report_followup = bool(re.search(SOURCE, q)) and not recipe_source
    explicit_recipe_resize = bool(portion and recipe and not asks)
    follow = bool(old and ((portion and not explicit_recipe_resize) or division or per_serving or report_followup))
    if not asks and not follow:
        if recipe:
            state.pop('nutrition_context', None)
        if not recipe and (per_serving or division):
            return limitation('NUTRITION_CONTEXT_REQUIRED', state.get('mon_hien_tai'))
        return None

    candidates = named_recipe_ids(q, danh_muc(payload['kho']))
    if len(candidates) > 1:
        state.pop('nutrition_context', None)
        state['mon_hien_tai'] = None
        return limitation('RECIPE_CLARIFICATION')
    topic = dict(id_goc=recipe.id_goc, cau_hoi=recipe.cau_hoi) if recipe else state.get('mon_hien_tai')
    if not recipe and re.search(r'\b(?:canh|lau|ca|ga|tom|banh)\b', q) and not re.search(r'\b(mon nay|mon do|cong thuc do)\b', q):
        state.pop('nutrition_context', None)
        state['mon_hien_tai'] = None
        return limitation('RECIPE_CLARIFICATION')
    if not topic:
        return limitation('NUTRITION_CONTEXT_REQUIRED')
    rid = topic['id_goc']
    row = ledger.get(rid)
    if not row or not row['allowed_for_answer']:
        return limitation('HELD_HEALTH')
    if not old or old.get('recipe_id') != rid or old.get('recipe_version') != recipe_version(manifest, row):
        old = {}
    if (per_serving or division) and not asks and not old:
        return limitation('NUTRITION_CONTEXT_REQUIRED', topic)
    metrics = [name for name, terms in METRICS.items() if re.search(r'\b(?:'+terms+r')\b', q)]
    metric = metrics[0] if len(metrics) == 1 else old.get('metric') if not asks else None
    ps = state.get('portion_state_v5') or {}
    target = old.get('target_servings') if old else (
        ps.get('target_requested') or ps.get('target_applied')) if ps.get('recipe_id') == rid else None
    view = 'division' if division else 'serving' if per_serving and not portion else None
    if portion and not division:
        target = serving_count(portion)
    if target is not None and not 1 <= target <= 100 or division and not 1 <= serving_count(division) <= 100:
        return limitation('MODIFICATION_UNSUPPORTED', topic)
    # A change to ingredients invalidates the original plan, including later followups.
    change_text=re.sub(r'\bkhong (?:bo|giam|thay)\b','giu nguyen',q)
    if (state.get('pending_ingredient_change') or {}).get('recipe_id')==rid or any((state.get('dieu_kien') or {}).get(k) for k in ('loai_tru','chua_ro','an_chay')) or re.search(r'(?<!toan )(?<!bun )(?<!thit )\bbo\s+|\b(giam|thay the|thay bang|khong dung|khong them)\b',change_text):
        return limitation('MODIFICATION_UNSUPPORTED',topic)
    request=dict(recipe_id=rid,recipe_version=recipe_version(manifest, row),target_servings=target,
                 metric=metric,view=view,division=serving_count(division) if division else None)
    state['nutrition_context']=dict(request)
    state['nutrition_portion_status']='REQUESTED_SCENARIO_NOT_APPLIED'
    result,text=render(request,manifest,ledger)
    if result['status']!='BLOCKED':state['nutrition_portion_status']='ARITHMETIC_SCENARIO_ONLY' if target is not None else 'REVIEWED_SOURCE_BASIS'
    return dict(loai='khong_chac' if result['status']=='BLOCKED' else 'tra_loi',reason_code='NUTRITION_BLOCKED' if result['status']=='BLOCKED' else 'NUTRITION_CALCULATED',cau_tra_loi=text,nguon=[],goi_y=[],doan_truy_hoi=[],chu_de=topic,giai_thich={},nutrition_request=request,nutrition_result=result)

def enforce(result,manifest,ledger):
    from backend.chatbot.recipe_views_v5 import limitation
    request=result.get('nutrition_request')
    if not isinstance(request,dict):
        if result.get('reason_code') == 'NUTRITION_CONTEXT_REQUIRED':
            return limitation('NUTRITION_CONTEXT_REQUIRED', result.get('chu_de')) | {
                'trang_thai': result.get('trang_thai')}
        return limitation('VALIDATION_FAILED')
    rid=request.get('recipe_id')
    if type(rid) is not int or rid not in ledger or not ledger[rid]['allowed_for_answer']:return limitation('VALIDATION_FAILED')
    if result.get('chu_de',{}).get('id_goc')!=rid:return limitation('VALIDATION_FAILED')
    state=result.get('trang_thai') or {}
    if (state.get('pending_ingredient_change') or {}).get('recipe_id')==rid or any((state.get('dieu_kien') or {}).get(k) for k in ('loai_tru','chua_ro','an_chay')):return limitation('MODIFICATION_UNSUPPORTED',result.get('chu_de'))
    if 'derivative_version' in request:
        from backend.chatbot.derived_nutrition import answer as derived_answer
        from backend.chatbot.recipe_edit_v1 import respond
        metric=request.get('metric')
        licensed=derived_answer(ledger[rid],state,manifest,metric) if metric is None or metric in NUTRIENTS else None
        if not licensed or licensed[0]['recipe_version']!=request['derivative_version']:
            return respond('EDIT_NUTRITION_BLOCKED',result['chu_de']) | {'trang_thai':state}
        _,data,text=licensed
        return dict(result,cau_tra_loi=text,nutrition_result=data,nguon=[],goi_y=[],doan_truy_hoi=[],structured_view=None,loai='tra_loi',reason_code='NUTRITION_CALCULATED')
    if manifest.get('recipe_edit_version')==1:
        from backend.chatbot.recipe_edit_v1 import active_for, respond
        if active_for(ledger[rid],state):
            return respond('EDIT_NUTRITION_BLOCKED',result['chu_de']) | {'trang_thai':state}
    data,text=render(request,manifest,ledger)
    r=dict(result);r.update(cau_tra_loi=text,nutrition_result=data,nguon=[],goi_y=[],doan_truy_hoi=[],structured_view=None,loai='khong_chac' if data['status']=='BLOCKED' else 'tra_loi',reason_code='NUTRITION_BLOCKED' if data['status']=='BLOCKED' else 'NUTRITION_CALCULATED')
    return r


def recipe_footer(row, view, state, manifest, ledger):
    missing = '**Dinh dưỡng:** Chưa có số liệu đã duyệt cho phiên bản công thức này.'
    if any((state.get('dieu_kien') or {}).get(k) for k in ('loai_tru','chua_ro','an_chay')):
        return missing
    if view['mode']=='recipe_edit':
        from backend.chatbot.derived_nutrition import answer
        approved=answer(row,state,manifest)
        if not approved:return missing
        _,data,_=approved
    else:
        if not manifest.get('nutrition_integration_version') or not manifest['artifacts'].get('nutrition_data/approval_registry.json'):
            return missing
        try:
            version=recipe_version(manifest,row)
        except KeyError:
            return missing
        data=evaluate(dict(recipe_id=row['id'],recipe_version=version,target_servings=None),manifest,ledger)
        if data.get('status')!='CALCULATED_APPROVED_INPUT_ESTIMATE':
            return missing
        servings=view.get('target_portions')
        if servings is not None and str(servings)!=data['servings_exact']:
            return missing
    title='**Dinh dưỡng mỗi khẩu phần**'
    line=components(data['per_serving'])
    if row['id']==276 and view['mode']=='full' and manifest.get('nutrition_derived_active'):
        basis='**Hồ sơ tham chiếu riêng đã duyệt:** 276-A-FDC89, 89 g bắp cải đầu vào, một phần. *USDA FDC 169975.*'
    else:
        basis='**Cơ sở:** Hồ sơ đã duyệt, cấp A theo nguyên liệu đầu vào.'
    return '\n\n'.join((title,line,basis,data['warning']))
