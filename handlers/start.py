import html
import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from session_manager import session_manager
from keyboards import get_main_dashboard_keyboard

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /start - display the primary Antigravity dashboard interface.
    """
    user = update.effective_user
    if not user:
        return

    if not Config.is_user_allowed(user.id):
        await update.effective_message.reply_text(
            f"Quyền truy cập bị từ chối!\n\n"
            f"Telegram User ID của bạn: <code>{user.id}</code>\n"
            f"Hãy thêm ID này vào biến ALLOWED_USER_IDS trong file .env trên máy chủ Ubuntu 24.04.",
            parse_mode="HTML"
        )
        return

    session = session_manager.get_session(user.id)
    text = (
        f"<b>Google Antigravity</b> (Ubuntu 24.04)\n\n"
        f"Model: <code>{html.escape(session.display_model)}</code>\n"
        f"Workspace: <code>{html.escape(session.display_project)}</code>\n"
        f"Session: <i>{html.escape(session.display_title)}</i>\n"
        f"Quyền: <code>{'Tự động' if session.auto_skip_permissions else 'Hỏi'}</code>\n\n"
        f"Gửi tin nhắn hoặc file code để bắt đầu."
    )

    await update.effective_message.reply_text(
        text=text,
        reply_markup=get_main_dashboard_keyboard(session),
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /help - commands overview.
    """
    user = update.effective_user
    if not user or not Config.is_user_allowed(user.id):
        return

    text = (
        f"<b>Danh sách lệnh Antigravity Bot:</b>\n\n"
        f"/new - Bắt đầu cuộc trò chuyện mới\n"
        f"/history - Xem lịch sử cuộc trò chuyện\n"
        f"/model - Đổi mô hình AI\n"
        f"/project - Quản lý thư mục dự án\n"
        f"/add_project &lt;path&gt; - Thêm thư mục làm việc\n"
        f"/status - Xem bảng điều khiển và trạng thái\n"
        f"/stop - Dừng tác vụ đang chạy\n"
        f"/tasks - Danh sách tác vụ định kỳ\n"
        f"/schedule &lt;lệnh&gt; every &lt;thời_gian&gt; - Lên lịch tác vụ định kỳ"
    )

    await update.effective_message.reply_text(text=text, parse_mode="HTML")
