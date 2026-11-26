# Bếp Miền Tây · Chạy demo offline trên Windows

Cần Python CPython 3.12 x64, bộ wheel Windows x64 đã chuẩn bị cục bộ và snapshot mô hình BKAI Vietnamese Bi-Encoder. Giải nén vào thư mục có quyền ghi. Bộ cài Python, wheel và trọng số mô hình chuẩn bị riêng. Runtime dùng CPU, SQLite và FAISS/BM25/RRF. Google OAuth tắt. MySQL và Neo4j không cần cài.

Chạy trong PowerShell từ thư mục vừa giải nén. Trỏ `$wheels` đến bộ wheel cục bộ và `$model` đến thư mục chứa trực tiếp `model.safetensors`, tokenizer và các file cấu hình của snapshot `84f9d9ada0d1a3c37557398b9ae9fcedcdf40be0`. Launcher kiểm tra SHA-256 trước khi chạy.

```powershell
$build = 'staging/release_candidate_20261118_m5_v2'
$wheels = 'C:\offline\wheels'
$model = 'C:\offline\vietnamese-bi-encoder'
py -3.12 -m venv .venv-demo
$p = '.\.venv-demo\Scripts\python.exe'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
& $p -m pip install --no-index --find-links $wheels -r "$build/code/requirements-demo.txt"
& $p -m pip check
& $p -B -X utf8 "$build/code/demo_offline.py" --model-dir $model
```

Mở trình duyệt tại `http://127.0.0.1:8501`. Tự tạo tài khoản khách trong giao diện. SQLite mới nằm trong `runtime` của build. Làm mới tab hoặc mở phiên trình duyệt mới cần đăng nhập lại. Lịch sử được giữ trong SQLite theo tài khoản.

Để kiểm thử quản trị, dừng máy chủ, tạo quyền cho tài khoản local đã đăng ký bằng terminal tại thư mục demo, rồi chạy lại. Không đưa mật khẩu vào lệnh.

```powershell
$env:CHATBOT_STAGING_BUILD = $build
$env:PYTHONPATH = (Resolve-Path "$build/code").Path
& $p -B -X utf8 -c "from backend.chatbot.tai_khoan_dich_vu import khoi_tao_admin_cuc_bo; ok,msg=khoi_tao_admin_cuc_bo(input('Ten dang nhap: ')); print(msg); raise SystemExit(0 if ok else 1)"
```

Gợi ý kịch bản: hỏi bắp cải luộc, thời gian và gợi ý món; mở đậu bắp xào tỏi, giảm dầu ăn, bỏ hạt nêm, viết lại rồi hoàn tác. Có thể hỏi cách lọc và bảo quản dầu đã chiên.

**Phạm vi gói portable.** Gói sạch chứa mã, kho câu trả lời, cấu hình demo và tài nguyên giao diện. Không có dữ liệu người dùng hoặc hồ sơ reviewer thật. Hỏi calo trên gói này sẽ nhận thông báo thiếu hồ sơ. Trong môi trường dự án có quyền, hồ sơ 276-A-FDC89 đang trả 22,25 kcal cho đúng 89 g đầu vào và một phần. Muốn trình diễn con số trên máy khác cần gói chứng cứ và quyền duyệt được phép chuyển giao. Các món còn lại và bản chỉnh sửa hiện chưa có phép tính được duyệt.



ID 267 tạm ẩn trong demo để chờ duyệt bước chế biến. Bản nháp sửa nằm ngoài chương trình trả lời.

## Nếu cần trình diễn calo trên máy khác

ZIP sạch có hồ sơ chứng cứ **chưa ký duyệt** cho 276-A-FDC89. Hỏi calo trước khi duyệt local sẽ chặn. Để xem hồ sơ trên máy nhận, trong PowerShell dùng cùng biến `$p` và `$build` ở trên.

```powershell
$env:PYTHONPATH = (Resolve-Path "$build/code").Path
& $p -B -X utf8 -m nutrition_pipeline.p276 show
```

Người quản lý máy nhận chỉ định người duyệt, xác minh người đó sở hữu tài khoản Admin local đang hoạt động và lập enrollment mới theo cơ chế của dự án. Dùng schema `scope=PRODUCTION` và `reviewers` gắn tên đăng nhập local với các scope in khi chạy CLI. Việc tạo một tài khoản Admin không cấp quyền reviewer. Enrollment và quyết định được giữ ở máy sở hữu, không chuyển từ máy dự án. Khi chưa có enrollment được cấp hợp lệ, dừng ở bước xem hồ sơ.

Sau khi người duyệt thực sự được cấp quyền và tự xem chứng cứ, chính người đó chạy quy trình tương tác dưới đây. Mật khẩu nhập trực tiếp ở terminal và không đưa vào lệnh.

```powershell
$reviewer = Read-Host 'Ten reviewer local da duoc cap quyen'
& $p -B -X utf8 -m nutrition_pipeline.p276 approve --reviewer $reviewer
# Chỉ tiếp tục sau khi quyết định APPROVE được ghi nhận hợp lệ.
& $p -B -X utf8 -m nutrition_pipeline.p276 activate --reviewer $reviewer
& $p -B -X utf8 "$($build)_active/code/demo_offline.py" --model-dir $model
```

Lệnh activate kiểm hồ sơ và engine rồi tạo candidate `_active` có runtime SQLite riêng. Đăng ký tài khoản local trên candidate này nếu cần. Sau đó tự kiểm câu hỏi calo, protein và nguồn FDC 169975, rồi kiểm lại khởi động. Chưa có kiểm thử kích hoạt thật trên máy độc lập.

