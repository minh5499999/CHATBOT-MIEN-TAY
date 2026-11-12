> Báo cáo lịch sử của bản trước nâng cấp LangChain. Xem `danh_gia_nang_cap.json` cho đánh giá truy hồi hiện tại.

# Đánh giá chatbot (Bài 4 – Phần V)

- Ngày chạy: 2026-10-22 10:50
- Chatbot **không dùng mô hình sinh câu trả lời**: câu trả lời là nguyên văn câu trả lời gốc của câu hỏi khớp nhất, nên chất lượng phụ thuộc hoàn toàn vào truy hồi và ngưỡng từ chối.
- Mô hình sinh vector (chỉ dùng để tìm kiếm): `bkai-foundation-models/vietnamese-bi-encoder`. Truy hồi tất định: chạy lại cho cùng kết quả.
- Bộ câu (đáp án viết trước khi chạy, trong `data/kiem_thu/`): 198 câu Test · 44 câu diễn đạt lại · 44 bản không dấu của chúng · 5 hội thoại nối tiếp · 30 câu ngoài phạm vi · 15 câu nấu ăn mà dữ liệu không có.

## 1. Truy hồi (kho `<cach>_tat_ca`)

> Câu Test nằm **nguyên văn** trong kho nên cột Test chỉ là cận trên. Bộ **diễn đạt lại** (cùng ý, khác chữ) gần với người dùng thật hơn và là căn cứ chọn cấu hình.

| Cách cắt | Cách tìm | Bộ câu | n | Hit@1 | Hit@3 | Hit@5 | MRR@5 | Nhóm đúng@1 | Trễ P50 (ms) | P90 | P95 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cau_truc | vector | Test (nguyên văn) | 198 | 0.944 | 0.975 | 0.985 | 0.962 | 0.985 | 98 | 121 | 133 |
| cau_truc | vector | Diễn đạt lại | 44 | 0.909 | 0.955 | 1.000 | 0.942 | 0.955 | 98 | 118 | 126 |
| cau_truc | vector | Không dấu | 44 | 0.727 | 0.955 | 0.977 | 0.834 | 0.864 | 18 | 21 | 24 |
| **cau_truc** | **lai** | Test (nguyên văn) | 198 | 0.955 | 0.985 | 0.985 | 0.969 | 0.995 | 106 | 120 | 126 |
| **cau_truc** | **lai** | Diễn đạt lại | 44 | 0.932 | 0.977 | 0.977 | 0.955 | 0.955 | 108 | 113 | 119 |
| **cau_truc** | **lai** | Không dấu | 44 | 0.727 | 0.955 | 0.977 | 0.834 | 0.864 | 19 | 25 | 27 |
| cau_truc | bm25 | Test (nguyên văn) | 198 | 0.980 | 0.995 | 0.995 | 0.987 | 0.995 | 10 | 13 | 13 |
| cau_truc | bm25 | Diễn đạt lại | 44 | 0.727 | 0.909 | 0.909 | 0.814 | 0.795 | 10 | 12 | 12 |
| cau_truc | bm25 | Không dấu | 44 | 0.727 | 0.955 | 0.977 | 0.834 | 0.864 | 18 | 21 | 23 |
| co_dinh | vector | Test (nguyên văn) | 198 | 0.944 | 0.980 | 0.985 | 0.963 | 0.985 | 98 | 114 | 131 |
| co_dinh | vector | Diễn đạt lại | 44 | 0.909 | 0.955 | 1.000 | 0.942 | 0.955 | 99 | 112 | 126 |
| co_dinh | vector | Không dấu | 44 | 0.705 | 0.955 | 0.977 | 0.823 | 0.864 | 18 | 23 | 24 |
| co_dinh | lai | Test (nguyên văn) | 198 | 0.955 | 0.985 | 0.985 | 0.969 | 0.995 | 106 | 121 | 129 |
| co_dinh | lai | Diễn đạt lại | 44 | 0.932 | 0.955 | 0.977 | 0.949 | 0.955 | 107 | 114 | 116 |
| co_dinh | lai | Không dấu | 44 | 0.705 | 0.955 | 0.977 | 0.823 | 0.864 | 19 | 30 | 33 |
| co_dinh | bm25 | Test (nguyên văn) | 198 | 0.970 | 0.995 | 0.995 | 0.982 | 0.980 | 10 | 13 | 14 |
| co_dinh | bm25 | Diễn đạt lại | 44 | 0.682 | 0.909 | 0.909 | 0.788 | 0.750 | 10 | 12 | 12 |
| co_dinh | bm25 | Không dấu | 44 | 0.705 | 0.955 | 0.977 | 0.823 | 0.864 | 18 | 21 | 22 |
| de_quy | vector | Test (nguyên văn) | 198 | 0.949 | 0.980 | 0.985 | 0.966 | 0.985 | 99 | 121 | 132 |
| de_quy | vector | Diễn đạt lại | 44 | 0.909 | 0.955 | 1.000 | 0.942 | 0.955 | 98 | 118 | 124 |
| de_quy | vector | Không dấu | 44 | 0.705 | 0.955 | 0.977 | 0.828 | 0.864 | 18 | 22 | 24 |
| de_quy | lai | Test (nguyên văn) | 198 | 0.955 | 0.985 | 0.985 | 0.969 | 0.995 | 106 | 120 | 127 |
| de_quy | lai | Diễn đạt lại | 44 | 0.932 | 0.977 | 0.977 | 0.955 | 0.955 | 108 | 114 | 120 |
| de_quy | lai | Không dấu | 44 | 0.705 | 0.955 | 0.977 | 0.828 | 0.864 | 19 | 25 | 27 |
| de_quy | bm25 | Test (nguyên văn) | 198 | 0.985 | 0.995 | 0.995 | 0.990 | 0.995 | 10 | 12 | 13 |
| de_quy | bm25 | Diễn đạt lại | 44 | 0.705 | 0.909 | 0.909 | 0.803 | 0.773 | 10 | 12 | 12 |
| de_quy | bm25 | Không dấu | 44 | 0.705 | 0.955 | 0.977 | 0.828 | 0.864 | 18 | 21 | 23 |

Tốt nhất (MRR@5 rồi Hit@1 trên bộ diễn đạt lại): **cau_truc + lai**.

### Theo nhóm – bộ diễn đạt lại (cau_truc + lai)

| Nhóm | n | Hit@1 | Hit@5 | MRR@5 |
|---|---|---|---|---|
| 02_huong_dan_nau_an | 4 | 1.000 | 1.000 | 1.000 |
| 03_huong_dan_nau_mon_mien_tay | 4 | 0.750 | 1.000 | 0.875 |
| 04_mon_an_mien_tay | 4 | 1.000 | 1.000 | 1.000 |
| 05_nguyen_lieu_gia_vi | 4 | 1.000 | 1.000 | 1.000 |
| 06_thay_the_nguyen_lieu | 4 | 1.000 | 1.000 | 1.000 |
| 07_dieu_chinh_cong_thuc | 4 | 1.000 | 1.000 | 1.000 |
| 08_dinh_duong | 4 | 1.000 | 1.000 | 1.000 |
| 09_goi_y_mon_theo_dinh_duong | 4 | 1.000 | 1.000 | 1.000 |
| 10_bao_quan_che_bien | 4 | 1.000 | 1.000 | 1.000 |
| 11_an_toan_thuc_pham | 4 | 0.750 | 0.750 | 0.750 |
| 12_goi_y_khi_om_met | 4 | 0.750 | 1.000 | 0.875 |

### Các câu truy hồi sai tệ nhất (cau_truc + lai, tối đa 10)

| ID đúng | Câu hỏi | Hạng đúng | Top-3 thực tế (ID · câu hỏi · điểm) |
|---|---|---|---|
| 884 | nấu ăn cho người ốm cần lưu ý điều gì | > 5 | 840 · Nấu gì cho nhanh khi người nhà bị ốm đột ngột · 0.614<br>815 · Bị ốm không muốn ăn cơm thì ăn gì thay · 0.545<br>834 · Bị cảm có nên tắm không và ăn uống thế nào · 0.601 |
| 36 | Chào cho mình hỏi chút | > 5 | 24 · Mình đi nấu đây · 0.591<br>20 · Cảm ơn để mình thử · 0.588<br>37 · Cảm ơn bạn rất nhiều · 0.611 |
| 35 | Bạn hỗ trợ được những việc gì vậy | > 5 | 7 · Bạn có thể giúp gì cho tôi · 0.468<br>36 · Chào cho mình hỏi chút · 0.279<br>1 · Xin chào · 0.275 |
| 33 | Chào nha | > 5 | 14 · Cảm ơn nhiều nha · 0.378<br>32 · Ừ cảm ơn nha mai hỏi tiếp · 0.428<br>37 · Cảm ơn bạn rất nhiều · 0.365 |
| 363 | Ngò om nấu ăn cho món nào | 2 | 324 · Ngò om dùng trong món gì · 0.725<br>363 · Ngò om nấu ăn cho món nào · 0.614<br>322 · Ngò rí dùng trong món gì · 0.575 |
| 831 | Đau bụng kinh dữ dội ăn gì uống gì | 2 | 810 · Uống gì giảm đau bụng kinh hiệu quả · 0.718<br>831 · Đau bụng kinh dữ dội ăn gì uống gì · 0.690<br>787 · Đau bụng kinh ăn gì cho bớt đau · 0.689 |
| 364 | Bông điên điển nấu gì ngon | 2 | 332 · Bông điên điển là gì · 0.706<br>364 · Bông điên điển nấu gì ngon · 0.661<br>129 · Canh chua bông điên điển chay nấu sao · 0.603 |
| 103 | công thức cá lóc kho chung với thịt ba chỉ | 2 | 106 · Cá kèo kho tộ với thịt ba chỉ làm sao · 0.705<br>103 · Cá lóc kho thịt ba rọi làm như thế nào · 0.644<br>218 · Thịt ba chỉ kho tiêu làm sao cho nước kho vừa sệt lại · 0.635 |
| 446 | Xương heo hết thì hầm nước dùng bằng gì | 2 | 939 · Cách làm nước dùng xương heo ngon · 0.680<br>446 · Xương heo hết thì hầm nước dùng bằng gì · 0.655<br>991 · Cách nấu súp ngon cho cả nhà · 0.462 |
| 815 | ốm không ăn được cơm thì ăn món gì thay | 2 | 700 · Nấu gì cho người mới ốm dậy ăn · 0.577<br>815 · Bị ốm không muốn ăn cơm thì ăn gì thay · 0.565<br>840 · Nấu gì cho nhanh khi người nhà bị ốm đột ngột · 0.561 |

## 2. Ngưỡng từ chối (Youden J, kho `cau_truc_tat_ca`)

- **Ngưỡng ngoài phạm vi**: tách câu trong lĩnh vực (diễn đạt lại + không có dữ liệu) khỏi câu ngoài phạm vi.
- **Ngưỡng tin cậy**: tách câu diễn đạt lại tìm đúng top-1 khỏi câu tìm sai / không có dữ liệu. Dưới ngưỡng này chatbot không trả lời mà đưa 3 câu hỏi gần nhất để người dùng chọn.
- Họ `khong_dau`: câu gõ không dấu tự chuyển sang BM25 trên chỉ mục phụ không dấu; ngưỡng đo trên bản không dấu của các bộ câu. Điểm họ này tách kém (J thấp) nên ngưỡng ngoài phạm vi được hạ xuống phân vị 5 của câu trong lĩnh vực; ngưỡng tin cậy nâng lên phân vị 95 của câu tìm sai, nên hầu hết câu không dấu nhận 3 câu gợi ý (Hit@3 cao) kèm lời nhắc gõ có dấu thay vì trả lời thẳng.

| Họ điểm | Ngưỡng ngoài phạm vi | J | Ngưỡng tin cậy | J | Điểm top-1 TB: tìm đúng | tìm sai | ngoài phạm vi | không có dữ liệu |
|---|---|---|---|---|---|---|---|---|
| vector | 0.426 | 0.92 | 0.632 | 0.75 | 0.722 (n=41) | 0.632 (n=3) | 0.241 (n=30) | 0.518 (n=15) |
| bm25 | 0.345 | 0.60 | 0.381 | 0.16 | 0.483 (n=32) | 0.459 (n=12) | 0.342 (n=30) | 0.384 (n=15) |
| khong_dau | 0.209 | 0.44 | 0.47 | 0.27 | 0.343 (n=32) | 0.325 (n=12) | 0.247 (n=30) | 0.298 (n=15) |

### Từ chối đo hai chiều (với ngưỡng trên)

| Họ điểm | Ngoài phạm vi bị từ chối ✓ | Không có dữ liệu không bị trả lời ✓ | Diễn đạt lại (tìm đúng) được trả lời ✓ | Diễn đạt lại bị từ chối nhầm ✗ |
|---|---|---|---|---|
| vector | 28/30 | 15/15 | 33/41 | 0/44 |
| bm25 | 22/30 | 9/15 | 29/32 | 3/44 |
| khong_dau | 13/30 | 13/15 | 2/32 | 1/44 |

## 3. Hội thoại nối tiếp (luồng chatbot đầy đủ, cấu hình đề xuất)

| Lượt 1 | Lượt 2 | Câu viết lại | Đúng khi KHÔNG nhớ lượt trước | Đúng khi có nhớ |
|---|---|---|---|---|
| cách nấu canh chua cá lóc miền Tây | món đó cần những nguyên liệu gì | Chỉ mình cách nấu canh chua cá lóc miền Tây với: món đó cần những nguyên liệu gì | ✗ | ✓ |
| hướng dẫn nấu lẩu mắm | món này nấu cho mấy người ăn | Hướng dẫn mình nấu lẩu mắm miền Tây: món này nấu cho mấy người ăn | ✗ | ✓ |
| cách nấu hủ tiếu Mỹ Tho | nó nấu mất bao lâu | Cách nấu hủ tiếu Mỹ Tho tại nhà: nó nấu mất bao lâu | ✗ | ✓ |
| cách kho cá rô với khế chua | món đó sơ chế cá sao cho hết tanh | Cá rô kho khế nấu như thế nào: món đó sơ chế cá sao cho hết tanh | ✗ | ✓ |
| nấu phở bò ở nhà sao cho đơn giản | món này cần những gia vị gì | Cách nấu phở bò tại nhà đơn giản: món này cần những gia vị gì | ✗ | ✓ |

Đúng: 0/5 khi không nhớ → 5/5 khi có nhớ hội thoại.

## 4. Câu trả lời cuối (kho `cau_truc_Train`, đáp án Test KHÔNG có trong kho)

Câu trả lời = nguyên văn câu trả lời gốc của câu hỏi Train khớp nhất, so với đáp án gốc của câu Test. Mốc so sánh: đáp án so với chính nó cho ROUGE-L = cosine = 1.

| Chỉ số | Giá trị |
|---|---|
| ROUGE-L F1 trung bình | 0.240 (n=198) |
| Cosine trung bình với đáp án gốc | 0.602 (n=198) |
| Câu khớp nhất cùng nhóm với câu Test | 0.631 (n=198) |
| Trả lời / chỉ gợi ý / từ chối | 55 / 118 / 25 (n=198) |
| ROUGE-L / cosine chỉ trên câu được trả lời | 0.290 / 0.719 (n=55) |

Phần lớn câu Test là món / ý hỏi không có trong Train, nên chatbot đúng ra phải **chỉ gợi ý** thay vì trả lời; điểm ROUGE-L thấp ở đây phản ánh dữ liệu thiếu, không phải câu trả lời bị bịa. Chấm tay 20 câu ngẫu nhiên trong `reports/cham_tay.csv`.

## 5. Kết luận

- Cấu hình đề xuất: kho **cau_truc**, cách tìm **lai** (diễn đạt lại: Hit@1 0.932, MRR@5 0.955, n=44); ngưỡng vector {'ngoai_pham_vi': 0.426, 'tin_cay': 0.632}, BM25 {'ngoai_pham_vi': 0.345, 'tin_cay': 0.381}.
- Chatbot trả nguyên văn dữ liệu nên không bịa nguyên liệu, định lượng; rủi ro chính là **chọn nhầm câu hỏi gốc** (câu cần ghép nhiều cặp hỏi–đáp, món không có trong dữ liệu nhưng tên gần giống, câu gõ không dấu).
- Hạn chế: bộ diễn đạt lại, ngoài phạm vi và không có dữ liệu là bộ nhỏ tự soạn nên ngưỡng còn dao động; câu Test nằm trong kho nên số trên bộ Test là cận trên.
- `python scripts/danh_gia.py --ghi_cau_hinh` ghi cấu hình đề xuất vào `cau_hinh/chatbot.json`.
