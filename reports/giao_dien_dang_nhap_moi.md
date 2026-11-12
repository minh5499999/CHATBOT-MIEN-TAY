# Giao diện đăng nhập Bếp Miền Tây

- Giao diện: `chatbot/giao_dien_dang_nhap.py`; được gọi từ `man_hinh_dang_nhap()` trong `app.py`.
- CSS và chuyển động: `assets/login/login.css`.
- Logo nồi SVG: `assets/login/brand-pot.svg`.
- Ảnh nền: `assets/login/bep_mien_tay_background.png`, tạo bằng công cụ imagegen tích hợp, chế độ chỉnh sửa từ ảnh tham khảo của người dùng. Prompt đầy đủ lưu ở `assets/login/IMAGE_PROMPT.txt`.
- Hiệu ứng: nền chuyển động nhẹ, hơi nóng, lá nổi, form xuất hiện và nút phản hồi khi rê chuột. Tôn trọng thiết lập giảm chuyển động của hệ điều hành.
- Form đăng nhập và đăng ký sử dụng dịch vụ tài khoản hiện có. Google chỉ bật khi được cấu hình.

## Kiểm tra

- Đã xem trực tiếp giao diện desktop và form đăng ký ở chiều rộng CSS 392px; form không tràn ngang.
- Kiểm thử `scripts/kiem_thu_admin_user.py --backend mysql` đạt: đăng nhập admin, phân quyền, tạo user, khóa tài khoản/thu hồi phiên, bảo vệ admin cuối và riêng tư lịch sử. Chỉ dùng database kiểm thử.
- Đã khởi động lại và kiểm tra hoạt động ở cổng 8501 và 8502.
