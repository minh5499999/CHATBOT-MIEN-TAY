# Bàn giao Bếp Miền Tây — LangChain, không LLM sinh văn bản

Ngày: 29/10/2026. Đây là bản nâng cấp trên dự án hiện có, không viết lại giao diện hay dữ liệu.


## 1. Kiểm toán và dữ liệu thực tế

Đã đọc các module chạy, scripts và tests; chạy baseline trước khi sửa: **35 tests đạt**. Baseline này chưa bao phủ đầy đủ những tính năng mới, nên không dùng để suy ra mức tăng accuracy.

Kho production có **993 câu gốc, 1.208 đoạn**, gồm 795 câu nhãn Train và 198 câu nhãn Test. Metadata không có bảng kcal/protein/chất béo theo khối lượng và khẩu phần. Parser trích được **250 công thức có danh sách nguyên liệu**, trong đó 216 có khẩu phần gốc rõ và 95 có cả thời gian chuẩn bị + chế biến rõ. Đây là số liệu parser đọc được, không phải xác nhận mọi công thức đã được chuẩn hóa hoàn chỉnh. Chi tiết: `kiem_toan_du_lieu_v2.json`.

Neo4j thực tế: instance BepDinhDuong, `bolt://127.0.0.1:17687`, database `neo4j`; kiểm tra kết nối thành công, 1.208 đoạn, chỉ mục `doan_vector` ONLINE. Đợt này chỉ đọc Neo4j, không nạp lại hoặc ghi đè dữ liệu. Mật khẩu chỉ đọc từ cấu hình riêng.

## 2. Trước và sau

Trước: LCEL truy hồi, đối chiếu FAQ/tên món, kiểm tra một số điều kiện và ghép chủ đề qua lịch sử; còn nhánh chọn câu bằng Qwen cục bộ. Lịch sử chỉ lưu chủ đề, chưa lưu đầy đủ thứ tự món đề xuất và hồ sơ điều kiện.

Sau: LCEL hội thoại thực hiện chuẩn hóa → nhiều intent/thực thể → khôi phục trạng thái → chọn nguồn/gợi ý có lọc → response selector → lưu trạng thái. LCEL truy hồi bên trong giữ nguyên embedding Việt, Vector + BM25 + RRF, Neo4j chính/FAISS dự phòng. Câu FAQ/tên món khớp rõ có đường tra trực tiếp; không gọi embedding cho mọi câu một cách không cần thiết. Câu mới chưa khớp vẫn dùng truy hồi lai và kiểm tra bằng chứng.

Không gán điểm cosine giả để nâng kết quả tra trực tiếp. Trạng thái người dùng không nằm trong cache truy hồi dùng chung; kết quả cache được sao chép trước khi lọc/sắp xếp.

## 3. LangChain nằm ở đâu? Có thể trình bày với giảng viên

- `chatbot/hoi_thoai.py`: `RunnableLambda(prepare) | RunnableLambda(answer) | RunnableLambda(finish)`; gọi chuỗi bằng `.invoke()` trong `tra_loi_co_trang_thai`.
- `chatbot/chuoi_langchain.py`: chuỗi `RunnableLambda` chuẩn hóa và truy hồi, đóng gói đoạn thành `langchain_core.documents.Document`, gọi `.invoke()`.
- `chatbot/sinh_cau_tra_loi.py`: hàm `tra_loi()` là cửa vào tương thích app; chuyển sang chuỗi hội thoại. Tên file giữ để tương thích dự án, không có nghĩa là gọi LLM sinh.
- `scripts/tach_tu.py`: Underthesea tách câu/từ và từ điển riêng. `scripts/tach_doan.py`: chia đoạn trước khi tạo embedding/index. Đây là tiền xử lý dữ liệu; không phải toàn bộ đều do LangChain tự làm.

**Cách giải thích ngắn:** “Em dùng LangChain Core/LCEL để điều phối NLP, ngữ cảnh, truy hồi và chọn phản hồi. Mô hình vietnamese-bi-encoder chỉ tạo vector ngữ nghĩa, không sinh đáp án. Neo4j và FAISS lưu/tìm vector; BM25 tìm từ khóa và RRF hợp nhất thứ hạng. Đáp án lấy từ nguồn rồi điền template. Khi thiếu dữ liệu hoặc có nhiều món tương đương, chatbot hỏi rõ.”

Hệ thống này là chatbot dựa trên truy hồi và trích xuất/template. Không mô tả là một LLM sinh câu trả lời bằng RAG, không nói LangChain tự bảo đảm hiểu mọi câu hỏi.

## 4. Qwen và dependency

Đã bỏ file chạy `chatbot/mo_hinh_sinh.py`, import/lời gọi mô hình sinh, các khóa cấu hình mô hình sinh và cờ tải `--kem-mo-hinh-sinh`. `scripts/chuan_bi_mo_hinh.py` chỉ chuẩn bị embedding. `chatbot/phan_hoi.py` thay bằng template và thân nội dung nguồn.

Giữ torch, transformers, sentence-transformers và các thư viện NLP vì embedding/tokenizer vẫn cần. Không xóa cache model chung hay các file `.bak` lịch sử; chúng không được import trong luồng chạy. Tests kiểm tra không có import dịch vụ sinh văn bản hoặc `AutoModelForCausalLM` trong Python chạy của chatbot/scripts.

## 5. File và trách nhiệm trong đợt nâng cấp

| File | Thay đổi |
|---|---|
| `chatbot/hoi_thoai.py` | Mới: LCEL hội thoại, chọn món theo số, điều kiện, giải thích và lưu trạng thái |
| `chatbot/intent.py` | Mới: đa intent, nguyên liệu sẵn có, thời gian, khẩu phần, kcal và khai báo dị ứng |
| `chatbot/trang_thai.py` | Mới: trạng thái JSON riêng từng cuộc trò chuyện, cập nhật/đính chính điều kiện |
| `chatbot/cong_thuc.py` | Mới: danh mục trích từ nguồn, lọc trước xếp hạng, quy đổi định lượng có đủ dữ liệu |
| `chatbot/fuzzy.py` | Mới: đề nghị tên gần giống để người dùng xác nhận |
| `chatbot/phan_hoi.py` | Mới: nhiều lời dẫn, không thay thân công thức |
| `chatbot/che_do_du_lieu.py` | Mới: production/evaluation, chặn metadata ngoài Train trong evaluation |
| `chatbot/ngon_ngu.py` | Cụm địa phương/viết tắt, phân biệt ít dầu/ít béo, ớt và phủ định |
| `chatbot/sinh_cau_tra_loi.py` | Bỏ Qwen, nhận điều kiện có cấu trúc, giữ đúng ID đã chọn, nhiều intent |
| `chatbot/tai_khoan.py`, `app.py` | Giữ trạng thái khi lưu/mở lịch sử; đánh số đúng các nút gợi ý |
| `chatbot/__init__.py` | Mô tả kiến trúc hiện tại; giữ tắt tracing ra ngoài |
| `cau_hinh/chatbot.json`, `.env.example` | Bỏ cấu hình sinh; thêm chế độ dữ liệu; ví dụ URI đúng cổng hiện tại |
| `scripts/quan_ly_keyword.py` | Mới: phân tích Train, đề xuất có ID nguồn và hash, không tự áp dụng |
| `scripts/kiem_thu_hoi_thoai_v2.py` | Mới: kiểm thử backend thật, báo lỗi nếu yêu cầu Neo4j mà dùng FAISS |
| `scripts/kiem_tra_giao_dien_v2.py` | Mới: Streamlit AppTest, mock lưu tài khoản/lịch sử để không đụng hồ sơ thật |
| `tests/test_hoi_thoai_v2.py`, `tests/test_chatbot.py` | Thêm regression hội thoại, dữ liệu, dị ứng, fuzzy, định lượng, bỏ test generator |
| `scripts/chuan_bi_mo_hinh.py` | Bỏ tùy chọn tải mô hình sinh |
| `scripts/kiem_toan_toan_bo.py`, `scripts/kiem_toan_bo_sung.py` | Chạy qua luồng mới, bỏ cờ mô hình sinh; ghi backend thực tế và nguồn kiểm toán |
| `scripts/danh_gia.py` | Khóa ghi ngưỡng từ benchmark production, bỏ Test khỏi tiêu chí phá hòa |
| `README.md` | Cập nhật kiến trúc, cài đặt và cách kiểm tra |

Các thay đổi Git có trước đợt này, tài liệu PDF đã thiếu từ trước và dữ liệu người dùng không được reset hoặc xóa để làm sạch working tree.

## 6. Hội thoại, điều kiện và phản hồi

Năm cách hỏi thịt kho hột vịt trong yêu cầu đều lấy nguồn **ID 59**, công thức kho rệu ghi rõ trứng vịt. Không có ID 59 hard-code trong tầng trả lời; ID mong đợi chỉ nằm ở bộ kiểm thử. Hột vịt được đổi theo cụm thành trứng vịt; hột é giữ nguyên. Phần trứng vịt được che khi nhận diện thịt vịt để tránh nhầm loài.

“Gợi ý món ăn từ cá lóc” tạo danh sách công thức thật và nêu nguyên liệu cần thêm. “Món thứ hai” lấy ID theo thứ tự danh sách đã lưu, không suy đoán lại bằng vector. “Không dùng ớt” giữ món đang nói và thêm điều kiện. Nếu nguồn chứa ớt, bot báo chưa có phiên bản đáp ứng; không tự bỏ ớt hoặc đổi món khác. “Nấu cho 3 người” ghi nhận khẩu phần ngay cả khi còn điều kiện khiến công thức chưa phù hợp.

Chỉ quy đổi dòng có số lượng và đơn vị rõ, khẩu phần gốc rõ. Dòng định lượng dạng khoảng, không định lượng hoặc chứa nhiều số quy đổi chưa chắc chắn được giữ ở mục chưa quy đổi. Công thức gốc vẫn có để đối chiếu. Không tự nhân thời gian nấu.

Dị ứng được lưu riêng và hợp nhất vào bộ lọc. “Bỏ hết điều kiện” hay “ăn lại tôm” không âm thầm xóa dị ứng đã khai báo; người dùng phải đính chính rõ như “tôi không dị ứng tôm”. Nguyên liệu dị ứng chưa nhận diện được vẫn giữ trạng thái cần làm rõ ở lượt sau.

## 7. Keyword Manager và dựng lại dữ liệu

Chạy từ thư mục dự án có `app.py`:

```powershell
.venv\Scripts\python.exe -X utf8 scripts/quan_ly_keyword.py
```

Manager kiểm tra kho chỉ có Train, quét cả câu hỏi/nội dung, trích cụm ứng viên, tiêu đề, nguyên liệu, nhãn dinh dưỡng có ID nguồn, từ địa phương hiện hành và mục trùng cần duyệt. Xuất `reports/de_xuat_keyword_train.json`: 795 câu Train, **451 cụm đề xuất chờ duyệt**, hash nguồn, phiên bản và quy trình kiểm thử. Không coi gần embedding là đồng nghĩa; không tự ghi 451 cụm vào từ điển. Danh sách cần người duyệt ngôn ngữ/dữ liệu và bổ sung ca đúng + ca nhầm/phủ định trước khi chấp nhận.

Khi sửa CSV gốc hoặc từ điển ảnh hưởng văn bản embedding, sao lưu nguồn rồi chạy tuần tự:

```powershell
.venv\Scripts\python.exe scripts/tach_tu.py
.venv\Scripts\python.exe scripts/tach_doan.py --cach cau_truc
.venv\Scripts\python.exe scripts/tao_kho_vector.py --cach cau_truc --tap Train
.venv\Scripts\python.exe scripts/tao_kho_vector.py --cach cau_truc --tap tat_ca
.venv\Scripts\python.exe scripts/nap_neo4j.py --kho kho_vector/cau_truc_tat_ca
.venv\Scripts\python.exe scripts/kiem_tra_neo4j.py
```

`nap_neo4j.py` làm mới các đoạn thuộc kho chỉ định; chỉ chạy khi dữ liệu/index thay đổi và đã kiểm tra bản sao lưu. Đợt nâng cấp mã này không cần chạy lệnh nạp. Sau cập nhật dữ liệu, khởi động lại Streamlit để xóa cache kho/câu hỏi. Không chỉ sửa file CSV rồi kỳ vọng Neo4j tự đồng bộ.

## 8. Production và evaluation

Production dùng toàn bộ tri thức đã phê duyệt trong `cau_truc_tat_ca`. Tùy chọn `che_do_du_lieu='evaluation'` chọn `cau_truc_Train`; yêu cầu dùng kho có bất kỳ dòng Test sẽ bị từ chối. Đối chiếu tên, fuzzy và danh mục công thức đều dùng đúng kho được chọn. Manager keyword chỉ đọc Train.

Các nhãn Test hiện có và bộ 44 câu đã được sử dụng trong lịch sử phát triển. Không thể tuyên bố chúng chưa từng được nhìn thấy. Chưa xây mô hình SVM hoặc tự hiệu chuẩn trọng số/ngưỡng mới trên Test. Ngưỡng fuzzy hiện là heuristic bảo thủ, kiểm tra bằng bộ phát triển và luôn chờ xác nhận, chưa phải ngưỡng tối ưu đã chứng minh trên validation độc lập.

Muốn đánh giá tổng quát hóa nghiêm túc cần đóng băng pipeline/từ điển, lập validation riêng từ dữ liệu Train được phép và thu bộ Test mới chưa dùng. Các kết quả bên dưới là regression/kiểm toán sản phẩm, không phải accuracy/F1 trên Test kín.

## 9. Kết quả thực tế

| Kiểm tra | Kết quả và giới hạn |
|---|---|
| Baseline trước sửa | 35 tests đạt |
| Unit/integration offline sau sửa | **58 tests đạt**, dùng FAISS/embedding thật, chặn kết nối mạng trong integration |
| Kiểm toán production diện rộng FAISS | **3.483 lượt**, không có ca trả sai ID/exception theo nhãn nguồn; có những ca chỉ gợi ý đúng, không phải tất cả đều trả lời trực tiếp |
| 993 câu gốc | 953 trả đúng ID, 40 xã giao đúng nhóm |
| 993 bản không dấu | 953 trả đúng ID, 40 xã giao đúng nhóm |
| 953 câu thêm lời dẫn | 953 trả đúng ID |
| 246 tên ngắn + 246 yêu cầu công thức | Mỗi nhóm: 241 trả đúng, 5 gợi ý có ID mong đợi |
| 30 ngoài phạm vi + 15 thiếu dữ liệu | 45 không trả lời như có đáp án |
| 7 ca thủ công | 5 trả đúng, 2 gợi ý đúng |
| Bộ mới có điều kiện/hội thoại | **15/15 trên FAISS**, **15/15 trên Neo4j thực tế**; báo cáo kiểm tra backend thực tế, không chấp nhận fallback thay cho Neo4j |
| Bộ 44 cách diễn đạt cũ | Trên mỗi backend: 33 trả đúng ID, 10 gợi ý đúng, **1 chưa khớp nhãn cũ** |
| 5 hội thoại cũ | 5/5 trên mỗi backend |
| Streamlit AppTest | Màn đăng nhập hiển thị; chat với tài khoản giả lập, số thứ tự, chọn món 2, lưu trạng thái và debug không lỗi |

Ca chưa khớp nhãn cũ: **“có sẵn thịt gà thì nấu món gì dễ”**. Nhãn cũ mong nguồn 711; luồng mới gợi ý công thức nguồn 210/46/85. Không sửa nhãn để biến thành đạt. Cần đánh giá thêm mức độ dễ và cách chọn giữa bài gợi ý chung với danh sách công thức, hiện chưa có dữ liệu độ khó có cấu trúc.

Độ trễ đo trên máy này nằm trong `hoi_thoai_v2_faiss.json` và `hoi_thoai_v2_neo4j.json` (có lần nạp/warm cache, mẫu nhỏ, không phải cam kết hiệu năng). Kiểm toán nguồn có hash phiên bản mã trong từng report. Kiểm thử quy đổi nhiều số được chạy ở bộ unit/integration riêng, không suy ra từ việc đối chiếu ID.

Bằng chứng: `unittest_v2.txt`, `kiem_toan_khong_llm_v2_cuoi.json`, `hoi_thoai_v2_faiss.json`, `hoi_thoai_v2_neo4j.json`, `kiem_toan_bo_sung_faiss.json`, `kiem_toan_bo_sung_neo4j.json`, `giao_dien_v2.json`. AppTest không đăng ký tài khoản thật, không kiểm thử OAuth Google thật và không phải kiểm tra thủ công mọi chi tiết giao diện.

## 10. Chạy trên Windows

Mở terminal tại thư mục dự án chứa `app.py`; bật instance BepDinhDuong trước nếu muốn dùng Neo4j.

```powershell
.venv\Scripts\python.exe scripts/kiem_tra_neo4j.py
.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Hoặc bấm `chay_web.bat`. Mở `http://localhost:8501`. Script `scripts/khoi_dong_lai_web.ps1` khởi động lại hai cổng 8501/8502 đang dùng của dự án, có kiểm tra tiến trình sở hữu cổng trước khi dừng.

Để lặp kiểm thử:

```powershell
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.venv\Scripts\python.exe -X utf8 scripts/kiem_thu_hoi_thoai_v2.py --backend faiss
.venv\Scripts\python.exe -X utf8 scripts/kiem_thu_hoi_thoai_v2.py --backend neo4j
.venv\Scripts\python.exe -X utf8 scripts/kiem_toan_bo_sung.py --backend faiss
.venv\Scripts\python.exe -X utf8 scripts/kiem_toan_bo_sung.py --backend neo4j
.venv\Scripts\python.exe -X utf8 scripts/kiem_tra_giao_dien_v2.py
```

## 11. Giới hạn và dữ liệu cần bổ sung

- NLP theo quy tắc, từ điển, fuzzy và truy hồi vẫn có thể bỏ sót cách nói, lỗi gõ nhiều từ, tên gần giống hoặc câu nhiều điều kiện phức tạp. Không cam kết hiểu mọi câu.
- Chưa có bảng dưỡng chất đáng tin theo gram/khẩu phần, chuẩn nguyên liệu, dị nguyên đầy đủ, thời gian/độ khó cho mọi món. Không tự suy calo/protein từ similarity hoặc từ việc có thịt/rau.
- Bộ lọc văn bản bảo thủ không kiểm tra nhãn gia vị hoặc tiếp xúc chéo. Dữ liệu sức khỏe giữ theo nguồn cũ, chưa được chuyên gia y khoa thẩm định toàn bộ.
- Không tự tạo công thức thay thế/phiên bản bỏ nguyên liệu. Nếu không có bản nguồn phù hợp sẽ hỏi rõ hoặc báo thiếu dữ liệu.
- Keyword Manager xuất đề xuất; quy trình duyệt và bổ sung regression trước áp dụng vẫn cần người chịu trách nhiệm dữ liệu.
- Chưa có bộ Test kín mới hay nhãn đa intent được chuyên gia kiểm duyệt để báo cáo F1/accuracy tổng quát. Các tests phát triển và câu có sẵn trong kho không thay thế được việc đó.
