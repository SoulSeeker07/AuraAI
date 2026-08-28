"""
TTS Text Cleaner

Sanitizes rich LLM/system text into natural speakable English for TTS engines.
Ensures emojis, markdown formatting, ANSI codes, and status icons are never
pronounced literally (e.g. avoiding "smiling face with smiling eyes" or "check mark").
"""

import re
import unicodedata

# Regex to detect ANSI escape codes
_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Regex to match Markdown headers, bold, italics, strikethrough, inline code, and links
_MD_HEADERS_RE = re.compile(r"^\s*#{1,6}\s+", re.MULTILINE)
_MD_BOLD_ITALIC_RE = re.compile(r"(\*\*|\*|__|_|~~)(.*?)\1")
_MD_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_MD_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_MD_LINKS_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_BULLETS_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_MD_NUMBERED_LIST_RE = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)
_MD_BLOCKQUOTE_RE = re.compile(r"^\s*>\s*", re.MULTILINE)

# Common CLI / Status symbols to remove from spoken output
_SYMBOLS_TO_REMOVE = {
    "✓", "✔", "✗", "✘", "❌", "⚠️", "➜", "➤", "➔", "►", "▶",
    "═", "─", "│", "┌", "┐", "└", "┘", "╭", "╮", "╯", "╰", "├", "┤", "┬", "┴", "┼",
    "■", "□", "●", "○", "◆", "◇", "▪", "▫", "★", "☆", "•", "·",
    "🎧", "🎤", "🤔", "😊", "🤖", "🚀", "💡", "🧠", "🔍", "⚙️", "🔧", "💻", "📁", "📄"
}

# Regex to match Unicode Emojis across all standard blocks
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # Emoticons
    "\U0001F300-\U0001F5FF"  # Misc Symbols and Pictographs
    "\U0001F680-\U0001F6FF"  # Transport and Map
    "\U0001F700-\U0001F77F"  # Alchemical Symbols
    "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
    "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
    "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
    "\U0001FA00-\U0001FA6F"  # Chess Symbols
    "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
    "\U00002702-\U000027B0"  # Dingbats
    "\U000024C2-\U0001F251"  # Enclosed Characters
    "\U00002600-\U000026FF"  # Misc symbols (sun, umbrella, warning, etc.)
    "\U0000FE00-\U0000FE0F"  # Variation Selectors
    "\U0000200D"              # Zero Width Joiner
    "]+",
    flags=re.UNICODE,
)


def clean_for_tts(text: str | None) -> str:
    """
    Sanitize rich LLM/system text into natural speakable English for TTS.
    
    Args:
        text: Raw response string from LLM or system.
        
    Returns:
        Clean, pronounceable English string without emojis or formatting artifacts.
    """
    if not text:
        return ""

    s = str(text)

    # 0. Remove thinking blocks from reasoning models (<think>...</think>)
    s = re.sub(r"<think>[\s\S]*?</think>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"<think>[\s\S]*$", "", s, flags=re.IGNORECASE)

    # 1. Remove ANSI escape codes
    s = _ANSI_RE.sub("", s)

    # 2. Remove code blocks entirely (code is displayed, not spoken verbatim)
    s = _MD_CODE_BLOCK_RE.sub("", s)

    # 3. Replace markdown links with link text [text](url) -> text
    s = _MD_LINKS_RE.sub(r"\1", s)

    # 4. Extract text from inline code `code` -> code
    s = _MD_INLINE_CODE_RE.sub(r"\1", s)

    # 5. Extract text from bold / italics **text** -> text
    # Run multiple passes for nested formatting
    for _ in range(3):
        s = _MD_BOLD_ITALIC_RE.sub(r"\2", s)

    # 6. Remove Markdown headers, bullets, and blockquotes
    s = _MD_HEADERS_RE.sub("", s)
    s = _MD_BULLETS_RE.sub("", s)
    s = _MD_NUMBERED_LIST_RE.sub("", s)
    s = _MD_BLOCKQUOTE_RE.sub("", s)

    # 7. Remove all Unicode Emojis
    s = _EMOJI_RE.sub("", s)

    # 8. Remove explicit status & box symbols
    for sym in _SYMBOLS_TO_REMOVE:
        s = s.replace(sym, "")

    # 9. Clean up whitespace and empty lines
    lines = [line.strip() for line in s.splitlines() if line.strip()]
    cleaned = " ".join(lines)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned
