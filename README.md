# Bếp Của Ngoại

### Chạy bản GitHub trên máy Windows mới

Giải nén ZIP, mở PowerShell tại thư mục có `chay_web.bat` và cài Python 3.12, MySQL và Ollama. Bản tải về đã có giao diện, Excel và kho FAISS của bản đang dùng. Hãy giữ nguyên thư mục `staging` để các checksum khớp.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:CHATBOT_MODEL_DIR = .\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; print(snapshot_download('bkai-foundation-models/vietnamese-bi-encoder', revision='84f9d9ada0d1a3c37557398b9ae9fcedcdf40be0', ignore_patterns=['*.bin','*.onnx','*.h5','*.msgpack','*.gguf']))"
ollama pull qwen2.5:3b
```

Nếu máy chưa có schema MySQL của ứng dụng, chạy `.\.venv\Scripts\python.exe scripts/chuan_bi_mysql.py`, rồi mở và chạy `du_lieu_nguoi_dung/khoi_tao_mysql_rieng.sql` trong MySQL Workbench bằng tài khoản có quyền tạo schema. Sau đó sao chép `du_lieu_nguoi_dung/mysql_ket_noi.env` thành `.env` tại gốc dự án. Nếu máy đã có schema và tài khoản ứng dụng, dùng cấu hình kết nối MySQL hiện có.

Trong cùng cửa sổ PowerShell, chạy `.\chay_web.bat` và mở http://localhost:8501. Biến `CHATBOT_MODEL_DIR` trỏ tới snapshot mô hình vừa tải. Khi mở PowerShell mới, đặt lại biến này hoặc lưu đường dẫn vào `.env`. Tạo tài khoản trong ứng dụng nếu cơ sở dữ liệu mới chưa có tài khoản.

### LLM cục bộ bằng Ollama

Bản web `chay_web.bat` có thêm tóm tắt bằng Ollama, mặc định dùng model đã cài
`qwen2.5:3b`. Không cần API key; chỉ kết nối `127.0.0.1:11434`, không dùng proxy
hay cloud. Nếu Ollama chưa chạy, launcher thử khởi động `ollama serve` ở nền.
Trên máy mới, cài Ollama rồi chạy `ollama pull qwen2.5:3b` một lần khi có mạng.
Sau khi tải đủ mô hình, phần này chạy ngoại tuyến.

Cấu hình tại `cau_hinh/ollama.json`: `enabled` bật/tắt, `model` chọn model đã
tải, `timeout_seconds` giới hạn chờ (tối đa 60 giây). Máy RTX 3050 4 GB dùng
ngữ cảnh 2048 token, batch 128, mô hình giữ trong bộ nhớ 5 phút khi rảnh.
Nếu đổi model hoặc cấu hình, khởi động lại web. Không cần `llama-cpp-python`.

Luồng: truy hồi và kiểm tra quyền nguồn hiện có → LLM chọn tối đa 3 đoạn liên
quan → mã Python dựng tóm tắt từ nguyên văn đoạn đã chọn. Đây là **RAG trích
xuất**, chưa phải chế độ diễn giải tự do. LLM không tạo định lượng, nguồn mới
hoặc lời khuyên điều trị. Tóm tắt hiện phía trên, công thức và nguồn đầy đủ
vẫn ở bên dưới. Các nhánh tính calo, đổi khẩu phần, sức khỏe, từ chối và nội
dung chưa được phép không qua bước rút gọn. Khi thiếu model, timeout hoặc đầu
ra sai, hiển thị câu trả lời gốc. Lựa chọn đoạn có thể chưa tối ưu, cần đối
chiếu nội dung đầy đủ. Không coi bản tóm tắt là toàn bộ quy trình nấu.

Tóm tắt chỉ giữ trong phiên giao diện (tối đa 30 lượt), không ghi thêm vào
MySQL hoặc thay đổi kho staging đã kiểm định. Khi mở lại lịch sử sau phiên
mới, người dùng vẫn thấy câu trả lời gốc.

Kiểm tra kết nối và suy luận thật, không truy cập tài khoản:
`.venv\Scripts\python.exe -B -X utf8 scripts/kiem_tra_ollama.py`.
Kiểm thử bảo toàn dữ liệu:
`.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -p test_ollama_local.py -v`.

### Luồng trả lời LangChain

Chạy bản web bằng `chay_web.bat`. LangChain điều phối xử lý ngữ cảnh, truy hồi và chọn câu trả lời từ dữ liệu. Mô hình embedding dùng cho tìm kiếm. Công thức và calo được lấy hoặc tính từ dữ liệu của dự án.

Tùy chọn backend `che_do_du_lieu=evaluation` giới hạn kho truy hồi ở `answer_Train`. Trước khi báo cáo điểm Test độc lập, cần kiểm tra cả đường trả lời khớp câu trong danh mục nguồn và đường calo, vì chúng có bước tra cứu riêng. Bản web thông thường dùng kho phục vụ `answer_all`; kết quả trên kho đó không phải điểm Test độc lập.

Đề tài môn Các ứng dụng AI của nhóm là xây dựng chatbot hỗ trợ hướng dẫn nấu ăn và gợi ý món ăn theo nhu cầu dinh dưỡng, ưu tiên món miền Tây.

Xem [Hướng dẫn chạy bản demo trên máy mới](HUONG_DAN_CHAY_DEMO.md) để chuẩn bị thư viện, mô hình và chạy thử. Bản demo để nộp dùng `app_demo.py` trong ZIP, chạy Streamlit và LangChain với SQLite, FAISS, BM25 và RRF cục bộ. Đây là cấu hình nhóm dùng để trình diễn.

## Ghi chú phát triển của dự án

Các phần sau ghi lại chức năng và thử nghiệm của mã nguồn dự án qua các phiên bản.

## Hiểu keyword và điều kiện

- Đồng nghĩa: protein/giàu đạm, đậu phụ/đậu hũ, ba chỉ/ba rọi, khổ qua/mướp đắng.
- Có hỗ trợ mẫu không dấu. “Không bị sốt” không mở rộng thành “bị sốt”.
- Dị ứng/không ăn/kiêng: kiểm tra toàn bộ công thức, cả gia vị và nút gợi ý.
- Ăn chay được lọc bảo thủ theo thuần chay.
- Lưu trạng thái riêng từng cuộc trò chuyện: món hiện tại, thứ tự đề xuất, nguyên liệu, điều kiện, dị ứng, thời gian, khẩu phần và câu cần làm rõ. Lưu lại khi mở lịch sử.
- “Món thứ hai” chọn đúng thứ tự vừa hiển thị. “Dùng lại ớt” bỏ sở thích tránh ớt; điều kiện dị ứng cần người dùng đính chính rõ. Điều kiện chưa hiểu được giữ để hỏi rõ.
- Fuzzy chỉ đề nghị tên món để xác nhận, không tự đổi món hoặc nguyên liệu.
- Chỉ công nhận đặc điểm dinh dưỡng khi nguồn có mô tả tương ứng. Không tự suy
  ra giàu đạm từ tên thịt. Chưa có bảng dưỡng chất để xác nhận số kcal/g cụ thể.
- Điều kiện chưa hiểu: hỏi rõ, không bỏ qua.

Bộ lọc văn bản chưa bao phủ tất cả dị nguyên, không kiểm tra tiếp xúc chéo,
không chứng nhận món ăn an toàn cho dị ứng. Chưa có bộ tính thực đơn cá nhân
theo năng lượng, bệnh nền và khẩu phần. Dữ liệu cần được chuyên gia thẩm định.

## Kiểm thử bản nâng cấp

```powershell
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.venv\Scripts\python.exe -X utf8 scripts/kiem_thu_hoi_thoai_v2.py --backend faiss
.venv\Scripts\python.exe -X utf8 scripts/kiem_thu_hoi_thoai_v2.py --backend neo4j
.venv\Scripts\python.exe -X utf8 scripts/kiem_toan_toan_bo.py --tag khong_llm_v2_cuoi --backend faiss
```

Tests chặn kết nối mạng, dùng FAISS và embedding thật, kiểm tra phủ định,
đồng nghĩa, lọc công thức/gợi ý, dữ liệu thiếu, nối tiếp và đường dẫn nguồn.
Kết quả hiện tại và những ca chưa khớp nhãn cũ nằm trong báo cáo bàn giao.
Các bộ phát triển đã dùng nhiều lần; không coi chúng là Test kín hay bằng chứng hiểu mọi câu hỏi. Báo cáo trước đây mô tả phiên bản trước.

## Chạy giao diện web

Bấm đúp `chay_web.bat`, hoặc chạy:
```
.venv\Scripts\python.exe -m streamlit run app.py
```
rồi mở trình duyệt: http://localhost:8501

## Kho tri thức Neo4j

Mặc định dùng **Neo4j cục bộ**, FAISS dự phòng. Dữ liệu lưu dạng đồ thị:
`(:Doan)-[:THUOC_VE]->(:CauHoi)-[:THUOC_NHOM]->(:Nhom)`, thêm một nút `(:Kho)` ghi thông tin kho.

1. Mở Neo4j Desktop → bấm **Start** cho instance (mặc định `bolt://127.0.0.1:17687`).
2. Điền mật khẩu instance vào `.env`: `NEO4J_PASSWORD=...` (xem `.env.example`).
3. Nạp dữ liệu (chỉ cần chạy lại khi dựng lại kho vector):
   ```
   .venv\Scripts\python.exe scripts/nap_neo4j.py
   ```
4. Chạy `chay_web.bat`. Bật chế độ giải thích (`&giai_thich=1` trên đường dẫn) sẽ thấy dòng "kho ... trên **neo4j**".

Neo4j tắt, sai mật khẩu hay chưa nạp dữ liệu → chatbot tự dùng kho FAISS trên đĩa, vẫn trả lời bình thường.
Muốn chỉ dùng FAISS: đặt `"kho_tim_kiem": "faiss"` trong `cau_hinh/chatbot.json`.
Thử truy vấn trong Neo4j Browser: `MATCH (d:Doan)-[:THUOC_VE]->(c:CauHoi)-[:THUOC_NHOM]->(n:Nhom) RETURN d, c, n LIMIT 25`

## Tài khoản

- **MySQL** lưu tài khoản, phân quyền `admin/user`, phiên và lịch sử trong schema `bep_mien_tay`; xem trực tiếp bằng MySQL Workbench. Neo4j tiếp tục giữ kiến thức món ăn.
- **baotram** đã được chủ máy chỉ định làm admin. Đăng nhập bằng mật khẩu hiện có rồi chọn **Quản trị** ở thanh bên.
- User đăng ký mới không tự nhận quyền admin. Admin có thể tạo tài khoản, đổi quyền, khóa/mở khóa và đặt lại mật khẩu; không thể khóa hoặc hạ quyền admin cuối cùng.
- Mỗi tài khoản có **lịch sử trò chuyện** riêng ở thanh bên (mở lại, xóa được). Dữ liệu JSON/SQLite cũ đã được sao lưu và chuyển sang MySQL, đối chiếu từng bản ghi trước khi commit.
- Chi tiết schema, phân quyền, sao lưu và kiểm thử: [HUONG_DAN_ADMIN_USER.md](HUONG_DAN_ADMIN_USER.md).

### Đăng nhập bằng Gmail (tùy chọn)

Nút "Đăng nhập bằng Gmail" bị mờ cho tới khi có mã Google OAuth:

1. Vào https://console.cloud.google.com → tạo một project (tên tùy ý).
2. **APIs & Services → OAuth consent screen** → chọn *External*, điền tên ứng dụng và email
   → ở mục *Test users* thêm các Gmail được phép đăng nhập.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID** → loại *Web application*
   → *Authorized redirect URIs* thêm: `http://localhost:8501/oauth2callback` → bấm *Create*.
4. Chép `.streamlit/secrets.toml.example` thành `.streamlit/secrets.toml`, điền `client_id`, `client_secret`
   vừa nhận, và `cookie_secret` bằng chuỗi in ra từ:
   `.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"`
5. Tắt và chạy lại `chay_web.bat`.

Đăng nhập Gmail được nhớ 30 ngày (tải lại trang không phải đăng nhập lại). **Không** đưa `secrets.toml` lên GitHub.

## Cách chatbot trả lời

### Calo từ Excel chuẩn hóa (23/11/2026)

File chạy web `chay_web.bat` dùng bản backend kế thừa
`staging/release_candidate_20261123_excel_calo`. Bản trước vẫn giữ tại
`staging/release_candidate_20261118_m5_v9`.

Dữ liệu nhập từ bản Excel có 250 công thức và 2.250 câu hỏi nằm trong
`data/calo/cong_thuc.json`; bản dùng trên web được ghim checksum trong manifest.
File `câu hoi.xlsx` tại gốc source hiện là bản mới, có đủ 993 câu gốc tại `Dataset`
và 2.250 câu calo tại `Hoi_dap_calo`, cùng các bảng tính và nguồn. Nội dung 993
câu gốc giữ nguyên. File cũ được sao lưu tại
`../project_backups/before_replace_cau_hoi_20261123/câu hoi.xlsx`.
Không trộn các câu calo vào Train/Test
hoặc dựng lại kho vector. Mỗi câu hỏi về calo được chọn theo đúng công thức đang
được phép sử dụng trong kho hiện tại; số trả lời được tính từ tổng kcal và số phần.

Có thể hỏi “Canh chua cá lóc bao nhiêu calo?”, rồi “Ăn nửa phần thì sao?”.
Tên chung như “cá kho tộ bao nhiêu calo” hiển thị các công thức liên quan để chọn
bằng nút hoặc “Món thứ 1”; không tự gán số calo của một loại cá cho tất cả món.
Kết quả calo kèm các mục xem một khẩu phần, nửa khẩu phần và công thức nấu.
Một tô/đĩa không mặc định bằng một khẩu phần; 100 g món chín cần cân món chín.
Nửa mẻ khác nửa khẩu phần. Công thức có thay nguyên liệu hoặc đang sửa không dùng
lại số gốc. Các bản đang chờ rà soát/tạm ẩn vẫn giữ nguyên giới hạn đó.

Kết quả này là **ước tính theo giả định Excel**, có nguyên liệu dùng dữ liệu đại
diện, không phải hồ sơ dinh dưỡng đã thẩm định, không áp dụng làm lời khuyên điều
trị. Không tự tạo số protein, béo, carbohydrate hoặc natri. Nguồn, cơ sở chia
phần và giả định được hiển thị cùng câu trả lời. Các câu nấu ăn khác tiếp tục
qua luồng hiện có.

Sau khi sửa Excel, nhập lại bằng Python có `openpyxl`:
`python scripts/nap_calo_excel.py "câu hoi.xlsx"`.
Sau đó chạy `python scripts/build_excel_calo.py` và
`python scripts/check_excel_calo_integration.py` bằng môi trường của dự án;
khởi động lại web để nạp phiên bản mới. Không sửa trực tiếp bundle đã ghim checksum.

Kiểm tra tích hợp được lưu tại `audit/excel_calo_integration.json`.

### Dữ liệu đạm, béo, carbohydrate khả dụng và natri

File `câu hoi.xlsx` có thêm sheet `Dinh_duong_250_mon`, các cột dưỡng chất theo
nguyên liệu và nguồn của từng chỉ số. Dữ liệu chuẩn bị cho bước giao diện được
lưu riêng tại `data/dinh_duong/cong_thuc_250.json`; xem định nghĩa và quy tắc thiếu
dữ liệu trong `data/dinh_duong/README.md`. Chưa bật bảng so sánh trước–sau hoặc
thay hồ sơ dinh dưỡng đã duyệt của runtime bằng dữ liệu ước tính này.

152/250 bản có số cho đủ cả bốn chỉ số theo nguồn/kịch bản đã chọn. Số bản có số
đạm: 247; béo: 233; carbohydrate khả dụng: 196; natri: 183. Chỉ số thiếu được ghi
rõ, không thay bằng 0 hoặc coi tổng một phần nguyên liệu là tổng đủ của món.

1. LCEL mở rộng đồng nghĩa, giữ câu gốc và phủ định.
2. Ghép chủ đề câu nối tiếp rồi truy hồi lai bằng RRF.
3. Lọc toàn bộ công thức theo điều kiện trước khi chọn đáp án.
4. Dưới ngưỡng tin cậy: hỏi rõ; ngoài phạm vi: giới thiệu khả năng của bot.
5. Đủ tin cậy: công thức đầy đủ hoặc mục được hỏi, kèm nguồn có thể bấm.
6. Response selector chọn lời dẫn theo template và giữ nội dung nguồn. Khẩu phần chỉ quy đổi dòng có định lượng và khẩu phần gốc rõ ràng; không tự nhân thời gian nấu.
7. Câu không dấu có BM25 phụ; nếu thêm keyword có dấu thì dùng truy hồi lai.

## Thành phần

| File | Vai trò |
|---|---|
| `backend/chatbot/truy_hoi.py` | Truy hồi: vector (FAISS), lai (vector + BM25, RRF), BM25 thuần, chỉ mục không dấu; lọc nhóm, gộp đoạn cùng `id_goc`. Thử: `python -m backend.chatbot.truy_hoi "món canh chua cá lóc"` |
| `backend/chatbot/sinh_cau_tra_loi.py` | Luồng một lượt hỏi (định tuyến, câu nối tiếp, lời nhắc sức khỏe, nhật ký `logs/hoi_thoai.jsonl` không ghi nguyên văn câu hỏi) |
| `app.py` | Giao diện Streamlit |
| `scripts/danh_gia.py` | Benchmark production lịch sử; không phải Test kín. Chế độ ghi ngưỡng từ benchmark đã khóa |
| `data/kiem_thu/` | Bộ câu kiểm thử tự soạn: diễn đạt lại, nối tiếp, ngoài phạm vi, không có dữ liệu |
| `cau_hinh/chatbot.json` | Mọi tham số (kho, k, cách tìm, ngưỡng...) |
