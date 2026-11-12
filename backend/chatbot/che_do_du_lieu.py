"""Chọn kho production/evaluation; evaluation chặn mọi đoạn Test."""
from functools import lru_cache
from pathlib import Path
import json
from backend.chatbot.cau_hinh import ROOT, doc_cau_hinh


@lru_cache(maxsize=8)
def xac_minh_train(kho):
    rows = [json.loads(s) for s in (ROOT/kho/'sieu_du_lieu.jsonl').read_text(encoding='utf-8').splitlines()]
    if not rows or any(r.get('tap') != 'Train' for r in rows):
        raise ValueError('Evaluation chỉ được dùng kho chứa Train; không dùng kho tat_ca/Test.')
    return True


def chon_kho(options=None):
    options = options or {}
    ch = doc_cau_hinh()
    mode = options.get('che_do_du_lieu', ch.get('che_do_du_lieu', 'production'))
    if mode not in ('production', 'evaluation'):
        raise ValueError('che_do_du_lieu phải là production hoặc evaluation')
    value = options.get('kho') or (ch['kho_danh_gia'] if mode == 'evaluation' else ch['kho_vector'])
    path = Path(value)
    relative = path.relative_to(ROOT).as_posix() if path.is_absolute() else path.as_posix()
    if mode == 'evaluation':
        xac_minh_train(relative)
    return relative, mode
