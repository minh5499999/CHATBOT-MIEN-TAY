import unittest
from test_engine import EngineTests as Fixture
from nutrition_levels import LevelEngine,A_SCOPES
from offline_nutrition import TrustStore
from test_engine import MathCatalog

class LevelTests(unittest.TestCase):
    setUp=Fixture.setUp
    sha=Fixture.sha
    reviewed=Fixture.reviewed
    write_inputs=Fixture.write_inputs
    write_registry=Fixture.write_registry
    def calc(self,level='A',**options):
        if level=='A':
            self.plan.update(calculation_level='A',accounting_method='INGREDIENT_INPUT_ESTIMATE')
            self.write_inputs();self.policy['plans']['plans/abstract.json']['review_scope']=list(A_SCOPES);self.write_registry()
        return LevelEngine(MathCatalog(),TrustStore(self.root,self.policy_hash,math_fixtures=True)).calculate_level('plans/abstract.json',**options)
    def test_A_exact_abstract_sum(self):
        r=self.calc();self.assertEqual(r['totals']['kcal']['exact'],'28');self.assertEqual(r['status'],'MATH_TEST_ONLY');self.assertEqual(r['calculation_level'],'A')
    def test_A_does_not_claim_finished_per100g(self):self.assertIsNone(self.calc()['per_100g'])
    def test_A_requires_no_retention_or_yield_but_never_claims_B(self):
        del self.plan['cooked_batch_yield_g']
        for i in self.plan['ingredients']:i.pop('retention_fractions');i.pop('fraction_consumed')
        r=self.calc();self.assertEqual(r['calculation_level'],'A');self.assertIn('không phải',r['warning'])
    def test_B_missing_retention_still_blocked(self):
        del self.plan['ingredients'][0]['retention_fractions'];self.write_inputs()
        self.assertEqual(self.calc('B')['issues'][0]['code'],'MISSING_RETENTION_ACCOUNTING')
    def test_B_missing_consumption_still_blocked(self):
        del self.plan['ingredients'][0]['fraction_consumed'];self.write_inputs()
        self.assertEqual(self.calc('B')['issues'][0]['code'],'MISSING_CONSUMPTION_ACCOUNTING')
    def test_A_missing_sodium(self):
        del self.dataset['foods']['ABSTRACT_A']['nutrients_per_100g']['sodium_mg']
        self.assertEqual(self.calc()['issues'][0]['code'],'MISSING_NUTRIENT_FIELDS')
    def test_A_wrong_state(self):
        self.plan['ingredients'][0]['food_state']='COOKED';self.assertEqual(self.calc()['issues'][0]['code'],'FOOD_STATE_MISMATCH')
    def test_A_incomplete_spices_mapping(self):
        self.plan['ingredients'].pop();self.assertEqual(self.calc()['issues'][0]['code'],'INCOMPLETE_RECIPE_MAPPING')
    def test_A_range(self):
        self.plan['servings']='4-6';self.assertEqual(self.calc()['issues'][0]['code'],'AMBIGUOUS_SERVINGS')
    def test_A_duplicate(self):
        self.plan['ingredients'][1]['id']='A';self.assertEqual(self.calc()['issues'][0]['code'],'DUPLICATE_INGREDIENT')
    def test_A_wrong_unit(self):
        self.plan['ingredients'][0]['unit']='splash';self.assertEqual(self.calc()['issues'][0]['code'],'UNSUPPORTED_UNIT')
    def test_A_multiple_scaling_absolute(self):
        r=self.calc(target_servings=8);self.assertEqual(r['scaled_batch']['totals']['kcal']['exact'],'112')
        r=self.calc(target_servings=2);self.assertEqual(r['scaled_batch']['totals']['kcal']['exact'],'28')
    def test_missing_version_is_not_implicit_latest(self):
        self.plan.pop('recipe_version');self.assertEqual(self.calc()['issues'][0]['code'],'RECIPE_VERSION_MISMATCH')

del Fixture
