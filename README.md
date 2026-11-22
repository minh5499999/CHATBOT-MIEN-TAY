# Chatbot Bếp Miền Tây

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
