# Nguồn local và hàng đợi duyệt Prompt 3B

Chưa có bộ dữ liệu thành phần thực phẩm hoặc bằng chứng recipe/mass/retention được duyệt. Không tự tải web hoặc dùng URL làm chứng cứ. Registry thực tế rỗng, mọi món vẫn BLOCKED.

`recipe_plans/` chứa chín hồ sơ nháp không thực thi, trích nguyên văn phần answer đã được phép từ v5, giữ ID/hash/version/locator/spans. Đây là dữ liệu dự án chưa xác minh, không phải bản nguồn bên ngoài. 214/277 chỉ có answer_text đã lọc; không nhập prose held. 78/203 giữ hồ sơ riêng.

## Tài liệu cần cung cấp để tính món 41 đầu tiên

- Bản nguồn công thức có trang/đoạn, phiên bản/ngày, quyền sử dụng và checksum, để đối chiếu 14 thành phần hiện có và những thứ thêm trong bước nấu.
- Bảng thành phần thực phẩm Việt Nam hoặc bản tải USDA hợp lệ cùng tài liệu định nghĩa, trạng thái thực phẩm, đơn vị, phiên bản và quyền sử dụng; đủ cả năm đại lượng cho từng nguyên liệu, kể cả gia vị, nước mắm, hạt nêm.
- Định lượng đường/muối/hạt nêm/tiêu đang ghi vừa đủ; nhãn nước mắm cụ thể; phần ăn được của cá; quy đổi thơm, cà chua, rau, muỗng; xác nhận số phần từ nguồn. Không tự biến cá nguyên con thành 500 g thịt cá.
- Cấp A: mapping mọi thành phần, khối lượng ăn được và basis đã duyệt; chỉ ước tính tổng nguyên liệu đầu vào, không dinh dưỡng món chín.
- Cấp B: thêm khối lượng thành phẩm, trạng thái, phần dầu/nước dùng/nước chấm thực sự ăn và hệ số giữ lại từng chất có căn cứ.

## Import chỉ để chờ duyệt

Đặt nguồn UTF-8 CSV hoặc JSON (array) trong `incoming/`. Cột bắt buộc xem `code/nutrition_import.py:REQUIRED`, bổ sung energy_unit=kcal, macro_unit=g, sodium_unit=mg. Dùng tên riêng cho mỗi phiên bản, giữ source_path local tương đối, source_sha256, passage, document_version, dataset_version, collected_at, source_locator và reuse_basis. Không dùng null hoặc chuỗi rỗng thay 0; 0 phải xuất hiện rõ trong nguồn.

Từ root dự án chạy:

```powershell
.venv/Scripts/python.exe -B -X utf8 staging/release_candidate_20261116_p3b_v1/code/nutrition_import.py ten_file.csv
```

Importer không xuất bảng APPROVED, chỉ ghi package mới theo SHA vào review_queue; không ghi registry. Bản khóa chỉ nên đọc; thu thập/import vào bản sao hoặc candidate kế tiếp. Định dạng USDA thô cần adapter riêng theo schema/version thực tế được cung cấp; không đoán cột. PDF chưa có file dinh dưỡng để trích; không import binary PDF như nguồn text.

## Quy trình duyệt thủ công

1. Người duyệt đối chiếu từng giá trị, trang/đoạn nguồn gốc, quyền sử dụng, food ID/state/basis/đơn vị, ghi chỗ thiếu và xung đột. Hợp lệ cú pháp chỉ là NEEDS_REVIEW, không APPROVED.
2. Duyệt riêng nguồn recipe, hàm lượng từng nguyên liệu, mass conversion/edible fraction và processing/consumption. Các phạm vi không thay nhau. Không coi bước này là phê duyệt y khoa.
3. Trong candidate mới, chuẩn bị evidence UTF-8 đối chiếu bản gốc, dataset và plan theo hợp đồng engine. Ghi thủ công reviewer, reviewed_at, review_scope, sha256, phiên bản nguồn vào approval_registry; không có nút tự ký duyệt.
4. Cấp B dùng hợp đồng 3A nguyên bản; cấp A cần accounting_method=INGREDIENT_INPUT_ESTIMATE, calculation_level=A, reviewed scopes recipe_mapping/portion_basis/mass/completeness/ingredient_input_estimate. Cấp A yêu cầu mass_basis=EDIBLE, edible_fraction=1 được duyệt, không xuất per100g thành phẩm, không áp hệ số retention/consumed mặc định.
5. Rebuild manifest candidate mới để ghim registry/dataset/evidence/plan, kiểm thử lại. Không sửa bản khóa hoặc thay production. Registry test SYNTHETIC_MATH_TESTS không có quyền production.
