"""LCEL theo phiên: NLP → context → truy hồi/gợi ý → trích xuất/template."""
import copy
import re
import time
from collections import Counter
from functools import lru_cache
from langchain_core.runnables import RunnableLambda
from backend.chatbot.che_do_du_lieu import chon_kho
from backend.chatbot.intent import phan_tich
from backend.chatbot.sinh_cau_tra_loi import mo_ta_nguon
from backend.chatbot.trang_thai import lay_trang_thai, cap_nhat, chon_theo_so, la_cau_noi_tiep
from backend.chatbot.cong_thuc import danh_muc, tu_vung_nguyen_lieu, goi_y_theo_dieu_kien, quy_doi_khau_phan, ten_nguyen_lieu
from backend.chatbot.phan_hoi import chon_phan_hoi
from backend.chatbot.ngon_ngu import chuan_hoa, chuan_hoa_dia_phuong, khoa_cau_hoi


def _empty(message, suggestions=()):
    return {'cau_tra_loi': message, 'loai':'khong_chac', 'nguon':[], 'goi_y':list(suggestions),
            'nhan_goi_y':'Chọn nội dung bạn muốn xem:', 'doan_truy_hoi':[], 'chu_de':None,
            'giai_thich':{}}


# Strip only framing around a request. Keep punctuation inside the question
# because it delimits negation, ingredient lists and separate requests.
_SOURCE_REQUEST = re.compile(
    r"[,.!?; ]+(?:và |rồi )?(?:(?:cho|gửi) (?:mình|tôi|tui|em) (?:biết |xin )?"
    r"(?:nguồn(?: tham khảo)?|tài liệu tham khảo)|(?:dẫn|trích|kèm) nguồn)"
    r"(?: (?:tham khảo|luôn|với|nhé|nha))?[ ?!.]*$", re.I,
)
_FRAMING = re.compile(
    r"^(?:(?:bạn )?giải thích (?:giúp|cho) (?:mình|tôi|em)|"
    r"chỉ (?:mình|tôi|em) với(?: (?:nghen|hen|nhé))?|"
    r"(?:bạn ơi|cho mình hỏi|xin hỏi))\s*[:,-]?\s+",
    re.I,
)


def _search_question(question):
    text = chuan_hoa_dia_phuong(question)
    text = _SOURCE_REQUEST.sub('', text)
    text = _FRAMING.sub('', text)
    return re.sub(r"\s+(?:nghen|hen)[ ?!.]*$", '', text, flags=re.I).strip()


def _question_words(text):
    return tuple(re.findall(r"\w+", chuan_hoa_dia_phuong(text).casefold()))


@lru_cache(maxsize=2048)
def _title_words(title):
    return _question_words(title)


@lru_cache(maxsize=2048)
def _title_key(title):
    return khoa_cau_hoi(title)


def _same_query_words(query, title):
    """Allow missing accents and a single doubled key, keeping accented words."""
    if len(query) != len(title):
        return False
    repairs = 0
    for given, expected in zip(query, title):
        if given == expected or (given.isascii() and given == chuan_hoa(expected)):
            continue
        collapsed = re.sub(r"(\w)\1+", r"\1", given)
        if collapsed == given or collapsed not in (expected, chuan_hoa(expected) if given.isascii() else expected):
            return False
        repairs += 1
    return repairs <= 1


def _reviewed_query(payload, manifest, ledger, question):
    """Resolve unambiguous variants through the existing authorized FAQ gate."""
    from backend.chatbot.source_qa_gate import route
    state = payload['state']
    if (state.get('tinh_trang_suc_khoe') or state.get('di_ung') or state.get('di_ung_chua_ro')
            or any(state['dieu_kien'].get(k) for k in ('loai_tru', 'chua_ro', 'an_chay'))):
        return None
    words = _question_words(question)
    if len(words) < 4:
        return None
    matches = [row for row in ledger.values()
               if _same_query_words(words, _title_words(row['question']))]
    if len(matches) != 1:
        return None
    row = matches[0]
    if row['decision'] != 'ALLOW_V3_REVIEWED_EXACT':
        return None
    if _SOURCE_REQUEST.search(chuan_hoa_dia_phuong(payload['question'])) and not row['source'].strip():
        return None
    return route({**payload, 'question': row['question']}, manifest, ledger)


_STEP_QUESTION = re.compile(
    r'\b(?:(?:buoc|khau|giai doan) (?:nao|\d+)|(?:khi|luc) nao|canh lua|thu tu|'
    r'(?:cho|bo|them) vao .+? nhu the nao)\b'
)
_STEP_FOLLOWUP = re.compile(
    r'(?:(?:nen\s+)?(?:cho|bo|them)\s+(?P<leading_item>(?:[a-z]+\s+){0,4}[a-z]+)'
    r'|(?P<item>(?:[a-z]+\s+){0,4}[a-z]+)\s+(?:nen\s+)?(?:cho|bo|them))\s+vao\s+'
    r'(?:o\s+)?(?:buoc|khau|giai doan)\s+nao(?:\s+(?:vay|nhe))?[?!.]*'
)
_RECIPE_REQUEST = re.compile(
    r'\b(?:huong dan|cong thuc|chuan bi|bat dau|lam sao|the nao|nau sao|'
    r'kho|xao|chien|hap|nuong|rang|khia|chung|goi|luoc|lau|canh|chao)\b'
)
_RECIPE_FILLERS = set(('minh toi tui ban chi bay hay lam cho voi cung va vao noi bang cua de '
                       'nay dem muon co nau theo kieu vung thi sao thuong chung can').split())
_RECIPE_GROUPS = ('02_huong_dan_nau_an','03_huong_dan_nau_mon_mien_tay')


def _recipe_identity(question):
    # Remove question framing, keeping distinctive ingredient and locality words.
    question = re.sub(
        r'\b(?:thi )?(?:cho|bo|them) vao (?:o )?(?:buoc|khau|giai doan) nao '
        r'(?:khi|luc) (?:lam|nau|che bien)\b',' ',question
    )
    q = re.split(
        r'\b(?:thi|lam sao|lam the nao|nau sao|chuan bi|muon thit|can nhung|'
        r'(?:o )?(?:buoc|khau) (?:nao|\d+)|de (?:thom|giu|an)|cho bua com|'
        r'bat dau|nhu the nao|canh lua|thu tu)\b',question,maxsplit=1
    )[0]
    q = re.sub(r'\b(?:huong dan|nguyen lieu nao|tai nha|o nha|cho ca nha|nha que|'
               r'bua nay|hom nay|tu dau|sao cho|(?:cho|bo|them) vao)\b',' ',q)
    q = re.split(r',\s*(?:lam|chi|bay)\b',q,maxsplit=1)[0]
    return Counter(word for word in re.findall(r'\w+',q) if word not in _RECIPE_FILLERS)


def _source_step(row, recipe, question, followup=None):
    from backend.chatbot.recipe_views_v5 import document, step_spans

    spans = step_spans(row)
    numbered = re.search(r'\bbuoc (\d+)\b',question)
    if numbered:
        heading = re.compile(r'^(?:buoc\s+)?'+re.escape(numbered[1])+r'(?:\b|[.)])')
        matches = [span for span in spans if heading.match(
            chuan_hoa(row['answer_text'][span['start']:span['end']].splitlines()[0])
        )]
        return matches[0] if len(matches)==1 else None
    if not followup and not re.search(r'\b(?:cho|bo|them) vao\b',question):
        return None
    names = {ten_nguyen_lieu(line) for line in recipe.nguyen_lieu}
    names.discard('')
    if followup:
        item = followup['item'] or followup['leading_item']
        if item not in names:
            return None
    else:
        ordered = sorted(names,key=lambda name:(-len(name),name))
        item = next((name for name in ordered if re.match(r'^'+re.escape(name)+r'\b',question)),None)
        if not item:
            item = next((name for name in ordered if re.search(
                r'\b(?:cho|bo|them) '+re.escape(name)+r'\b',question)),None)
    section = document(row)['sections'].get('steps')
    if not item or not section:
        return None
    addition = re.compile(r'\b(?:cho|them|tron)\s+'+re.escape(item)+r'\b(?!\s+(?:ra|di|khoi)\b)')
    matches = []
    for span in spans:
        text = row['answer_text'][span['start']:span['end']].strip()
        if (section['start'] <= span['start'] and span['end'] <= section['end']
                and text.startswith(('-','•')) and addition.search(chuan_hoa(text))):
            matches.append(span)
    return matches[0] if len(matches)==1 else None


def _retrieved_recipe(payload, manifest, ledger, question, *, followup=None):
    from backend.chatbot.chuoi_langchain import truy_hoi_langchain
    from backend.chatbot.fuzzy import de_nghi_ten_mon
    from backend.chatbot.recipe_views_v5 import (
        RECIPE_REFERENCE, INGREDIENT_REQUEST, _check_recipe, _surface_score, document,
        recipe_aliases, recipe_option_label, recipe_read_view, reference, render_view, view,
    )

    q = chuan_hoa(question)
    p = payload['parsed']
    state = payload['state']
    intents = set(p['intents'])
    if (payload.get('choice') or payload.get('error') or p.get('khau_phan')
            or state.get('tinh_trang_suc_khoe')
            or (state.get('health_context_v5') or {}).get('active')
            or intents & {'dieu_chinh_nguyen_lieu','thay_the','hoi_chi_so_dinh_duong','bao_quan'}
            or re.search(r'\b(?:di ung|chan doan|dieu tri|thuoc|calo|kcal|natri|protein|'
                         r'thay bang|bo nguyen lieu|sua cong thuc|doi mon|goi y|an gi|mon nao)\b',q)):
        return None
    if not followup and not (_RECIPE_REQUEST.search(q)
            or intents & {'cong_thuc','nguyen_lieu','che_bien'}):
        return None
    current = (payload['previous'].get('mon_hien_tai') or {}).get('id_goc')
    if (followup and not current) or (not followup and re.search(RECIPE_REFERENCE,q)):
        return None

    recipes = [recipe for recipe in danh_muc(payload['kho'])
               if recipe.id_goc in ledger and ledger[recipe.id_goc]['allowed_for_answer']
               and ledger[recipe.id_goc]['scope']=='IN_SCOPE'
               and (payload['mode']!='evaluation' or ledger[recipe.id_goc]['split']=='Train')
               and ledger[recipe.id_goc]['group_folder'] in _RECIPE_GROUPS
               and recipe.id_goc not in manifest.get('demo_excluded_recipe_ids',())]
    needs_confirmation = False
    exact_names = set()
    if followup:
        matching = [recipe for recipe in recipes if recipe.id_goc==current]
        ranks = {current:0}
        retrieval_mode = 'memory'
    else:
        identity = _recipe_identity(q)
        if len(identity)<2 or re.search(r'\b(?:hoac|hay la|so sanh|khac nhau)\b',q):
            return None
        matching = []
        for recipe in recipes:
            if _surface_score(question,recipe.cau_hoi)<0:
                continue
            aliases = recipe_aliases(recipe)
            if any(identity <= Counter(alias.split()) for alias in aliases):
                matching.append(recipe)
                if any(identity == _recipe_identity(alias) for alias in aliases):
                    exact_names.add(recipe.id_goc)
        if not matching:
            needs_confirmation = True
            fuzzy = set(de_nghi_ten_mon(question,payload['kho']))
            matching = [recipe for recipe in recipes if recipe.cau_hoi in fuzzy]
            if not matching:
                return None
        opts = {'loc_tap':['Train']} if payload['mode']=='evaluation' else {}
        found = truy_hoi_langchain(question,k=5,kho=payload['kho'],loc_nhom=list(_RECIPE_GROUPS),**opts)
        ranks = {row['id_goc']:i for i,row in enumerate(found['doan'])}
        retrieval_mode = found['che_do_truy_hoi']

    eligible = [recipe for recipe in matching if not _check_recipe(ledger[recipe.id_goc],state)[0]]
    if needs_confirmation or len(eligible)!=1:
        # Auxiliary signals may order matching sources for confirmation,
        # but never decide which explicit dish the user intended.
        if eligible and not _STEP_QUESTION.search(q):
            keywords = [chuan_hoa(word) for word in p.get('tu_khoa_chinh',())]
            candidates = [r for r in eligible if r.id_goc in ranks
                          and (needs_confirmation or r.id_goc in exact_names)]
            candidates.sort(key=lambda r:(ledger[r.id_goc]['group']!=p.get('nhom_ml'),
                -sum(word in chuan_hoa(r.cau_hoi) for word in keywords),ranks[r.id_goc]))
            labels = Counter(recipe_option_label(r.cau_hoi) for r in candidates)
            rows = [ledger[r.id_goc] for r in candidates if labels[recipe_option_label(r.cau_hoi)]==1][:3]
            if rows:
                result = _empty('Bạn chọn đúng công thức giúp mình nhé.',[row['question'] for row in rows])
                result.update(reason_code='RECIPE_OPTIONS',nguon=[reference(row) for row in rows])
                return result
        return None

    recipe = eligible[0]
    if recipe.id_goc not in ranks:
        # A specific step can dilute the dish name in the search query.
        # Retry using the one complete identity validated against the catalog.
        found = truy_hoi_langchain(recipe.cau_hoi,k=5,kho=payload['kho'],
                                   loc_nhom=list(_RECIPE_GROUPS),**opts)
        if not any(item['id_goc']==recipe.id_goc for item in found['doan']):
            return None
        retrieval_mode = found['che_do_truy_hoi']
    row = ledger[recipe.id_goc]
    trial = copy.deepcopy(state)
    try:
        value = recipe_read_view(row,trial,q)
        if _STEP_QUESTION.search(q):
            if value['mode']=='recipe_edit':
                return None  # A source step cannot describe an edited recipe safely.
            if re.search(r'\bthu tu\b',q):
                value = view(row,'steps',trial.get('khau_phan'))
            else:
                step = _source_step(row,recipe,q,followup)
                if step is None:
                    return None
                value = view(row,'step',trial.get('khau_phan'),selector=step)
        elif value['mode']=='full' and (re.search(INGREDIENT_REQUEST,q) or 'nguyen_lieu' in intents):
            value = view(row,'ingredients')
        elif value['mode']=='full' and re.search(r'\b(?:so che|lam sach|khu tanh)\b',q):
            value = view(row,'prep')
        elif value['mode']=='full' and 'steps' not in document(row)['sections']:
            return None
        if value['mode']!='recipe_edit':
            render_view(row,value)
    except (ValueError,KeyError,TypeError,ZeroDivisionError):
        return None
    payload['state'] = trial
    return dict(loai='tra_loi',reason_code='EDIT_REWRITTEN' if value['mode']=='recipe_edit' else 'SOURCE_UNVERIFIED',
                cau_tra_loi='',nguon=[reference(row)],goi_y=[],doan_truy_hoi=[],
                chu_de={'id_goc':row['id'],'cau_hoi':row['question']},structured_view=value,
                giai_thich={'che_do_truy_hoi':retrieval_mode})


@lru_cache(maxsize=1)
def chuoi_hoi_thoai():
    def prepare(payload):
        started = time.perf_counter()
        kho, mode = chon_kho(payload['options'])
        from backend.chatbot.knowledge_policy import sanitize_history
        payload['history'] = sanitize_history(payload['history'], kho)
        from backend.chatbot.knowledge_policy import policy
        selected_policy=policy(kho)
        nlp_question = _search_question(payload['question']) or payload['question']
        if selected_policy and selected_policy[0].get('runtime_policy_version')==5:
            from backend.chatbot.health_context_v5 import food_text
            nlp_question=food_text(nlp_question)
        parsed = phan_tich(nlp_question, tu_vung_nguyen_lieu(kho))
        parsed['cau_goc']=payload['question']
        if ('ngoai_pham_vi' not in parsed['intents'] and 'hoi_nguon' not in parsed['intents']
                and _SOURCE_REQUEST.search(chuan_hoa_dia_phuong(payload['question']))):
            parsed['intents'].append('hoi_nguon')
        previous = lay_trang_thai(payload['history'])
        if 'tinh_trang_suc_khoe' not in previous:
            from backend.chatbot.suc_khoe import cap_nhat as cap_nhat_suc_khoe
            for turn in payload['history']:
                previous['tinh_trang_suc_khoe'] = cap_nhat_suc_khoe(previous.get('tinh_trang_suc_khoe'),turn.get('cau_hoi',''))
        # Tương thích lịch sử trước phiên bản trạng thái có cấu trúc.
        if not previous.get('mon_hien_tai') and not any(isinstance(h.get('trang_thai'), dict) for h in payload['history']):
            previous['mon_hien_tai'] = next((h['chu_de'] for h in reversed(payload['history']) if h.get('chu_de')), None)
        if not any(h.get('trang_thai') for h in payload['history']) and payload['history']:
            from backend.chatbot.ngon_ngu import dieu_kien
            from backend.chatbot.suc_khoe import cap_nhat as cap_nhat_suc_khoe
            previous['dieu_kien'] = dieu_kien('', payload['history'])
            for turn in payload['history']:
                previous['tinh_trang_suc_khoe'] = cap_nhat_suc_khoe(previous.get('tinh_trang_suc_khoe'),turn.get('cau_hoi',''))
        outside = parsed['intents'] == ['ngoai_pham_vi']
        state = copy.deepcopy(previous) if outside else cap_nhat(previous, parsed)
        choice, error = (None, None) if outside else chon_theo_so(payload['question'], previous)
        if choice:
            state['mon_hien_tai'] = choice
        if not outside:
            if 'goi_y_mon' in parsed['intents']:
                # Keep request-local analysis together while persistent
                # preferences/allergies still come from cap_nhat.
                state['phan_tich_goi_y'] = {
                    key:list(parsed.get(key, ())) for key in (
                        'nguyen_lieu_lua_chon','nguyen_lieu_khong_co','nguyen_lieu_khong_muon_dung')
                }
                state['phan_tich_goi_y']['cho_phep_mua_them'] = bool(parsed.get('cho_phep_mua_them'))
            if parsed.get('nguyen_lieu_co'):
                state.pop('nguyen_lieu_bat_buoc', None)
            required = parsed.get('nguyen_lieu_bat_buoc', ())
            if required:
                state['nguyen_lieu_bat_buoc'] = list(required)
        scoped = {key: parsed[field] for key, field in (
            ('di_ung','di_ung_theo_luot'), ('di_ung_chua_ro','di_ung_theo_luot_chua_ro')
        ) if parsed.get(field)}
        saved_allergies = {key:state.get(key,[]) for key in scoped}
        for key, values in scoped.items():
            state[key] = sorted(set(saved_allergies[key]) | set(values))
        return {**payload, 'started':started, 'kho':kho, 'mode':mode, 'parsed':parsed, 'state':state,
                'previous':previous, 'choice':choice, 'error':error,
                'scoped_allergies':scoped, 'saved_allergies':saved_allergies}

    def answer(payload):
        from backend.chatbot.sinh_cau_tra_loi import _tra_loi_truy_hoi, mo_ta_nguon, nhan_dien_xa_giao
        from backend.chatbot.doi_chieu import chi_muc_cau_hoi
        from backend.chatbot.fuzzy import de_nghi_ten_mon
        p, state, q, kho = payload['parsed'], payload['state'], payload['question'], payload['kho']
        from backend.chatbot.knowledge_policy import policy
        knowledge_policy = policy(kho)
        intents = set(p['intents'])
        from backend.chatbot.recipe_views_v5 import limitation
        followup = _STEP_FOLLOWUP.fullmatch(chuan_hoa(q))
        if followup and knowledge_policy and knowledge_policy[0].get('runtime_policy_version')==5:
            from backend.chatbot.health_context_v5 import analyze
            health = analyze(q,state.get('health_context_v5'))
            if not (health['health_need'] or health['cure_question']):
                recovered = _retrieved_recipe(payload,*knowledge_policy,q,followup=followup)
                if recovered:
                    p['intents'] = ['che_bien']
                    payload['result'] = recovered
                    return payload
        if p['intents'] == ['ngoai_pham_vi']:
            payload['result'] = limitation('OUT_OF_SCOPE')
            return payload
        if payload['error']:
            payload['result'] = limitation('RECIPE_CLARIFICATION')
            return payload
        search = _search_question(q) or q
        folded = chuan_hoa(search)
        if (not state.get('mon_hien_tai') and not (intents & {'goi_y_mon','thong_tin'})
                and re.fullmatch(
                    r'(?:(?:huong dan|chi (?:minh|toi)) (?:cach )?(?:nau|lam) )?'
                    r'(?:mon (?:do|nay|tren|vua chon)|cong thuc (?:do|nay|tren))'
                    r'(?: (?:di|voi|nhe|thi sao))*[?!.]*',folded)):
            payload['result'] = limitation('RECIPE_CLARIFICATION')
            return payload
        suggest_first = bool('goi_y_mon' in intents
                             and (intents & {'goi_y_theo_nguyen_lieu','goi_y_dinh_duong'}
                                  or state.get('nguyen_lieu_bat_buoc')))
        pending = state.get('yeu_cau_dang_cho') or {}
        if suggest_first and not payload['choice']:
            pending = dict(nau='cong_thuc' in intents,calo='hoi_chi_so_dinh_duong' in intents,
                           nguon='hoi_nguon' in intents,khau_phan=p.get('khau_phan'))
            if any(pending.values()):
                state['yeu_cau_dang_cho'] = pending
            else:
                state.pop('yeu_cau_dang_cho', None)
        if knowledge_policy:
            from backend.chatbot.source_qa_gate import route as source_qa_route
            source_qa = source_qa_route(payload, *knowledge_policy)
            if source_qa is not None:
                payload['result'] = source_qa
                return payload
        if knowledge_policy and knowledge_policy[0].get('excel_calorie_estimates') and not suggest_first:
            from backend.chatbot.excel_calo_gate import route
            calorie_payload = payload
            if state.get('mon_hien_tai') and re.fullmatch(
                    r'(?:(?:vay|con)\s+)?(?:bao nhieu (?:calo|kcal)|(?:calo|kcal) bao nhieu)[?!.]*',folded):
                current = state['mon_hien_tai']
                pending_count = pending.get('khau_phan') if pending.get('recipe_id')==current['id_goc'] else None
                if pending_count and pending_count!=state.get('khau_phan'):
                    calorie_payload = {**payload,'question':f'Nấu món này cho {pending_count} người thì bao nhiêu calo?'}
                else:
                    pending_count = None
                    calorie_payload = {**payload,'question':'Món này '+q}
            else:
                pending_count = None
            estimate = route(calorie_payload, *knowledge_policy)
            if pending_count and (not estimate or
                    (estimate.get('giai_thich', {}).get('calo') or {}).get('servings')!=pending_count):
                estimate = limitation('MISSING_NUTRITION',state['mon_hien_tai'])
            if estimate is not None:
                payload['result'] = estimate
                return payload
        if knowledge_policy and knowledge_policy[0].get('runtime_policy_version') in (4,5):
            if knowledge_policy[0]['runtime_policy_version']==5:
                from backend.chatbot.recipe_views_v5 import route
            else:
                from backend.chatbot.recipe_views import route
            route_payload = payload
            protected = bool(state.get('tinh_trang_suc_khoe') or
                             (state.get('health_context_v5') or {}).get('active'))
            if knowledge_policy[0]['runtime_policy_version'] == 5 and not protected:
                from backend.chatbot.health_context_v5 import analyze
                health_context = analyze(q, state.get('health_context_v5'))
                protected = health_context['health_need'] or health_context['cure_question']
                question_key = khoa_cau_hoi(q)
                if not protected and not any(
                    not row['allowed_for_answer'] and question_key == _title_key(row['question'])
                    for row in knowledge_policy[1].values()
                ):
                    reviewed = _reviewed_query(payload, *knowledge_policy, search)
                    if reviewed is not None:
                        payload['result'] = reviewed
                        return payload
                    current = state.get('mon_hien_tai')
                    if current and re.fullmatch(
                        r'(?:huong dan|chi minh) (?:cach )?(?:nau|lam|che bien) '
                        r'(?:mon (?:do|nay|tren|luc nay)|cong thuc (?:tren|vua roi))'
                        r'(?: di| voi| nhe)?[?!.]*', chuan_hoa(search)
                    ):
                        route_payload = {**payload, 'question': current['cau_hoi']}
                    elif current and not payload['choice'] and re.fullmatch(
                            r'(?:(?:huong dan|chi (?:minh|toi)) )cach (?:nau|lam)(?: (?:di|voi|nhe))?[?!.]*',folded):
                        route_payload = {**payload,'question':current['cau_hoi']}
                    elif search != q:
                        route_payload = {**payload, 'question': search}
            structured = route(route_payload, *knowledge_policy)
            # The recipe router clears prior requirements when it sees a new
            # pantry list. Preserve explicit requirements supplied by intent
            # for the final common validation, without updating source rows.
            required = p.get('nguyen_lieu_bat_buoc')
            if required:
                state['nguyen_lieu_bat_buoc'] = list(required)
            if (suggest_first and not payload['choice'] and not protected
                    and not (state.get('health_context_v5') or {}).get('active')
                    and knowledge_policy[0]['runtime_policy_version']==5
                    and (structured is None or structured.get('reason_code') in ('MISSING_DISH','NUTRITION_CONTEXT_REQUIRED','MISSING_NUTRITION'))
                    and not state.get('dieu_kien', {}).get('can_dinh_luong')):
                from backend.chatbot.recipe_views_v5 import reference, simple_recipe_options
                manifest, ledger = knowledge_policy
                excluded = set(manifest.get('demo_excluded_recipe_ids', ()))
                choices = simple_recipe_options(
                    folded, (recipe for recipe in danh_muc(kho) if recipe.id_goc not in excluded),
                    ledger, state,
                )
                if choices:
                    state['mon_hien_tai'] = None
                    state['goi_y_cho_calo'] = bool(pending.get('calo'))
                    structured = limitation('MISSING_CONDITIONAL_RECIPE')
                    structured.update(reason_code='RECIPE_OPTIONS',nguon=[reference(row) for row in choices],
                                      goi_y=[row['question'] for row in choices])
                elif state.get('dieu_kien', {}).get('nhu_cau'):
                    structured = limitation('MISSING_NUTRITION')
            if (payload['choice'] and pending.get('khau_phan') and structured
                    and structured.get('structured_view') and knowledge_policy[0]['runtime_policy_version']==5):
                trial_state = copy.deepcopy(state)
                portions = route({**payload,'state':trial_state,
                                  'question':f"Nếu nấu cho {pending['khau_phan']} người thì sao?"},*knowledge_policy)
                if (portions and portions.get('structured_view')
                        and (portions.get('chu_de') or {}).get('id_goc')==payload['choice']['id_goc']
                        and trial_state.get('khau_phan')==pending['khau_phan']):
                    structured = portions
                    state = trial_state
                    payload['state'] = state
            if (structured and not protected and structured.get('reason_code') == 'RECIPE_OPTIONS'
                    and p.get('nguyen_lieu_co')
                    and 'cong_thuc' in intents
                    and 'hoi_chi_so_dinh_duong' not in intents
                    and not p.get('khau_phan')
                    and len(structured.get('goi_y', ())) == 1):
                for title in structured.get('goi_y', ())[:1]:
                    candidate_state = copy.deepcopy(state)
                    detail = route({**payload, 'question': title, 'state': candidate_state}, *knowledge_policy)
                    if detail and detail.get('structured_view'):
                        structured = detail
                        payload['state'] = candidate_state
            if (structured and structured.get('reason_code') in ('RECIPE_CLARIFICATION','MISSING_DISH')
                    and not protected and not suggest_first and knowledge_policy[0]['runtime_policy_version']==5):
                recovered = _retrieved_recipe(payload,*knowledge_policy,search)
                if recovered:
                    structured = recovered
            if structured is not None:
                technical = re.search(
                    r'\b(?:tai sao|vi sao|de lam gi|(?:sao cho|lam sao (?:de|cho)) (?:khoi|khong))\b',
                    chuan_hoa(search),
                )
                if technical and structured.get('reason_code') in ('RECIPE_OPTIONS', 'DISH_FAMILY_OPTIONS'):
                    payload['state']['mon_hien_tai'] = payload['previous'].get('mon_hien_tai')
                    structured = route({**payload, 'question': q}, *knowledge_policy) if protected else None
                    if structured is None:
                        from backend.chatbot.recipe_views_v5 import limitation
                        structured = limitation('TECHNIQUE_SOURCE_MISSING')
                payload['result'] = structured
                return payload
        if knowledge_policy and any(khoa_cau_hoi(q) == khoa_cau_hoi(row['question'])
                                    and not row['allowed_for_answer']
                                    for row in knowledge_policy[1].values()):
            payload['result'] = _empty('Nội dung đang chờ kiểm duyệt.')
            return payload
        from backend.chatbot.suc_khoe import id_co_bang_chung, thong_bao_thieu
        health = [] if nhan_dien_xa_giao(q) else state.get('tinh_trang_suc_khoe', [])
        food_request = not ('thong_tin' in p['intents'] and not set(p['intents']) & {'goi_y_mon','cong_thuc','che_bien','nguyen_lieu'})
        health_ids = id_co_bang_chung(kho,tuple(health),food_request) if health else None
        current = state.get('mon_hien_tai')
        if health and not health_ids:
            result = _empty(thong_bao_thieu(health))
        elif payload['error']:
            result = _empty(payload['error'])
        else:
            
            nau_nhanh = 'nau_nhanh' in p['intents']

            constrained = bool(
                state.get('nguyen_lieu_co')
                or state.get('thoi_gian_toi_da') is not None
                or state.get('khong_chien')
                or nau_nhanh
            )

            exact = bool(
                chi_muc_cau_hoi(kho).get(khoa_cau_hoi(q))
            )

            
            recommend = (
                ('goi_y_mon' in p['intents'] or nau_nhanh)
                and constrained
                and (not exact or nau_nhanh)
            )

            if recommend:
                options = goi_y_theo_dieu_kien(kho, state)
                if not options:
                    result = _empty('Mình chưa tìm được công thức có đủ dữ liệu để đáp ứng đồng thời các điều kiện này. Bạn có thể bổ sung nguyên liệu hoặc nới giới hạn thời gian không?')
                else:
                    
                    lines = [
                        "Mình gợi ý bạn một vài món có thời gian "
                        "chế biến ngắn trong kho công thức nhé!"
                        if nau_nhanh else
                        "Mình tìm được một vài món phù hợp "
                        "với yêu cầu của bạn:"
                    ]

                    
                    for i, (_, _, recipe, missing) in enumerate(options, 1):
                        ten_mon = recipe.cau_hoi.strip()

                        # Bỏ phần mở đầu của câu hỏi.
                        ten_mon = re.sub(
                            r'^(?:cách nấu|cách làm|hướng dẫn nấu|'
                            r'hướng dẫn làm|nấu|làm)\s+',
                            '',
                            ten_mon,
                            flags=re.IGNORECASE
                        )

                        # Bỏ phần hỏi ở cuối, giữ dấu tiếng Việt.
                        ten_mon = re.sub(
                            r'\s+(?:như thế nào|ra sao|làm sao|'
                            r'nấu thế nào|nấu sao)\s*[?!.]*$',
                            '',
                            ten_mon,
                            flags=re.IGNORECASE
                        )

                        ten_mon = ten_mon.strip(" ?!.").capitalize()

                        if recipe.tong_phut is not None:
                            lines.append(
                                f"{i}. **{ten_mon}** — {recipe.tong_phut} phút"
                            )
                        else:
                            lines.append(f"{i}. **{ten_mon}**")

                        if state.get("nguyen_lieu_co") and missing:
                            raw_missing = [
                                line.lstrip("- ")
                                for line in recipe.nguyen_lieu
                                if ten_nguyen_lieu(line) in missing
                            ]
                            lines.append(
                                "   Cần thêm theo nguồn: "
                                + ", ".join(raw_missing) + "."
                            )

                    lines.append(
                        "Bạn chọn món muốn nấu nhé, "
                        "mình sẽ hướng dẫn nguyên liệu "
                        "và cách làm chi tiết."
                    )

                    result = _empty(
                        "\n\n".join(lines),
                        [r[2].cau_hoi for r in options]
                    )

                    result["nguon"] = [
                        mo_ta_nguon(dict(r[2].metadata, diem=0.0))
                        for r in options
                    ]

            else:
                # Không fuzzy-sửa một câu có điều kiện tránh/dị ứng.
                dk = state['dieu_kien']
                protected = bool(dk['loai_tru'] or dk['chua_ro'] or dk['an_chay'])
                proposals = de_nghi_ten_mon(q, kho) if not protected and not la_cau_noi_tiep(q) and not payload['choice'] else []
                if proposals:
                    result = _empty('Tên món bạn nhập có thể bị gõ nhầm. Ý bạn là công thức nào dưới đây? Mình chờ bạn xác nhận để không đổi nhầm món.', proposals)
                else:
                    tc = {**payload['options'], 'kho':kho, 'dieu_kien':dk}
                    if current and (payload['choice'] or la_cau_noi_tiep(q)) and 'thay_the' not in p['intents']:
                        tc['id_chu_de'] = current['id_goc']
                    result = _tra_loi_truy_hoi(p['cau_chuan'], payload['history'], tc)
                    # Một công thức đúng món chưa chắc trả lời được bảo quản/thay thế.
                    # Không dùng ngữ cảnh để biến câu hỏi đó thành yêu cầu nấu lại.
                    aspects = set(p['intents']) & {'bao_quan','thay_the'}
                    if aspects and current and la_cau_noi_tiep(q) and result['loai'] == 'tra_loi':
                        from backend.chatbot.sinh_cau_tra_loi import noi_dung_day_du
                        source_text = '\n'.join(noi_dung_day_du(kho,n['id_goc']) for n in result['nguon'])
                        support = {'bao_quan':r'\b(bao quan|tru dong|cap dong|tu lanh)\b',
                                   'thay_the':r'\b(thay bang|thay the|co the dung .+ thay)\b'}
                        if not all(re.search(support[a],chuan_hoa(source_text)) for a in aspects):
                            name = 'bảo quản' if 'bao_quan' in aspects else 'thay thế nguyên liệu'
                            result = _empty(f"Mình đang giữ món **{current['cau_hoi']}**, nhưng nguồn vừa tìm chưa có hướng dẫn {name} đủ rõ cho yêu cầu này. Bạn nêu cụ thể nguyên liệu hoặc cách bảo quản muốn hỏi để mình tìm tiếp nhé.")
                    if current and not aspects and tc.get('id_chu_de') is not None and result['loai'] == 'khong_chac' and not result['nguon']:
                        details = ', '.join(dk['loai_tru'])
                        reason = f' điều kiện tránh {details}' if details else ' các điều kiện đang giữ'
                        result['cau_tra_loi'] = (f"Mình vẫn đang giữ món **{current['cau_hoi']}**. "
                            f"Công thức trong nguồn chưa đáp ứng{reason}; mình chưa có phiên bản đã kiểm chứng để tự thay nguyên liệu. "
                            + (f"Mình đã ghi nhận khẩu phần {state['khau_phan']} người. " if state.get('khau_phan') else '')
                            + 'Bạn có thể chọn món khác hoặc điều chỉnh yêu cầu. Các điều kiện dị ứng vẫn được giữ.')
        if health and health_ids:
            # Áp dụng cho cả nhánh truy hồi, fuzzy, gợi ý nguyên liệu và nút phụ.
            if any(n['id_goc'] not in health_ids for n in result.get('nguon', [])):
                result = _empty(thong_bao_thieu(health))
            allowed_titles = chi_muc_cau_hoi(kho)
            result['goi_y'] = [title for title in result.get('goi_y', [])
                              if set(allowed_titles.get(khoa_cau_hoi(title), {})) & health_ids]
            if result['loai'] == 'khong_chac':
                result['cau_tra_loi'] = ('Mình tìm được các tài liệu cùng chủ đề sức khỏe dưới đây. Bạn chọn nội dung muốn xem nhé.'
                                        if result['goi_y'] else thong_bao_thieu(health))
                result['nhan_goi_y'] = 'Chọn tài liệu cùng chủ đề sức khỏe:'
        payload['result'] = result
        return payload

    def finish(payload):
        from backend.chatbot.doi_chieu import chi_muc_cau_hoi
        result, state, p = payload['result'], payload['state'], payload['parsed']
        kho = payload['kho']
        if p['intents'] == ['ngoai_pham_vi']:
            from backend.chatbot.knowledge_policy import seal_result
            result['trang_thai'] = copy.deepcopy(payload['previous'])
            return seal_result(result,kho)
        pending = state.get('yeu_cau_dang_cho')
        topic = result.get('chu_de') or {}
        if pending is not None:
            bound = pending.get('recipe_id')
            if topic and bound is not None and topic.get('id_goc') != bound:
                state.pop('yeu_cau_dang_cho', None)
            else:
                pending = dict(pending)
                if topic:
                    pending['recipe_id'] = topic['id_goc']
                if result.get('structured_view', {}).get('mode') in ('full','recipe_edit'):
                    pending['nau'] = False
                if result.get('loai') == 'tra_loi' and result.get('nguon'):
                    pending['nguon'] = False
                if result.get('loai') == 'tra_loi' and (result.get('excel_calo_request') or result.get('nutrition_request')):
                    pending['calo'] = False
                if result.get('loai') == 'tra_loi' and result.get('structured_view') and pending.get('khau_phan')==state.get('khau_phan'):
                    pending['khau_phan'] = None
                if any(pending.get(field) for field in ('nau','calo','nguon','khau_phan')):
                    state['yeu_cau_dang_cho'] = pending
                else:
                    state.pop('yeu_cau_dang_cho', None)
        if result.get('chu_de'):
            state['mon_hien_tai'] = copy.deepcopy(result['chu_de'])
        if payload['choice'] and not result.get('chu_de'):
            state['mon_hien_tai'] = copy.deepcopy(payload['choice'])
        state['calo_hien_tai'] = bool(result.get('excel_calo_request'))
        state['de_xuat'] = []
        for title in result.get('goi_y', []):
            rows = chi_muc_cau_hoi(kho).get(khoa_cau_hoi(title), {})
            if rows:
                d = next(iter(rows.values()))
                state['de_xuat'].append({'id_goc':d['id_goc'], 'cau_hoi':title, 'kho':kho})
        if result.get('excel_calo_request'):
            state['de_xuat'] = [dict(item, kho=kho) for item in result.get('giai_thich', {}).get('calo_goi_y', [])]
        if (result.get('reason_code') != 'TECHNIQUE_SOURCE' and not result.get('structured_view')
                and not result.get('excel_calo_request') and state.get('khau_phan')
                and result['loai']=='tra_loi' and state.get('mon_hien_tai')):
            recipe = next((r for r in danh_muc(kho) if r.id_goc == state['mon_hien_tai']['id_goc']), None)
            if recipe:
                scaled = quy_doi_khau_phan(recipe, state['khau_phan'])
                if scaled and scaled['goc'] != scaled['dich']:
                    lines = [f"**Ước tính nguyên liệu cho {scaled['dich']} người** (nguồn gốc {scaled['goc']} người, hệ số {scaled['he_so']}):", *scaled['dong']]
                    if scaled['chua_quy_doi']:
                        lines += ['Các dòng chưa đủ định lượng để tự đổi:', *scaled['chua_quy_doi']]
                    lines.append('Không tự nhân thời gian nấu; gia vị và kích thước nguyên liệu cần điều chỉnh thực tế. Công thức gốc ở dưới để đối chiếu.')
                    result['cau_tra_loi'] = '\n\n'.join(lines)+'\n\n'+result['cau_tra_loi']
                elif not scaled:
                    result['cau_tra_loi'] = 'Nguồn chưa ghi rõ khẩu phần gốc nên mình chưa thể quy đổi định lượng chính xác.\n\n'+result['cau_tra_loi']
        result = chon_phan_hoi(result, payload['question'], p['intents'], payload['previous'].get('mau_phan_hoi'))
        state['can_lam_ro'] = result['loai'] == 'khong_chac'
        state['cau_hoi_can_lam_ro'] = payload['question'] if state['can_lam_ro'] else None
        state['mau_phan_hoi'] = result.get('mau_phan_hoi')
        state.update(payload['saved_allergies'])
        result['trang_thai'] = state
        if payload['scoped_allergies']:
            result['di_ung_theo_phan_hoi'] = payload['scoped_allergies']
        g = result.setdefault('giai_thich', {})
        from backend.chatbot.truy_hoi import nap_kho
        defaults = {'may_tim':nap_kho(kho)[2]['may_tim'], 'che_do_truy_hoi':'loc_cong_thuc',
                    'thoi_gian_giay':0.0, 'diem_cao_nhat':0.0, 'nguong_ngoai_pham_vi':None,
                    'nguong_tin_cay':None, 'cau_hoi_sach':p['cau_chuan'],
                    'cau_hoi_vao_mo_hinh':'', 'cau_hoi_viet_lai':None}
        for key,value in defaults.items():
            g.setdefault(key,value)
        g.update(framework='langchain', che_do_phan_hoi='trich_xuat_template', che_do_du_lieu=payload['mode'], intents=p['intents'], kho=kho)
        g['thoi_gian_giay'] = round(time.perf_counter()-payload['started'], 3)
        result['giai_thich'] = g
        if result.get('loai') in ('ngoai_pham_vi', 'khong_chac') or (g.get('diem_cao_nhat', 0) < 0.40 and not result.get('chu_de')):
            try:
                from backend.chatbot.tu_hoc import ghi_nhan_cau_hoi_cho_hoc
                from backend.chatbot.knowledge_policy import policy
                if not policy(kho):
                    ghi_nhan_cau_hoi_cho_hoc(payload['question'], result.get('loai', 'diem_thap'), g.get('diem_cao_nhat', 0), kho)
            except Exception:
                pass
        from backend.chatbot.knowledge_policy import seal_result
        return seal_result(result, kho)

    return RunnableLambda(prepare, name='nlp_va_trang_thai') | RunnableLambda(answer, name='chon_nguon_va_loc') | RunnableLambda(finish, name='response_selector')


def tra_loi_co_trang_thai(question, history=None, options=None):
    if not isinstance(question, str) or not question.strip():
        return _empty('Bạn nhập tên món hoặc nhu cầu ăn uống để mình tìm giúp nhé.')
    return chuoi_hoi_thoai().invoke({'question':question.strip(), 'history':history or [], 'options':options or {}}, config={'callbacks':[]})
