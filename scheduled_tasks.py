import asyncio
import logging
import uuid
import datetime
from typing import Dict, List, Optional
from telegram.ext import Application, ContextTypes
from config import Config
from session_manager import session_manager
from agy_client import agy_client
from formatters import format_session_header, markdown_to_telegram_html, split_message

logger = logging.getLogger(__name__)

class ScheduledTaskManager:
    def __init__(self):
        self.app: Optional[Application] = None

    def set_application(self, app: Application):
        self.app = app

    def add_task(
        self,
        user_id: int,
        prompt: str,
        interval_seconds: int,
        interval_str: str
    ) -> str:
        task_id = str(uuid.uuid4())[:8]
        with session_manager._get_conn() as conn:
            conn.execute("""
                INSERT INTO scheduled_tasks (id, user_id, prompt, interval_str, interval_seconds, enabled)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (task_id, user_id, prompt, interval_str, interval_seconds))
            conn.commit()

        # Register in job_queue if app is available
        if self.app and self.app.job_queue:
            self._schedule_job(task_id, user_id, prompt, interval_seconds)

        return task_id

    def list_tasks(self, user_id: int) -> List[Dict]:
        with session_manager._get_conn() as conn:
            rows = conn.execute("""
                SELECT id, prompt, interval_str, interval_seconds, enabled, created_at, last_run
                FROM scheduled_tasks
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def remove_task(self, task_id: str, user_id: int) -> bool:
        with session_manager._get_conn() as conn:
            conn.execute("DELETE FROM scheduled_tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
            conn.commit()

        if self.app and self.app.job_queue:
            current_jobs = self.app.job_queue.get_jobs_by_name(f"task_{task_id}")
            for job in current_jobs:
                job.schedule_removal()
        return True

    def _schedule_job(self, task_id: str, user_id: int, prompt: str, interval_seconds: int):
        if not self.app or not self.app.job_queue:
            return

        async def _job_callback(context: ContextTypes.DEFAULT_TYPE):
            logger.info(f"Executing scheduled task {task_id} for user {user_id}")
            session = session_manager.get_session(user_id)
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ <b>[Tác vụ định kỳ]</b>: <i>{prompt}</i>\nĐang thực thi với <code>agy</code>...",
                    parse_mode="HTML"
                )

                # Execute agy
                accumulated = ""
                async for event in agy_client.stream_chat(
                    user_id=user_id,
                    prompt=prompt,
                    conversation_id=session.conversation_id,
                    model=session.model,
                    effort=session.effort,
                    project_dir=session.project_dir,
                    sandbox=session.sandbox,
                    auto_skip_permissions=session.auto_skip_permissions
                ):
                    if event["type"] == "step_update":
                        accumulated = event.get("accumulated", "")
                    elif event["type"] == "result":
                        accumulated = event.get("response", accumulated)

                # Record last_run
                with session_manager._get_conn() as conn:
                    conn.execute(
                        "UPDATE scheduled_tasks SET last_run = CURRENT_TIMESTAMP WHERE id = ?",
                        (task_id,)
                    )
                    conn.commit()

                # Send response
                header = f"⏰ <b>Kết quả tác vụ:</b> <code>{task_id}</code>\n"
                chunks = split_message(accumulated or "Tác vụ đã hoàn tất nhưng không có nội dung trả về.")
                for i, chunk in enumerate(chunks):
                    prefix = header if i == 0 else ""
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"{prefix}{markdown_to_telegram_html(chunk)}",
                        parse_mode="HTML"
                    )

            except Exception as e:
                logger.error(f"Error executing scheduled task {task_id}: {e}", exc_info=True)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ Lỗi khi chạy tác vụ hẹn giờ <code>{task_id}</code>: {e}",
                    parse_mode="HTML"
                )

        self.app.job_queue.run_repeating(
            _job_callback,
            interval=interval_seconds,
            first=10,
            name=f"task_{task_id}"
        )

    def load_and_schedule_all(self, app: Application):
        self.set_application(app)
        if not app.job_queue:
            return

        with session_manager._get_conn() as conn:
            rows = conn.execute("SELECT id, user_id, prompt, interval_seconds FROM scheduled_tasks WHERE enabled = 1").fetchall()
            for r in rows:
                self._schedule_job(r["id"], r["user_id"], r["prompt"], r["interval_seconds"])
                logger.info(f"Loaded and scheduled background task {r['id']}")

scheduled_task_manager = ScheduledTaskManager()
