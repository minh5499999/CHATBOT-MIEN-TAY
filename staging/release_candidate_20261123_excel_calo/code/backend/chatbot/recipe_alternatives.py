"""Resolve alternatives offered together by the authorized recipe itself."""
import re

# These pairs only describe culinary roles for checking an explicit source
# choice. They do not authorize a substitution in recipes lacking that choice.
ROLES = {
    frozenset(('hanh la','ngo ri')): 'AROMATIC_FINISH',
    frozenset(('tieu','ngo gai')): 'OPTIONAL_FINISH',
}
NAMES={'hanh la':'hành lá','ngo ri':'ngò rí','tieu':'tiêu','ngo gai':'ngò gai'}


def choices(doc, items, steps):
    from backend.chatbot.recipe_bindings_v2 import fold, exact_word, QUANTITY, QUALIFIER
    offers=[]
    for item in items:
        raw=item['raw']
        if ' hoac ' not in fold(raw):
            continue
        # Resolve both names from the controlled role vocabulary before parsing the suffix.
        pair=next((parts for parts in ROLES if any(
            re.fullmatch(re.escape(a)+r' hoac '+re.escape(b)+r'(?:\s+.*)?',fold(raw))
            for a,b in (sorted(parts),sorted(parts,reverse=True)))),None)
        if not pair:
            continue
        alternatives=next((tuple(names) for names in (sorted(pair),sorted(pair,reverse=True))
                           if fold(raw).startswith(' hoac '.join(names))))
        literal=' hoac '.join(alternatives)
        actual_suffix=raw[len(literal):].strip()
        suffix=fold(actual_suffix)
        quantity=QUANTITY.fullmatch(suffix)
        if not quantity and not re.fullmatch(r'(?:1 it|'+QUALIFIER+r'|\(tuy thich\))',suffix):
            continue
        names=re.compile('|'.join(exact_word(n) for n in alternatives))
        usages=[]
        for step in steps:
            body=fold(step['text'])
            if not names.search(body):continue
            matches=list(re.finditer(exact_word(literal),body))
            if len(matches)!=1 or len(list(names.finditer(body)))!=2:
                break
            if step['section']=='prep':
                if ROLES[pair]!='AROMATIC_FINISH' or not re.fullmatch(
                    literal+r' (?:cat bo goc roi cat khuc|rua sach, cat nho)[.]?',body.lstrip('-• ')):
                    break
            elif not re.search(r'\b(?:rac|co the them|cho)\s+'+re.escape(literal)+r'\b',body):
                break
            elif step['section']=='steps' and not re.search(r'\bvao dao nhanh \d+(?:-\d+)? giay\b',body):
                break
            usages.append((step['id'], matches[0].start(), matches[0].end()))
        else:
            if usages and any(steps[i]['section']!='prep' for i,_,_ in usages):
                offers.append(dict(item=item,alternatives=alternatives,role=ROLES[pair],
                    amount=actual_suffix, quantity=quantity['value'].replace(',','.') if quantity else None,
                    unit=actual_suffix[quantity.start('unit'):quantity.end('unit')] if quantity else None,usages=usages))
    return offers


def option(row, old, new=None):
    from backend.chatbot.recipe_bindings_v2 import profile
    try:
        found=[s for s in choices(*profile(row)) if old in s['alternatives']
               and (new is None or new in s['alternatives'] and new!=old)]
    except (ValueError, TypeError):
        return None
    if len(found)!=1:return None
    chosen=found[0]
    return chosen | {'chosen':next(x for x in chosen['alternatives'] if x!=old)}

