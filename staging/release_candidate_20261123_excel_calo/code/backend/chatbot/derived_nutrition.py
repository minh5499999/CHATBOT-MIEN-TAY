"""Exact derivative identity and adapter for reviewed Level A inputs."""
import json
from fractions import Fraction

from offline_nutrition.trust import NutritionError, digest, require
from nutrition_levels import A_SCOPES, LevelEngine
from nutrition_pipeline.runtime_trust import ActionBoundTrustStore


def descriptor(row, events):
    from backend.chatbot.recipe_edit_v1 import replay
    require(row.get('allowed_for_answer') and row.get('scope')=='IN_SCOPE',
            'HELD_RECIPE','Recipe cannot authorize nutrition')
    plan=replay(row,events)
    require(plan['changed'],'DERIVATIVE_REQUIRED','No active edit')
    components=[]
    for item in plan['items']:
        components.append(dict(component_id=f"span:{item['start']}:{item['end']}",
                               ingredient=item['key'], quantity=item.get('quantity'), unit=item.get('unit')))
    require(len({i['component_id'] for i in components})==len(components),
            'DUPLICATE_COMPONENT','Ingredient spans must be unique')
    operations=[events[i]['command'] for i in plan['active']]
    steps=[(s['section'],s['text']) for s in plan['steps'] if s['text']]
    body=dict(schema=1,recipe_id=row['id'],base_sha256=row['answer_sha256'],
              source=row['source'],operations=operations,servings=plan['portions'],
              components=components,steps_sha256=digest(encoded(steps)))
    return body | {'recipe_version':digest(encoded(body))}


def encoded(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')


class DerivativeCatalog:
    def __init__(self, catalog, contract):
        self.catalog=catalog
        self.contract=contract

    def check(self, recipe_id, version=None):
        d=self.contract
        original=self.catalog.check(recipe_id)
        require(original['recipe_version']==d['base_sha256'] and
                recipe_id==d['recipe_id'] and version==d['recipe_version'],
                'RECIPE_VERSION_MISMATCH','Wrong derivative or original version')
        return dict(recipe_id=recipe_id,recipe_version=version,
                    components={c['component_id'] for c in d['components']})


def calculate(catalog,store,path,contract):
    """Review binds one recipe snapshot; LevelEngine retains all numeric checks."""
    plan,_=store.load('plans',path,A_SCOPES|{'derivative_recipe_identity'})
    require(plan.get('derivative_contract')==contract and
            plan.get('recipe_version')==contract['recipe_version'] and
            plan.get('recipe_id')==contract['recipe_id'] and
            plan.get('calculation_level')=='A',
            'DERIVATIVE_CONTRACT_MISMATCH','Approved Level A plan must bind the exact derivative')
    require(type(contract['servings']) is int and contract['servings']>0 and
            Fraction(plan.get('servings'))==contract['servings'],
            'AMBIGUOUS_SERVINGS','Reviewed plan must match exact derivative servings')
    expected={i['component_id']:i for i in contract['components']}
    items=plan.get('ingredients')
    require(isinstance(items,list) and len(items)==len(expected),'INCOMPLETE_RECIPE_MAPPING','Every input must be assigned')
    remaining=set(expected)
    for item in items:
        mapping=item.get('source_component_ids')
        require(isinstance(mapping,list) and len(mapping)==1 and mapping[0] in remaining,
                'INCOMPLETE_RECIPE_MAPPING','Each modified ingredient needs its own reviewed mapping')
        source=expected[mapping[0]]
        require(item.get('derivative_source_quantity')==source['quantity'] and
                item.get('derivative_source_unit')==source['unit'] and source['quantity'] is not None,
                'DERIVATIVE_SOURCE_QUANTITY_UNBOUND','Cookbook quantity must be exact and reviewed alongside edible mass')
        remaining.remove(mapping[0])
    return LevelEngine(DerivativeCatalog(catalog,contract),store).calculate_level(
        path,expected_recipe_id=contract['recipe_id'])


def answer(row,state,manifest,metric=None):
    from backend.chatbot.recipe_edit_v1 import base_edit
    from backend.chatbot.nutrition_runtime import build_path, components
    from backend.chatbot.knowledge_policy import ROOT
    from offline_nutrition import KnowledgeCatalog
    from offline_nutrition.trust import read_json
    entries=manifest.get('derived_nutrition_plans',{})
    if not entries:return None
    try:
        d=descriptor(row,base_edit(row,state)['events'])
        entry=entries.get(d['recipe_version'])
        if not entry:return None
        # The registry is a separate pinned namespace. The original registry
        # continues serving ID 276 and cannot resolve a derivative plan.
        build=build_path(manifest).resolve()
        registry='derivative_nutrition/approval_registry.json'
        bundle=build/'derivative_nutrition'
        require(bundle.resolve().is_relative_to(build),'PATH_ESCAPE','Invalid derivative bundle location')
        path=entry['plan_path']
        registered='derivative_nutrition/'+path
        require((bundle/path).resolve().is_relative_to(bundle.resolve()) and
                digest((bundle/path).read_bytes())==manifest['artifacts'][registered],
                'DERIVATIVE_PLAN_CHANGED','Derivative plan differs from frozen manifest')
        review=manifest['derived_nutrition_review']
        review_root=(ROOT/review['directory']).resolve()
        require(review_root.is_relative_to(ROOT/'staging') and not (review_root/'decision.lock').exists(),
                'REVIEW_ACTION_CHANGED','Derivative review changed or is in progress')
        enrollment=review_root.parent/'reviewer_enrollment.json'
        require(digest(enrollment.read_bytes())==review['enrollment_sha256'],
                'REVIEW_ACTION_CHANGED','Derivative enrollment revoked or changed')
        store=ActionBoundTrustStore(bundle,manifest['artifacts'][registry],review_root,review['pins'])
        binding=(build/'nutrition_binding.json').read_bytes()
        require(digest(binding)==manifest['artifacts']['nutrition_binding.json'],
                'NUTRITION_BUNDLE_CHANGED','Original knowledge binding changed')
        catalog=KnowledgeCatalog(ROOT,read_json(binding))
        result=calculate(catalog,store,path,d)
        if result['status']!='CALCULATED_APPROVED_INPUT_ESTIMATE' or result.get('input_review_scope')!='PRODUCTION':
            return None
    except (NutritionError,OSError,KeyError,TypeError,ValueError,ZeroDivisionError):
        return None
    title=f"**{row['question']} · phiên bản {d['recipe_version'][:12]} — cấp A**"
    lines=[title,result['warning'],'Tổng nguyên liệu đầu vào: '+components(result['totals'],metric),
           'Mỗi phần: '+components(result['per_serving'],metric)]
    refs=result['provenance']['plan_citations']
    for item in result['ingredient_contributions']:refs=refs+item['citations']
    quotes={(ref['path'],ref['document_version'],ref['sha256'],ref['passage']) for ref in refs}
    lines+=['Nguồn cục bộ đã ghim:',*(f'- {p} | {v} | SHA-256 {h} | {s}' for p,v,h,s in sorted(quotes))]
    return d,result,'\n\n'.join(lines)

