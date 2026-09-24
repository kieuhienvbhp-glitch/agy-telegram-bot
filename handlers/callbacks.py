import html
import logging
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

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Dispatcher for inline button interactions.
    """
    query = update.callback_query
    if not query:
        return

    user = query.from_user
    if not user or not Config.is_user_allowed(user.id):
        await query.answer("Quyền truy cập bị từ chối.", show_alert=True)
        return

    data = query.data or ""
    session = session_manager.get_session(user.id)

    # 1. Main Menu
    if data == "menu:main":
        await query.answer()
        await _show_main_menu(query, session)

    # 2. Refresh Status
    elif data == "action:refresh_status":
        await query.answer("Đã làm mới!")
        await _show_main_menu(query, session)

    # 3. New Chat
    elif data == "action:new_chat":
        session_manager.start_new_conversation(user.id)
        session = session_manager.get_session(user.id)
        await query.answer("Đã tạo cuộc trò chuyện mới!", show_alert=False)
        await _show_main_menu(query, session)

    # 4. Stop Execution
    elif data == "action:stop_execution":
        cancelled = await agy_client.cancel_task(user.id)
        if cancelled:
            await query.answer("Đã dừng tác vụ agy!", show_alert=True)
        else:
            await query.answer("Không có tác vụ nào đang chạy.", show_alert=False)

    # 5. Models Menu & Selection
    elif data == "menu:models":
        await query.answer()
        models = await agy_client.list_models()
        await query.edit_message_text(
            "<b>Chọn Model cho agy:</b>",
            parse_mode="HTML",
            reply_markup=get_models_keyboard(session.model, models)
        )

    elif data.startswith("set_model:"):
        model_id = data.split(":", 1)[1]
        session.model = model_id
        session_manager.save_session(session)
        await query.answer(f"Đã chọn: {model_id}")
        await _show_main_menu(query, session)

    # 6. Projects Menu & Selection
    elif data == "menu:projects":
        await query.answer()
        projects = session_manager.list_projects(user.id)
        await query.edit_message_text(
            f"<b>Quản lý Workspace:</b>\n\n"
            f"Hiện tại: <code>{html.escape(session.display_project)}</code>",
            parse_mode="HTML",
            reply_markup=get_projects_keyboard(session, projects)
        )

    elif data.startswith("set_project:"):
        proj_val = data.split(":", 1)[1]
        if proj_val == "none":
            session.project_dir = None
            session_manager.save_session(session)
            await query.answer("Đã chọn: No Project")
        else:
            projects = session_manager.list_projects(user.id)
            target = next((p for p in projects if str(p["id"]) == proj_val), None)
            if target:
                session.project_dir = target["path"]
                session_manager.save_session(session)
                await query.answer(f"Đã chọn: {target['name']}")
        await _show_main_menu(query, session)

    elif data.startswith("del_project:"):
        pid = int(data.split(":", 1)[1])
        session_manager.remove_project(user.id, pid)
        await query.answer("Đã xóa khỏi danh sách.")
        projects = session_manager.list_projects(user.id)
        await query.edit_message_reply_markup(reply_markup=get_projects_keyboard(session, projects))

    elif data == "prompt:add_project":
        await query.answer()
        context.user_data["waiting_for_project_path"] = True
        await query.message.reply_text(
            "Nhập đường dẫn thư mục dự án:\n"
            "Ví dụ: <code>/home/ubuntu/my-project</code>",
            parse_mode="HTML"
        )

    # 7. History Menu & Resume
    elif data.startswith("menu:history:"):
        page = int(data.split(":")[2])
        await query.answer()
        history = session_manager.get_conversation_history(user.id, limit=20)
        await query.edit_message_text(
            "<b>Lịch sử cuộc trò chuyện:</b>",
            parse_mode="HTML",
            reply_markup=get_history_keyboard(history, page=page, per_page=5)
        )

    elif data.startswith("resume_conv:"):
        conv_id = data.split(":", 1)[1]
        session = session_manager.set_active_conversation(user.id, conv_id)
        await query.answer(f"Đã chuyển: {session.display_title}")
        await _show_main_menu(query, session)

    # 8. Scheduled Tasks Menu
    elif data == "menu:tasks":
        await query.answer()
        tasks = scheduled_task_manager.list_tasks(user.id)
        if not tasks:
            msg = (
                "<b>Tác vụ đã lên lịch:</b>\n\n"
                "Chưa có tác vụ nào.\n"
                "Tạo mới: <code>/schedule &lt;lệnh&gt; every &lt;X&gt;s|m|h</code>"
            )
        else:
            msg = "<b>Danh sách tác vụ định kỳ:</b>\n\n"
            for t in tasks:
                msg += f"ID: <code>{t['id']}</code> ({t['interval_str']})\nLệnh: <i>{html.escape(t['prompt'])}</i>\n\n"
            msg += "Xóa: /deltask <ID>"

        await query.message.reply_text(msg, parse_mode="HTML")

    elif data == "noop":
        await query.answer()

async def _show_main_menu(query, session):
    text = (
        f"<b>Google Antigravity</b> (Ubuntu 24.04)\n\n"
        f"Model: <code>{html.escape(session.display_model)}</code>\n"
        f"Workspace: <code>{html.escape(session.display_project)}</code>\n"
        f"Session: <i>{html.escape(session.display_title)}</i>\n"
        f"Quyền: <code>{'Tự động' if session.auto_skip_permissions else 'Hỏi'}</code>\n\n"
        f"Gửi tin nhắn hoặc file code để bắt đầu."
    )
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=get_main_dashboard_keyboard(session),
            parse_mode="HTML"
        )
    except Exception:
        await query.message.reply_text(
            text=text,
            reply_markup=get_main_dashboard_keyboard(session),
            parse_mode="HTML"
        )
