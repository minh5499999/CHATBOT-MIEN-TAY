"""Offline regression: actual catalog join, portion invariance, ingredient cuts."""
import json
import os
from pathlib import Path
import sys
from dataclasses import replace

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'staging/release_candidate_20261123_excel_calo'
os.chdir(ROOT)
os.environ.update(CHATBOT_STAGING_BUILD=str(BUILD),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
sys.path[:0]=[str(BUILD/'code'),str(ROOT)]
import importlib.util
spec=importlib.util.spec_from_file_location('frontend',ROOT/'frontend/__init__.py',submodule_search_locations=[str(ROOT/'frontend')])
module=importlib.util.module_from_spec(spec)
sys.modules['frontend']=module
spec.loader.exec_module(module)

def main():
    from backend.chatbot.cong_thuc import danh_muc
    from backend.chatbot.cau_hinh import doc_cau_hinh
    from frontend.du_lieu_dieu_chinh import scenario, METRICS
    import torch
    torch.set_num_threads(4)
    recipes=danh_muc(doc_cau_hinh()['kho_vector'])
    matched=[]
    for recipe in recipes:
        original=scenario(recipe,2)
        if original is None: continue
        matched.append(recipe.id_goc)
        assert abs(sum(x['energy_kcal'] for x in original['energy_breakdown'])-original['total']['energy_kcal'])<1e-6
        assert all(x['mass']>=0 and x['energy_kcal']>=0 for x in original['energy_breakdown'])
        double=scenario(recipe,4)
        for m,_,_ in METRICS:
            assert abs(double['total'][m]-2*original['total'][m])<1e-6
        reduced=scenario(recipe,2,50,50)
        for m,_,_ in METRICS:
            assert reduced['total'][m]<=original['total'][m]+1e-6
        assert scenario(replace(recipe,nguyen_lieu=recipe.nguyen_lieu+('Muối thêm 100g',)),2) is None
    recipe=next(r for r in recipes if r.id_goc==42)
    a=scenario(recipe,2)
    b=scenario(recipe,2,50,50)
    assert a and b and b['total']['sodium_mg']<a['total']['sodium_mg']
    assert b['total']['fat_g']<a['total']['fat_g']
    assert scenario(recipe,0) is None and scenario(recipe,2,100,0) is None
    assert all(scenario(r,2) is None for r in recipes if r.id_goc in {214,267,277})
    assert len(matched)>150, len(matched)
    (ROOT/'audit/adjustment_view.json').write_text(json.dumps(dict(matched=len(matched),ids=matched,
        checks='same recipe/portion basis, 2→4 batch scaling, oil/salt cuts, mismatched source blocked, held recipes blocked'),ensure_ascii=False,indent=2),encoding='utf8')
    print('PASS: actual catalog',len(matched),'reference joins; portion invariance; cuts; source mismatch and held boundaries')
    if '--ui' in sys.argv:
        from unittest.mock import patch
        import frontend.dieu_chinh_cong_thuc as view
        class State(dict):
            def __setattr__(self,k,v): self[k]=v
        class UI:
            def __init__(self): self.session_state=State(); self.events=[]; self.click=None; self.choice=None; self.salt=0; self.oil=0
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def columns(self,columns,**kwargs): return [self]* (columns if isinstance(columns,int) else len(columns))
            def tabs(self,names): return [self]*len(names)
            def selectbox(self,label,options,**kwargs):
                return {'adjust_recipe_id':self.choice,'adjust_salt_cut':self.salt,'adjust_oil_cut':self.oil}[kwargs['key']]
            def number_input(self,*args,**kwargs): return 2
            def chat_input(self,*args,**kwargs): return None
            def button(self,*args,**kwargs):
                clicked=kwargs.get('key')==self.click
                if clicked and kwargs.get('on_click'): kwargs['on_click'](*kwargs.get('args',()))
                return clicked
            def __getattr__(self,name):
                def call(*args,**kwargs):
                    self.events.append((name,args,kwargs))
                    return self
                return call
        ui=UI()
        def draw():
            ui.events=[]
            view.hien_thi_dieu_chinh('fixture','__test_no_write__',lambda q:None)
            return [args[0] for name,args,kw in ui.events if name=='table']
        with patch.object(view,'st',ui), patch.object(view,'danh_muc',return_value=recipes), patch.object(view.mon_yeu_thich,'da_luu',return_value=False):
            assert not draw()
            ui.choice=42;ui.click='adjust_apply'
            assert len(draw())==2
            assert any(name=='expander' and kw.get('expanded') is False for name,args,kw in ui.events)
            ui.click=None;ui.salt=50
            assert not draw()
            ui.click='adjust_apply'
            tables=draw();assert len(tables)==2 and any('green' in r['Chênh lệch'] for r in tables[1])
            ui.click='adjust_again';draw()
            ui.click=None;assert not draw()
            assert '2 thìa nước mắm' not in view._cooking_text(recipe)
            assert '30 phút' in view._cooking_text(recipe)
        print('PASS: UI render smoke (recorded elements): apply, tables, collapsed sources, stale result hidden, reset and cooking quantities')

if __name__=='__main__': main()
