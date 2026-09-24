# 🌌 AGY Telegram Bot (Ubuntu 24.04 LTS)

Dự án **AGY Telegram Bot** mang toàn bộ trải nghiệm giao diện và sức mạnh của **Google Antigravity (AGY)** lên Telegram trên hệ điều hành **Ubuntu 24.04 LTS**.

Bạn có thể điều khiển `agy` từ xa mọi lúc mọi nơi qua điện thoại hoặc máy tính thông qua Telegram: chuyển đổi Model AI, chọn thư mục dự án (Workspace), xem và khôi phục lịch sử chat, gửi code, upload file, và thiết lập tác vụ tự động.

---

## 📸 So khớp tính năng với Giao diện Antigravity IDE

| Giao diện Antigravity Desktop (Ảnh) | Tính năng trên Telegram Bot | Lệnh & Thao tác |
| :--- | :--- | :--- |
| **`+ New Conversation`** | Khởi tạo phiên trò chuyện mới độc lập | Nút `➕ Cuộc trò chuyện mới` hoặc `/new` |
| **`Conversation History`** | Xem danh sách các cuộc hội thoại cũ & tiếp tục | Nút `📜 Lịch sử chat` hoặc `/history` |
| **`Conversations` List** | Tự động đồng bộ lịch sử từ `~/.gemini/antigravity` | Nút khôi phục theo tiêu đề prompt |
| **`Projects` / `No Project`** | Quản lý và đổi thư mục làm việc (Workspace root) | Nút `📁 Dự án` hoặc `/project`, `/add_project` |
| **`Model Selector` (Gemini 3.8 Flash High)** | Đổi trực tiếp mô hình AI cho phiên làm việc | Nút `🤖 Model` hoặc `/model` |
| **`Scheduled Tasks`** | Lên lịch chạy lệnh định kỳ (Cron / Intervals) | Nút `⏰ Tác vụ hẹn giờ` hoặc `/schedule` |
| **Chat Input / Submit** | Gửi tin nhắn văn bản, code, ảnh, file đính kèm | Nhập tin nhắn hoặc đính kèm tệp trực tiếp |
| **Realtime Streaming & Tools** | Cập nhật trực tiếp kết quả suy luận & thực thi tool | Live stream edit message kèm nút `🛑 Dừng tác vụ` |

---

## 📂 Cấu trúc thư mục dự án

```text
agy-telegram-bot/
├── config.py                 # Nạp cấu hình (.env), kiểm tra whitelist ID, đường dẫn
├── agy_client.py             # Giao tiếp bất đồng bộ với agy CLI (stream-json, hủy tiến trình)
├── session_manager.py        # Lưu trữ trạng thái phiên người dùng, đồng bộ lịch sử Antigravity
├── keyboards.py              # Bàn phím Inline Telegram mô phỏng giao diện Antigravity
├── formatters.py             # Định dạng HTML Telegram, chia nhỏ tin nhắn dài, hiển thị badge
├── scheduled_tasks.py        # Quản lý tác vụ định kỳ qua JobQueue của Telegram
├── handlers/
│   ├── start.py              # /start (Dashboard chính) và /help
│   ├── chat.py               # Xử lý prompt, streaming trực tiếp và tệp đính kèm
│   ├── callbacks.py          # Xử lý sự kiện click các nút Inline
│   └── commands.py           # Phím tắt (/new, /model, /project, /history, /stop, /schedule)
├── main.py                   # Điểm khởi chạy Bot & đăng ký handlers
├── requirements.txt          # Các thư viện Python cần thiết
├── .env.example              # Mẫu biến môi trường
├── install.sh                # Script cài đặt tự động 1-Click trên Ubuntu 24.04
├── agy-telegram-bot.service  # File cấu hình chạy ngầm Systemd Service
└── README.md                 # Tài liệu hướng dẫn sử dụng
```

---

## 🚀 Hướng dẫn cài đặt nhanh trên Ubuntu 24.04 LTS

### Bước 1: Sao chép thư mục dự án lên Ubuntu
Nếu bạn copy thư mục này lên máy chủ Ubuntu (ví dụ tại `/home/ubuntu/agy-telegram-bot`):

```bash
cd /home/ubuntu/agy-telegram-bot
```

### Bước 2: Chạy script cài đặt tự động
Cấp quyền thực thi và chạy `install.sh`:

```bash
chmod +x install.sh
./install.sh
```

Script sẽ tự động:
1. Cài đặt Python 3, `python3-pip`, `python3-venv`.
2. Kiểm tra lệnh `agy` CLI trên máy.
3. Tạo môi trường ảo `venv` và cài đặt các thư viện cần thiết.
4. Tạo file cấu hình `.env`.

---

## ⚙️ Cấu hình biến môi trường (`.env`)

Mở file `.env` vừa được tạo:

```bash
nano .env
```

Điền các thông tin:

```ini
# Token nhận từ @BotFather trên Telegram (BẮT BUỘC)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz

# Danh sách ID Telegram được phép dùng bot (Bảo mật - phân cách bằng dấu phẩy)
# Chat với @userinfobot trên Telegram để lấy ID của bạn
ALLOWED_USER_IDS=12345678,98765432

# Đường dẫn đến file agy (mặc định là 'agy' nếu đã có trong $PATH)
AGY_BIN_PATH=agy

# Model mặc định khi tạo chat mới
DEFAULT_MODEL=gemini-3.8-flash-high

# Mức độ suy luận mặc định: low, medium, high
DEFAULT_EFFORT=high

# Thư mục làm việc mặc định (để trống nếu muốn "No Project")
DEFAULT_PROJECT_DIR=

# Thư mục Antigravity trên Ubuntu
ANTIGRAVITY_HOME=~/.gemini/antigravity
```

Lưu file bằng `Ctrl + O` -> `Enter`, sau đó thoát bằng `Ctrl + X`.

---

## 🏃 Khởi động và kiểm tra Bot

### Chạy thử nghiệm thủ công:
```bash
source venv/bin/activate
python main.py
```
Mở Telegram, tìm bot của bạn và gõ `/start` để xem Bảng điều khiển Antigravity!

---

## 🛡️ Thiết lập chạy ngầm vĩnh viễn (Systemd Service)

Để bot tự khởi động khi máy chủ Ubuntu boot lại và tự khởi động lại nếu có sự cố:

1. Chỉnh sửa đường dẫn và user trong file `agy-telegram-bot.service` nếu username của bạn khác `ubuntu`:
   ```bash
   nano agy-telegram-bot.service
   ```

2. Cài đặt service vào hệ thống:
   ```bash
   sudo cp agy-telegram-bot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable agy-telegram-bot
   sudo systemctl start agy-telegram-bot
   ```

3. Kiểm tra trạng thái service:
   ```bash
   sudo systemctl status agy-telegram-bot
   ```

4. Xem nhật ký log thời gian thực:
   ```bash
   journalctl -u agy-telegram-bot -f
   ```

---

## 💡 Hướng dẫn sử dụng các chức năng chính

### 1. Bảng điều khiển chính (`/start` hoặc `/status`)
Hiển thị đầy đủ trạng thái tương tự như cửa sổ Antigravity:
- Model đang chọn (ví dụ: `gemini-3.8-flash-high`)
- Thư mục dự án đang chọn (ví dụ: `No Project` hoặc `/home/ubuntu/app`)
- Cuộc hội thoại đang chọn
- Mức độ suy luận (`HIGH`) & Chế độ duyệt quyền (`TỰ ĐỘNG`)

### 2. Bắt đầu phiên chat mới (`/new`)
Bấm nút `➕ Cuộc trò chuyện mới` hoặc gõ `/new`. Bot sẽ tách biệt ngữ cảnh hoàn toàn, tạo một session mới với `agy`.

### 3. Chọn Model AI (`/model`)
Bấm nút `🤖 Model`. Bot sẽ liệt kê danh sách các model khả dụng được lấy trực tiếp từ `agy models`:
- `Gemini 3.8 Flash (High)` *(Mặc định)*
- `Gemini 3.8 Flash (Medium)`
- `Gemini 3.1 Pro (High)`
- `Claude Sonnet 4.6 (Thinking)`
- ...

### 4. Quản lý Thư mục Dự án (`/project` & `/add_project`)
- Bấm `📁 Dự án` để xem các workspace đã lưu hoặc chọn `No Project`.
- Thêm nhanh một thư mục mới:
  ```text
  /add_project /home/ubuntu/my-backend Dự án Backend
  ```
  `agy` sẽ sử dụng thư mục này làm workspace (tương đương `--add-dir` và `cwd`).

### 5. Xem lịch sử và tiếp tục chat (`/history`)
Bấm `📜 Lịch sử chat` để xem danh sách các cuộc hội thoại (được đồng bộ từ cả dữ liệu bot lẫn các phiên bạn từng chat trên Antigravity IDE máy chủ). Bấm vào tiêu đề cuộc trò chuyện bất kỳ để Resume lại ngay lập tức!

### 6. Lên lịch tác vụ định kỳ (`/schedule` & `/tasks`)
Tương đương mục `Scheduled Tasks` trên Antigravity:
- Đặt lịch kiểm tra định kỳ:
  ```text
  /schedule kiểm tra trạng thái ổ cứng và docker containers every 1h
  ```
  ```text
  /schedule git pull và thông báo commit mới every 30m
  ```
- Xem danh sách: `/tasks`
- Hủy tác vụ: `/deltask <ID>`

### 7. Dừng tác vụ khẩn cấp (`/stop`)
Trong khi `agy` đang suy luận hoặc chạy các lệnh nặng, bạn có thể bấm nút `🛑 Dừng tác vụ (Stop)` xuất hiện dưới tin nhắn hoặc gõ `/stop` để hủy tiến trình ngay lập tức.
