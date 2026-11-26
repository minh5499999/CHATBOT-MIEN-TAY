"""Offline CSV adapter for the observed SR Legacy ZIP layout."""
import csv
import io
import zipfile
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath

DEFINITIONS = {
    '1008': ('kcal', 'Energy', 'KCAL', 'METABOLIZABLE'),
    '1003': ('protein_g', 'Protein', 'G', ''),
    '1004': ('lipid_g', 'Total lipid (fat)', 'G', ''),
    '1005': ('carbohydrate_g', 'Carbohydrate, by difference', 'G', 'BY_DIFFERENCE'),
    '1093': ('sodium_mg', 'Sodium, Na', 'MG', ''),
}

def checked_members(archive):
    members = {}
    total = 0
    for entry in archive.infolist():
        name = PurePosixPath(entry.filename)
        if name.is_absolute() or '..' in name.parts or ':' in entry.filename or chr(92) in entry.filename:
            raise ValueError('Unsafe ZIP path')
        total += entry.file_size
        if total > 100_000_000:
            raise ValueError('Uncompressed limit exceeded')
        if not entry.is_dir():
            if name.name in members:
                raise ValueError('Duplicate ZIP member basename')
            members[name.name] = entry
    return members

def read_tables(path):
    stats = Counter()
    observations = defaultdict(lambda: defaultdict(list))
    with zipfile.ZipFile(path) as archive:
        members = checked_members(archive)
        def table(name, required):
            with archive.open(members[name]) as stream:
                reader = csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig', newline=''))
                if not reader.fieldnames or not set(required) <= set(reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
                    raise ValueError(f'Invalid schema for {name}')
                for line, row in enumerate(reader, 2):
                    yield line, row
        def indexed(name, key, required):
            rows = {}
            for _, row in table(name, required):
                if not row[key] or row[key] in rows:
                    raise ValueError(f'Duplicate or missing key in {name}')
                rows[row[key]] = row
            return rows
        foods = indexed('food.csv', 'fdc_id', ['fdc_id', 'description', 'data_type', 'publication_date'])
        definitions = indexed('nutrient.csv', 'id', ['id', 'name', 'unit_name'])
        for nid, (_, label, unit, _) in DEFINITIONS.items():
            if (definitions[nid]['name'], definitions[nid]['unit_name']) != (label, unit):
                raise ValueError(f'Nutrient definition mismatch {nid}')
        seen = set()
        for line, row in table('food_nutrient.csv', ['id', 'fdc_id', 'nutrient_id', 'amount', 'footnote', 'derivation_id']):
            stats['source_nutrient_rows'] += 1
            if not row['id'] or row['id'] in seen or row['fdc_id'] not in foods or row['nutrient_id'] not in definitions:
                raise ValueError(f'Duplicate or orphan nutrient row {line}')
            seen.add(row['id'])
            nid = row['nutrient_id']
            if nid not in DEFINITIONS:
                stats['outside_target_rows'] += 1
                continue
            key, _, unit, basis = DEFINITIONS[nid]
            try:
                amount = Decimal(row['amount'])
                valid = amount.is_finite() and amount >= 0
            except (InvalidOperation, TypeError):
                valid = False
            observations[row['fdc_id']][key].append(dict(amount=row['amount'] if valid else None, nutrient_id=nid, unit=unit, basis=basis, row_id=row['id'], csv_record=line, footnote=row['footnote'], derivation_id=row['derivation_id']))
            stats['target_rows'] += 1
    normalized = {}
    for fid, food in foods.items():
        if food['data_type'] != 'sr_legacy_food':
            raise ValueError('Unexpected USDA data type')
        values = {}
        issues = []
        for key, *_ in DEFINITIONS.values():
            rows = observations[fid][key]
            if len(rows) != 1 or rows[0]['amount'] is None:
                issues.append(key + (':DUPLICATE' if len(rows) > 1 else ':MISSING_OR_INVALID'))
            else:
                values[key] = rows[0]['amount']
                stats['values_retained'] += 1
            if any(row['footnote'] for row in rows):
                issues.append(key + ':FOOTNOTE_REVIEW')
        normalized['USDA:FDC:'+fid] = dict(**food, food_state=None, basis_mass_g=100, mass_basis='EDIBLE', energy_basis='METABOLIZABLE', carbohydrate_basis='BY_DIFFERENCE', nutrients_per_100g=values, source_rows=dict(observations[fid]), issues=issues, status='NEEDS_REVIEW')
        stats['five_values_present'] += len(values) == 5
    stats['food_rows'] = len(foods)
    return normalized, dict(stats), definitions
