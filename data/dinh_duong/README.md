# Dữ liệu dinh dưỡng cho công thức chuẩn hóa

`cong_thuc_250.json` là dữ liệu chuẩn bị cho bước hiển thị dinh dưỡng, chưa được
dùng làm hồ sơ dinh dưỡng đã thẩm định hoặc để chứng nhận món phù hợp với bệnh.
Nguồn Excel hiện tại là `câu hoi.xlsx`, sheet `Dinh_duong_250_mon`; checksum nằm
trong JSON. 993 câu gốc và 2.250 câu calo được giữ nguyên.

- `profiles`: dưỡng chất trên 100 g hoặc 100 ml, đơn vị cơ sở và nguồn riêng từng
  chỉ số. `proxy_metrics` ghi các chỉ số dùng thực phẩm đại diện/mô hình.
- `ingredients`: định lượng, đơn vị, phần ăn được, kịch bản giữ lại, giá trị từng
  nguyên liệu và ghi chú giả định. Không tự lấy ml làm g.
- `recipes`: tổng, mỗi phần, số phần và danh sách nguyên liệu thiếu theo chỉ số.
  `null` nghĩa là chưa đủ dữ liệu. `known_subtotal` chỉ là phần cộng được, không
  phải tổng đầy đủ của món. Không đưa phần cộng này vào bảng so sánh như tổng.

Chỉ số gồm `protein_g`, `fat_g`, `carbohydrate_available_g`, `sodium_mg`.
Carbohydrate khả dụng dùng Glucid Việt Nam hoặc USDA carbohydrate by difference
trừ dietary fiber. Nếu USDA thiếu fiber thì để thiếu, không mặc định fiber = 0.
Hai phương pháp phân tích không hoàn toàn đồng nhất; đây là phép ghép nguồn ước
tính. Không suy ngược macro bằng tỷ lệ 4/9/4. Phiên bản dinh dưỡng mới là
`DD-<ID>-02`, có `base_version=CH-<ID>-01`. Năng lượng được cộng lại theo kịch bản
nước màu mới; bảng calo CH-01 và câu trả lời calo cũ vẫn giữ nguyên. Khi sử dụng
phải lấy năng lượng và dưỡng chất của cùng phiên bản, không ghép hai phiên bản.

Các hồ sơ đại diện về natri (như loài cá khác) và nguyên liệu gia vị không rõ nhãn
không được dùng để kết luận món ít natri hoặc đáp ứng chế độ ăn điều trị. Muốn
so sánh trước–sau cần giữ đúng phiên bản, định lượng, số phần và nguồn của từng
nguyên liệu; chia số phần đơn thuần không chứng minh giảm muối/béo mỗi phần.

Trong bộ dữ liệu DD-02, 250/250 bản có số cho đủ cả bốn chỉ số theo kịch bản
tham chiếu được người dùng chấp thuận. Đây là mức đủ dữ liệu tính toán, không
phải 250 món đã kiểm nghiệm. Từng chỉ số bổ sung có tên thực phẩm, URL và cờ
đại diện; có thể ghép dữ liệu từ nhiều loài/dạng thực phẩm khác nhau.

Các đại diện có sai khác đáng kể cần chú ý: natri da heo dùng tai heo sống,
natri sá sùng dùng tôm khô, khô cá dùng cá tuyết khô muối, chả lụa dùng bologna
heo, mắm dùng Pla-ra/Ka-pi. Không coi các số này là giá trị chính xác của món.
Nước lá dứa dùng chiết xuất thương mại BIO-NUTRICIA (cô đặc), màu vàng dùng
Queen Yellow; nước dành dành dùng mô hình màu vàng pha loãng 1% với nước.
Đây là kịch bản tính dữ liệu, không hướng dẫn thay chất màu hoặc liều lượng.
Hồ sơ `color` cũ vẫn để null, được thay bằng hồ sơ riêng tại từng nguyên liệu
qua `nutrition_profile_key`. Ngày hoàn thiện: 2026-11-23.
