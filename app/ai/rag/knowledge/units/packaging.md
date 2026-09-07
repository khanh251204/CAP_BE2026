# Quy tắc đơn vị tiền tệ Việt Nam

## Mục đích

Tài liệu này dùng để hiểu và chuẩn hóa các cách nói về tiền trong giao dịch tiếng Việt, đặc biệt là cách nói thường dùng của tiểu thương/hộ kinh doanh.

---

## 1. Đơn vị tiền phổ biến

| Cách nói     |       Giá trị |
| ------------ | ------------: |
| 1 nghìn      |     1.000 VNĐ |
| 1 ngàn       |     1.000 VNĐ |
| 1k           |     1.000 VNĐ |
| 1 cành       |     1.000 VNĐ |
| 1 chục       |    10.000 VNĐ |
| 1 chục nghìn |    10.000 VNĐ |
| 1 vạn        |    10.000 VNĐ |
| 1 xị         |   100.000 VNĐ |
| 1 trăm       |   100.000 VNĐ |
| 1 lít        |   100.000 VNĐ |
| 1 triệu      | 1.000.000 VNĐ |
| 1 củ         | 1.000.000 VNĐ |

---

## 2. Quy tắc số + "k"

"K" hoặc "k" sau một số biểu thị đơn vị nghìn đồng.

| Cách nói | Giá trị chuẩn hóa |
| -------- | ----------------: |
| 1k       |             1.000 |
| 2k       |             2.000 |
| 5k       |             5.000 |
| 10k      |            10.000 |
| 15k      |            15.000 |
| 28k      |            28.000 |
| 50k      |            50.000 |
| 100k     |           100.000 |

Ví dụ:

"giá 28k"

→ price = 28000

"mỗi hộp 28k"

→ price = 28000

"mỗi cái 15k"

→ price = 15000

"bán 5 chai, mỗi chai 12k"

→ quantity = 5
→ unit = "chai"
→ price = 12000

---

## 3. Phân biệt số lượng và tiền

Khi câu có cả số lượng và giá, phải phân biệt rõ:

### Số đứng trước tên sản phẩm thường là số lượng

Ví dụ:

"nhập 500 sữa chua Vinamilk"

→ quantity = 500
→ product = "sữa chua Vinamilk"

Không được hiểu:

→ price = 500

---

### Giá đứng sau các từ khóa chỉ giá

Các từ khóa thường gặp:

* giá
* mỗi
* mỗi cái
* mỗi hộp
* mỗi chai
* mỗi lốc
* đơn giá
* một cái
* một hộp
* một lốc
* /cái
* /hộp
* /lốc

Ví dụ:

"nhập 500 sữa chua Vinamilk, mỗi loại 28k"

→ quantity = 500
→ product = "sữa chua Vinamilk"
→ price = 28000

`28k` là đơn giá, không phải số lượng.

---

## 4. Quy tắc "mỗi"

Khi xuất hiện cấu trúc:

**[số lượng] + [sản phẩm] + mỗi + [giá]**

thì:

* số đứng trước sản phẩm → quantity
* số tiền sau "mỗi" → price

Ví dụ:

"nhập 500 sữa chua Vinamilk, mỗi loại 28k"

→ product = "sữa chua Vinamilk"
→ quantity = 500
→ price = 28000

Ví dụ:

"nhập 100 hộp sữa, mỗi hộp 12k"

→ product = "sữa"
→ quantity = 100
→ unit = "hộp"
→ price = 12000

Ví dụ:

"nhập 50 chai nước, mỗi chai 8k"

→ product = "nước"
→ quantity = 50
→ unit = "chai"
→ price = 8000

---

## 5. "Mỗi loại" cũng có thể chỉ đơn giá

Trong ngữ cảnh nhập/bán sản phẩm, các cụm:

* mỗi loại
* mỗi cái
* mỗi sản phẩm
* mỗi đơn vị
* mỗi hộp
* mỗi lốc
* mỗi chai

có thể dùng để biểu thị **đơn giá của một đơn vị sản phẩm**.

Ví dụ:

"nhập 500 sữa chua Vinamilk, mỗi loại 28k"

→ price = 28000

Không được hiểu `28k` là tổng tiền.

---

## 6. Khi có đơn vị rõ ràng

Nếu người dùng nói:

"nhập 500 hộp sữa chua, mỗi hộp 28k"

→ product = "sữa chua"
→ quantity = 500
→ unit = "hộp"
→ price = 28000

Tổng giá trị:

→ total_amount = 500 × 28.000
→ total_amount = 14.000.000 VNĐ

---

## 7. Khi thiếu đơn vị

Nếu người dùng nói:

"nhập 500 sữa chua Vinamilk, mỗi loại 28k"

thì:

→ product = "sữa chua Vinamilk"
→ quantity = 500
→ price = 28000
→ unit = null

Không được tự đoán `unit`.

Hệ thống phải yêu cầu người dùng bổ sung đơn vị:

"500 sữa chua Vinamilk là hộp, lốc hay thùng?"

---

## 8. Phân biệt giá đơn vị và tổng tiền

Nếu câu có:

### "mỗi", "mỗi cái", "mỗi hộp", "mỗi lốc"

→ số tiền sau đó là **đơn giá**.

Ví dụ:

"500 hộp, mỗi hộp 28k"

→ quantity = 500
→ unit = "hộp"
→ price = 28000

---

Nếu câu có:

### "tổng", "hết", "tất cả", "thành tiền"

→ số tiền sau đó là **tổng tiền**.

Ví dụ:

"nhập 500 hộp sữa, tổng 14 triệu"

→ quantity = 500
→ unit = "hộp"
→ total_amount = 14000000

---

## 9. Khi có cả đơn giá và tổng tiền

Ví dụ:

"nhập 500 hộp sữa, mỗi hộp 28k, tổng 14 triệu"

→ quantity = 500
→ unit = "hộp"
→ price = 28000
→ total_amount = 14000000

Hệ thống có thể kiểm tra:

quantity × price = total_amount

500 × 28.000 = 14.000.000

→ hợp lệ.

---

## 10. Không được tự suy diễn giá trị

Nếu cách nói không rõ ràng thì không được tự đoán.

Ví dụ:

"nhập 500 sữa chua"

→ quantity = 500
→ product = "sữa chua"
→ unit = null
→ price = null

Phải yêu cầu người dùng bổ sung thông tin còn thiếu.

Ví dụ:

"nhập 500 sữa chua, mỗi loại 28k"

→ quantity = 500
→ product = "sữa chua"
→ price = 28000
→ unit = null

Chỉ yêu cầu bổ sung `unit`.

---

## 11. Quy tắc ưu tiên khi extract

Khi phân tích câu giao dịch:

1. Xác định sản phẩm.
2. Xác định số lượng.
3. Xác định đơn vị.
4. Xác định đơn giá.
5. Xác định tổng tiền nếu người dùng nói rõ.
6. Không nhầm số lượng với tiền.
7. Không nhầm đơn giá với tổng tiền.
8. Không tự đoán đơn vị khi người dùng không nói.

### Ví dụ quan trọng

"Nhập 500 sữa chua Vinamilk, mỗi loại 28k."

Kết quả mong muốn:

```json
{
  "product": "sữa chua Vinamilk",
  "quantity": 500,
  "unit": null,
  "price": 28000
}
```

Không được trả:

```json
{
  "product": "sữa chua Vinamilk",
  "quantity": 500,
  "unit": null,
  "price": null
}
```

vì `28k` đã xác định rõ là giá.

Không được trả:

```json
{
  "product": "sữa chua Vinamilk",
  "quantity": 28,
  "price": 500000
}
```

vì `500` là số lượng và `28k` là đơn giá.
