"""Separate ingredient-input estimate; the strict 3A finished-food engine is unchanged."""
from fractions import Fraction
from offline_nutrition.engine import NutritionEngine,NUTRIENTS,STATES,DATA_SCOPES,number,vector,blocked
from offline_nutrition.trust import NutritionError,require

A_SCOPES={'recipe_mapping','portion_basis','mass','completeness','ingredient_input_estimate'}
class LevelEngine(NutritionEngine):
    def calculate_level(self,path,*,expected_recipe_id=None,target_servings=None):
        try:
            # Trust is checked before consulting a submitted level flag.
            plan,_=self.store.load('plans',path,{'recipe_mapping','mass','completeness'})
            require(isinstance(plan.get('recipe_version'),str) and len(plan['recipe_version'])==64,'RECIPE_VERSION_MISMATCH','Explicit pinned recipe answer hash required')
            level=plan.get('calculation_level','B')
            require(level in ('A','B'),'INVALID_CALCULATION_LEVEL','Explicit A or B required')
            if level=='B':
                result=super().calculate(path,expected_recipe_id=expected_recipe_id,target_servings=target_servings)
                result['calculation_level']='B';return result
            return self._input_estimate(path,expected_recipe_id,target_servings)
        except NutritionError as exc:return blocked(exc,expected_recipe_id)
        except (OSError,KeyError,TypeError,ValueError):return blocked(NutritionError('LOCAL_INPUT_INVALID','Invalid local level input'),expected_recipe_id)
    def _input_estimate(self,path,expected,target):
        plan,review=self.store.load('plans',path,A_SCOPES)
        rid=plan.get('recipe_id');require(expected is None or rid==expected,'RECIPE_ID_MISMATCH','Wrong recipe')
        spec=self.catalog.check(rid,plan.get('recipe_version'))
        require(plan.get('schema_version')==1 and plan.get('accounting_method')=='INGREDIENT_INPUT_ESTIMATE','ACCOUNTING_METHOD_UNAPPROVED','Level A must explicitly estimate input ingredients')
        require(plan.get('serving_basis')=='SOURCE_APPROVED_EXACT','UNVERIFIED_SERVING_BASIS','Exact reviewed serving basis required')
        servings=number(plan.get('servings'),'servings',positive=True,code='AMBIGUOUS_SERVINGS')
        refs=self.store.citations(plan.get('citations'),'plan.citations')
        require(isinstance(plan.get('method_notes'),str) and plan['method_notes'].strip(),'MISSING_METHOD_EVIDENCE','Explain input accounting')
        dataset,data_review=self.store.load('datasets',plan.get('dataset_path'),DATA_SCOPES)
        require(dataset.get('schema_version')==1 and number(dataset.get('basis_mass_g'),'basis',positive=True)==100,'UNSUPPORTED_NUTRIENT_BASIS','per100g required')
        foods=dataset.get('foods');require(isinstance(foods,dict),'DATASET_SCHEMA','Food dictionary required')
        items=plan.get('ingredients');require(isinstance(items,list) and bool(items),'MISSING_INGREDIENTS','Complete inputs required')
        used=set();ids=set();totals={k:Fraction(0) for k in NUTRIENTS};contributions=[];bases=set()
        for i,item in enumerate(items):
            loc=f'ingredients[{i}]';require(isinstance(item,dict),'INGREDIENT_SCHEMA','Object required')
            uid=item.get('id');require(isinstance(uid,str) and uid and uid not in ids,'DUPLICATE_INGREDIENT','Unique ingredient ID required');ids.add(uid)
            components=item.get('source_component_ids')
            require(isinstance(components,list) and components and all(isinstance(x,str) for x in components),'MISSING_COMPONENT_MAPPING','Explicit source components required')
            require(len(components)==len(set(components)) and not used.intersection(components),'DUPLICATE_COMPONENT','Duplicate source component');used.update(components)
            require(item.get('mass_basis')=='EDIBLE','EDIBLE_INPUT_REQUIRED','Level A requires documented edible input mass')
            food=foods.get(item.get('food_id'));require(isinstance(food,dict),'UNKNOWN_FOOD','Reviewed food mapping missing')
            require(item.get('food_state') in STATES and item['food_state']==food.get('food_state'),'FOOD_STATE_MISMATCH','State mismatch')
            require(food.get('carbohydrate_basis') in ('TOTAL','AVAILABLE','BY_DIFFERENCE') and food.get('energy_basis') in ('METABOLIZABLE','GROSS','OTHER_REVIEWED'),'INCOMPATIBLE_NUTRIENT_BASES','Explicit definitions required')
            bases.add((food['carbohydrate_basis'],food['energy_basis']))
            citations=self.store.citations(item.get('citations'),loc)+self.store.citations(food.get('citations'),loc+'.food')
            amounts=food.get('nutrients_per_100g');require(isinstance(amounts,dict) and all(amounts.get(k) is not None for k in NUTRIENTS),'MISSING_NUTRIENT_FIELDS','All five nutrients required')
            mass,trace=self._mass(item,loc)
            values={k:mass/100*number(amounts[k],loc+'.'+k,code='INVALID_NUTRIENT_VALUE') for k in NUTRIENTS}
            for k in NUTRIENTS:totals[k]+=values[k]
            contributions.append(dict(ingredient_id=uid,food_id=item['food_id'],food_state=item['food_state'],source_component_ids=components,edible_mass_g_exact=str(mass),conversion=trace,contribution=vector(values),citations=citations))
        require(used==set(spec['components']),'INCOMPLETE_RECIPE_MAPPING','Every input including spices, oil and broth must be reviewed')
        require(len(bases)==1,'INCOMPATIBLE_NUTRIENT_BASES','Different bases cannot be summed')
        scaled=None
        if target is not None:
            target=number(target,'target_servings',positive=True,code='INVALID_TARGET_SERVINGS');factor=target/servings
            scaled=dict(status='PROPORTIONAL_INPUT_SCENARIO_ONLY',target_servings_exact=str(target),factor_exact=str(factor),totals=vector({k:v*factor for k,v in totals.items()}))
        return dict(status='MATH_TEST_ONLY' if self.store.math_fixtures else 'CALCULATED_APPROVED_INPUT_ESTIMATE',calculation_level='A',recipe_id=rid,recipe_version=spec['recipe_version'],input_review_scope='SYNTHETIC_MATH_TESTS' if self.store.math_fixtures else 'PRODUCTION',source_verified_by_engine=False,servings_exact=str(servings),totals=vector(totals),per_serving=vector({k:v/servings for k,v in totals.items()}),per_100g=None,scaled_batch=scaled,ingredient_contributions=contributions,issues=[],provenance=dict(plan=review,dataset=data_review,plan_citations=refs),warning='Ước tính theo nguyên liệu đầu vào; không phải dinh dưỡng thành phẩm hoặc phần thực sự ăn.')
