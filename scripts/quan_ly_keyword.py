"""Phân tích Train và xuất đề xuất có nguồn; không tự sửa từ điển/index."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.chatbot.cau_hinh import ROOT
from backend.chatbot.che_do_du_lieu import xac_minh_train
from backend.chatbot.ngon_ngu import chuan_hoa, DIA_PHUONG, NHU_CAU


def phan_tich_train(kho='kho_vector/cau_truc_Train'):
    xac_minh_train.cache_clear()
    xac_minh_train(kho)
    path = ROOT/kho/'sieu_du_lieu.jsonl'
    raw = path.read_bytes()
    rows = [json.loads(s) for s in raw.decode('utf-8').splitlines() if s.strip()]
    phrases, origins, titles = Counter(), defaultdict(set), {}
    for row in rows:
        titles[row['id_goc']] = row['cau_hoi']
        # Cụm xuất hiện nhiều: ứng viên, tuyệt đối không gán quan hệ đồng nghĩa.
        words = chuan_hoa(row['cau_hoi']+' '+row['noi_dung']).split()
        for n in (2, 3, 4):
            for i in range(len(words)-n+1):
                phrase = ' '.join(words[i:i+n])
                if not any(c.isdigit() for c in phrase):
                    phrases[phrase] += 1
                    origins[phrase].add(row['id_goc'])
    dictionary = (ROOT/'cau_hinh/tu_dien_rieng.txt').read_text(encoding='utf-8').splitlines()
    normalized = [chuan_hoa(s) for s in dictionary if s.strip() and not s.startswith('#')]
    duplicates = [s for s,c in Counter(normalized).items() if c > 1]
    candidates = [{'cum_tu':p, 'so_lan':c, 'id_nguon_train':sorted(origins[p]),
                   'trang_thai':'cho_duyet', 'quan_he_dong_nghia':None}
                  for p,c in phrases.most_common(500) if c >= 3 and p not in normalized]
    # Các tên giống nhau có thể là biến thể món; cần người duyệt chứ không gộp ID.
    by_title = defaultdict(list)
    for idx,title in titles.items():
        by_title[chuan_hoa(title)].append(idx)
    ingredients = defaultdict(set)
    nutrients = defaultdict(set)
    for row in rows:
        for line in row['noi_dung'].splitlines():
            if line.strip().startswith(('-', '•')) and re.search(r'\d+\s*(?:g|kg|ml|quả|trái|củ|con|muỗng|tép)\b',line,re.I):
                name = re.split(r'\d',line.strip().lstrip('-• '))[0].strip()
                if name:
                    ingredients[name].add(row['id_goc'])
        for label, aliases in NHU_CAU.items():
            if any(re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',chuan_hoa(row['noi_dung'])) for alias in aliases):
                nutrients[label].add(row['id_goc'])
    return {'phien_ban':1, 'thoi_diem_utc':datetime.now(timezone.utc).isoformat(),
            'kho_train':kho, 'sha256_nguon':hashlib.sha256(raw).hexdigest(),
            'so_cau_train':len(titles), 'so_doan_train':len(rows),
            'trung_lap_tu_dien':duplicates,
            'ten_trung_can_duyet':{k:v for k,v in by_title.items() if len(v)>1},
            'tieu_de_train':titles,
            'ung_vien_nguyen_lieu':{k:sorted(v) for k,v in ingredients.items()},
            'nhan_dinh_duong_co_nguon_train':{k:sorted(v) for k,v in nutrients.items()},
            'tu_dia_phuong_dang_dung':list(DIA_PHUONG),
            'nhan_dinh_duong':list(NHU_CAU), 'de_xuat':candidates,
            'quy_trinh_duyet':['Đối chiếu từng ID Train với nguồn gốc.',
                              'Thêm ca kiểm thử đồng nghĩa và ca tên gần giống/phủ định.',
                              'Chỉ chấp nhận sau khi kiểm thử regression đạt.',
                              'Lưu phiên bản từ điển và dựng lại index nếu văn bản embedding đổi.'],
            'tu_dong_ap_dung':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kho', default='kho_vector/cau_truc_Train')
    parser.add_argument('--out', default='reports/de_xuat_keyword_train.json')
    args = parser.parse_args()
    report = phan_tich_train(args.kho)
    target = (ROOT/args.out).resolve()
    target.relative_to(ROOT.resolve())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Đã phân tích {report['so_cau_train']} câu Train; {len(report['de_xuat'])} đề xuất chờ duyệt: {args.out}")
