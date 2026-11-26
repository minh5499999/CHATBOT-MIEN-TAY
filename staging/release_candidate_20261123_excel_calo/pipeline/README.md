# Pipeline nguồn local — Prompt 3C

Chưa có nguồn dinh dưỡng thật hoặc hành động APPROVED. 250 hồ sơ chỉ giúp chuẩn bị; không phải 250 công thức đủ dinh dưỡng. Các giá trị còn thiếu giữ null. Không API/tải web, không thay engine hay chatbot từ đầu.

## Đường đi dữ liệu

1. CSV/JSON nguồn chuẩn hóa + evidence UTF-8 local → importer 3B `intake` → queue bất biến → `nutrition_pipeline.intake.import_draft` kiểm lại hash và xuất bundle **IMPORTED_UNVERIFIED**, tương thích shape dataset engine. Lỗi bất kỳ dòng/identity/trùng/xung đột chặn cả bundle; không chọn dòng đầu/mới nhất.
2. Người duyệt đối chiếu bản gốc, đơn vị/giá trị/trạng thái/identity/quyền sử dụng; user bổ nhiệm actor và scopes trong reviewer_policy của version mới. Policy hiện tại reviewers={} nên không ai được APPROVED. Import hợp lệ hoặc tên reviewer không tự tạo hành động duyệt.
3. Quyết định riêng (subject path/hash, actor, action, reason, scopes, evidence checks path/hash/passage/document_version/date) được `ReviewQueue.record` ghi append-only theo sequence/previous hash. States: MISSING_SOURCE, IMPORTED_UNVERIFIED, NEEDS_REVIEW, APPROVED, REJECTED, BLOCKED. Chỉ hành động APPROVED được actor có đúng mọi scope mới đủ điều kiện xét dùng. Quyết định sau REJECTED/NEEDS_REVIEW vô hiệu approval trước.
4. `resolve_food` chỉ dùng alias/food catalog đã duyệt với identity_key (loài/sản phẩm) và food_state chính xác; không fuzzy chọn, không dùng trạng thái khác. `resolve_conversion` ràng buộc food/state/unit/mass_basis và chứng cứ. Chưa có alias/conversion thật được duyệt; 946 nhóm tên chỉ là candidate.
5. `build_plan` ghép mapping đủ component theo đúng recipe/version, số phần nguồn chính xác và step review EXPLICITLY_RECONCILED. Chỉ tạo NEEDS_REVIEW, không chứng nhận đầu vào đủ tính. Plan vẫn cần review toàn bộ và engine 3A/3B kiểm đủ năm chất/mass/citations/accounting.
6. `export_reviewed_bundle` chỉ sao đúng bytes của subjects đã có hành động duyệt đầy đủ; dataset/evidence còn cần scope reuse_rights. Không kích hoạt runtime. Test export phải chọn math_fixtures=True và chỉ có scope SYNTHETIC_MATH_TESTS. Không đổi registry scope để phát hành.
7. Candidate mới phải ghim registry, policy, review events và mọi artifact. Adapter 3C dùng `ActionBoundTrustStore`: kiểm cơ chế 3A trước, sau đó cần hành động duyệt phù hợp bytes/actor/scopes/quyền sử dụng và policy PRODUCTION. Reject review event mới/sửa ngoài manifest; reviewer metadata đơn lẻ không đủ. Không tự VERIFIED.

Review log/policy là audit trail local, **không phải chữ ký mật mã chứng minh danh tính/chuyên môn**. Việc bổ nhiệm actor và thẩm định nguồn là hành động của người dùng/người có thẩm quyền; AI không tự làm. Không có phê duyệt y khoa.

## Hồ sơ và template

- catalogs/recipes.jsonl: 250 answer được phép, đúng hash/spans. Original != bản bài gốc ngoài dự án.
- catalogs/recipe_proposals.jsonl: 250 hồ sơ step review; hai bộ riêng originals/proposals cho chín món ưu tiên.
- catalogs/ingredient_occurrences.jsonl: 3017 component giữ quantity/unit as written, food/state/mass null.
- food_catalog/approved_aliases/approved_conversions hiện rỗng. Không nhập dữ liệu dự phòng.
- templates/nutrient_import.csv: header tương thích importer, thêm identity_key và đơn vị explicit; JSON [] để người dùng điền bản ghi thật. Header/array rỗng chưa phải dữ liệu import được.
- templates/aliases.csv, unit_conversions.csv và review_decision.json: chỉ trường trống, không approval/hàm lượng giả.
- Kết hợp nguồn Việt Nam/USDA chỉ khi basis/state/định nghĩa tương thích; không đoán schema gốc, chưa có PDF hoặc dataset thật để viết adapter theo phiên bản.

## Chạy từ root dự án

```powershell
.venv/Scripts/python.exe -B -X utf8 staging/release_candidate_20261116_p3c_v1/code/run_nutrition_pipeline.py status
```

Import trong bản sao/candidate chưa khóa: đặt CSV/JSON và evidence dưới nutrition_sources/incoming, rồi gọi entry với `import ten_file.csv ten_bundle_moi`. Đọc template đầy đủ. Review: đặt decision dưới pipeline/decisions rồi gọi `review ten_quyet_dinh.json`; không gọi APPROVED khi người dùng/chuyên gia chưa thực hiện đối chiếu. Bản khóa từ chối cả import và review. Helper export là API nội bộ, không có nút tự xuất bản/phê duyệt trong Streamlit.

## Giới hạn cần giữ

Step scan liệt kê câu nguồn và gắn cờ, không chứng minh đã tìm mọi thành phần. Nếu xuất hiện thành phần chỉ trong bước mà không biểu diễn được đúng trong component contract hiện có, giữ BLOCKED; cần review cách nhóm/thành phần hoặc catalog có version được duyệt. Không gán thêm source span giả để vượt engine.

Cấp A hiện yêu cầu exact servings theo hợp đồng 3B, kể cả tổng mẻ; chưa nới điều kiện này. Cấp B giữ yield/consumption/retention riêng. Không dùng retention=1 mặc định. Tính thành công bằng ABSTRACT fixture không phải độ chính xác thực phẩm.
