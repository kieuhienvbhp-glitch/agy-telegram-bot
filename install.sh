#!/usr/bin/env bash
# ==============================================================================
# Script cài đặt tự động Google Antigravity Telegram Bot trên Ubuntu 24.04 LTS
# ==============================================================================

set -e

echo "=========================================================="
echo "🚀 Bắt đầu cài đặt AGY Telegram Bot trên Ubuntu 24.04 LTS"
echo "=========================================================="

# 1. Cập nhật hệ thống và cài đặt gói phụ thuộc
echo "📦 [1/6] Đang cập nhật apt và cài đặt gói phụ thuộc hệ thống..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git curl

# 2. Kiểm tra agy CLI
echo "🔍 [2/6] Kiểm tra Google Antigravity CLI (agy)..."
if command -v agy &> /dev/null; then
    echo "✅ Đã tìm thấy agy tại: $(which agy)"
    agy --version || true
else
    echo "⚠️ CHÚ Ý: Chưa tìm thấy lệnh 'agy' trong PATH hệ thống!"
    echo "   Nếu bạn đã cài đặt Antigravity ở thư mục khác, hãy tạo symlink:"
    echo "   sudo ln -s /path/to/agy /usr/local/bin/agy"
    echo "   Hoặc cấu hình đường dẫn tuyệt đối trong file .env (AGY_BIN_PATH)."
fi

# 3. Khởi tạo môi trường ảo Python (virtual environment)
echo "🐍 [3/6] Thiết lập Python Virtual Environment (venv)..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Đã tạo thư mục venv"
else
    echo "ℹ️ Thư mục venv đã tồn tại."
fi

source venv/bin/activate

# 4. Cài đặt các thư viện Python
echo "📥 [4/6] Cài đặt dependencies từ requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Kiểm tra file cấu hình .env
echo "⚙️ [5/6] Kiểm tra file cấu hình .env..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "📄 Đã tạo file .env từ .env.example."
    echo "👉 VUI LÒNG CHỈNH SỬA FILE .env ĐỂ ĐIỀN TELEGRAM_BOT_TOKEN VÀ ALLOWED_USER_IDS:"
    echo "   nano .env"
else
    echo "ℹ️ File .env đã tồn tại."
fi

# 6. Tạo thư mục storage
mkdir -p storage/media

echo ""
echo "=========================================================="
echo "🎉 CÀI ĐẶT HOÀN TẤT THÀNH CÔNG!"
echo "=========================================================="
echo "Để chạy thử nghiệm bot ngay:"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo "Để cài đặt bot chạy ngầm vĩnh viễn (Systemd Service):"
echo "   sudo cp agy-telegram-bot.service /etc/systemd/system/"
echo "   (Chỉnh sửa User và WorkingDirectory trong /etc/systemd/system/agy-telegram-bot.service nếu cần)"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable agy-telegram-bot"
echo "   sudo systemctl start agy-telegram-bot"
echo "   sudo systemctl status agy-telegram-bot"
echo "=========================================================="
