import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from test_p3b_import import ImportTests as ImportFixture
from nutrition_pipeline.intake import import_draft,merge_drafts,sha,write_new
from nutrition_pipeline.review import ReviewQueue
from nutrition_pipeline.mapping import resolve_food,resolve_conversion,build_plan
from nutrition_pipeline.bundle import export_reviewed_bundle
from nutrition_pipeline.runtime_trust import ActionBoundTrustStore
from offline_nutrition import NutritionError,TrustStore

SCOPES=['food_aliases','nutrient_values','food_states','basis_and_units','reuse_rights','unit_conversion','mass_basis','recipe_mapping','portion_basis','mass','retention','completeness','ingredient_input_estimate','source_text']
class PipelineTests(unittest.TestCase):
    _fixture_setup=ImportFixture.setUp
    def setUp(self):
        self._fixture_setup();self.row['identity_key']='ABSTRACT_IDENTITY_A'
        self.review_root=self.root/'review';self.review_root.mkdir();(self.review_root/'review_events').mkdir()
        self.policy=dict(scope='SYNTHETIC_MATH_TESTS',reviewers={'SYNTHETIC_REVIEWER_ONLY':SCOPES})
        self.write('reviewer_policy.json',self.policy)
        (self.review_root/'abstract.txt').write_text(self.text,encoding='utf-8')
        self.q=ReviewQueue(self.review_root)
        self.check=dict(path='abstract.txt',sha256=sha(self.review_root/'abstract.txt'),passage=self.text,document_version='abstract-v1',collected_at='2026-11-16')
    def write(self,name,value):
        p=self.review_root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value),encoding='utf-8');return p
    def approve(self,name,scopes=SCOPES,action='APPROVED'):
        return self.q.record(dict(action=action,actor='SYNTHETIC_REVIEWER_ONLY',reason='Abstract review workflow only, no food or professional approval',subject_path=name,subject_sha256=sha(self.review_root/name),review_scope=list(scopes),evidence_checks=[self.check],document_version='abstract-v1'))
    def import_data(self,rows=None):
        p=self.root/'input.json';p.write_text(json.dumps(rows if rows is not None else [self.row]),encoding='utf-8')
        return import_draft(p,self.root,self.queue,self.root/'draft')
    def denied(self,code,call):
        with self.assertRaises(NutritionError) as raised:call()
        self.assertEqual(raised.exception.code,code)
    def test_normalized_engine_shape_remains_unverified(self):
        r=self.import_data();d=json.loads(Path(r['dataset']).read_text());self.assertEqual(d['status'],'IMPORTED_UNVERIFIED');self.assertFalse(d['approval_granted']);self.assertEqual(d['foods']['ABSTRACT_A']['nutrients_per_100g']['sodium_mg'],'11')
    def test_source_bytes_and_passage_preserved(self):
        d=json.loads(Path(self.import_data()['dataset']).read_text());ref=d['foods']['ABSTRACT_A']['citations'][0]
        self.assertEqual(sha(self.root/'draft'/ref['path']),ref['sha256']);self.assertIn(ref['passage'],(self.root/'draft'/ref['path']).read_text())
    def test_no_identity_no_draft(self):
        self.row.pop('identity_key');r=self.import_data();self.assertEqual(r['status'],'BLOCKED');self.assertFalse((self.root/'draft').exists())
    def test_duplicate_cannot_export_first_valid_row(self):
        r=self.import_data([self.row,self.row]);self.assertEqual(r['status'],'BLOCKED');self.assertIsNone(r['dataset'])
    def test_missing_nutrient_no_partial_dataset(self):
        self.row['sodium_mg']=None;self.assertEqual(self.import_data()['status'],'BLOCKED')
    def test_cross_source_conflict_does_not_pick_latest(self):
        a=dict(schema_version=1,basis_mass_g='100',foods={'A':dict(food_state='RAW',value='2')});b=copy.deepcopy(a);b['foods']['A']['value']='3'
        r=merge_drafts([a,b]);self.assertEqual(r['status'],'BLOCKED');self.assertFalse(r['foods'])
    def test_identical_rows_merge_unverified(self):
        a=dict(schema_version=1,basis_mass_g='100',foods={'A':dict(food_state='RAW')});self.assertEqual(merge_drafts([a,a])['status'],'IMPORTED_UNVERIFIED')
    def test_import_label_approved_never_grants_action(self):
        self.write('input.json',dict(status='APPROVED',reviewed_by='SYNTHETIC_REVIEWER_ONLY'));self.denied('INPUT_NOT_APPROVED',lambda:self.q.approved('input.json',{'mass'}))
    def test_empty_reviewer_policy_rejects_approval(self):
        self.write('reviewer_policy.json',dict(scope='PRODUCTION',reviewers={}));self.write('input.json',{})
        self.denied('REVIEWER_NOT_AUTHORIZED',lambda:self.approve('input.json'))
    def test_explicit_action_can_be_rejected_later(self):
        self.write('input.json',{});self.approve('input.json');self.approve('input.json',action='REJECTED')
        self.denied('INPUT_NOT_APPROVED',lambda:self.q.approved('input.json',{'mass'}))
    def test_subject_tamper_revokes_review(self):
        self.write('input.json',{});self.approve('input.json');self.write('input.json',{'changed':True})
        self.denied('INPUT_NOT_APPROVED',lambda:self.q.approved('input.json',{'mass'}))
    def test_source_tamper_revokes_review(self):
        self.write('input.json',{});self.approve('input.json');(self.review_root/'abstract.txt').write_text('changed')
        self.denied('EVIDENCE_DIGEST_MISMATCH',lambda:self.q.approved('input.json',{'mass'}))
    def test_missing_scope_rejected(self):
        self.write('input.json',{});self.approve('input.json',['mass'])
        self.denied('INSUFFICIENT_REVIEW_SCOPE',lambda:self.q.approved('input.json',{'retention'}))
    def test_chain_tamper_detected(self):
        self.write('input.json',{});self.approve('input.json');self.approve('input.json',action='NEEDS_REVIEW')
        p=self.review_root/'review_events/000001.json';d=json.loads(p.read_text());d['reason']='tamper';p.write_text(json.dumps(d))
        self.denied('REVIEW_CHAIN_INVALID',self.q.events)
    def mapping_data(self):
        self.write('aliases.json',dict(aliases=[dict(alias='abstract',food_id='A',food_state='RAW',identity_key='A')]))
        self.write('foods.json',dict(foods={'A':dict(food_state='RAW',identity_key='A')}))
        self.approve('aliases.json');self.approve('foods.json')
    def test_reviewed_alias_reuse_requires_identity_and_state(self):
        self.mapping_data();self.assertEqual(resolve_food(self.q,'aliases.json','foods.json','abstract','RAW','A')[0],'A')
    def test_alias_does_not_cross_state(self):
        self.mapping_data();self.denied('MISSING_FOOD_MAPPING',lambda:resolve_food(self.q,'aliases.json','foods.json','abstract','COOKED','A'))
    def test_alias_does_not_cross_species_identity(self):
        self.mapping_data();self.denied('MISSING_FOOD_MAPPING',lambda:resolve_food(self.q,'aliases.json','foods.json','abstract','RAW','B'))
    def test_conflicting_same_alias_cannot_pick_first(self):
        self.mapping_data();self.write('aliases.json',dict(aliases=[dict(alias='abstract',food_id=fid,food_state='RAW',identity_key='A') for fid in ('A','B')]))
        self.approve('aliases.json');self.denied('AMBIGUOUS_FOOD_ID',lambda:resolve_food(self.q,'aliases.json','foods.json','abstract','RAW','A'))
    def test_conversion_bound_to_food_state_and_basis(self):
        self.write('units.json',dict(conversions=[dict(food_id='A',food_state='RAW',unit='item',mass_basis='EDIBLE',grams_per_unit='17',citations=[self.check])]))
        self.approve('units.json');self.assertEqual(resolve_conversion(self.q,'units.json','A','RAW','item','EDIBLE')['grams_per_unit'],'17')
        self.denied('MISSING_OR_AMBIGUOUS_CONVERSION',lambda:resolve_conversion(self.q,'units.json','A','COOKED','item','EDIBLE'))
    def plan_fixture(self):
        class Catalog:
            def check(self,rid):return dict(recipe_id=rid,recipe_version='a'*64,components={'A','B'})
        self.mapping=dict(recipe_id=900000,recipe_version='a'*64,step_ingredient_review='EXPLICITLY_RECONCILED',servings='2',serving_basis='SOURCE_APPROVED_EXACT',ingredients=[dict(source_component_ids=[c]) for c in ('A','B')])
        self.write('mapping.json',self.mapping);self.approve('mapping.json');return Catalog()
    def test_plan_assembly_is_not_approval_or_calculation(self):
        plan=build_plan(self.q,self.plan_fixture(),900000,'mapping.json');self.assertEqual(plan['status'],'NEEDS_REVIEW');self.assertFalse(plan['approval_granted'])
    def test_missing_steps_accounting_blocks_plan(self):
        cat=self.plan_fixture();self.mapping.pop('step_ingredient_review');self.write('mapping.json',self.mapping);self.approve('mapping.json')
        self.denied('STEPS_NOT_RECONCILED',lambda:build_plan(self.q,cat,900000,'mapping.json'))
    def test_duplicate_component_blocks_plan(self):
        cat=self.plan_fixture();self.mapping['ingredients'][1]['source_component_ids']=['A'];self.write('mapping.json',self.mapping);self.approve('mapping.json')
        self.denied('INCOMPLETE_RECIPE_MAPPING',lambda:build_plan(self.q,cat,900000,'mapping.json'))
    def test_test_review_cannot_export_production_bundle(self):self.denied('REGISTRY_SCOPE_MISMATCH',lambda:export_reviewed_bundle(self.review_root,{},self.root/'export'))
    def test_review_states_not_auto_approved(self):
        self.write('input.json',{});self.approve('input.json',action='NEEDS_REVIEW')
        self.denied('INPUT_NOT_APPROVED',lambda:self.q.approved('input.json',{'mass'}))
    def runtime_store(self):
        bundle=self.root/'runtime_bundle';bundle.mkdir();(bundle/'evidence').mkdir()
        source=bundle/'evidence/abstract.txt';source.write_text(self.text,encoding='utf-8')
        registry=dict(schema_version=1,scope='PRODUCTION',plans={},datasets={},evidence={'evidence/abstract.txt':dict(status='APPROVED',sha256=sha(source),reviewed_by='SYNTHETIC_REVIEWER_ONLY',reviewed_at='2026-11-16',review_scope=['source_text','reuse_rights'],review_subject_path='abstract.txt')})
        (bundle/'approval_registry.json').write_text(json.dumps(registry),encoding='utf-8')
        pinned={'reviewer_policy.json':sha(self.review_root/'reviewer_policy.json')}
        pinned.update({p.relative_to(self.review_root).as_posix():sha(p) for p in (self.review_root/'review_events').glob('*.json')})
        return ActionBoundTrustStore(bundle,sha(bundle/'approval_registry.json'),self.review_root,pinned)
    def test_registry_metadata_without_action_cannot_authorize(self):
        store=self.runtime_store();self.denied('INPUT_NOT_APPROVED',lambda:store.approved('evidence','evidence/abstract.txt',{'source_text'}))
    def test_runtime_refuses_synthetic_review(self):
        self.approve('abstract.txt');store=self.runtime_store();self.denied('TEST_DATA_FORBIDDEN',lambda:store.approved('evidence','evidence/abstract.txt',{'source_text'}))
    def test_runtime_pins_review_action_hash(self):
        self.approve('abstract.txt');store=self.runtime_store();p=self.review_root/'review_events/000001.json';value=json.loads(p.read_text());value['reason']='changed';p.write_text(json.dumps(value))
        self.denied('REVIEW_ACTION_CHANGED',lambda:store.approved('evidence','evidence/abstract.txt',{'source_text'}))
    def test_runtime_new_action_requires_new_manifest(self):
        self.approve('abstract.txt');store=self.runtime_store();self.approve('abstract.txt',action='NEEDS_REVIEW')
        self.denied('UNPINNED_REVIEW_ACTION',lambda:store.approved('evidence','evidence/abstract.txt',{'source_text'}))
    def test_synthetic_export_preserves_scope_and_bytes_only(self):
        self.write('plan.json',dict(recipe_id=900000,calculation_level='A'));self.write('dataset.json',dict(abstract_test_only=True))
        for path in ('plan.json','dataset.json','abstract.txt'):self.approve(path)
        target=self.root/'export';result=export_reviewed_bundle(self.review_root,dict(plans={'plans/abstract.json':'plan.json'},datasets={'datasets/abstract.json':'dataset.json'},evidence={'evidence/abstract.txt':'abstract.txt'}),target,math_fixtures=True)
        self.assertEqual(result['scope'],'SYNTHETIC_MATH_TESTS');self.assertFalse(result['activated'])
        self.assertEqual(sha(target/'evidence/abstract.txt'),sha(self.review_root/'abstract.txt'))
        self.denied('REGISTRY_SCOPE_MISMATCH',lambda:TrustStore(target,sha(target/'approval_registry.json')))

del ImportFixture
