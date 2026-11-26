"""Lớp ước tính Excel: kiểm tra kho, quyền dùng công thức và tính lại khi hiển thị."""
import copy
import hashlib
import re
from fractions import Fraction

from backend.chatbot import calo


def health_text(question,kho):
    from backend.chatbot.cong_thuc import danh_muc
    from backend.chatbot.recipe_views_v5 import recipe_aliases
    q=calo.key(question)
    names={calo.key(r.cau_hoi) for r in danh_muc(kho)}
    names.update(a for r in danh_muc(kho) for a in recipe_aliases(r))
    for name in sorted(names,key=len,reverse=True):
        q=re.sub(r'(?<!\w)'+re.escape(name)+r'(?!\w)',' ',q)
    return q


def _current_nutrients(question, state):
    """Only extend the Excel gate to explicit nutrition queries on this dish."""
    from backend.chatbot.nutrition_runtime import METRICS
    q = calo.key(question)
    return bool(
        state.get('mon_hien_tai')
        and re.search(r'\b(?:mon (?:nay|do|tren)|cong thuc (?:nay|tren|hien tai)|bao nhieu|co nhieu)\b', q)
        and any(re.search(r'\b(?:'+METRICS[key]+r')\b', q) for key in METRICS if key != 'kcal')
        and not re.search(r'\b(?:goi y|mon nao|an gi|nau gi)\b', q)
    )


def _nutrition_followup(question, previous):
    # Bind only nutrition wording with no independent object to the current dish.
    from backend.chatbot.nutrition_runtime import COUNT, METRICS
    q = calo.key(question)
    if previous.get('calo_hien_tai') and re.fullmatch(
        r'(?:(?:con so|so lieu|nguon)(?: (?:nay|do|so lieu|nay ne))?(?: (?:lay|o|tu|dau|vay|a))+'
        r'|tinh lai(?: (?:cho|giup|tui|minh|toi|voi|nhe|nghen|di))*)', q,
    ):
        return 'energy'
    energy = bool(re.search(r'\b(?:'+METRICS['kcal']+r'|calories)\b', q))
    metrics = [metric for metric, words in METRICS.items() if metric != 'kcal'
               and re.search(r'\b(?:'+words+r')\b', q)]
    quantity = (r'\b(?:moi (?:khau phan|phan|nguoi)|'+COUNT+r' (?:khau phan|phan|nguoi)'
                r'|(?:1 2|1 4|nua)(?: (?:khau )?phan| me)?|mot phan tu(?: khau phan)?'
                r'|(?:ca|nguyen|toan bo) (?:me|noi|mon)|(?:100 ?g|100 gram|mot tram gam))\b')
    has_quantity = bool(re.search(quantity,q))
    asks = re.search(r'\b(?:bao nhieu|thi sao|the nao|tinh)\b',q)
    if not (asks and (energy or metrics or has_quantity and previous.get('calo_hien_tai'))):
        return None
    q = re.sub(quantity,' ',q)
    terms = '|'.join(METRICS.values())
    q = re.sub(r'\b(?:'+terms+r'|calories|bao nhieu|thi sao|the nao|'
               r'mon (?:nay|do|tren)|cong thuc (?:nay|do|hien tai)|'
               r'con|vay|co|la|thi|an|tinh|tren|cho|minh|toi|tui|giup|voi|nhe|nghen|nha|a|va|cua|duoc|khoang)\b',' ',q)
    if not q.strip():
        return 'metrics' if metrics and not energy else 'energy'
    return None


def _edit_command(question):
    """Reuse the recipe editor's typed commands, with serving wording aliases."""
    from backend.chatbot.recipe_edit_v1 import operation
    from backend.chatbot.recipe_views_v5 import PORTION_WORDS
    q = _scenario_text(question)
    if q.startswith('neu '):
        condition, separator, outcome = q[4:].partition(' thi ')
        if separator and _nutrition_words(outcome):
            q = condition
    q = re.sub(r'\bchia (?:(?:cung (?:mot )?|mot )me(?: hien tai)?|me hien tai)\b', 'chia me nay', q)
    q = re.sub(r'\b(cho|thanh|con) (\d+|'+'|'.join(PORTION_WORDS)+r') khau phan\b',
               r'\1 \2 phan',q)
    # Exact dish names with the accented forms do not start editing.
    if re.match(r'\s*(?:bò|bơ|bột)\b',question,re.I):
        return None
    try:
        return operation(q)
    except (ValueError, ZeroDivisionError):
        return None


def _nutrition_words(question):
    from backend.chatbot.nutrition_runtime import METRICS
    q = calo.key(question)
    return bool(re.search(r'\b(?:calories|dinh duong|'+ '|'.join(METRICS.values())+r')\b',q))


def _scenario_text(question):
    return re.sub(r'^(?:tinh thu|gia su)(?: neu)?\s+', 'neu ', calo.key(question))


def _serving_scenario(question):
    command = _edit_command(question)
    if not command or command['kind'] not in ('scale','divide') or not _nutrition_words(question):
        return None
    q = _scenario_text(question)
    if re.match(r'^(?:neu )?(?:nau|chia|doi)\b',q):
        return command
    return None


def _version_result(question, result, row, state, manifest, *, nutrients_only):
    from backend.chatbot.derived_nutrition import answer, descriptor
    from backend.chatbot.recipe_edit_v1 import active_for, base_edit, replay
    from backend.chatbot.recipe_views_v5 import document, limitation, reference, portion_transform
    from offline_nutrition.trust import NutritionError

    topic = dict(id_goc=row['id'], cau_hoi=row['question'])
    edited = active_for(row, state)
    portion = state.get('portion_state_v5') or {}
    portion_matches = (portion.get('recipe_id') == row['id']
                       and portion.get('recipe_version') == row['answer_sha256'])
    base = document(row)['base_portions']
    target = portion.get('target_applied') if portion_matches else None
    scenario = _serving_scenario(question)
    if not edited and not scenario and (target is None or target == base):
        return None

    context = limitation('MODIFICATION_UNSUPPORTED', topic)
    context['reason_code'] = 'CURRENT_NUTRITION_UNAVAILABLE'
    dk = state.get('dieu_kien', {})
    if (state.get('di_ung') or state.get('di_ung_chua_ro')
            or any(dk.get(k) for k in ('loai_tru','chua_ro','an_chay'))):
        context['cau_tra_loi'] = 'Chưa đủ dữ liệu để xác nhận công thức đáp ứng điều kiện ăn uống đang áp dụng. Mình chưa tính dinh dưỡng cho phiên bản này.'
        return context
    # A new hypothetical change is separate from the last applied recipe.
    if re.search(r'(?<!\w)(?:giam|bot luong|bo duong|bo nuoc mam|them|thay bang|tang)\b', calo.key(question)):
        context['cau_tra_loi'] = 'Mình cần phiên bản đã áp dụng và định lượng mới của nguyên liệu để tính phần thay đổi. Chưa dùng số của phiên bản cũ.'
        return context

    change = None
    if edited:
        try:
            change = descriptor(row, base_edit(row,state)['events'])
        except (NutritionError, ValueError, TypeError, KeyError, ZeroDivisionError):
            pass
        if change is not None and not scenario:
            metric = None
            if nutrients_only:
                from backend.chatbot.nutrition_runtime import METRICS
                matched = [k for k, words in METRICS.items()
                           if re.search(r'\b(?:'+words+r')\b',calo.key(question))]
                if len(matched)==1:
                    metric = matched[0]
            amount = re.search(r'\b(?:100 ?g|100 gram|mot tram gam|nua|mot phan tu|1 2|1 4|hai phan)\b',calo.key(question))
            licensed = None if amount else answer(row,state,manifest,metric)
            if licensed is not None:
                contract, data, text = licensed
                return dict(context, loai='tra_loi', reason_code='CURRENT_NUTRITION_CALCULATED',
                            cau_tra_loi=text, nguon=[reference(row)],
                            nutrition_result=data, giai_thich={'recipe_version':contract['recipe_version']})
        if change is not None:
            target = change['servings']
    if scenario:
        target = scenario['count']

    original = (result or {}).get('giai_thich',{}).get('calo')
    portions_only = change is not None and all(op['kind'] in ('scale','divide') for op in change['operations'])
    can_scale = (not nutrients_only and original and type(base) is int and original['servings']==base
                 and type(target) is int and 1<=target<=100 and (not edited or portions_only))
    if can_scale:
        if portion_matches and not scenario and not edited:
            portion_transform(row,target,portion.get('base_confirmation'))
        multiplier = Fraction(target,base)
        if scenario and scenario['kind']=='divide':
            multiplier = (Fraction(replay(row,base_edit(row,state)['events'])['scale']) if edited
                          else Fraction(portion.get('target_applied') or base,base) if portion_matches
                          else Fraction(1))
        elif not scenario and edited:
            multiplier = Fraction(replay(row,base_edit(row,state)['events'])['scale'])
        total = Fraction(str(original['total'])) * multiplier
        per = total / target
        # Keep the source and assumptions from the checked Excel result.
        text = result['cau_tra_loi'].splitlines()
        remainder = [line for line in text[1:] if not line.startswith(
            ('Theo bản chuẩn hóa', '- Cả công thức:', '- Mỗi khẩu phần:', '- Lượng bạn hỏi'))]
        q = calo.key(question)
        part = re.search(r'\b(nua|mot phan tu|1 2|1 4)\s+(?:(?:khau )?phan|me|noi|cong thuc)\b', q)
        requested = []
        if part:
            fraction = Fraction(1,4) if part[1] in ('mot phan tu','1 4') else Fraction(1,2)
            whole = not part[0].endswith('phan')
            value = (total if whole else per)*fraction
            requested.append(f'- Lượng bạn hỏi ({fraction} {"mẻ" if whole else "khẩu phần"}): khoảng **{float(value):,.0f} kcal**.')
        extras = re.search(r'\b(?:an\s+)?(hai|ba|bon|\d+)\s+(?:khau )?phan\b',q) if not scenario and not part else None
        if extras:
            count = {'hai':2,'ba':3,'bon':4}.get(extras[1]) or int(extras[1])
            requested.append(f'- Lượng bạn hỏi ({count} khẩu phần): khoảng **{float(per*count):,.0f} kcal**.')
        divided = (scenario and scenario['kind']=='divide') or (
            not scenario and portions_only and change['operations'][-1]['kind']=='divide')
        basis = f'chia mẻ hiện tại thành {target} khẩu phần, giữ tổng năng lượng của mẻ' if divided else f'quy đổi đồng tỷ lệ từ {base} thành {target} khẩu phần'
        text = [
            text[0],
            f"Ước tính từ **{result['giai_thich']['phien_ban_calo']}**, {basis}.",
            f'- Cả công thức: khoảng **{float(total):,.0f} kcal**.',
            f'- Mỗi khẩu phần: khoảng **{float(per):,.0f} kcal**.',
            *requested,
            *remainder,
        ]
        explanation = dict(result['giai_thich'], calo=dict(original, total=float(total),
                                                           per_serving=float(per), servings=target))
        explanation['calo_goi_y'] = []
        return dict(result, cau_tra_loi='\n'.join(text), giai_thich=explanation,
                    reason_code='CURRENT_CALORIE_ESTIMATE', goi_y=[])

    missing = []
    if change is not None:
        plan = replay(row,base_edit(row,state)['events'])
        missing = [i['name'] for i in plan['items'] if i['quantity'] is None or not i['unit']]
    detail = (' Chưa có định lượng hoặc đơn vị cho: ' + ', '.join(dict.fromkeys(missing)) + '.') if missing else ''
    context['cau_tra_loi'] = (
        f"**{row['question']}**" + (f" · {target} khẩu phần." if target else ".")
        + "\n\nChưa có hồ sơ dinh dưỡng ứng với đúng phiên bản này. "
          "Cần đối chiếu khối lượng phần ăn được, quy đổi đơn vị và dữ liệu thành phần của từng nguyên liệu."
        + detail
    )
    if re.search(r'\b100 ?g\b',calo.key(question)):
        context['cau_tra_loi'] += ' Cần thêm khối lượng món chín ăn được để tính trên 100 g.'
    return context


def _evaluate(question,kho,state,previous,manifest,ledger):
    from backend.chatbot.recipe_views_v5 import limitation
    from backend.chatbot.health_context_v5 import analyze
    from backend.chatbot.recipe_edit_v1 import active_for, base_edit
    config=manifest['excel_calorie_estimates']
    expected=manifest['artifacts'][config['path']]
    if hashlib.sha256(calo.DATA.read_bytes()).hexdigest()!=expected:
        return limitation('VALIDATION_FAILED')
    from backend.chatbot.suc_khoe import cap_nhat
    health_question=health_text(question,kho)
    health=analyze(health_question,previous.get('health_context_v5'))
    state['tinh_trang_suc_khoe']=cap_nhat(previous.get('tinh_trang_suc_khoe'),health_question)
    unresolved=calo.key(previous.get('cau_hoi_can_lam_ro') or '')
    prior_id=(previous.get('mon_hien_tai') or {}).get('id_goc')
    if previous.get('can_lam_ro') and prior_id and re.search(r'^(?:bo|bot|giam|thay|them)\b',unresolved):
        state['excel_pending_change']=prior_id
    if re.search(r'\b(?:theo|dung|tinh|giu nguyen|quay ve) (?:ban )?cong thuc goc\b',calo.key(question)):
        state.pop('excel_pending_change',None)
    if health['cure_question'] or health['health_need'] or health['context']['active'] or state.get('tinh_trang_suc_khoe'):
        return limitation('HELD_HEALTH')
    followup = _nutrition_followup(question, previous)
    if not re.match(r'^neu\b',_scenario_text(question)):
        parts = re.split(r'\s+(?:roi|va sau do)\s+',calo.key(question),maxsplit=1)
        instruction = _edit_command(parts[0]) if len(parts)==2 and _nutrition_words(parts[1]) else None
        if instruction and instruction['kind'] not in ('rewrite','cancel'):
            return dict(limitation('MODIFICATION_UNSUPPORTED',state.get('mon_hien_tai')),
                        reason_code='CALORIE_EDIT_SEQUENCE_REQUIRED',
                        cau_tra_loi='Mình chưa áp dụng thay đổi trong yêu cầu gộp này. Bạn gửi lệnh chỉnh công thức trước, rồi hỏi lại dinh dưỡng của phiên bản đã áp dụng.')
    probe = question
    if followup == 'energy':
        if not re.search(r'\b(?:mon (?:nay|do|tren)|cai do)\b',calo.key(question)):
            probe = 'Món này '+probe
        if not calo.is_request(probe, {}):
            probe += ' calo'
    scenario = _serving_scenario(question)
    if (scenario and state.get('mon_hien_tai')
            and re.match(r'^(?:neu )?(?:nau cho|chia (?:cung |mot |me|thanh)|doi thanh)\b',_scenario_text(question))
            and not re.search(r'\b(?:mon (?:nay|do|tren)|cai do)\b',calo.key(question))):
        probe = 'Món này '+question
    if (previous.get('calo_hien_tai') and re.match(r'^(?:neu|gia su|tinh thu)\b',calo.key(question))
            and _edit_command(question) and not _nutrition_words(question)):
        return dict(limitation('RECIPE_CLARIFICATION',state.get('mon_hien_tai')),
                    reason_code='CALORIE_OR_EDIT_CLARIFICATION',
                    cau_tra_loi='Bạn muốn áp dụng thay đổi vào công thức hay chỉ tính thử calo? Mình giữ nguyên phiên bản đang dùng.')
    result = None if followup == 'metrics' else calo.answer_calories(probe,kho,state,previous)
    nutrients_only = followup == 'metrics' or (result is None and _current_nutrients(question,state))
    pending_choices = {item.get('id_goc') for item in previous.get('de_xuat',()) if item.get('id_goc') is not None}
    if followup and (not state.get('mon_hien_tai') or len(pending_choices)>1):
        state['mon_hien_tai'] = None
        return dict(limitation('RECIPE_CLARIFICATION'),reason_code='EXCEL_CALORIE_CLARIFICATION',
                    cau_tra_loi='Bạn muốn xem dinh dưỡng của món nào? Hãy chọn một món hoặc cho mình tên công thức.')
    if result is None and not nutrients_only:return None
    rid=((result or {}).get('chu_de') or {}).get('id_goc')
    current=state.get('mon_hien_tai') or {}
    check_id=rid if rid is not None else current.get('id_goc')
    if check_id is not None:
        row=ledger.get(check_id)
        if not row or not row.get('allowed_for_answer'):
            return limitation('HELD_HEALTH')
        if row.get('scope')!='IN_SCOPE':
            return limitation('DEMO_RECIPE_UNDER_REVIEW')
        if check_id in manifest.get('demo_excluded_recipe_ids',[]):
            return limitation('DEMO_RECIPE_UNDER_REVIEW')
        if state.get('excel_pending_change')==check_id or base_edit(row,state).get('pending') or (state.get('pending_ingredient_change') or {}).get('recipe_id')==check_id:
            return limitation('MODIFICATION_UNSUPPORTED',dict(id_goc=check_id,cau_hoi=row['question']))
        if (_nutrition_words(question) and re.match(r'^neu\b',_scenario_text(question))
                and (_edit_command(question) or {}).get('kind') in
                ('add','remove','replace','replace_proposal','fraction','set','quantity_clarify')):
            return dict(limitation('MODIFICATION_UNSUPPORTED',dict(id_goc=check_id,cau_hoi=row['question'])),
                        reason_code='CURRENT_NUTRITION_UNAVAILABLE',
                        cau_tra_loi='Chưa có đủ dữ liệu định lượng và thành phần cho thay đổi giả định này. Công thức hiện tại vẫn được giữ nguyên.')
        if followup:
            from backend.chatbot.cong_thuc import danh_muc
            if not any(recipe.id_goc==check_id for recipe in danh_muc(kho)):
                return limitation('RECIPE_CLARIFICATION')
        # An explicit unresolved dish must not borrow the active recipe.
        use_current = followup or re.search(r'\b(?:mon (?:nay|do|tren)|cong thuc (?:nay|tren|hien tai))\b',calo.key(question))
        if rid is not None or (use_current and current.get('id_goc')==check_id) or (nutrients_only and active_for(row,state) and health_text(question,kho).strip() == calo.key(question)):
            versioned = _version_result(question,result,row,state,manifest,nutrients_only=nutrients_only)
            if versioned is not None:return versioned
        if followup == 'metrics':
            from backend.chatbot.nutrition_runtime import METRICS, recipe_version, render
            from backend.chatbot.recipe_views_v5 import document, reference
            topic = dict(id_goc=row['id'],cau_hoi=row['question'])
            unavailable = dict(limitation('MISSING_NUTRITION',topic),reason_code='CURRENT_NUTRITION_UNAVAILABLE')
            dk = state.get('dieu_kien', {})
            if (state.get('di_ung') or state.get('di_ung_chua_ro')
                    or any(dk.get(k) for k in ('loai_tru','chua_ro','an_chay'))
                    or re.search(r'\b(?:100 ?g|100 gram|mot tram gam|nua|mot phan tu|1 2|1 4)\b',calo.key(question))):
                return unavailable
            metrics = [k for k, words in METRICS.items() if re.search(r'\b(?:'+words+r')\b',calo.key(question))]
            try:
                req = dict(recipe_id=check_id,recipe_version=recipe_version(manifest,row),target_servings=None)
            except KeyError:
                return unavailable
            if len(metrics)==1:
                req.update(view='serving',metric=metrics[0])
            data,text = render(req,manifest,ledger)
            if data['status']=='BLOCKED':
                return dict(unavailable,cau_tra_loi=text)
            source_servings = document(row)['base_portions']
            if source_servings is None or str(source_servings)!=data.get('servings_exact'):
                return dict(unavailable,cau_tra_loi='Có hồ sơ tham chiếu riêng, nhưng chưa xác nhận cùng mốc khẩu phần với công thức đang dùng. Mình chưa dùng hồ sơ đó để trả dưỡng chất cho món hiện tại.')
            return dict(unavailable,loai='tra_loi',reason_code='CURRENT_NUTRITION_CALCULATED',
                        cau_tra_loi=text,nguon=[reference(row)],nutrition_result=data,
                        giai_thich={'recipe_version':req['recipe_version']})
        if active_for(row,state) and result is not None and rid == check_id:
            return limitation('MODIFICATION_UNSUPPORTED',result.get('chu_de'))
        # A combined request may have a vetted profile for the unchanged
        # recipe. Keep the Excel energy fallback for recipes without it.
        if (rid is not None and _current_nutrients(question, state | {'mon_hien_tai': {'id_goc': rid}})
                and result['giai_thich'].get('calo')
                and not re.search(r'\b(?:100 ?g|nua|phan tu|mot to|mot dia|chia)\b',calo.key(question))):
            from backend.chatbot.nutrition_runtime import recipe_version, render
            from backend.chatbot.recipe_views_v5 import reference
            req = dict(recipe_id=rid, recipe_version=recipe_version(manifest,row), target_servings=None)
            nutrition, text = render(req,manifest,ledger)
            if nutrition['status']!='BLOCKED':
                return dict(result, cau_tra_loi=text, reason_code='CURRENT_NUTRITION_CALCULATED',
                            nutrition_result=nutrition, goi_y=[], nguon=[reference(row)],
                            giai_thich={'recipe_version':req['recipe_version']})
    if result is None:return None
    excluded=set(manifest.get('demo_excluded_recipe_ids',[]))
    choices=[item for item in result.get('giai_thich',{}).get('calo_goi_y',[])
             if ledger.get(item['id_goc'],{}).get('allowed_for_answer')
             and ledger[item['id_goc']].get('scope')=='IN_SCOPE' and item['id_goc'] not in excluded]
    result['giai_thich']['calo_goi_y']=choices
    result['goi_y']=[item['cau_hoi'] for item in choices]
    result['reason_code']='EXCEL_CALORIE_ESTIMATE' if result['loai']=='tra_loi' else 'EXCEL_CALORIE_CLARIFICATION'
    if result['loai']=='tra_loi':
        result['cau_tra_loi']='**Calo ước tính từ bảng Excel chuẩn hóa.** Các giả định chưa được thẩm định chuyên môn; số này không thuộc hồ sơ dinh dưỡng đã duyệt của chatbot.\n\n'+result['cau_tra_loi']
    return result


def evaluate(question,kho,state,previous,manifest,ledger):
    result = _evaluate(question,kho,state,previous,manifest,ledger)
    if result is not None and re.match(r'^neu\b',_scenario_text(question)):
        topic = result.get('chu_de') or {}
        current = previous.get('mon_hien_tai') or {}
        if topic.get('id_goc') != current.get('id_goc'):
            result['chu_de'] = None
        result['goi_y'] = []
        result['giai_thich'].pop('calo_goi_y',None)
    return result


def route(payload,manifest,ledger):
    question=payload['question']
    q = calo.key(question)
    command = _edit_command(question)
    explicit_nutrition = _nutrition_words(question)
    hypothetical = re.match(r'^(?:neu|gia su|tinh thu)\b',q)
    recognized_edit = command and (
        command['kind'] not in ('scale','divide')
        or re.match(r'^(?:doi|nau|chia|giam xuong|cho ca nha)\b',q)
    )
    if recognized_edit and not explicit_nutrition and not hypothetical:
        return None
    if payload.get('choice') and payload['previous'].get('calo_hien_tai'):
        question=payload['choice']['cau_hoi']
    ambiguous = bool(command and hypothetical and not explicit_nutrition and payload['previous'].get('calo_hien_tai'))
    followup = _nutrition_followup(question,payload['previous'])
    if not (ambiguous or followup or calo.is_request(question,payload['previous'])
            or _current_nutrients(question,payload['state'])):
        return None
    state=copy.deepcopy(payload['state']);previous=copy.deepcopy(payload['previous'])
    result=evaluate(question,payload['kho'],state,previous,manifest,ledger)
    if result is None:return None
    if _serving_scenario(question) or hypothetical:
        live = payload['state']
        # Nutrition trial fields are request-local. The current recipe keeps
        # its applied portions and dietary preferences even on a refusal.
        live['khau_phan'] = previous.get('khau_phan')
        if hypothetical:
            live['dieu_kien'] = copy.deepcopy(previous['dieu_kien'])
    if followup or _current_nutrients(question, state):
        if followup and state.get('mon_hien_tai') is None:
            payload['state']['mon_hien_tai'] = None
        # A lookup of the current formula does not set a new dietary target.
        for field in ('nhu_cau','can_dinh_luong'):
            payload['state']['dieu_kien'][field] = copy.deepcopy(previous['dieu_kien'][field])
        payload['state']['calo_yeu_cau'] = previous.get('calo_yeu_cau')
    payload['state']['tinh_trang_suc_khoe']=state.get('tinh_trang_suc_khoe',[])
    if state.get('excel_pending_change') is not None:
        payload['state']['excel_pending_change']=state['excel_pending_change']
    else:
        payload['state'].pop('excel_pending_change',None)
    result['excel_calo_request']=dict(question=question,state=state,previous=previous)
    return result


def enforce(result,kho,manifest,ledger):
    from backend.chatbot.recipe_views_v5 import limitation
    request=result.get('excel_calo_request')
    try:
        recomputed=evaluate(request['question'],kho,request['state'],request['previous'],manifest,ledger)
        if recomputed is None:return limitation('VALIDATION_FAILED')
        recomputed['excel_calo_request']=copy.deepcopy(request)
        recomputed['trang_thai']=copy.deepcopy(result.get('trang_thai',{}))
        nutrition_keys = {'calo','calo_chuan_hoa','calo_goi_y','phien_ban_calo','recipe_version'}
        recomputed['giai_thich'] = {
            **{k:v for k,v in result.get('giai_thich',{}).items() if k not in nutrition_keys},
            **recomputed['giai_thich'],
        }
        return recomputed
    except (KeyError,TypeError,ValueError,OSError):
        return limitation('VALIDATION_FAILED')
