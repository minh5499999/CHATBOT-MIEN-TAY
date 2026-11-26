-- Schema tai khoan Bep Mien Tay. Khong chua mat khau hoac du lieu ca nhan.
CREATE DATABASE IF NOT EXISTS bep_mien_tay CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_ci;
USE bep_mien_tay;
CREATE TABLE IF NOT EXISTS cau_hinh_db (
 khoa VARCHAR(191) PRIMARY KEY, gia_tri LONGTEXT NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS nguoi_dung (
 ten_dang_nhap VARCHAR(384) PRIMARY KEY,
 ten_hien_thi VARCHAR(255) NOT NULL, email VARCHAR(320), google TINYINT NOT NULL DEFAULT 0,
 muoi VARCHAR(128), bam VARCHAR(128), so_vong_bam INT NOT NULL DEFAULT 200000,
 vai_tro VARCHAR(16) NOT NULL DEFAULT 'user', kich_hoat TINYINT NOT NULL DEFAULT 1,
 ngay_tao VARCHAR(32) NOT NULL, cap_nhat VARCHAR(32) NOT NULL,
 CONSTRAINT ck_bmt_vai_tro CHECK (vai_tro IN ('admin','user')),
 CONSTRAINT ck_bmt_kich_hoat CHECK (kich_hoat IN (0,1))
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS phien (
 bam_ma VARCHAR(64) PRIMARY KEY, ten_dang_nhap VARCHAR(384) NOT NULL,
 het_han VARCHAR(32) NOT NULL, tao_luc VARCHAR(32) NOT NULL,
 CONSTRAINT fk_bmt_phien_user FOREIGN KEY (ten_dang_nhap) REFERENCES nguoi_dung(ten_dang_nhap) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS cuoc_tro_chuyen (
 ten_dang_nhap VARCHAR(384) NOT NULL, ma VARCHAR(32) NOT NULL,
 tieu_de VARCHAR(255) NOT NULL, tao_luc VARCHAR(32) NOT NULL, cap_nhat VARCHAR(32) NOT NULL,
 PRIMARY KEY(ten_dang_nhap,ma),
 CONSTRAINT fk_bmt_cuoc_user FOREIGN KEY (ten_dang_nhap) REFERENCES nguoi_dung(ten_dang_nhap) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS tin_nhan (
 id BIGINT PRIMARY KEY AUTO_INCREMENT,
 ten_dang_nhap VARCHAR(384) NOT NULL, ma_cuoc VARCHAR(32) NOT NULL,
 thu_tu INT NOT NULL, du_lieu_json LONGTEXT NOT NULL,
 UNIQUE KEY uq_bmt_tin_thu_tu(ten_dang_nhap,ma_cuoc,thu_tu),
 CONSTRAINT fk_bmt_tin_cuoc FOREIGN KEY(ten_dang_nhap,ma_cuoc)
 REFERENCES cuoc_tro_chuyen(ten_dang_nhap,ma) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS nhat_ky_quan_tri (
 id BIGINT PRIMARY KEY AUTO_INCREMENT,
 nguoi_thuc_hien VARCHAR(384) NOT NULL, doi_tuong VARCHAR(384) NOT NULL,
 hanh_dong VARCHAR(64) NOT NULL, chi_tiet LONGTEXT NOT NULL, tao_luc VARCHAR(32) NOT NULL
) ENGINE=InnoDB;
