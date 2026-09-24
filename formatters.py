import re
import html
from typing import List, Optional
from session_manager import UserSession

MAX_TELEGRAM_MESSAGE_LENGTH = 4000

def escape_html(text: str) -> str:
    """Escapes special characters for Telegram HTML mode."""
    return html.escape(text)

def markdown_to_telegram_html(text: str) -> str:
    """
    Converts standard Markdown into Telegram-supported HTML tags:
    <b>, <i>, <code>, <pre>, <s>, <u>, <blockquote>, <a href="...">
    """
    if not text:
        return ""

    # Preserve fenced code blocks: ```lang ... ```
    code_blocks = []
    def code_block_sub(match):
        lang = match.group(1) or ""
        code = match.group(2)
        escaped_code = html.escape(code.rstrip())
        idx = len(code_blocks)
        if lang:
            code_blocks.append(f'<pre><code class="language-{html.escape(lang)}">{escaped_code}</code></pre>')
        else:
            code_blocks.append(f'<pre><code>{escaped_code}</code></pre>')
        return f"@@@CODE_BLOCK_{idx}@@@"

    text = re.sub(r'```(\w+)?\n([\s\S]*?)```', code_block_sub, text)

    # Preserve inline code: `code`
    inline_codes = []
    def inline_code_sub(match):
        code = match.group(1)
        idx = len(inline_codes)
        inline_codes.append(f'<code>{html.escape(code)}</code>')
        return f"@@@INLINE_CODE_{idx}@@@"

    text = re.sub(r'`([^`\n]+)`', inline_code_sub, text)

    # Escape HTML special chars in remaining text
    text = html.escape(text)

    # Headers: ### Header -> <b>Header</b>
    text = re.sub(r'^###\s+(.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^##\s+(.*?)$', r'<b><u>\1</u></b>', text, flags=re.MULTILINE)
    text = re.sub(r'^#\s+(.*?)$', r'<b><ins>\1</ins></b>', text, flags=re.MULTILINE)

    # Bold: **bold** or __bold__
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)

    # Italic: *italic* or _italic_
    text = re.sub(r'(?<!\w)\*(?!\s)(.*?)(?<!\s)\*(?!\w)', r'<i>\1</i>', text)
    text = re.sub(r'(?<!\w)_(?!\s)(.*?)(?<!\s)_(?!\w)', r'<i>\1</i>', text)

    # Strikethrough: ~~strike~~
    text = re.sub(r'~~(.*?)~~', r'<s>\1</s>', text)

    # Blockquotes: > quote
    text = re.sub(r'^&gt;\s+(.*?)$', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)

    # Markdown links: [title](url)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'<a href="\2">\1</a>', text)

    # Restore inline codes
    for idx, snippet in enumerate(inline_codes):
        text = text.replace(f"@@@INLINE_CODE_{idx}@@@", snippet)

    # Restore code blocks
    for idx, snippet in enumerate(code_blocks):
        text = text.replace(f"@@@CODE_BLOCK_{idx}@@@", snippet)

    return text

def split_message(text: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> List[str]:
    """
    Splits long messages into Telegram-compliant chunks without breaking code blocks.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk = []
    current_length = 0

    for line in lines:
        line_len = len(line) + 1
        if current_length + line_len > max_length:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_length = line_len
            else:
                # Single line exceeds limit, force split by length
                for i in range(0, len(line), max_length):
                    chunks.append(line[i:i + max_length])
                current_chunk = []
                current_length = 0
        else:
            current_chunk.append(line)
            current_length += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks

def format_session_header(session: UserSession) -> str:
    """
    Builds the visual header mimicking the Antigravity desktop IDE.
    """
    proj = session.display_project
    title = session.display_title
    return (
        f"🤖 <b>{escape_html(session.model)}</b> ({escape_html(session.effort)})\n"
        f"📁 <code>{escape_html(proj)}</code>\n"
        f"💬 <i>{escape_html(title)}</i>\n"
        f"────────────────────────"
    )

def format_live_stream(header: str, body: str, status_note: Optional[str] = None) -> str:
    """
    Combines header, streaming body, and ongoing activity indicators.
    """
    formatted_body = markdown_to_telegram_html(body) if body else "<i>Đang tải...</i>"
    parts = [header, formatted_body]
    if status_note:
        parts.append(f"\n────────────────────────\n<i>{escape_html(status_note)}</i>")
    return "\n".join(parts)
