import html
import logging
import os
import re
from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from session_manager import session_manager
from agy_client import agy_client
from scheduled_tasks import scheduled_task_manager
from keyboards import (
    get_main_dashboard_keyboard,
    get_models_keyboard,
    get_projects_keyboard,
    get_history_keyboard
)

logger = logging.getLogger(__name__)

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new conversation session."""
    user = update.effective_user
    if not user or not Config.is_user_allowed(user.id):
        return

    session_manager.start_new_conversation(user.id)
    session = session_manager.get_session(user.id)
    await update.effective_message.reply_text(
        "Đã khởi tạo cuộc trò chuyện mới.",
        parse_mode="HTML",
        reply_markup=get_main_dashboard_keyboard(session)
    )

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View or change AI model."""
    user = update.effective_user
    if not user or not Config.is_user_allowed(user.id):
        return

    args = context.args
    session = session_manager.get_session(user.id)

    if args:
        chosen_model = args[0].strip()
        session.model = chosen_model
        session_manager.save_session(session)
        await update.effective_message.reply_text(
            f"Đã thiết lập model: <code>{html.escape(chosen_model)}</code>",
            parse_mode="HTML"
        )
        return

    models = await agy_client.list_models()
    await update.effective_message.reply_text(
        "<b>Chọn Model cho agy:</b>",
        parse_mode="HTML",
        reply_markup=get_models_keyboard(session.model, models)
    )

async def project_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage workspace projects."""
    user = update.effective_user
    if not user or not Config.is_user_allowed(user.id):
        return

    session = session_manager.get_session(user.id)
    projects = session_manager.list_projects(user.id)
    await update.effective_message.reply_text(
        f"<b>Quản lý Workspace:</b>\n\nHiện tại: <code>{html.escape(session.display_project)}</code>",
        parse_mode="HTML",
        reply_markup=get_projects_keyboard(session, projects)
    )

async def add_project_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a directory path as a project."""
    user = update.effective_user
    if not user or not Config.is_user_allowed(user.id):
        return

    args = context.args
    if not args:
        await update.effective_message.reply_text(
            "Cú pháp: <code>/add_project &lt;đường_dẫn&gt; [tên_dự_án]</code>\n"
            "Ví dụ: <code>/add_project /home/ubuntu/my-app MyApp</code>",
            parse_mode="HTML"
        )
        return

    path = args[0].strip()
    name = " ".join(args[1:]) if len(args) > 1 else None

    session_manager.add_project(user.id, path, name)
    session = session_manager.get_session(user.id)
    session.project_dir = path
    session_manager.save_session(session)

    await update.effective_message.reply_text(
        f"Đã thêm và kích hoạt thư mục: <code>{html.escape(path)}</code>",
        parse_mode="HTML",
        reply_markup=get_main_dashboard_keyboard(session)
    )

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View conversation history."""
    user = update.effective_user
    if not user or not Config.is_user_allowed(user.id):
        return

    history = session_manager.get_conversation_history(user.id, limit=20)
    await update.effective_message.reply_text(
        "<b>Lịch sử cuộc trò chuyện:</b>",
        parse_mode="HTML",
        reply_markup=get_history_keyboard(history, page=0, per_page=5)
    )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Emergency cancel/stop running agy execution."""
    user = update.effective_user
    if not user or not Config.is_user_allowed(user.id):
        return

    cancelled = await agy_client.cancel_task(user.id)
    if cancelled:
        await update.effective_message.reply_text("Đã dừng tác vụ agy.", parse_mode="HTML")
    else:
        await update.effective_message.reply_text("Không có tác vụ nào đang chạy.", parse_mode="HTML")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display current session dashboard."""
    user = update.effective_user
    if not user or not Config.is_user_allowed(user.id):
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
        text,
        parse_mode="HTML",
        reply_markup=get_main_dashboard_keyboard(session)
    )

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Schedule a recurring prompt."""
    user = update.effective_user
    if not user or not Config.is_user_allowed(user.id):
        return

    text = " ".join(context.args) if context.args else ""
    match = re.search(r"^(.*?)\s+every\s+(\d+)\s*(s|m|h|d)$", text, re.IGNORECASE)
    if not match:
        await update.effective_message.reply_text(
            "Cú pháp: <code>/schedule &lt;lệnh&gt; every &lt;thời_gian&gt;</code>\n"
            "Ví dụ: <code>/schedule kiểm tra ổ cứng every 1h</code>",
            parse_mode="HTML"
        )
        return

    prompt = match.group(1).strip()
    val = int(match.group(2))
    unit = match.group(3).lower()

    multiplier = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    seconds = val * multiplier

    if seconds < 10:
        await update.effective_message.reply_text("Khoảng thời gian tối thiểu là 10 giây.")
        return

    interval_str = f"Mỗi {val} {unit}"
    task_id = scheduled_task_manager.add_task(user.id, prompt, seconds, interval_str)

    await update.effective_message.reply_text(
        f"Đã lên lịch tác vụ: <code>{task_id}</code> ({interval_str})\n"
        f"Lệnh: <i>{html.escape(prompt)}</i>\n"
        f"Hủy: /deltask {task_id}",
        parse_mode="HTML"
    )

async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List scheduled tasks."""
    user = update.effective_user
    if not user or not Config.is_user_allowed(user.id):
        return

    tasks = scheduled_task_manager.list_tasks(user.id)
    if not tasks:
        await update.effective_message.reply_text("Không có tác vụ định kỳ nào.", parse_mode="HTML")
        return

    msg = "<b>Tác vụ định kỳ:</b>\n\n"
    for t in tasks:
        msg += f"ID: <code>{t['id']}</code> ({t['interval_str']})\nLệnh: <i>{html.escape(t['prompt'])}</i>\n\n"
    msg += "Xóa: /deltask <ID>"
    await update.effective_message.reply_text(msg, parse_mode="HTML")

async def deltask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a scheduled task."""
    user = update.effective_user
    if not user or not Config.is_user_allowed(user.id):
        return

    if not context.args:
        await update.effective_message.reply_text("Cú pháp: <code>/deltask &lt;ID&gt;</code>", parse_mode="HTML")
        return

    task_id = context.args[0].strip()
    scheduled_task_manager.remove_task(task_id, user.id)
    await update.effective_message.reply_text(f"Đã xóa tác vụ: <code>{task_id}</code>", parse_mode="HTML")
