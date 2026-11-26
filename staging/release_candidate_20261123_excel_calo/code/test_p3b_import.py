import hashlib,json,tempfile,unittest
from pathlib import Path
from nutrition_import import intake
from offline_nutrition import NutritionError

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.queue=self.root/'queue'
        self.text='ABSTRACT CONSTANTS ONLY: A 2 3 5 7 11; not a food source.'
        (self.root/'source.txt').write_text(self.text,encoding='utf-8')
        self.row=dict(food_id='ABSTRACT_A',name='Abstract A',food_state='RAW',basis_mass_g='100',dataset_version='test-v1',source_path='source.txt',source_sha256=hashlib.sha256((self.root/'source.txt').read_bytes()).hexdigest(),passage=self.text,document_version='abstract',collected_at='2026-11-16',source_locator='ABSTRACT_TEST_NOT_FOOD',reuse_basis='test',carbohydrate_basis='TOTAL',energy_basis='METABOLIZABLE',kcal='2',protein_g='3',lipid_g='5',carbohydrate_g='7',sodium_mg='11',energy_unit='kcal',macro_unit='g',sodium_unit='mg')
    def run_rows(self,rows):
        p=self.root/'input.json';p.write_text(json.dumps(rows),encoding='utf-8');return intake(p,self.root,self.queue)[0]
    def test_valid_is_not_approved(self):
        r=self.run_rows([self.row]);self.assertEqual(r['records'][0]['status'],'NEEDS_REVIEW');self.assertEqual(r['approved_records'],0)
    def test_missing_vs_zero(self):
        self.row['sodium_mg']=None;self.assertIn('MISSING_FIELD',self.run_rows([self.row])['records'][0]['issues'])
    def test_explicit_zero_allowed_pending_review(self):
        self.row['sodium_mg']='0';self.assertFalse(self.run_rows([self.row])['records'][0]['issues'])
    def test_negative(self):
        self.row['kcal']='-1';self.assertIn('INVALID_NUTRIENT_VALUE',self.run_rows([self.row])['records'][0]['issues'])
    def test_wrong_unit(self):
        self.row['sodium_unit']='g';self.assertIn('NUTRIENT_UNIT_MISMATCH',self.run_rows([self.row])['records'][0]['issues'])
    def test_duplicate_id(self):self.assertIn('DUPLICATE_FOOD_ID',self.run_rows([self.row,self.row])['records'][1]['issues'])
    def test_wrong_source_hash(self):
        self.row['source_sha256']='0'*64;self.assertIn('EVIDENCE_DIGEST_MISMATCH',self.run_rows([self.row])['records'][0]['issues'])
    def test_missing_passage(self):
        self.row['passage']='absent';self.assertIn('PASSAGE_NOT_FOUND',self.run_rows([self.row])['records'][0]['issues'])
    def test_path_escape(self):
        self.row['source_path']='../source.txt';self.assertIn('INVALID_LOCAL_PATH',self.run_rows([self.row])['records'][0]['issues'])
    def test_ambiguous_name_states_both_flagged(self):
        other=dict(self.row,food_id='ABSTRACT_B',food_state='COOKED')
        for r in self.run_rows([self.row,other])['records']:self.assertIn('AMBIGUOUS_NAME_OR_STATE',r['issues'])
    def test_json_duplicate_key_rejected(self):
        p=self.root/'input.json';p.write_text('[{"food_id":"A","food_id":"B"}]')
        with self.assertRaises(NutritionError):intake(p,self.root,self.queue)
    def test_csv(self):
        import csv
        p=self.root/'input.csv'
        with p.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=self.row);w.writeheader();w.writerow(self.row)
        self.assertEqual(intake(p,self.root,self.queue)[0]['records'][0]['status'],'NEEDS_REVIEW')
    def test_append_only(self):
        self.run_rows([self.row])
        with self.assertRaises(FileExistsError):self.run_rows([self.row])
