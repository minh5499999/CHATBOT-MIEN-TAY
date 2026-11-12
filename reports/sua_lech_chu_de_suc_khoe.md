# Sửa lỗi gợi ý lệch chủ đề sức khỏe — 29/10/2026

## Lỗi đã tái hiện

Hai câu “bị tiểu đường thì nấu được món gì” và “mình bị tiểu đường thì nấu ăn món nào được” đều đi vào nhánh làm rõ chung; các nút gợi ý trước sửa gồm bài ăn chay, tập nấu và ăn nhạt. Các bài này không có bằng chứng đáp ứng tình trạng được hỏi.

Quét nội dung toàn bộ 1.208 đoạn trong kho hiện tại không thấy tiểu đường/đái tháo đường. Kiểm tra kho Neo4j thật cũng không tìm được tài liệu chuyên biệt cho chủ đề này. Vì vậy sửa routing không đồng nghĩa đã có dữ liệu để gợi ý món cho tiểu đường.

Bộ kiểm toán production trước đây chủ yếu đối chiếu câu có sẵn và biến thể với ID nguồn. Nó đã bỏ sót yêu cầu sức khỏe không có trong kho; không thể dùng kết quả đó để tuyên bố bao phủ nhóm câu này.

## Thay đổi

- Thêm `chatbot/suc_khoe.py`: registry thực thể sức khỏe theo cụm và từ đồng nghĩa, kiểm tra phủ định, kiểm tra nguồn cùng chủ đề. Registry chỉ nhận diện tên tình trạng, không chứa đáp án món ăn hay quy tắc điều trị.
- `chatbot/intent.py`: nhận diện cấu trúc “nấu được món gì”, “nấu ăn món nào”, thêm thực thể sức khỏe. Không ánh xạ tiểu đường thành ít đường hay ăn chay.
- `chatbot/trang_thai.py`, `chatbot/hoi_thoai.py`: giữ chủ đề sức khỏe qua các lượt và khôi phục từ câu hỏi trong lịch sử cũ; cho phép đính chính phủ định. Xã giao vẫn được xử lý riêng.
- Trước gợi ý món, yêu cầu tài liệu có tiêu đề chuyên biệt cho tình trạng đang hỏi; nhắc thoáng qua trong nội dung không đủ bằng chứng. Không dùng tiêu đề phủ định làm bằng chứng.
- Cả nguồn trả lời và các nút gợi ý đều qua kiểm tra chủ đề, áp dụng cả nhánh từ nguyên liệu và nhánh truy hồi. Nếu kho không có nguồn phù hợp, phản hồi thiếu dữ liệu theo đúng chủ đề và không kèm nút gợi ý không liên quan.
- Không thêm dữ liệu y khoa chưa được xác minh, không ghi lại database, không đổi kiến trúc LangChain/embedding/Neo4j/FAISS.

Phản hồi hiện tại cho hai câu trong ảnh:

> Bạn đang hỏi về ăn uống cho người có tình trạng **tiểu đường**. Kho hiện tại chưa có tài liệu chuyên biệt đủ để xác nhận món ăn phù hợp với yêu cầu này. Mình cần bổ sung nguồn dinh dưỡng phù hợp cho tình trạng này trước khi gợi ý món có căn cứ.

## Kiểm thử

- **65 tests đạt**: giữ 58 tests cũ, thêm 7 tests cho intent/thực thể, dữ liệu thiếu, đồng nghĩa/không dấu, phủ định, trạng thái hội thoại, lịch sử cũ và xã giao. Một test có nhiều biến thể đầu vào.
- **6/6 trường hợp trên FAISS và 6/6 trên Neo4j thực tế**, gồm hai câu trong ảnh, cách hỏi không dấu, đái tháo đường, thêm nguyên liệu và hỏi tiếp khẩu phần. Báo cáo ghi backend thực tế và không chấp nhận fallback thay cho kết quả Neo4j.
- Mở rộng Streamlit AppTest: gửi hai câu trong ảnh sau khi đang trao đổi một món; yêu cầu phản hồi có đúng chủ đề và không còn nút gợi ý công thức không liên quan. Tài khoản và ghi lịch sử được giả lập trong bộ nhớ.
- Khởi động lại Streamlit ở 8501/8502; health endpoint đều trả thành công.

Bằng chứng: `unittest_suc_khoe.txt`, `sua_chu_de_suc_khoe_faiss.json`, `sua_chu_de_suc_khoe_neo4j.json`, `giao_dien_v2.json`.

## Giới hạn còn lại

Đây là sửa lỗi liên quan chủ đề và xử lý thiếu dữ liệu, chưa phải bổ sung thực đơn cho người tiểu đường. Muốn trả lời bằng gợi ý món cụ thể cần bổ sung nguồn phù hợp đã được duyệt, cùng dữ liệu khẩu phần/dưỡng chất nếu muốn tính toán. Registry tên tình trạng có phạm vi hữu hạn; không khẳng định nhận diện mọi bệnh hoặc mọi cách diễn đạt.
