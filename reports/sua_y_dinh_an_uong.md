# Sửa nhầm ý định hỏi món khi cảm — 29/10/2026

Ví dụ lỗi: “tôi bị cảm thì ăn món gì được” chọn bài ID 823 về ăn hải sản.
Đáp án đúng ý định chung trong kho là ID 771 “Bị cảm nên ăn gì cho mau khỏe”.

## Thay đổi

- `chatbot/y_dinh_an_uong.py`: tách chủ đề và ý định ăn gì/uống gì khỏi câu có
  thực phẩm cụ thể, câu kiêng ăn, trẻ nhỏ, triệu chứng kèm theo và phủ định.
- LCEL đối chiếu câu tổng quát với tiêu đề có cùng ý định/chủ đề, không chọn
  chỉ vì cùng từ “cảm”. Nếu không có một bài tổng quát duy nhất thì giữ đường
  truy hồi, không tự gán một ID cố định hoặc bịa điểm cosine cao.
- Không gọi mô hình sinh cho nhóm dữ liệu sức khỏe 12; giữ nội dung nguồn và
  lời nhắc giới hạn thay vì để Qwen tự diễn đạt lại lời khuyên sức khỏe.
- Test phân biệt câu gợi ý món, câu uống gì, câu hỏi hải sản, kiêng ăn, phủ định
  triệu chứng và trường hợp có yêu cầu riêng. Có các bản có dấu/không dấu.

## Xác minh

- Đã chạy 35 unittest thành công sau lần sửa chính.
- Đã chạy đúng câu lỗi qua Neo4j: `loai=tra_loi`, `nguon_id=771`, `may_tim=neo4j`.
- Các câu nói chung về cảm/ho/sốt được kiểm tra với câu nguồn tương ứng;
  câu hỏi rõ về hải sản không bị đổi thành câu gợi ý món chung.

Lượt kiểm toán 3.483 trường hợp trước đó không bao phủ mọi cách hỏi mới;
không dùng con số đó để khẳng định chatbot không còn lỗi. Đợt này bổ sung bộ
kiểm thử cho nhóm ý định còn thiếu. Nội dung y khoa trong toàn bộ kho vẫn chưa
được chuyên gia kiểm duyệt.

Tham khảo nguyên tắc chăm sóc cảm lạnh chung: [NHS — Common cold](https://www.nhs.uk/conditions/common-cold/)
(nghỉ ngơi, uống đủ nước, ăn uống lành mạnh). Nguồn này không được dùng để suy
ra lệnh kiêng hải sản hoặc tác dụng chữa bệnh của từng món trong dữ liệu nội bộ.
