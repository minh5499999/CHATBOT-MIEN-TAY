"""Exact offline arithmetic over fully reviewed local plans/datasets only."""
from decimal import Decimal,InvalidOperation,localcontext,ROUND_HALF_EVEN
from fractions import Fraction
import re
from .trust import NutritionError,require,fail

NUTRIENTS=('kcal','protein_g','lipid_g','carbohydrate_g','sodium_mg')
UNITS={'kcal':'kcal','protein_g':'g','lipid_g':'g','carbohydrate_g':'g','sodium_mg':'mg'}
PLAN_SCOPES={'recipe_mapping','portion_basis','mass','retention','completeness'}
DATA_SCOPES={'nutrient_values','food_states','basis_and_units'}
STATES={'RAW','COOKED','DRIED','DRAINED','AS_SOLD'}
COUNT_UNITS={'item','quả','trái','con','củ','tép','nhánh','miếng','muỗng canh','muỗng cà phê','thìa cà phê','chén','bó','tô'}

def number(value,path,*,positive=False,fraction=False,code='INVALID_QUANTITY'):
    require(not isinstance(value,(bool,float)) and isinstance(value,(str,int,Decimal)),code,'Explicit finite decimal required; unknown is not zero',path)
    text=str(value).strip()
    require(len(text)<=100 and bool(re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?',text)),code,'Ambiguous/range/non-finite amount',path)
    try:d=Decimal(text)
    except InvalidOperation as exc:raise NutritionError(code,'Invalid decimal',path) from exc
    require(d.is_finite() and abs(d)<=Decimal('1e12') and (d==0 or d.adjusted()>=-100),code,'Number outside supported precision/size',path)
    require(d>0 if positive else d>=0,code,'Positive amount required' if positive else 'Negative amount forbidden',path)
    require(not fraction or d<=1,code,'Fraction must be between zero and one',path)
    return Fraction(d)

def packed(value,key):
    places=2 if key in ('kcal','sodium_mg') else 3
    with localcontext() as c:
        c.prec=80
        display=(Decimal(value.numerator)/Decimal(value.denominator)).quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_EVEN)
    return {'exact':str(value),'display':format(display,'f'),'unit':UNITS[key]}

def vector(values):return {k:packed(values[k],k) for k in NUTRIENTS}

def blocked(issue,recipe_id=None):
    return {'status':'BLOCKED','recipe_id':recipe_id,'issues':[issue.issue()],'totals':None,'per_serving':None,'per_100g':None,'scaled_batch':None,'ingredient_contributions':[],'source_verified_by_engine':False}

class NutritionEngine:
    """Readonly dependency injection: CLI uses pinned catalog and empty production registry.

    Math-test mode is visibly marked and cannot be opened as a production registry.
    Nothing here writes approvals, generates nutrient records, or diagnoses illness.
    """
    def __init__(self,catalog,store):self.catalog=catalog;self.store=store
    def assess_recipe(self,recipe_id):
        try:
            self.catalog.check(recipe_id)
            return self.calculate(self.store.plan_path(recipe_id),expected_recipe_id=recipe_id)
        except NutritionError as exc:return blocked(exc,recipe_id)
        except (OSError,KeyError,TypeError) as exc:return blocked(NutritionError('LOCAL_INPUT_INVALID','Missing or invalid local catalog/registry'),recipe_id)
    def calculate(self,plan_path,*,expected_recipe_id=None,target_servings=None):
        recipe_id=expected_recipe_id
        try:
            plan,plan_review=self.store.load('plans',plan_path,PLAN_SCOPES)
            recipe_id=plan.get('recipe_id')
            require(expected_recipe_id is None or recipe_id==expected_recipe_id,'RECIPE_ID_MISMATCH','Approved plan belongs to another recipe')
            spec=self.catalog.check(recipe_id,plan.get('recipe_version'))
            require(plan.get('schema_version')==1,'PLAN_SCHEMA','Unsupported plan schema')
            require(plan.get('serving_basis')=='SOURCE_APPROVED_EXACT','UNVERIFIED_SERVING_BASIS','A user scenario/range does not approve official recipe servings')
            servings=number(plan.get('servings'),'servings',positive=True,code='AMBIGUOUS_SERVINGS')
            cooked_yield=number(plan.get('cooked_batch_yield_g'),'cooked_batch_yield_g',positive=True,code='MISSING_COOKED_YIELD')
            plan_citations=self.store.citations(plan.get('citations'),'plan.citations')
            require(plan.get('accounting_method')=='REVIEWED_COMPONENT_RETENTION_AND_CONSUMPTION','ACCOUNTING_METHOD_UNAPPROVED','Explicit reviewed cooking/consumption accounting required')
            require(isinstance(plan.get('method_notes'),str) and bool(plan['method_notes'].strip()),'MISSING_METHOD_EVIDENCE','Method notes required')
            items=plan.get('ingredients')
            require(isinstance(items,list) and bool(items),'MISSING_INGREDIENTS','Reviewed complete ingredient list required')
            dataset,dataset_review=self.store.load('datasets',plan.get('dataset_path'),DATA_SCOPES)
            require(dataset.get('schema_version')==1,'DATASET_SCHEMA','Unsupported dataset schema')
            require(number(dataset.get('basis_mass_g'),'dataset.basis_mass_g',positive=True,code='UNSUPPORTED_NUTRIENT_BASIS')==100,'UNSUPPORTED_NUTRIENT_BASIS','This engine requires explicitly reviewed per100g data')
            foods=dataset.get('foods');require(isinstance(foods,dict),'DATASET_SCHEMA','Food dictionary required')
            used_ids=set();used_components=set();contributions=[];totals={k:Fraction(0) for k in NUTRIENTS};carb_bases=set();energy_bases=set()
            for index,item in enumerate(items):
                path=f'ingredients[{index}]'
                require(isinstance(item,dict),'INGREDIENT_SCHEMA','Ingredient object required',path)
                uid=item.get('id');require(isinstance(uid,str) and bool(uid) and uid not in used_ids,'DUPLICATE_INGREDIENT','Unique nonempty ingredient id required',path);used_ids.add(uid)
                refs=item.get('source_component_ids')
                require(isinstance(refs,list) and bool(refs) and all(isinstance(r,str) for r in refs),'MISSING_COMPONENT_MAPPING','Recipe source component mapping required',path)
                require(len(refs)==len(set(refs)) and not set(refs)&used_components,'DUPLICATE_COMPONENT','Recipe component would be counted twice',path)
                used_components.update(refs)
                ingredient_citations=self.store.citations(item.get('citations'),path+'.citations')
                food=foods.get(item.get('food_id'));require(isinstance(food,dict),'UNKNOWN_FOOD','No reviewed nutrient mapping for ingredient',path)
                state=item.get('food_state');require(state in STATES and food.get('food_state')==state,'FOOD_STATE_MISMATCH','Raw/cooked/other states must match reviewed data',path)
                require(food.get('carbohydrate_basis') in ('TOTAL','AVAILABLE','BY_DIFFERENCE'),'UNKNOWN_CARBOHYDRATE_BASIS','Explicit carbohydrate definition required',path)
                require(food.get('energy_basis') in ('METABOLIZABLE','GROSS','OTHER_REVIEWED'),'UNKNOWN_ENERGY_BASIS','Explicit energy definition required',path)
                carb_bases.add(food['carbohydrate_basis']);energy_bases.add(food['energy_basis'])
                food_citations=self.store.citations(food.get('citations'),path+'.nutrient_citations')
                amounts=food.get('nutrients_per_100g')
                missing=[k for k in NUTRIENTS if not isinstance(amounts,dict) or amounts.get(k) is None]
                require(not missing,'MISSING_NUTRIENT_FIELDS','Missing explicit fields: '+','.join(missing),path)
                nutrients={k:number(amounts[k],path+'.'+k,code='INVALID_NUTRIENT_VALUE') for k in NUTRIENTS}
                mass,conversion_trace=self._mass(item,path)
                consumed=number(item.get('fraction_consumed'),path+'.fraction_consumed',fraction=True,code='MISSING_CONSUMPTION_ACCOUNTING')
                retention=item.get('retention_fractions')
                require(isinstance(retention,dict) and all(k in retention and retention[k] is not None for k in NUTRIENTS),'MISSING_RETENTION_ACCOUNTING','All five retention fractions must be explicit and reviewed',path)
                factors={k:number(retention[k],path+'.retention.'+k,fraction=True,code='INVALID_RETENTION') for k in NUTRIENTS}
                values={k:mass/Fraction(100)*nutrients[k]*consumed*factors[k] for k in NUTRIENTS}
                for k in NUTRIENTS:totals[k]+=values[k]
                contributions.append({'ingredient_id':uid,'food_id':item['food_id'],'food_state':state,'source_component_ids':refs,'edible_mass_g_exact':str(mass),'conversion':conversion_trace,'fraction_consumed_exact':str(consumed),'retention_fractions_exact':{k:str(v) for k,v in factors.items()},'formula':'edible_mass_g / 100 * value_per_100g * fraction_consumed * nutrient_retention','contribution':vector(values),'citations':ingredient_citations+food_citations})
            require(set(spec['components'])==used_components,'INCOMPLETE_RECIPE_MAPPING','All reviewed recipe components must be accounted for, without additions/omissions')
            require(len(carb_bases)==1 and len(energy_bases)==1,'INCOMPATIBLE_NUTRIENT_BASES','Do not sum incompatible carbohydrate or energy definitions')
            per_serving={k:v/servings for k,v in totals.items()};per_100g={k:v/cooked_yield*100 for k,v in totals.items()}
            scaled=None
            if target_servings is not None:
                target=number(target_servings,'target_servings',positive=True,code='INVALID_TARGET_SERVINGS');factor=target/servings
                scaled={'status':'PROPORTIONAL_ARITHMETIC_SCENARIO_ONLY','target_servings_exact':str(target),'factor_exact':str(factor),'cooked_batch_yield_g_exact':str(cooked_yield*factor),'totals':vector({k:v*factor for k,v in totals.items()}),'warning':'Arithmetic scaling is not validation of a modified recipe or cooking process.'}
            return {'status':'MATH_TEST_ONLY' if self.store.math_fixtures else 'CALCULATED_FROM_APPROVED_INPUTS','recipe_id':recipe_id,'recipe_version':spec['recipe_version'],'source_verified_by_engine':False,'input_review_scope':'SYNTHETIC_MATH_TESTS' if self.store.math_fixtures else 'PRODUCTION','servings_exact':str(servings),'cooked_batch_yield_g_exact':str(cooked_yield),'serving_mass_g_exact':str(cooked_yield/servings),'totals':vector(totals),'per_serving':vector(per_serving),'per_100g':vector(per_100g),'scaled_batch':scaled,'ingredient_contributions':contributions,'issues':[],'provenance':{'plan':plan_review,'dataset':dataset_review,'plan_citations':plan_citations,'carbohydrate_basis':next(iter(carb_bases)),'energy_basis':next(iter(energy_bases))},'display_rounding':{'method':'HALF_EVEN','kcal_places':2,'grams_places':3,'sodium_mg_places':2,'exact_rational_values_preserved':True},'warning':'No diagnosis, treatment or source approval is performed by this calculator.'}
        except NutritionError as exc:return blocked(exc,recipe_id)
        except (OSError,KeyError,TypeError,ZeroDivisionError,InvalidOperation) as exc:return blocked(NutritionError('LOCAL_INPUT_INVALID','Missing or malformed local input; no partial total returned'),recipe_id)
    def _mass(self,item,path):
        amount=number(item.get('quantity'),path+'.quantity',positive=True)
        unit=item.get('unit');require(isinstance(unit,str),'UNIT_REQUIRED','Unit must be explicit',path)
        unit=' '.join(unit.lower().split());basis=item.get('mass_basis')
        require(basis in ('AS_SOLD','EDIBLE'),'MASS_BASIS_REQUIRED','Mass basis must be explicit',path)
        edible=number(item.get('edible_fraction'),path+'.edible_fraction',positive=True,fraction=True,code='MISSING_EDIBLE_FRACTION')
        require(basis!='EDIBLE' or edible==1,'EDIBLE_MASS_DOUBLE_ADJUSTMENT','Edible mass must not receive another inedible-fraction reduction',path)
        if unit in ('g','kg','mg'):
            factor={'g':Fraction(1),'kg':Fraction(1000),'mg':Fraction(1,1000)}[unit]
            gross=amount*factor;trace={'method':'EXACT_SI_MASS','unit_factor_exact':str(factor)}
        elif unit in ('ml','l','lít') or unit in COUNT_UNITS:
            c=item.get('conversion');require(isinstance(c,dict),'MISSING_UNIT_CONVERSION','No density or unit-mass inference is allowed',path)
            require(c.get('unit')==unit and c.get('mass_basis')==basis,'CONVERSION_BASIS_MISMATCH','Conversion unit and mass basis mismatch',path)
            refs=self.store.citations(c.get('citations'),path+'.conversion.citations')
            if unit in ('ml','l','lít'):
                density=number(c.get('density_g_per_ml'),path+'.density_g_per_ml',positive=True,code='MISSING_DENSITY')
                factor=density*(1000 if unit in ('l','lít') else 1);method='REVIEWED_DENSITY'
            else:
                factor=number(c.get('grams_per_unit'),path+'.grams_per_unit',positive=True,code='MISSING_UNIT_MASS');method='REVIEWED_UNIT_MASS'
            gross=amount*factor;trace={'method':method,'unit_factor_exact':str(factor),'citations':refs}
        else:fail('UNSUPPORTED_UNIT','Unsupported unit; no automatic guess or substitution',path)
        trace.update(quantity_exact=str(amount),unit=unit,mass_basis=basis,gross_mass_g_exact=str(gross),edible_fraction_exact=str(edible))
        return gross*edible,trace
