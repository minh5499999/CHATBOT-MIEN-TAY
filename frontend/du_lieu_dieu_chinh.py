"""Reference scenarios for the UI, separate from medical advice."""
import json
import math
from functools import lru_cache
from pathlib import Path
import re

DATA = Path(__file__).resolve().parents[1] / 'data/dinh_duong/cong_thuc_250.json'
BASE = DATA.parents[1] / 'calo/cong_thuc.json'
SALTY = {'salt', 'fishsauce', 'soysauce', 'msg', 'seasoning', 'shrimpaste', 'fermentedfish', 'miso', 'hoisin', 'oystersauce', 'veganfishsauce', 'sweetfishsauce', 'chilisalt', 'peanutsalt'}
OILS = {'oil', 'sesameoil', 'porkfat', 'scallionoil'}
METRICS = [('energy_kcal', 'Năng lượng', 'kcal'), ('protein_g', 'Đạm', 'g'), ('fat_g', 'Chất béo', 'g'), ('carbohydrate_available_g', 'Carbohydrate', 'g'), ('sodium_mg', 'Natri', 'mg')]

@lru_cache(maxsize=2)
def _load(stamp, base_stamp):
    return json.loads(DATA.read_text(encoding='utf-8')), json.loads(BASE.read_text(encoding='utf-8'))

def clean(text):
    return re.sub(r'\s+', ' ', str(text).strip().lstrip('-• ').strip()).casefold()

def original_scenario(recipe):
    """Original recipe display may use the workbook's explicit range midpoint."""
    try: data, _ = _load(DATA.stat().st_mtime_ns, BASE.stat().st_mtime_ns)
    except (OSError, ValueError): return None
    ref=next((r for r in data['recipes'] if r['id']==recipe.id_goc),None)
    if not ref: return None
    return scenario(recipe, ref['servings'], reference_range=True)

def scenario(recipe, target, salt_cut=0, oil_cut=0, *, reference_range=False):
    if recipe.id_goc in {214, 267, 277}: return None
    if not isinstance(target, (int, float)) or not math.isfinite(target) or not 1 <= target <= 30:
        return None
    if salt_cut not in (0, 25, 50) or oil_cut not in (0, 25, 50): return None
    try: data, base = _load(DATA.stat().st_mtime_ns, BASE.stat().st_mtime_ns)
    except (OSError, ValueError): return None
    ref = next((r for r in data['recipes'] if r['id'] == recipe.id_goc), None)
    rows = [x for x in data['ingredients'] if x['recipe_id'] == recipe.id_goc]
    if not ref or not rows or not ref['servings']: return None
    if recipe.khau_phan != ref['servings']:
        header=recipe.noi_dung.split('\n- ',1)[0]
        span=re.search(r'(\d+)\s*(?:đến|[-–])\s*(\d+)\s*(?:người|phần)',header,re.I)
        if not (reference_range and span and (int(span[1])+int(span[2]))/2==ref['servings']
                and target==ref['servings'] and not salt_cut and not oil_cut):return None
    if clean(ref['question']) != clean(recipe.cau_hoi): return None
    source = next((r for r in base['recipes'] if r['id']==recipe.id_goc), None)
    if not source or data['workbook_sha256'] != base['workbook_sha256']: return None
    if clean(source['original_answer']) != clean(recipe.noi_dung): return None
    # Normalization can split one source line into several ingredient rows.
    # Verify the entire original recipe, plus its original ingredient section.
    section = re.search(r'(?ims)^\s*(?:nguyên liệu|chuẩn bị nguyên liệu)[^\n]*\n(.*?)(?=^\s*(?:sơ chế|cách chế biến|cách làm|các bước|chế biến|hoàn thành)\b|\Z)', source['original_answer'])
    lines = [clean(x) for x in section[1].splitlines() if x.strip().startswith(('-', '•'))] if section else []
    if lines != [clean(x) for x in recipe.nguyen_lieu]: return None
    scale = target/ref['servings']
    totals = {m: 0.0 for m, _, _ in METRICS}
    ingredients, changes, sources, assumptions, energy_breakdown = [], [], set(), [], []
    profiles = {p['key']: p for p in data['profiles']}
    for row in rows:
        cut = salt_cut if row['food_key'] in SALTY else oil_cut if row['food_key'] in OILS else 0
        ratio = scale*(1-cut/100)
        q, unit = row['quantity'], row['quantity_unit']
        ingredients.append({'Nguyên liệu gốc': row['original'], 'Lượng chuẩn hóa': f'{q:g} {unit}',
            'Sau điều chỉnh': f'{q*ratio:g} {unit}', 'Thay đổi': f'Giảm {cut}% sau quy đổi' if cut else 'Quy đổi khẩu phần'})
        if cut: changes.append(f"{row['original']}: giảm {cut}% sau quy đổi khẩu phần.")
        values = dict(row['values'], energy_kcal=row['nutrition_energy_kcal'])
        for m in totals:
            v = values.get(m)
            if v is None or not isinstance(v, (int, float)) or not math.isfinite(v): return None
            totals[m] += v*ratio
        p = profiles[row['nutrition_profile_key']]
        energy = values['energy_kcal']*ratio
        energy_mass = row['mass_before_refuse']*row['edible_fraction']*row['energy_retention']*ratio
        flags=[]
        if row['quantity_assumed']:flags.append('Lượng quy đổi/giả định')
        if row['ingredient_proxy'] or row['food_key']=='color':flags.append('Thực phẩm/mô hình đại diện')
        energy_breakdown.append(dict(ingredient=row['original'],mass=energy_mass,
            unit=p['source_unit'] if row['food_key']=='color' else row['source_unit'],
            energy_kcal=energy,per_serving_kcal=energy/target,note='; '.join(flags) or 'Theo lượng và nguồn đã chọn'))
        for url in p['references'].values(): sources.update(u.strip() for u in url.split(' ; ') if u.strip())
        if row['quantity_assumed'] or row['ingredient_proxy'] or p['proxy_metrics']:
            assumptions.append(f"{row['original']} — {row['conversion_note']} {p['notes']}")
    nutrition = []
    for m, label, unit in METRICS:
        old = ref['energy_per_serving_kcal'] if m == 'energy_kcal' else ref['per_serving'][m]
        new = totals[m]/target
        digits = 0 if unit in ('mg', 'kcal') else 1
        pct = (new/old-1)*100 if old else None
        nutrition.append({'Thành phần': label, 'Công thức gốc': f'≈ {old:,.{digits}f} {unit}',
            'Sau điều chỉnh': f'≈ {new:,.{digits}f} {unit}',
            'Chênh lệch': 'Giữ nguyên' if pct is None or abs(pct)<.05 else f'{pct:+.0f}%'})
    return dict(reference=ref, ingredients=ingredients, nutrition=nutrition, changes=changes,
        assumptions=assumptions, sources=sorted(sources), total=totals, scale=scale,energy_breakdown=energy_breakdown)
