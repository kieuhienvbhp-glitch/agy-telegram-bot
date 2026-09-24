from typing import List, Dict, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from session_manager import UserSession

def get_main_dashboard_keyboard(session: UserSession) -> InlineKeyboardMarkup:
    """Clean, compact main dashboard without unnecessary icons or redundant settings."""
    buttons = [
        [
            InlineKeyboardButton("Cuộc trò chuyện mới", callback_data="action:new_chat")
        ],
        [
            InlineKeyboardButton("Lịch sử", callback_data="menu:history:0"),
            InlineKeyboardButton("Dự án", callback_data="menu:projects")
        ],
        [
            InlineKeyboardButton(f"Model: {session.display_model}", callback_data="menu:models")
        ],
        [
            InlineKeyboardButton("Tác vụ hẹn giờ", callback_data="menu:tasks"),
            InlineKeyboardButton("Làm mới", callback_data="action:refresh_status")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

def get_models_keyboard(current_model: str, models: List[Dict[str, str]]) -> InlineKeyboardMarkup:
    """Clean model selector with radio checkboxes."""
    buttons = []
    for m in models:
        mid = m["id"]
        mname = m["name"]
        prefix = "[x] " if mid == current_model else "[ ] "
        buttons.append([InlineKeyboardButton(f"{prefix}{mname}", callback_data=f"set_model:{mid}")])

    buttons.append([InlineKeyboardButton("Quay lại", callback_data="menu:main")])
    return InlineKeyboardMarkup(buttons)

def get_projects_keyboard(session: UserSession, projects: List[Dict]) -> InlineKeyboardMarkup:
    """Clean projects directory selector."""
    buttons = []
    no_proj_prefix = "[x] " if not session.project_dir else "[ ] "
    buttons.append([
        InlineKeyboardButton(f"{no_proj_prefix}No Project", callback_data="set_project:none")
    ])

    for p in projects:
        prefix = "[x] " if session.project_dir and session.project_dir == p["path"] else "[ ] "
        buttons.append([
            InlineKeyboardButton(f"{prefix}{p['name']} ({p['path']})", callback_data=f"set_project:{p['id']}"),
            InlineKeyboardButton("Xóa", callback_data=f"del_project:{p['id']}")
        ])

    buttons.append([InlineKeyboardButton("+ Thêm thư mục mới", callback_data="prompt:add_project")])
    buttons.append([InlineKeyboardButton("Quay lại", callback_data="menu:main")])
    return InlineKeyboardMarkup(buttons)

def get_history_keyboard(conversations: List[Dict], page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Clean conversation history selector."""
    total = len(conversations)
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, total)
    current_items = conversations[start_idx:end_idx]

    buttons = []
    for conv in current_items:
        title = conv.get("title", f"Conv-{conv['id'][:8]}")
        buttons.append([
            InlineKeyboardButton(title, callback_data=f"resume_conv:{conv['id']}")
        ])

    # Pagination navigation
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("< Trước", callback_data=f"menu:history:{page - 1}"))
    
    total_pages = max(1, (total + per_page - 1) // per_page)
    nav_row.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))

    if end_idx < total:
        nav_row.append(InlineKeyboardButton("Sau >", callback_data=f"menu:history:{page + 1}"))

    if nav_row:
        buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton("Chat mới", callback_data="action:new_chat"),
        InlineKeyboardButton("Quay lại", callback_data="menu:main")
    ])
    return InlineKeyboardMarkup(buttons)

def get_running_keyboard() -> InlineKeyboardMarkup:
    """Clean cancel button while running."""
    buttons = [
        [InlineKeyboardButton("Dừng tác vụ", callback_data="action:stop_execution")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_chat_response_keyboard(conversation_id: Optional[str] = None) -> Optional[InlineKeyboardMarkup]:
    """Returns None for clean output."""
    return None
