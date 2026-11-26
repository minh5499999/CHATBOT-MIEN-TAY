"""Deterministic dossiers for all permitted recipes; no nutrient/name/mass inference."""
import hashlib,re
from collections import Counter,defaultdict
from nutrition_import import normalized
from offline_nutrition.trust import require

def prepare_catalog(inventory,ledger):
    originals=[];proposals=[];readiness=[];occurrences=[];reuse=defaultdict(list);units=Counter()
    for recipe in inventory:
        rid=recipe['recipe_id'];row=ledger.get(rid)
        require(row and row['allowed_for_answer'],'HELD_RECIPE','Catalog cannot import held answers')
        require(recipe['recipe_version']==row['answer_sha256'] and hashlib.sha256(row['answer_text'].encode('utf-8')).hexdigest()==row['answer_sha256'],'RECIPE_VERSION_MISMATCH','Exact authorized source required')
        text=row['answer_text'];components=recipe['ingredients']
        steps=[]
        for section,span in recipe['source_sections'].items():
            if section=='ingredients':continue
            block=text[span['start']:span['end']]
            for match in re.finditer(r'(?m)^[-•][^\n]+',block):
                start=span['start']+match.start();end=span['start']+match.end()
                steps.append(dict(section=section,start=start,end=end,text=text[start:end],status='NEEDS_REVIEW',material_or_consumption_flag=bool(re.search(r'\b(them|cho|uop|nuoc|muoi|mam|duong|dau|nem|bot|cham)\b',normalized(match[0])))))
        original=dict(recipe_id=rid,recipe_version=row['answer_sha256'],answer_sha256=row['answer_sha256'],source_locator=row['source'],answer_text=text,source_verification='UNVERIFIED',ingredients=components,source_sections=recipe['source_sections'],servings_as_recorded=recipe['servings'],origin='Authorized project snapshot, not independently checked external source')
        originals.append(original)
        for item in components:
            span=item['source_span'];require(text[span['start']:span['end']]==item['raw_text'],'SOURCE_SPAN_MISMATCH','Ingredient span changed')
            name=item.get('ingredient_name_as_written') or item['raw_text']
            key=normalized(name);uid='candidate:'+hashlib.sha256(key.encode()).hexdigest()[:16]
            reuse[key].append(rid)
            if item.get('unit_as_written'):units[item['unit_as_written']]+=1
            occurrences.append(dict(recipe_id=rid,recipe_version=row['answer_sha256'],component_id=f"span:{span['start']}:{span['end']}",ingredient_candidate_id=uid,name_as_written=name,raw_text=item['raw_text'],quantity_as_written=item.get('quantity_as_written'),unit_as_written=item.get('unit_as_written'),food_id=None,identity_key=None,food_state=None,edible_mass_g=None,status='NEEDS_REVIEW',approved=False))
        unresolved=sum(i['parse_status']!='SINGLE_AMOUNT_SAME_UNIT' for i in components)
        conversion=sum(bool(i.get('unit_as_written')) and i['unit_as_written'].lower() not in ('g','kg','mg') for i in components)
        missing=['RECIPE_SOURCE','NUTRIENT_SOURCE','APPROVED_MAPPING','EDIBLE_MASS','COMPOUND_AND_SPICE_ACCOUNTING','STEP_COMPLETENESS_REVIEW','SOURCE_SERVING_REVIEW']
        if not recipe['servings']['exact_from_source']:missing.append('EXACT_SERVING_BASIS')
        readiness.append(dict(recipe_id=rid,recipe_version=row['answer_sha256'],question=row['question'],components=len(components),unresolved_amounts=unresolved,conversion_components=conversion,servings_as_recorded=recipe['servings']['exact_from_source'],servings_range=recipe['servings']['range_from_source'],step_lines_to_review=len(steps),status='BLOCKED',level_A=False,level_B=False,source_complete_for_review=False,missing=';'.join(missing),level_B_additional_missing='COOKED_YIELD;CONSUMED_OIL_BROTH_SAUCE;RETENTION',readiness_basis='Structural preparation effort only; not approval or nutritional readiness'))
        proposals.append(dict(recipe_id=rid,recipe_version=row['answer_sha256'],status='NEEDS_REVIEW',executable=False,step_review=steps,required_reviewer_actions=['Compare ingredients against all steps and serving suggestions','Resolve quantities/state/edible mass/compound ingredients','Obtain local recipe + nutrient + conversion + processing evidence','Map every source component with explicit reviewed identity','Approve separately by scope; never auto-populate unknown values'],new_values_assumed=False))
    # Rank effort by unresolved quantities/conversions, then reuse coverage. No source claim.
    frequencies={k:len(set(ids)) for k,ids in reuse.items()}
    for row in readiness:
        row['reuse_candidate_score']=sum(frequencies[normalized(i['name_as_written'])] for i in occurrences if i['recipe_id']==row['recipe_id'])
    ordered=sorted(readiness,key=lambda r:(r['unresolved_amounts'],r['conversion_components'],-r['reuse_candidate_score'],r['recipe_id']))
    ranks={r['recipe_id']:i for i,r in enumerate(ordered,1)}
    for row in readiness:row['preparation_priority_rank']=ranks[row['recipe_id']]
    reusable=[dict(name_as_written_key=k,recipe_count=len(set(ids)),occurrence_count=len(ids),recipe_ids=sorted(set(ids)),food_id=None,food_state=None,identity_key=None,status='NEEDS_REVIEW',approved=False) for k,ids in sorted(reuse.items(),key=lambda kv:(-len(set(kv[1])),-len(kv[1]),kv[0]))]
    return dict(originals=originals,proposals=proposals,readiness=readiness,occurrences=occurrences,reusable=reusable,units=dict(units))
