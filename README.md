# Thi trắc nghiệm

Web thi trắc nghiệm cho lớp học, chạy trên máy của giáo viên. Sinh viên trong cùng mạng LAN hoặc Wi-Fi mở trình duyệt vào thi.

- **Giáo viên:**
  - tải ngân hàng câu hỏi bằng **file Word**;
  - đặt số câu mỗi sinh viên, thời gian làm bài, giờ mở và đóng phòng;
  - mở hoặc đóng phòng thi;
  - xem bảng điểm và **xuất Excel**.
- **Sinh viên:** không cần tài khoản. Chỉ nhập **mã phòng thi + họ tên + MSSV**, làm bài trong thời gian quy định rồi nộp.
- **Đề khác nhau cho từng sinh viên:**
  - Mỗi sinh viên được rút ngẫu nhiên N câu từ ngân hàng, ví dụ 40 trên 80 câu, với thứ tự câu ngẫu nhiên.
  - Thứ tự phương án A/B/C/D được trộn riêng cho từng người.
- **Câu nhiều đáp án đúng:**
  - Sinh viên thấy nhãn "Chọn tất cả đáp án đúng" và chọn bằng ô tích.
  - Giáo viên chọn cách chấm: đúng hết mới có điểm, hoặc tính điểm từng phần.

## Chạy chương trình

### Cách 1: Python (Windows, Linux, macOS)

Cần Python 3.11 trở lên. Mở PowerShell trong thư mục dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Màn hình in ra 2 địa chỉ:
```
Giáo viên:  http://localhost:8000/teacher
Sinh viên:  http://192.168.1.10:8000/   (máy cùng mạng LAN/Wi-Fi)
```

> **Windows:** lần đầu chạy, Windows hỏi có cho Python dùng mạng không. Chọn **Allow** (cho phép) ở mạng **Private**. Nếu không, máy sinh viên sẽ không vào được.

Cách dừng và các tùy chọn khác:
- Dừng server: nhấn `Ctrl+C`.
- Đổi cổng: `python run.py --port 5000`.

### Cách 2: Docker

```powershell
docker compose up -d --build       # dựng và chạy
docker compose logs -f             # xem nhật ký
docker compose down                # dừng (dữ liệu vẫn giữ trong volume quiz-data)
docker compose down -v             # dừng và XÓA toàn bộ dữ liệu
```

Trong Docker, trang web không tự biết IP thật của máy bạn. Nếu muốn trang giáo viên hiện đúng địa chỉ cho sinh viên, đặt biến `PUBLIC_URL` trước khi chạy:
```powershell
$env:PUBLIC_URL = "http://192.168.1.10:8000"; docker compose up -d --build
```

## Hướng dẫn cho giáo viên

1. **Tạo tài khoản.** Lần đầu vào `http://localhost:8000/teacher`, trang tự chuyển sang bước tạo tài khoản giáo viên.
   - Muốn có thêm tài khoản thì chạy: `python run.py create-teacher TÊN`.
   - Lệnh này cũng dùng để đặt lại mật khẩu cho tài khoản đã có.
2. **Soạn đề trong Word.** Tải **file Word mẫu** ở trang "Tạo đề thi" rồi soạn theo mẫu (xem mục [Định dạng file Word](#định-dạng-file-word)).
3. **Tạo đề thi.** Bấm **Tạo đề thi**, chọn file `.docx`, rồi điền: tên đề, số câu mỗi sinh viên, thời gian làm bài, khung giờ mở phòng (không bắt buộc).
4. **Kiểm tra ngân hàng câu hỏi.** Đề mới tạo luôn ở trạng thái **đóng**.
   - Trang đề thi hiện lại toàn bộ câu hỏi, đáp án đúng có dấu ✓.
   - Câu bị lỗi định dạng được liệt kê riêng, kèm lý do.
   - Sửa file Word rồi bấm **Thay bằng file Word khác** để tải lại. Chỉ làm được khi chưa có ai thi.
5. **Mở phòng thi.** Bấm **Mở phòng thi**, rồi đọc cho sinh viên **mã phòng** (6 ký tự) và **địa chỉ web** hiện trên trang.
6. **Theo dõi bài thi.** Trang **Bảng điểm** cho thấy ai đang làm, ai đã nộp, điểm, phổ điểm.
   - Trong lúc thi, trang tự cập nhật 20 giây một lần.
   - **Xem bài:** mở bài làm của từng sinh viên, thấy chọn đúng hay sai ở từng câu.
   - **Cho vào lại:** dùng khi sinh viên bị thoát, hết pin hoặc đổi máy. Sinh viên vào lại bằng đúng MSSV và làm tiếp. Thời gian vẫn chạy, không được cộng thêm.
   - **Cho thi lại:** xóa bài làm để sinh viên thi lại từ đầu, với đề mới.
   - **Xuất Excel:** tải bảng điểm về máy.
7. **Đóng phòng.** Bấm **Đóng phòng thi**. Sinh viên đang làm vẫn được làm tiếp đến hết giờ.

Trang đề thi có thêm thống kê **"đúng …%"** cho từng câu. Câu có tỉ lệ đúng quá thấp thường là câu quá khó, hoặc nhập nhầm đáp án.

## Hướng dẫn cho sinh viên

1. Mở trình duyệt (máy tính hoặc điện thoại), vào địa chỉ giáo viên cho.
2. Nhập **mã phòng thi**, **họ tên**, **MSSV**, rồi bấm **Bắt đầu làm bài**. Đồng hồ bắt đầu chạy từ lúc này.
3. Trong lúc làm bài:
   - Mỗi lần chọn đáp án là được **lưu ngay**. Lỡ tải lại trang hay mở lại trình duyệt thì bài vẫn còn.
   - Bảng số bên cạnh cho biết câu nào đã làm, bấm vào số để nhảy tới câu đó.
4. Bấm **Nộp bài** để nộp. **Hết giờ thì bài tự nộp.**

## Định dạng file Word

```
Câu 1: Thủ đô của Việt Nam là?
A. Hà Nội
B. Huế
C. Đà Nẵng
D. TP. Hồ Chí Minh
Đáp án: A

Câu 2: Những số nào sau đây là số nguyên tố?
A. 2        B. 9        C. 7        D. 15
Đáp án: A, C
```

**Quy tắc chung:**
- **Câu hỏi** bắt đầu bằng `Câu 1:`. Các dạng `Câu 1.`, `CÂU 1 (0,25đ):` và `Câu hỏi 1:` cũng được nhận.
- Nếu cả file không có chữ "Câu" nào, hệ thống nhận dạng `1.` hoặc `1)` là đầu câu hỏi.
- Nội dung câu hỏi được viết nhiều dòng, ví dụ đoạn code.
- **Phương án** bắt đầu bằng `A.` hoặc `A)`, có thể dùng từ A đến H.
- Nhiều phương án ngắn được viết trên **một dòng**, cách nhau bằng phím **Tab**.
- **Đáp án** là dòng `Đáp án: B`. Hệ thống cũng nhận `Đáp án đúng là: B`.
- **Câu nhiều đáp án đúng** viết `Đáp án: A, C`. Các dạng `A và C` và `AC` cũng được nhận.

**Hệ thống tự xử lý:**
- Phần chữ **trước câu đầu tiên** (tiêu đề, hướng dẫn) và **lời giải sau dòng Đáp án** đều được bỏ qua, sinh viên không thấy.
- File dùng **đánh số tự động của Word** cho câu hỏi (1. 2. 3.) hoặc phương án (A. B. C.) vẫn đọc được.
- Phương án có kiểu "Cả A và B", "Tất cả các đáp án trên" thì câu đó **giữ nguyên thứ tự phương án** khi trộn, để không sai nghĩa.

**Báo lỗi và cảnh báo:**
- Câu thiếu dòng đáp án, đáp án không có trong các phương án, hoặc ít hơn 2 phương án sẽ **bị bỏ qua**, kèm thông báo lỗi chỉ rõ số câu.
- Câu trùng nội dung với câu khác chỉ được **cảnh báo**, không bị bỏ qua.
- Câu có hình ảnh hoặc công thức cũng bị cảnh báo, vì hiện chỉ hiển thị được phần chữ.

**Chỉ nhận file `.docx`.** File `.doc` cũ thì mở bằng Word rồi chọn **Lưu thành (Save As)**, định dạng `.docx`.

## Cách chấm điểm

- **Thang điểm:** thang 10. Mỗi câu có giá trị bằng nhau, tức là 10 chia cho số câu của đề.
- **Câu một đáp án:** chọn đúng được trọn điểm câu đó.
- **Câu nhiều đáp án,** tùy cài đặt của đề:
  - **Đúng hết mới có điểm** (mặc định): phải chọn đúng và đủ tất cả đáp án đúng, không chọn thừa.
  - **Tính điểm từng phần:** điểm câu = (số đáp án đúng đã chọn − số đáp án sai đã chọn) / số đáp án đúng, thấp nhất là 0.
  - Đổi cách chấm sau khi đã có bài nộp thì các bài đó được **chấm lại tự động**.
- **Giờ nộp bài** do máy chủ quyết định:
  - Đồng hồ trên trình duyệt chỉ để hiển thị.
  - Sinh viên tắt máy giữa chừng thì bài vẫn được tính, gồm các câu đã lưu, khi hết giờ.
  - Nộp muộn quá 15 giây sau giờ hết hạn thì chỉ tính các câu đã lưu trước đó.

## An toàn

- **Đáp án đúng không bao giờ được gửi xuống trình duyệt** của sinh viên. Xem mã nguồn trang cũng không thấy.
- **Mỗi MSSV chỉ thi một lần cho mỗi đề.** Cùng MSSV vào thi trên máy khác sẽ bị chặn, trừ khi giáo viên bấm "Cho vào lại".
- **Phiên thi** gắn với trình duyệt bằng token ngẫu nhiên. Mọi form đều có mã chống giả mạo (CSRF).
- **Mật khẩu giáo viên** được lưu dạng băm, không lưu mật khẩu gốc.

> Vì sinh viên không có tài khoản, hệ thống không chống được việc một người nhập MSSV của người khác. Khi thi trên lớp, giáo viên đối chiếu danh sách trên bảng điểm với sĩ số thực tế.

## Cấu trúc thư mục

```
run.py                  chạy server, tạo tài khoản giáo viên
quiz/
  parser.py             đọc ngân hàng câu hỏi từ file Word
  grading.py            rút đề ngẫu nhiên, trộn phương án, chấm điểm
  teacher.py            các trang giáo viên
  student.py            các trang sinh viên (vào thi, làm bài, tự lưu, nộp)
  export.py             xuất bảng điểm Excel
  sample.py             file Word mẫu
  db.py                 cơ sở dữ liệu SQLite
  templates/, static/   giao diện
tests/                  kiểm thử
data/                   CSDL quiz.db (tự tạo khi chạy lần đầu)
```

Chạy kiểm thử:
```powershell
python -m unittest discover -s tests -v
```

**Thư viện:**

| Thư viện | Phiên bản | Dùng để |
|---|---|---|
| Flask | 3.1.3 | web |
| python-docx | 1.2.0 | đọc file Word |
| openpyxl | 3.1.5 | xuất Excel |
| waitress | 3.0.2 | máy chủ web, chạy được trên Windows |
