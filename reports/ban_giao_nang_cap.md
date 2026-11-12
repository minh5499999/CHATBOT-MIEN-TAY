# Bàn giao nâng cấp chatbot — 29/10/2026

## Mã nguồn

- `chatbot/chuoi_langchain.py`: LCEL thực thi chuẩn hóa → truy hồi lai; biểu diễn đoạn bằng LangChain Document.
- `chatbot/ngon_ngu.py`: đồng nghĩa và mẫu không dấu; xử lý phủ định; trích xuất điều kiện loại trừ/nhu cầu dinh dưỡng.
- `chatbot/sinh_cau_tra_loi.py`: lọc toàn bộ tài liệu gốc trước khi trả lời; lọc cả gợi ý; giữ ngưỡng tin cậy; sửa lỗi thiếu nguyên liệu khi hỏi toàn bộ cách nấu; trích URL nguồn từ chuỗi tài liệu tham khảo.
- `chatbot/mo_hinh_sinh.py`: ChatPromptTemplate → mô hình Transformers cục bộ → StrOutputParser. Không sinh khi không có nguồn. Kiểm tra từng câu đầy đủ với nguồn; không đạt thì trả đáp án gốc.
- `chatbot/mo_hinh_vector.py`: chế độ offline không tự tải embedding khi có câu hỏi.
- `scripts/chuan_bi_mo_hinh.py`: tải trước model khi có mạng, độc lập với lúc phục vụ hội thoại.
- `tests/test_chatbot.py`, `scripts/danh_gia_nang_cap.py`: kiểm thử hồi quy, đánh giá có thể chạy lại.

Không thay dữ liệu gốc, không dựng lại hay thay kho vector. Các sửa đổi khác đã có trong workspace trước đợt nâng cấp được giữ nguyên.

## Cấu hình triển khai hiện tại

- LangChain Core 1.7.1 đã được cài trong `.venv`.
- Đã chuẩn bị cache embedding tiếng Việt và Qwen2.5-0.5B-Instruct.
- FAISS local mặc định, `chi_chay_cuc_bo=true`.
- Tắt LangSmith tracing ở cấp package, không cần API key mô hình.
- Model sinh chỉ hỗ trợ chọn câu thông tin đủ tin cậy; công thức và yêu cầu có điều kiện dùng dữ liệu trực tiếp.
- Đăng nhập Google và Neo4j vẫn là tùy chọn riêng. Google cần mạng; FAISS không cần Neo4j.

## Kết quả đã xác minh

- 22 tests đã chạy thành công, bao gồm truy hồi với FAISS/embedding thật khi chặn kết nối socket.
- Kiểm tra cú pháp Python và `pip check` thành công.
- Kiểm thử giao diện bằng Streamlit AppTest: khởi tạo màn hình chat thành công, không có exception, có ô nhập chat. Bộ kiểm thử cần socket nội bộ nên đã chạy ngoài sandbox; chưa phải kiểm thử trực quan trên trình duyệt.
- Trên 44 câu diễn đạt lại: truy hồi không mở rộng có Hit@1 = 41/44; LCEL + keyword đạt 42/44 (95,45%). Hit@5 cả hai = 43/44. Chi tiết trong `danh_gia_nang_cap.json`.
- Đã nạp và chạy thử Qwen thật khi chặn kết nối mạng. Mẫu thử không đạt kiểm tra trích nguồn nên trả `None` để tầng trả lời giữ bản gốc, đúng thiết kế.
- Các kiểm tra này chưa phải đánh giá độ tự nhiên trên nhiều hội thoại hoặc xác nhận độ đúng của tri thức dinh dưỡng.

## Giới hạn cần hiểu khi sử dụng

1. Chưa có bảng dưỡng chất theo khối lượng, khẩu phần và cách chế biến; không thể xác nhận thực đơn 500 kcal hay đủ một lượng protein cụ thể. Bot hỏi rõ khi nhận diện yêu cầu số liệu này.
2. Danh mục loại trừ/đồng nghĩa là danh mục hữu hạn. Nguyên liệu cần tránh chưa hiểu được sẽ khiến bot hỏi rõ, không tự đề xuất món.
3. Bộ lọc văn bản không chứng nhận món ăn an toàn cho dị ứng, không kiểm tra nhãn hàng và tiếp xúc chéo. Ăn chay được xử lý bảo thủ theo thuần chay.
4. Loại trừ nhớ tối đa số lượt cấu hình (hiện 4), không phải hồ sơ dinh dưỡng lâu dài. Muốn đổi hồ sơ rõ ràng, bắt đầu cuộc trò chuyện mới.
5. Qwen 0.5B có năng lực hạn chế. Vì vậy ưu tiên nguồn và trả lời mẫu có cấu trúc, không cam kết diễn đạt tự do mọi câu hỏi.
6. Cần mở rộng bộ kiểm thử độc lập và chuyên gia kiểm duyệt dữ liệu trước khi triển khai tư vấn dinh dưỡng thực tế.

## Chạy lại

Bấm `chay_web.bat` hoặc:

```powershell
.venv\Scripts\python.exe -m streamlit run app.py --server.address localhost
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.venv\Scripts\python.exe -X utf8 scripts/danh_gia_nang_cap.py
```
