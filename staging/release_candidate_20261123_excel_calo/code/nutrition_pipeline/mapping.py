"""No fuzzy food/state inference. Reuse only explicit, reviewed identities and conversions."""
from nutrition_import import normalized
from offline_nutrition.trust import require
from offline_nutrition.engine import number
from .review import ReviewQueue

def resolve_food(queue,alias_path,food_path,ingredient_name,food_state,identity_key):
    aliases,_=queue.approved(alias_path,{'food_aliases'})
    foods,_=queue.approved(food_path,{'nutrient_values','food_states','basis_and_units'})
    candidates=[r for r in aliases.get('aliases',[]) if normalized(r['alias'])==normalized(ingredient_name) and r.get('food_state')==food_state and r.get('identity_key')==identity_key]
    ids={r.get('food_id') for r in candidates}
    require(len(ids)==1,'AMBIGUOUS_FOOD_ID' if ids else 'MISSING_FOOD_MAPPING','Need exactly one reviewed identity/state mapping')
    fid=next(iter(ids));food=foods.get('foods',{}).get(fid)
    require(isinstance(food,dict) and food.get('food_state')==food_state and food.get('identity_key')==identity_key,'FOOD_STATE_OR_IDENTITY_MISMATCH','Do not substitute species, state or product identity')
    return fid,food

def resolve_conversion(queue,path,food_id,food_state,unit,mass_basis):
    conversions,_=queue.approved(path,{'unit_conversion','food_states','mass_basis'})
    candidates=[r for r in conversions.get('conversions',[]) if (r.get('food_id'),r.get('food_state'),r.get('unit'),r.get('mass_basis'))==(food_id,food_state,unit,mass_basis)]
    require(len(candidates)==1,'MISSING_OR_AMBIGUOUS_CONVERSION','Exactly one identity/state/unit conversion required')
    row=candidates[0];key='density_g_per_ml' if unit in ('ml','l','lít') else 'grams_per_unit'
    number(row.get(key),key,positive=True);require(bool(row.get('citations')),'MISSING_EVIDENCE','Conversion citation required')
    return row

def build_plan(queue,catalog,recipe_id,mapping_path,level='A'):
    """Produce a reviewable plan, NEVER write/approve a runtime registry."""
    require(level in ('A','B'),'INVALID_CALCULATION_LEVEL','A or B required')
    spec=catalog.check(recipe_id)
    mapping,event=queue.approved(mapping_path,{'recipe_mapping','mass','portion_basis','completeness'})
    require(mapping.get('recipe_id')==recipe_id and mapping.get('recipe_version')==spec['recipe_version'],'RECIPE_VERSION_MISMATCH','Wrong recipe/version')
    require(mapping.get('step_ingredient_review')=='EXPLICITLY_RECONCILED','STEPS_NOT_RECONCILED','Review all water/oil/sauce/spices and steps, not only ingredient bullets')
    ingredients=mapping.get('ingredients');require(isinstance(ingredients,list) and ingredients,'MISSING_INGREDIENTS','Reviewed mappings required')
    used=[]
    for item in ingredients:
        require(isinstance(item,dict) and isinstance(item.get('source_component_ids'),list),'MISSING_COMPONENT_MAPPING','Explicit source spans required')
        used+=item['source_component_ids']
    require(len(set(used))==len(used) and set(used)==set(spec['components']),'INCOMPLETE_RECIPE_MAPPING','Do not drop or duplicate source components')
    number(mapping.get('servings'),'servings',positive=True,code='AMBIGUOUS_SERVINGS')
    require(mapping.get('serving_basis')=='SOURCE_APPROVED_EXACT','UNVERIFIED_SERVING_BASIS','Reviewed exact source servings required')
    plan={k:mapping.get(k) for k in ('recipe_id','recipe_version','servings','serving_basis','method_notes','citations','dataset_path','ingredients')}
    plan.update(schema_version=1,calculation_level=level,accounting_method='INGREDIENT_INPUT_ESTIMATE' if level=='A' else 'REVIEWED_COMPONENT_RETENTION_AND_CONSUMPTION',status='NEEDS_REVIEW',approval_granted=False,mapping_review_sequence=event['sequence'])
    if level=='B':plan['cooked_batch_yield_g']=mapping.get('cooked_batch_yield_g')
    # This is structural assembly only; the existing engine must validate mass,
    # state, complete nutrient values, citations and A/B accounting after review.
    return plan
