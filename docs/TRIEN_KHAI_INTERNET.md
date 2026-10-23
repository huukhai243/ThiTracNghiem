# Đưa web thi lên Internet (PythonAnywhere)

Sau khi làm xong, web có địa chỉ cố định **`https://TÊN-CỦA-BẠN.pythonanywhere.com`**:
- Sinh viên thi ở phòng máy, ở nhà hay bằng điện thoại 4G đều được.
- Máy của giáo viên tắt cũng không ảnh hưởng.

Không cần biết quản trị máy chủ: mọi thao tác làm trên trình duyệt, mất khoảng 15 phút.

> Trong hướng dẫn này, **`TÊN`** là tên tài khoản PythonAnywhere của bạn. Hãy thay bằng tên thật ở mọi chỗ.

## Chọn gói

**Beginner (miễn phí):**
- 1 web worker, 512 MB dung lượng.
- Mỗi tháng phải bấm gia hạn một lần (mục 6).
- Đủ để thử và cho lớp nhỏ thi. Mình đã thử 50 sinh viên bấm liên tục trên 1 worker: không lỗi, mỗi lần lưu đáp án trung bình 0,9 giây.

**Developer (~10 USD/tháng):**
- 3 web worker, 5 GB dung lượng.
- **Nên nâng lên gói này cho tháng có thi thật với cả lớp đông.** Thi xong có thể hạ về gói miễn phí.

Giá và giới hạn có thể thay đổi, xem lại tại https://www.pythonanywhere.com/pricing/.

## 1. Tạo tài khoản

1. Vào https://www.pythonanywhere.com → **Pricing & signup** → **Create a Beginner account**.
2. Chọn **tên tài khoản** cẩn thận, vì tên này sẽ thành địa chỉ web (`TÊN.pythonanywhere.com`). Ví dụ: `thitracnghiem-k66`.
3. Xác nhận email.

## 2. Tải code và cài thư viện

Ở trang **Dashboard**, mục *New console*, bấm **Bash**. Cửa sổ dòng lệnh mở ra, dán lần lượt các lệnh sau:

```bash
git clone https://github.com/huukhai243/ThiTracNghiem.git
cd ThiTracNghiem
python3.13 -m venv .venv          # nếu báo không có python3.13 thì dùng python3.12 hoặc python3.11
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests       # kiểm tra: dòng cuối phải là OK
```

**Tạo tài khoản giáo viên ngay bây giờ, trước khi mở web:**
```bash
python run.py create-teacher giaovien
```
Gõ mật khẩu hai lần. Lúc gõ, màn hình không hiện ký tự nào, đó là bình thường.

> Phải tạo tài khoản ở bước này. Nếu chưa có tài khoản giáo viên nào, trang web sẽ mở bước "tạo tài khoản đầu tiên" cho bất kỳ ai vào trước.

## 3. Tạo web app

1. Mở tab **Web** (menu góc trên bên phải) → **Add a new web app** → **Next**.
2. Chọn **Manual configuration**. **Không** chọn "Flask".
3. Chọn đúng phiên bản Python đã dùng ở bước 2 (ví dụ **Python 3.13**) → **Next**.

## 4. Cấu hình (vẫn ở tab Web)

**Virtualenv:** bấm *Enter path to a virtualenv*, nhập:
```
/home/TÊN/ThiTracNghiem/.venv
```

**Code → WSGI configuration file:**
1. Bấm vào đường dẫn dạng `/var/www/TÊN_pythonanywhere_com_wsgi.py`.
2. **Xóa toàn bộ** nội dung có sẵn, dán đoạn sau vào:
   ```python
   import sys
   sys.path.insert(0, '/home/TÊN/ThiTracNghiem')
   from wsgi import application
   ```
3. Bấm **Save**.

**Static files:** thêm một dòng:

| URL | Directory |
|---|---|
| `/static/` | `/home/TÊN/ThiTracNghiem/quiz/static` |

**Security:** bật **Force HTTPS**.

Kéo lên đầu trang, bấm nút xanh **Reload TÊN.pythonanywhere.com**.

## 5. Dùng thử

1. **Giáo viên:** mở `https://TÊN.pythonanywhere.com/teacher`, đăng nhập bằng tài khoản vừa tạo, tạo đề từ file Word, rồi bấm **Mở phòng thi**.
2. **Sinh viên:** mở `https://TÊN.pythonanywhere.com/`, nhập mã phòng, họ tên, MSSV.
3. **Trước buổi thi thật**, cho 2–3 người thi thử. Xong vào Bảng điểm bấm **Cho thi lại** để xóa bài thử.

Giờ trên web luôn là **giờ Việt Nam**, dù máy chủ của PythonAnywhere chạy giờ UTC.

## 6. Việc cần nhớ

- **Gói miễn phí phải gia hạn hằng tháng.** Vào tab **Web**, bấm **Run until 1 month from today**. Quên gia hạn thì web bị tắt. Trước ngày thi, xem lại ngày hết hạn ghi ở tab này.
- **Sao lưu điểm:** sau mỗi buổi thi, bấm **Xuất Excel** trong Bảng điểm. Muốn giữ toàn bộ bài làm thì vào tab **Files** → `ThiTracNghiem/data/` → tải file `quiz.db` về.
- **Cập nhật khi code có bản mới:** mở Bash console rồi chạy:
  ```bash
  cd ~/ThiTracNghiem && git pull && source .venv/bin/activate && pip install -r requirements.txt
  ```
  Sau đó vào tab **Web** bấm **Reload**. Dữ liệu (đề, bài làm, tài khoản) trong thư mục `data/` vẫn được giữ nguyên.
- **Thêm giáo viên hoặc đổi mật khẩu:** trong Bash console, chạy:
  ```bash
  cd ~/ThiTracNghiem && source .venv/bin/activate && python run.py create-teacher TÊN_GV
  ```

## Khi web báo lỗi

- Trang hiện *"Something went wrong"*: vào tab **Web** → **Log files** → **Error log**, xem dòng lỗi cuối cùng.
- Lỗi `ModuleNotFoundError`: đường dẫn Virtualenv chưa đúng, hoặc chưa chạy `pip install -r requirements.txt`.
- Trang hiện nhưng mất màu, mất bố cục: mục **Static files** chưa đúng đường dẫn.
- Sinh viên bị thoát giữa giờ (mất mạng, hết pin): vào Bảng điểm bấm **Cho vào lại**. Sinh viên vào lại bằng đúng MSSV và làm tiếp, thời gian vẫn tính tiếp.
