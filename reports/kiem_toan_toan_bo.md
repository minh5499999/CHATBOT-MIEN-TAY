> Cập nhật tiếp theo: đã phát hiện thêm lỗi hỏi món khi cảm và sửa ở lớp ý định. Thống kê trong trang này là của lượt kiểm toán trước lần sửa đó, không phải cam kết bao phủ mọi câu mới. Xem [báo cáo sửa ý định](sua_y_dinh_an_uong.md).

# Kiểm toán toàn bộ chatbot — 29/10/2026

## Phạm vi và cách đo

Kiểm tra toàn bộ **993 câu hỏi gốc** trong kho sản phẩm, không chỉ một vài ví dụ.
Luồng được gọi là `tra_loi()` thực tế, có LCEL, định tuyến, lọc điều kiện,
gợi ý và truy xuất nội dung đầy đủ. Khi đánh giá, tắt sinh tự do và ghi lịch sử.

Các bộ kiểm tra:

- Mọi câu gốc, bản không dấu, bản thêm lời dẫn.
- Tên món rút gọn từ câu nguồn và yêu cầu thêm nguyên liệu/các bước.
- Câu vùng miền viết riêng, trong đó có “thịt kho hột vịt”.
- 30 câu ngoài phạm vi và 15 câu món chưa có dữ liệu.
- 44 câu diễn đạt lại có nhãn và 5 hội thoại nối tiếp có sẵn.
- Bộ unittest kiểm tra các lỗi cụ thể, chế độ offline và điều kiện ăn uống.
- Một lượt 993 câu gốc chạy qua Neo4j thật; bộ diễn đạt lại/nối tiếp cũng đã chạy qua Neo4j.

Đối chiếu ID câu nguồn và các gợi ý được trả về. “Gợi ý đúng” khác với “trả lời
trực tiếp”: khi chưa chắc hoặc có nhiều công thức, bot đưa lựa chọn đúng để người
dùng xác nhận. Không cộng hai loại này rồi gọi chung là tỷ lệ trả lời trực tiếp.

## Kết quả cuối

Lượt cuối trên FAISS: **3483 trường hợp**, mã băm xử lý khớp với mã hiện tại.

| Bộ câu | Số lượt | Trả đúng ID | Xã giao | Gợi ý đúng | Không trả bừa khi không có đáp án |
|---|---:|---:|---:|---:|---:|
| Câu gốc | 993 | 953 | 40 | 0 | 0 |
| Chưa có dữ liệu | 15 | 0 | 0 | 0 | 15 |
| Không dấu | 993 | 953 | 40 | 0 | 0 |
| Thêm lời dẫn | 953 | 953 | 0 | 0 | 0 |
| Ngoài phạm vi | 30 | 0 | 0 | 0 | 30 |
| Tên món ngắn | 246 | 241 | 0 | 5 | 0 |
| Câu vùng miền/tự soạn | 7 | 5 | 0 | 2 | 0 |
| Hỏi nguyên liệu và các bước | 246 | 241 | 0 | 5 | 0 |

Không có exception, trả sai ID hoặc câu chưa giải đáp theo các nhãn trong lượt cuối này.

Neo4j: **993 câu gốc**, gồm 953 câu trả đúng ID và 40 câu xã giao.
Bộ diễn đạt lại qua Neo4j: **33/44 trả đúng ID, 11/44 đưa gợi ý đúng**.
Hội thoại qua Neo4j: **5/5 đúng ID ở câu nối tiếp**.
Unittest cuối: **33/33 đạt**, gồm kiểm tra cache không bị sửa chéo giữa các lượt.

Hai máy chủ chatbot 8501 và 8502 đã khởi động lại, health check HTTP 200.

Lưu ý: các câu trong lịch sử cũ không được sửa lại; bắt đầu cuộc trò chuyện mới để kiểm tra đầu ra mới.

## Nguyên nhân và sửa đổi

1. **Ngữ nghĩa gần nhưng khác món:** thêm đối chiếu câu FAQ, danh mục tên món
   theo dữ liệu, và kiểm tra tên/nguyên liệu trước khi chấp nhận nguồn. Không tự
   nâng điểm cosine để vượt ngưỡng; bằng chứng khớp câu, tên món và nguyên liệu
   được ghi riêng trong `giai_thich`.
2. **Từ vùng miền:** chuẩn hóa cụm đầy đủ “hột vịt” → “trứng vịt”, “hột gà” →
   “trứng gà”, mướp đắng/khổ qua, đậu phụ/đậu hũ… Không đổi “hột é” thành trứng.
   Phân biệt tên trứng với tên thịt tương ứng.
3. **Thịt kho hột vịt:** dữ liệu có công thức kho rệu ID 59, ghi rõ trứng vịt
   trong nguyên liệu. Bot dùng công thức đó; không dùng bài vịt kho nước dừa.
4. **Bài giới thiệu/ăn kèm lấn công thức:** đối chiếu phần tên món, bỏ lời dẫn
   và phần hỏi đúng ranh giới. Sửa cả lỗi khoảng trắng làm mất đối chiếu tên món.
5. **Phủ định và điều kiện:** phân biệt hỏi “kiêng ăn gì” với khai báo nguyên liệu
   cần tránh; không xem “ăn kiêng” hay “tránh ngộ độc” là một nguyên liệu.
   Không xem câu nhắc “không dùng ớt” là có thêm ớt vào công thức.
6. **Hội thoại:** câu có đại từ chỉ món đã xác nhận được nối bằng ID nguồn,
   không phụ thuộc việc câu nối tiếp còn tìm được ID đó trong top-k hay không.
7. **Trả thiếu mục:** hỏi cả nguyên liệu và các bước sẽ trả toàn bộ công thức.
8. **Tiến trình cũ:** phát hiện hai máy chủ ở cổng 8501/8502; khởi động lại có
   kiểm tra tiến trình thuộc đúng dự án, giữ dữ liệu tài khoản/lịch sử trên đĩa.

Không sửa nội dung CSV hoặc thêm công thức tự viết để làm đẹp số kiểm thử.

Về hiệu năng: câu FAQ/tên món khớp rõ được đối chiếu trực tiếp với metadata trước
khi gọi embedding. Câu chưa khớp vẫn dùng vector + BM25. Cache truy hồi có giới hạn,
cấu hình tham gia khóa cache; trả bản sao cho từng lượt để thao tác lọc/sắp xếp
không làm điều kiện của người trước ảnh hưởng người sau. Đổi dữ liệu cần restart
để nạp lại cache, giống kho/vector hiện có.

## Báo cáo máy có thể đối chiếu

- `kiem_toan_truoc.json`: kết quả trước đợt kiểm toán, có chi tiết từng câu.
- `kiem_toan_cuoi.json`: toàn bộ bộ kiểm tra cuối trên FAISS, kèm mã băm các file xử lý.
- `kiem_toan_neo4j.json`: lượt 993 câu gốc qua Neo4j.
- `kiem_toan_bo_sung_faiss.json`, `kiem_toan_bo_sung_neo4j.json`: diễn đạt lại/nối tiếp.

Các file `sau_v1`, `sau` là kết quả trung gian, không dùng làm kết quả cuối.

## Giới hạn của kết quả

- Câu gốc đã nằm trong kho. So khớp đúng chúng chứng minh khả năng định tuyến
  lại nguồn, không chứng minh hiểu mọi cách diễn đạt mới.
- Tên món ngắn và lời dẫn có một phần sinh tự động. Chúng hữu ích để tìm lỗi
  hệ thống nhưng không thay thế bộ câu người dùng độc lập.
- Bộ 44 câu đã được dùng để phân tích và cải tiến, vì vậy là bộ hồi quy trong
  đợt này; không phải tập giữ lại chưa từng được xem khi tinh chỉnh.
- So khớp ID không thẩm định nội dung dinh dưỡng, độ an toàn y khoa hay độ tự
  nhiên của mô hình sinh. Dữ liệu vẫn cần người có chuyên môn kiểm duyệt.
- Không có kiểm thử hữu hạn nào bảo đảm không còn lỗi với mọi câu hỏi có thể có.
  Với món/điều kiện chưa rõ, hỏi lại hoặc nói thiếu dữ liệu là hành vi cần thiết.

## Chạy lại

```powershell
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.venv\Scripts\python.exe -X utf8 scripts/kiem_toan_toan_bo.py --tag cuoi --backend faiss
.venv\Scripts\python.exe -X utf8 scripts/kiem_toan_toan_bo.py --tag neo4j --backend neo4j --chi-goc
.venv\Scripts\python.exe -X utf8 scripts/kiem_toan_bo_sung.py --backend faiss
.venv\Scripts\python.exe -X utf8 scripts/kiem_toan_bo_sung.py --backend neo4j
```

Neo4j cần RUNNING khi chọn backend neo4j. Không cần nạp lại vector cho đợt sửa
này vì nội dung nguồn và mô hình embedding không thay đổi.
