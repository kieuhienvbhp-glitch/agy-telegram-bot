import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Config:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

    # Security: whitelist of user IDs allowed to interact with the bot
    _raw_allowed = os.getenv("ALLOWED_USER_IDS", "").strip()
    ALLOWED_USER_IDS: set[int] = {
        int(uid.strip())
        for uid in _raw_allowed.split(",")
        if uid.strip().isdigit()
    }

    # AGY CLI Binary
    AGY_BIN_PATH: str = os.getenv("AGY_BIN_PATH", "agy").strip()

    # Defaults
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gemini-3.8-flash-high").strip()
    DEFAULT_EFFORT: str = os.getenv("DEFAULT_EFFORT", "").strip().lower()
    DEFAULT_PROJECT_DIR: str = os.getenv("DEFAULT_PROJECT_DIR", "").strip()
    
    # Auto permissions & Sandbox
    AUTO_SKIP_PERMISSIONS: bool = os.getenv("AUTO_SKIP_PERMISSIONS", "true").lower() in ("true", "1", "yes")
    DEFAULT_SANDBOX: bool = os.getenv("DEFAULT_SANDBOX", "false").lower() in ("true", "1", "yes")

    # Storage paths
    STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", "./storage")).resolve()
    MEDIA_DIR: Path = STORAGE_DIR / "media"
    DB_PATH: Path = STORAGE_DIR / "bot_data.db"

    # Antigravity paths
    raw_ag_home = os.getenv("ANTIGRAVITY_HOME", "~/.gemini/antigravity").strip()
    ANTIGRAVITY_HOME: Path = Path(os.path.expanduser(raw_ag_home)).resolve()
    CONVERSATIONS_DIR: Path = ANTIGRAVITY_HOME / "conversations"
    BRAIN_DIR: Path = ANTIGRAVITY_HOME / "brain"

    @classmethod
    def ensure_directories(cls):
        cls.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        cls.MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def is_user_allowed(cls, user_id: int) -> bool:
        if not cls.ALLOWED_USER_IDS:
            # If no whitelist is specified, log warning but allow (or recommend setting it)
            return True
        return user_id in cls.ALLOWED_USER_IDS

# Ensure initial dirs exist
Config.ensure_directories()
