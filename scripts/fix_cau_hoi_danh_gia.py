"""Cập nhật 4 câu hỏi (689, 799, 878, 906) theo đúng nhận xét phản biện của Giảng viên.

Đồng bộ:
- data/groups/08_dinh_duong/all.csv (ID 689)
- data/groups/12_goi_y_khi_om_met/all.csv (ID 799)
- data/groups/11_an_toan_thuc_pham/all.csv (ID 878, 906)
- data/merged/dataset.csv
- data/merged/dataset.jsonl
- kho_vector/cau_truc_tat_ca/sieu_du_lieu.jsonl
- kho_vector/cau_truc_tat_ca/index.faiss (cập nhật vector embedding)
"""
import csv
import json
import sys
from pathlib import Path

import faiss
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.chatbot.mo_hinh_vector import sinh_vector
from scripts.tach_tu import TachTu, doc_tu_dien, tien_xu_ly

SUA_NOI_DUNG = {
    "689": (
        "Uống một ly nước khoảng 20 đến 30 phút trước bữa ăn giúp bôi trơn đường tiêu hóa và tạo cảm giác no nhẹ, hỗ trợ kiểm soát khẩu phần ăn.\n\n"
        "Về mặt sinh lý tiêu hóa, nước lọc được hấp thu rất nhanh qua dạ dày trong vài phút và dạ dày luôn tự điều tiết dịch vị cùng acid hydrochloric (HCl) để giữ nồng độ pH ổn định, nên nước không làm vô hiệu hóa enzym tiêu hóa. Tuy nhiên, tránh uống quá nhiều nước sát giờ ăn để không làm dạ dày căng tức quá mức hoặc đầy bụng khó chịu khi tiếp nhận thức ăn. Trong bữa ăn, bạn có thể nhấp từng ngụm nhỏ vừa đủ để dễ nuốt."
    ),
    "799": (
        "Cảm nắng là cách gọi dân gian cho các vấn đề do quá nhiệt, cần phân biệt rõ mức độ để xử trí đúng cách:\n\n"
        "1. Thể kiệt sức do nhiệt (nhẹ đến vừa): Cơ thể mệt lả, vã nhiều mồ hôi, da tái lạnh, còn tỉnh táo. Cần đưa vào nơi râm mát, nới lỏng áo quần và bù nước, điện giải từ từ bằng nước lọc, dung dịch oresol hoặc nước dừa tươi uống từng ngụm nhỏ liên tục. Khi đỡ mệt, nên ăn cháo loãng giải cảm, súp ấm hoặc trái cây nhiều nước (cam, dưa hấu).\n\n"
        "2. Thể sốc nhiệt (cực kỳ nguy kịch): Thân nhiệt tăng cao trên 40 độ C, da nóng ran và khô khốc (ngừng toát mồ hôi), kèm lú lẫn, co giật hoặc hôn mê. Đây là tình trạng đe dọa tính mạng, phải gọi cấp cứu 115 ngay. Lưu ý tuyệt đối: Không được cố ép người bệnh đang lơ mơ hoặc hôn mê uống nước vì rất dễ sặc vào phổi gây ngạt thở. Trong lúc chờ cấp cứu, nhanh chóng làm mát ngoài da bằng cách lau khăn ẩm mát và chườm lạnh vùng nách, bẹn, cổ."
    ),
    "878": (
        "Khi phát hiện trẻ có dấu hiệu dị ứng thức ăn (nổi mề đay, mẩn đỏ, ngứa ngáy), cần ngừng ngay thực phẩm đó và giữ lại mẫu thức ăn hoặc bao bì để xác định nguyên nhân.\n\n"
        "Lưu ý đặc biệt quan trọng: Dị ứng thức ăn ở trẻ nhỏ không thể xem nhẹ vì phản ứng có thể tiến triển rất nhanh từ triệu chứng ngoài da sang sốc phản vệ đe dọa tính mạng. Cha mẹ không nên chủ quan tự theo dõi tại nhà mà cần quan sát liên tục từng phút. Nếu trẻ xuất hiện bất kỳ dấu hiệu chuyển nặng nào như: khó thở, thở rít, khàn giọng, sưng môi, sưng lưỡi, nôn tháo, đau bụng dữ dội, li bì hoặc tái nhợt, phải đưa trẻ đến cơ sở y tế gần nhất cấp cứu ngay lập tức. Sau khi ổn định, hãy đưa trẻ đi khám chuyên khoa dị ứng để làm test định danh và có phác đồ dự phòng chuẩn xác."
    ),
    "906": (
        "Dầu ăn chiên đi chiên lại nhiều lần sẽ bị oxy hóa và biến tính nhiệt, tạo ra các hợp chất độc hại như hydroperoxide, aldehyde, acrolein và acid béo chuyển hóa (trans fat) gây hại cho tim mạch và gan.\n\n"
        "Mức độ an toàn khi tái sử dụng dầu không thể ấn định cứng nhắc bằng số lần, mà phụ thuộc chặt chẽ vào:\n"
        "- Loại dầu và điểm khói (smoke point): Các loại dầu giàu chất béo không bão hòa đa (như dầu mè, hướng dương, đậu nành) rất dễ bị phân hủy khi đun nóng; trong khi dầu có điểm khói cao bền nhiệt hơn.\n"
        "- Nhiệt độ chiên: Nếu nhiệt độ vượt quá điểm khói của dầu, dầu sẽ bị cháy và biến chất độc hại ngay từ lần chiên đầu tiên.\n"
        "- Thời gian sử dụng và cặn thức ăn: Chiên liên tục trong nhiều giờ hoặc để cặn thức ăn cháy đọng lại sẽ đẩy nhanh quá trình ôi thiu oxy hóa.\n\n"
        "Khuyến nghị an toàn: Hạn chế tối đa tái sử dụng dầu chiên ngập dầu. Nếu tận dụng dầu chiên nhẹ một lần, phải lọc sạch toàn bộ cặn và bảo quản kín nơi tối, mát. Cần loại bỏ ngay lập tức nếu dầu có bất kỳ dấu hiệu nào sau: sẫm màu, bốc khói ở nhiệt độ thấp, sủi nhiều bọt nổi váng, dầu đặc quánh hoặc có mùi khét/ôi dầu."
    ),
}


def cap_nhat_file_csv(path: Path) -> int:
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        return 0
    reader = csv.reader(lines, delimiter=";")
    header = next(reader)
    id_col = header.index("ID")
    tl_col = header.index("Câu trả lời")
    out_rows = [header]
    count = 0
    for row in reader:
        if not any(c.strip() for c in row):
            continue
        rid = row[id_col]
        if rid in SUA_NOI_DUNG:
            row[tl_col] = SUA_NOI_DUNG[rid]
            count += 1
        out_rows.append(row)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerows(out_rows)
    return count


def cap_nhat_dataset_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    out_lines = []
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        str_id = str(obj.get("id") or "")
        if str_id in SUA_NOI_DUNG:
            obj["cau_tra_loi"] = SUA_NOI_DUNG[str_id]
            count += 1
        out_lines.append(json.dumps(obj, ensure_ascii=False))
    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return count


def cap_nhat_kho_vector() -> None:
    kho_dir = ROOT / "kho_vector" / "cau_truc_tat_ca"
    sieu_path = kho_dir / "sieu_du_lieu.jsonl"
    index_path = kho_dir / "index.faiss"
    if not sieu_path.exists() or not index_path.exists():
        print("Không tìm thấy kho_vector/cau_truc_tat_ca")
        return

    tach = TachTu(doc_tu_dien())
    sieu_docs = [json.loads(line) for line in sieu_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Load FAISS index via deserialize_index to avoid Windows Unicode path issues
    index = faiss.deserialize_index(np.frombuffer(index_path.read_bytes(), dtype=np.uint8))
    d = index.d
    ntotal = index.ntotal
    xb = np.zeros((ntotal, d), dtype=np.float32)
    for i in range(ntotal):
        xb[i] = index.reconstruct(i)

    updated_indices = []
    for idx, doc in enumerate(sieu_docs):
        str_id = str(doc.get("id_goc") or "")
        if str_id in SUA_NOI_DUNG:
            new_tl = SUA_NOI_DUNG[str_id]
            cau_hoi = doc.get("cau_hoi", "")
            nhom = doc.get("nhom", "")
            tl_tx = tien_xu_ly(new_tl, {"doi_kieu_dau": 0, "them_cach_sau_dau": 0})
            hoi_tx = tien_xu_ly(cau_hoi, {"doi_kieu_dau": 0, "them_cach_sau_dau": 0})
            tl_tach, _ = tach.tach_cau_tra_loi(tl_tx)
            hoi_tach = tach.tach_cau_hoi(hoi_tx)
            nhom_tach = tach.tach_cau_hoi(nhom)

            noi_dung_kem_tieu_de = f"{nhom} · {cau_hoi}\n{new_tl}"
            noi_dung_kem_tieu_de_tach_tu = f"{nhom_tach} · {hoi_tach} {tl_tach}"

            doc["noi_dung"] = new_tl
            doc["noi_dung_kem_tieu_de"] = noi_dung_kem_tieu_de
            doc["noi_dung_kem_tieu_de_tach_tu"] = noi_dung_kem_tieu_de_tach_tu
            doc["so_token"] = len(noi_dung_kem_tieu_de_tach_tu.split())
            doc["so_ky_tu"] = len(noi_dung_kem_tieu_de)
            doc["vi_tri_ky_tu"] = [0, len(noi_dung_kem_tieu_de)]

            # Compute new vector
            v = sinh_vector([noi_dung_kem_tieu_de_tach_tu])
            xb[idx] = v[0]
            updated_indices.append((str_id, idx))

    # Ghi lại sieu_du_lieu.jsonl
    with sieu_path.open("w", encoding="utf-8") as f:
        for doc in sieu_docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    # Tạo lại index và ghi file bằng serialize_index
    new_index = faiss.IndexFlatIP(d)
    new_index.add(xb)
    index_path.write_bytes(faiss.serialize_index(new_index).tobytes())

    print(f"Đã cập nhật vector và siêu dữ liệu cho {len(updated_indices)} đoạn trong FAISS Index: {updated_indices}")


def main():
    print("Bắt đầu cập nhật 4 câu hỏi 689, 799, 878, 906...")
    for p in [
        ROOT / "data/groups/08_dinh_duong/all.csv",
        ROOT / "data/groups/12_goi_y_khi_om_met/all.csv",
        ROOT / "data/groups/11_an_toan_thuc_pham/all.csv",
        ROOT / "data/merged/dataset.csv",
    ]:
        n = cap_nhat_file_csv(p)
        print(f"Cập nhật {p.relative_to(ROOT)}: {n} dòng")

    n_jsonl = cap_nhat_dataset_jsonl(ROOT / "data/merged/dataset.jsonl")
    print(f"Cập nhật data/merged/dataset.jsonl: {n_jsonl} dòng")

    cap_nhat_kho_vector()
    print("Hoàn tất cập nhật 4 câu hỏi!")


if __name__ == "__main__":
    main()
