import asyncio
import html
import logging
import os
import time
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from config import Config
from session_manager import session_manager
from agy_client import agy_client
from formatters import (
    markdown_to_telegram_html,
    split_message,
    escape_html
)
from keyboards import get_running_keyboard

logger = logging.getLogger(__name__)

EDIT_INTERVAL = 1.2  # Throttled live updates for Telegram

async def keep_typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Periodically sends typing chat action while agy is processing."""
    try:
        while True:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(4.0)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"Typing action exception: {e}")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text prompts and code snippets."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not message.text:
        return

    if not Config.is_user_allowed(user.id):
        await message.reply_text("⛔ Bạn không có quyền sử dụng bot này.", parse_mode="HTML")
        return

    prompt = message.text.strip()

    # Check if user was prompted to enter a project path
    if context.user_data.get("waiting_for_project_path"):
        context.user_data["waiting_for_project_path"] = False
        session_manager.add_project(user.id, prompt)
        session = session_manager.get_session(user.id)
        session.project_dir = prompt
        session_manager.save_session(session)
        await message.reply_text(
            f"✅ <b>Đã thêm và kích hoạt thư mục dự án:</b>\n<code>{escape_html(prompt)}</code>",
            parse_mode="HTML"
        )
        return

    await process_agent_turn(user.id, prompt, update, context)

async def handle_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document, code file, or photo uploads."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    if not Config.is_user_allowed(user.id):
        await message.reply_text("⛔ Bạn không có quyền sử dụng bot này.", parse_mode="HTML")
        return

    caption = message.caption or ""
    saved_path = None

    if message.document:
        doc = message.document
        filename = doc.file_name or f"file_{doc.file_id[:8]}"
        saved_path = Config.MEDIA_DIR / f"{int(time.time())}_{filename}"
        telegram_file = await doc.get_file()
        await telegram_file.download_to_drive(custom_path=str(saved_path))
        logger.info(f"Downloaded document to {saved_path}")

    elif message.photo:
        photo = message.photo[-1]
        saved_path = Config.MEDIA_DIR / f"photo_{int(time.time())}_{photo.file_id[:8]}.jpg"
        telegram_file = await photo.get_file()
        await telegram_file.download_to_drive(custom_path=str(saved_path))
        logger.info(f"Downloaded photo to {saved_path}")

    if saved_path:
        prompt = (
            f"[Người dùng gửi tệp đính kèm: {saved_path.resolve()}]\n"
            f"{caption if caption else 'Hãy đọc và xử lý tệp tin đính kèm này.'}"
        )
        await process_agent_turn(user.id, prompt, update, context)
    elif caption:
        await process_agent_turn(user.id, caption, update, context)

async def process_agent_turn(user_id: int, prompt: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Execute agy stream and stream results cleanly and naturally to Telegram.
    """
    session = session_manager.get_session(user_id)
    chat_id = update.effective_chat.id

    # Clean, minimal status placeholder
    status_msg = await update.effective_message.reply_text(
        "<i>Đang suy nghĩ...</i>",
        parse_mode="HTML",
        reply_markup=get_running_keyboard()
    )

    # Trigger native Telegram typing indicator in background
    typing_task = asyncio.create_task(keep_typing(context, chat_id))

    accumulated_text = ""
    current_status = "Đang suy nghĩ..."
    last_edit_time = time.time()
    last_rendered_text = ""
    stats = {}

    try:
        effort_to_pass = session.effort if session.effort not in ("", "default") else None

        async for event in agy_client.stream_chat(
            user_id=user_id,
            prompt=prompt,
            conversation_id=session.conversation_id,
            model=session.model,
            effort=effort_to_pass,
            project_dir=session.project_dir,
            sandbox=session.sandbox,
            auto_skip_permissions=session.auto_skip_permissions
        ):
            event_type = event.get("type")

            if event_type == "init":
                cid = event.get("conversation_id")
                if cid and not session.conversation_id:
                    session.conversation_id = cid
                    clean_title = " ".join(prompt.split())[:35]
                    session.active_title = clean_title
                    session_manager.record_conversation(
                        conversation_id=cid,
                        user_id=user_id,
                        title=clean_title,
                        project_dir=session.project_dir,
                        model=session.model
                    )
                    session_manager.save_session(session)

            elif event_type == "step_update":
                stype = event.get("step_type")
                delta = event.get("text_delta", "")
                if delta:
                    accumulated_text += delta

                if stype == "agent_response":
                    current_status = "Đang phản hồi..."
                elif stype == "tool_call":
                    raw = event.get("raw", {})
                    tool_call = raw.get("tool_call") or {}
                    tool_name = tool_call.get("name") or raw.get("name") or "công cụ hệ thống"
                    current_status = f"Đang chạy: <code>{escape_html(tool_name)}</code>..."
                elif stype in ("thought", "thinking"):
                    current_status = "Đang suy luận..."

                # Live edit
                now = time.time()
                if (now - last_edit_time) >= EDIT_INTERVAL:
                    if accumulated_text:
                        rendered = f"{markdown_to_telegram_html(accumulated_text)}\n\n<i>{current_status}</i>"
                    else:
                        rendered = f"<i>{current_status}</i>"

                    if len(rendered) > 3900:
                        rendered = rendered[:3800] + "\n\n<i>[...đang tải tiếp...]</i>"

                    if rendered != last_rendered_text:
                        try:
                            await status_msg.edit_text(
                                rendered,
                                parse_mode="HTML",
                                reply_markup=get_running_keyboard()
                            )
                            last_edit_time = now
                            last_rendered_text = rendered
                        except BadRequest as be:
                            if "Message is not modified" not in str(be):
                                logger.debug(f"Edit msg warning: {be}")

            elif event_type == "result":
                res_text = event.get("response")
                if res_text:
                    accumulated_text = res_text
                stats["duration"] = event.get("duration")
                stats["usage"] = event.get("usage")
                stats["status"] = event.get("status")

            elif event_type == "error":
                accumulated_text = f"<b>Lỗi agy:</b>\n<code>{escape_html(event.get('message', 'Unknown error'))}</code>"

    except asyncio.CancelledError:
        accumulated_text += "\n\n<i>Tác vụ đã được hủy.</i>"
    except Exception as e:
        logger.error(f"Error during agent turn: {e}", exc_info=True)
        accumulated_text += f"\n\n<i>Lỗi: {escape_html(str(e))}</i>"
    finally:
        typing_task.cancel()

    # Final rendering - Clean and natural
    if not accumulated_text:
        accumulated_text = "<i>Không có kết quả trả về từ agy.</i>"

    chunks = split_message(accumulated_text, max_length=3800)

    # First chunk updates the status message, removing the stop button
    first_chunk_text = markdown_to_telegram_html(chunks[0])

    try:
        await status_msg.edit_text(
            first_chunk_text,
            parse_mode="HTML",
            reply_markup=None  # Clean response without cluttering buttons
        )
    except Exception as e:
        logger.warning(f"Final edit failed: {e}. Sending new message.")
        await update.effective_message.reply_text(
            first_chunk_text,
            parse_mode="HTML"
        )

    # Subsequent chunks sent as new messages
    for i in range(1, len(chunks)):
        chunk_text = markdown_to_telegram_html(chunks[i])
        await update.effective_message.reply_text(
            chunk_text,
            parse_mode="HTML"
        )
