# Báo cáo rà soát mã nguồn (2026-10-22)

## 1. Phạm vi và giả định

- Công nghệ: Python 3.12, Streamlit 1.66, sentence-transformers + FAISS, underthesea.
- Quy chuẩn: PEP8 (độ dài dòng 120), kiểm bằng `pyflakes` và `pycodestyle`.
- Phạm vi: `app.py`, `chatbot/`, `scripts/`, `cau_hinh/`, `requirements.txt`, các file cấu hình. Bỏ qua `.venv/`,
  `.venv_uv_cu/`, `.git/`, `__pycache__/`.
- Quyền hạn: tự sửa lỗi nhỏ và tối ưu không đổi hành vi. Xóa dữ liệu, đổi cơ chế đăng nhập hay đổi cấu trúc thư mục
  thì chỉ đề xuất (mục 5), chưa làm.

## 2. Lỗi đã sửa

| # | File | Lỗi | Cách sửa |
|---|---|---|---|
| 1 | `chatbot/truy_hoi.py` | `truy_hoi()` tạo khóa kho bằng `str(Path)`, trên Windows ra `kho_vector\cau_truc_tat_ca`. `app.py` nạp sẵn kho bằng `kho_vector/cau_truc_tat_ca` (lấy từ cấu hình). Hai khóa khác nhau nên `lru_cache` trượt: kho và chỉ mục BM25 bị nạp **hai lần**, tốn gấp đôi RAM, và câu hỏi đầu tiên chậm vì phải đọc lại đĩa. Đo được `nap_kho.cache_info()` báo `misses=2`. | Dùng `.as_posix()`. Sau khi sửa còn `misses=1`. |
| 2 | `chatbot/cau_hinh.py`, `chatbot/mo_hinh_vector.py` | `.env.example` hướng dẫn điền `HF_TOKEN`, nhưng `.env` không được nạp ở đâu cả: hàm duy nhất gọi `nap_env()` là `lay_bien_moi_truong()`, mà hàm này không ai dùng (sót lại từ phiên bản dùng LLM). | `nap_mo_hinh()` gọi `nap_env()` trước khi tải mô hình. Bỏ `lay_bien_moi_truong()` và `import os` không dùng. |

## 3. Tối ưu và dọn mã (không đổi hành vi)

| File | Thay đổi |
|---|---|
| `app.py` | `cau_hoi_theo_chu_de()` dùng lại kho đã nạp (`nap_kho`) thay vì đọc và parse lại `sieu_du_lieu.jsonl`. Bỏ `import json` và `ROOT` không còn dùng. |
| `chatbot/sinh_cau_tra_loi.py` | `nhan_dien_xa_giao()` trước đây chạy 2 lần mỗi lượt, giờ tính 1 lần. Bỏ list comprehension thừa `[q for q in ...]`. Đổi tên biến `l` thành `luot` (PEP8 E741). |
| `chatbot/tai_khoan.py` | Sắp lại thứ tự `import` theo bảng chữ cái. |
| `scripts/tach_tu.py`, `scripts/tao_kho_vector.py` | Bỏ tiền tố `f` ở 2 chuỗi không có biến (pyflakes). |
| `requirements.txt` | Bỏ `tqdm`: không file nào import trực tiếp. `sentence-transformers` và `huggingface_hub` vẫn tự cài nó. |

## 4. File đã xóa

| File | Lý do |
|---|---|
| `chatbot/__pycache__/llm.cpython-312.pyc` | Bộ đệm biên dịch của `chatbot/llm.py`, file nguồn này đã bị xóa. Git không theo dõi file này, và xóa đi không ảnh hưởng gì. |

## 5. Đề xuất (chưa thực hiện, cần bạn quyết định)

### 5.1 Bảo mật

1. **Mã phiên đăng nhập nằm trên đường dẫn (`?phien=...`)** (`app.py`, dòng 109–117 và 210–213). Ai thấy đường dẫn
   (lịch sử trình duyệt, ảnh chụp màn hình, link gửi cho người khác) là vào được tài khoản trong 30 ngày.
   Đề xuất: chỉ giữ mã trong cookie, và bỏ phần sao chép mã lên đường dẫn. Đổi lại, trình duyệt nào chặn cookie
   thì người dùng phải đăng nhập lại sau khi tải lại trang. Chưa sửa vì đây là chủ ý thiết kế ghi trong chú thích.
2. **Không giới hạn số lần đăng nhập sai** (`tai_khoan.dang_nhap`). Mật khẩu tối thiểu chỉ 6 ký tự. Đề xuất: khóa tạm
   một tài khoản sau khoảng 5 lần sai liên tiếp.
3. **Ghi file JSON không khóa** (`nguoi_dung.json`, `phien.json`, `lich_su/*.json`). Hai tab hoặc hai người cùng
   ghi một lúc thì có thể mất bản ghi của bên ghi trước (đọc, sửa, ghi đè). Chạy trên máy cá nhân thì rủi ro thấp.
   Nếu triển khai cho nhiều người, nên chuyển sang SQLite.
4. Tên đăng nhập không tồn tại thì bị trả lời ngay, còn tên đúng thì phải băm 200.000 vòng. Dựa vào thời gian phản hồi,
   người ngoài đoán được tên nào đã có. Mức độ nhẹ.

### 5.2 File đề xuất xóa hoặc di chuyển

| File / thư mục | Kích thước | Lý do | Đề xuất |
|---|---|---|---|
| `data/doan/doan_*_01_chao_hoi.jsonl` (3 file) | 3 × 44 KB | Kết quả chạy thử riêng nhóm Chào hỏi. Là tập con của `doan_<cach>.jsonl`, không code nào đọc. | Xóa |
| `data/doan/_toan_bo.json` | 3,1 MB | Cùng nội dung với `doan_cau_truc.jsonl`, chỉ khác định dạng. Không code nào đọc. | Xóa, hoặc thôi ghi trong `tach_doan.py` |
| `data/merged/dataset.jsonl` | 978 KB | Bản JSONL của `dataset.csv`. Không code nào đọc. | Giữ nếu dùng để nộp bài, không thì xóa |
| `kho_vector/_bo_dem/` | 11 MB | Bộ đệm vector, sinh lại được, git không theo dõi | Xóa được khi cần chỗ trống |
| `câu hoi.xlsx` (thư mục gốc) | — | Tên có dấu cách, lại thiếu dấu ("hoi"), đặt lẫn với mã nguồn | Chuyển vào `data/raw/` |
| `tài liệu/` (10 file PDF bài giảng) | 4,9 MB | Chưa có trong `.gitignore`. Slide bài giảng thường không nên đưa lên GitHub công khai. | Thêm `tài liệu/` vào `.gitignore` |

### 5.3 Cấu trúc

1. `chatbot/mo_hinh_vector.py` thêm `scripts/` vào `sys.path` để import `tach_tu`. Vì vậy gói `chatbot` (chạy thật)
   phụ thuộc vào thư mục script xử lý dữ liệu. Đề xuất: chuyển `TachTu`, `tien_xu_ly` và `doc_tu_dien` sang
   `chatbot/tien_xu_ly.py`, rồi để `scripts/tach_tu.py` import ngược lại từ đó.
2. Tên file chưa thống nhất: `scripts/merge_groups.py`, `split_by_group.py` và thư mục `data/groups`, `data/merged`
   đặt tên tiếng Anh, còn các phần khác tiếng Việt không dấu. Nếu muốn thống nhất thì cần sửa cả README và báo cáo.
3. Còn 58 dòng dài hơn 120 ký tự và 4 chỗ gán `lambda` vào biến (PEP8 E501, E731). Không ảnh hưởng chạy, nên tôi giữ nguyên
   để diff gọn.

## 6. Kiểm chứng sau khi sửa

- `pyflakes app.py chatbot scripts`: không còn cảnh báo.
- Chạy `tra_loi()` qua đủ các luồng, kết quả đúng như trước:

| Câu hỏi | Loại | Cách tìm | Điểm |
|---|---|---|---|
| xin chào | chao_hoi | vector | 0,456 |
| cách nấu canh chua cá lóc | tra_loi | vector | 0,764 |
| món đó nấu bao lâu (nối tiếp) | tra_loi (đúng món canh chua) | vector | 0,868 |
| cach nau hu tieu my tho | tra_loi | khong_dau | 0,611 |
| giá vàng hôm nay | ngoai_pham_vi | vector | 0,184 |
| cảm ơn nha | chao_hoi | vector | 0,414 |

- `streamlit.testing.AppTest` dựng được màn hình đăng nhập (2 tab, 6 ô nhập) và màn hình chủ đề mà không có lỗi.
  Web khởi động lại bình thường, kiểm tra `/_stcore/health` trả về 200.
- Chưa chạy lại `scripts/danh_gia.py` (mất nhiều thời gian). Các thay đổi không đụng tới cách tính điểm hay xếp hạng,
  nên số liệu trong `reports/danh_gia_chatbot.md` vẫn đúng.
