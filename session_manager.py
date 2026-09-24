import json
import logging
import os
import sqlite3
import datetime
from pathlib import Path
from typing import Dict, List, Optional
from config import Config

logger = logging.getLogger(__name__)

class UserSession:
    def __init__(
        self,
        user_id: int,
        conversation_id: Optional[str] = None,
        model: str = Config.DEFAULT_MODEL,
        effort: str = Config.DEFAULT_EFFORT,
        project_dir: Optional[str] = None,
        sandbox: bool = Config.DEFAULT_SANDBOX,
        auto_skip_permissions: bool = Config.AUTO_SKIP_PERMISSIONS,
        active_title: Optional[str] = None
    ):
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.model = model
        self.effort = effort
        self.project_dir = project_dir or (Config.DEFAULT_PROJECT_DIR if Config.DEFAULT_PROJECT_DIR else None)
        self.sandbox = sandbox
        self.auto_skip_permissions = auto_skip_permissions
        self.active_title = active_title

    @property
    def display_project(self) -> str:
        if not self.project_dir:
            return "No Project"
        return os.path.basename(os.path.normpath(self.project_dir)) or self.project_dir

    @property
    def display_title(self) -> str:
        if self.active_title:
            return self.active_title
        if self.conversation_id:
            return f"Conv-{self.conversation_id[:8]}"
        return "Mới"

    @property
    def display_effort(self) -> str:
        return self.effort.upper() if self.effort else "Auto"

    @property
    def display_model(self) -> str:
        from agy_client import get_model_display_name
        return get_model_display_name(self.model)


class SessionManager:
    def __init__(self, db_path: Path = Config.DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    user_id INTEGER PRIMARY KEY,
                    conversation_id TEXT,
                    model TEXT,
                    effort TEXT,
                    project_dir TEXT,
                    sandbox INTEGER DEFAULT 0,
                    auto_skip_permissions INTEGER DEFAULT 1,
                    active_title TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    title TEXT,
                    project_dir TEXT,
                    model TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT,
                    path TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    prompt TEXT,
                    interval_str TEXT,
                    interval_seconds INTEGER,
                    enabled INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_run TIMESTAMP
                );
            """)
            conn.commit()

    def get_session(self, user_id: int) -> UserSession:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM user_sessions WHERE user_id = ?", (user_id,)
            ).fetchone()

            if row:
                return UserSession(
                    user_id=user_id,
                    conversation_id=row["conversation_id"],
                    model=row["model"] or Config.DEFAULT_MODEL,
                    effort=row["effort"] or Config.DEFAULT_EFFORT,
                    project_dir=row["project_dir"],
                    sandbox=bool(row["sandbox"]),
                    auto_skip_permissions=bool(row["auto_skip_permissions"]),
                    active_title=row["active_title"]
                )

        # Create new default session
        session = UserSession(user_id=user_id)
        self.save_session(session)
        return session

    def save_session(self, session: UserSession):
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO user_sessions (
                    user_id, conversation_id, model, effort, project_dir,
                    sandbox, auto_skip_permissions, active_title, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    conversation_id = excluded.conversation_id,
                    model = excluded.model,
                    effort = excluded.effort,
                    project_dir = excluded.project_dir,
                    sandbox = excluded.sandbox,
                    auto_skip_permissions = excluded.auto_skip_permissions,
                    active_title = excluded.active_title,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                session.user_id,
                session.conversation_id,
                session.model,
                session.effort,
                session.project_dir,
                1 if session.sandbox else 0,
                1 if session.auto_skip_permissions else 0,
                session.active_title
            ))
            conn.commit()

    def record_conversation(
        self,
        conversation_id: str,
        user_id: int,
        title: str,
        project_dir: Optional[str] = None,
        model: Optional[str] = None
    ):
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO conversations (conversation_id, user_id, title, project_dir, model, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    title = excluded.title,
                    project_dir = COALESCE(excluded.project_dir, conversations.project_dir),
                    model = COALESCE(excluded.model, conversations.model),
                    updated_at = CURRENT_TIMESTAMP
            """, (conversation_id, user_id, title, project_dir, model))
            conn.commit()

    def start_new_conversation(self, user_id: int) -> UserSession:
        session = self.get_session(user_id)
        session.conversation_id = None
        session.active_title = None
        self.save_session(session)
        return session

    def set_active_conversation(self, user_id: int, conversation_id: str, title: Optional[str] = None) -> UserSession:
        session = self.get_session(user_id)
        session.conversation_id = conversation_id
        if title:
            session.active_title = title
        else:
            # Look up recorded title
            with self._get_conn() as conn:
                row = conn.execute("SELECT title FROM conversations WHERE conversation_id = ?", (conversation_id,)).fetchone()
                if row:
                    session.active_title = row["title"]
        self.save_session(session)
        return session

    def get_conversation_history(self, user_id: int, limit: int = 15) -> List[Dict]:
        """
        Combines SQLite recorded conversations with existing Antigravity brain transcripts.
        """
        results = []
        seen_ids = set()

        # 1. Fetch from SQLite
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT conversation_id, title, project_dir, model, updated_at
                FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()
            for r in rows:
                cid = r["conversation_id"]
                seen_ids.add(cid)
                results.append({
                    "id": cid,
                    "title": r["title"] or f"Conv-{cid[:8]}",
                    "project_dir": r["project_dir"],
                    "model": r["model"],
                    "time": r["updated_at"],
                    "source": "bot"
                })

        # 2. Also scan ~/.gemini/antigravity/brain for IDE conversations
        try:
            if Config.BRAIN_DIR.exists():
                for folder in sorted(Config.BRAIN_DIR.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
                    if not folder.is_dir() or folder.name in seen_ids or folder.name.startswith("."):
                        continue
                    transcript_path = folder / ".system_generated" / "logs" / "transcript.jsonl"
                    if transcript_path.exists():
                        title = self._extract_title_from_transcript(transcript_path) or f"IDE Conv ({folder.name[:8]})"
                        mtime = datetime.datetime.fromtimestamp(folder.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                        results.append({
                            "id": folder.name,
                            "title": title,
                            "project_dir": None,
                            "model": None,
                            "time": mtime,
                            "source": "antigravity_ide"
                        })
                        seen_ids.add(folder.name)
                        if len(results) >= limit:
                            break
        except Exception as e:
            logger.warning(f"Error scanning brain dir: {e}")

        return results[:limit]

    def _extract_title_from_transcript(self, transcript_path: Path) -> Optional[str]:
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    if data.get("type") == "USER_INPUT":
                        content = data.get("content", "").strip()
                        # Strip XML tags if present like <USER_REQUEST>
                        if "<USER_REQUEST>" in content:
                            content = content.split("<USER_REQUEST>")[1].split("</USER_REQUEST>")[0].strip()
                        clean = " ".join(content.split())
                        return clean[:45] + ("..." if len(clean) > 45 else "")
        except Exception:
            pass
        return None

    def list_projects(self, user_id: int) -> List[Dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, name, path FROM user_projects WHERE user_id = ? ORDER BY id DESC",
                (user_id,)
            ).fetchall()
            return [{"id": r["id"], "name": r["name"], "path": r["path"]} for r in rows]

    def add_project(self, user_id: int, path: str, name: Optional[str] = None) -> bool:
        norm_path = os.path.normpath(os.path.expanduser(path))
        if not name:
            name = os.path.basename(norm_path) or norm_path
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO user_projects (user_id, name, path)
                    VALUES (?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET name = excluded.name
                """, (user_id, name, norm_path))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding project: {e}")
            return False

    def remove_project(self, user_id: int, project_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM user_projects WHERE id = ? AND user_id = ?", (project_id, user_id))
            conn.commit()

session_manager = SessionManager()
