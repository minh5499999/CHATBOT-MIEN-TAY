-- Mo trong MySQL Workbench va chay de xem tai khoan cua Bep Mien Tay.
-- Mat khau duoc luu bang PBKDF2; cot mat_khau_bam la ma bam, khong phai mat khau goc.
-- CONCAT tao cot tinh toan chi de xem, tranh sua nham ma bam trong Result Grid.
USE bep_mien_tay;
SELECT ten_dang_nhap, ten_hien_thi, CONCAT('', bam) AS mat_khau_bam,
       vai_tro, kich_hoat, ngay_tao
FROM nguoi_dung ORDER BY vai_tro, ten_dang_nhap;
