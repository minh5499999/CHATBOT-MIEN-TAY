"""API tài khoản của app; backend được chọn bằng TAI_KHOAN_BACKEND.

Backend: tai_khoan_dich_vu.py. Kết nối: co_so_du_lieu.py/co_so_du_lieu_mysql.py.
Giữ tên hàm để tương thích giao diện và lịch sử cũ.
"""
from backend.chatbot.tai_khoan_dich_vu import (
    dang_ky, dang_nhap, dang_nhap_google, doc_ho_so, la_admin,
    tao_phien, nguoi_dung_theo_phien, xoa_phien,
    danh_sach_cuoc_tro_chuyen, luu_cuoc_tro_chuyen, xoa_cuoc_tro_chuyen,
    rut_gon_ket_qua, danh_sach_nguoi_dung, admin_tao_tai_khoan,
    admin_cap_nhat, admin_dat_lai_mat_khau, nhat_ky_quan_tri, admin_xoa_tai_khoan,
)
