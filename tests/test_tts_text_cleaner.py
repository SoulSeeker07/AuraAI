"""
Unit tests for TTS Text Cleaner.
"""

from src.voice.tts_text_cleaner import clean_for_tts


def test_clean_for_tts_emojis():
    """Verify emojis are completely stripped and not converted to word descriptions."""
    raw = "Hey Sreekanta! How’s it going? 😊 👍 🚀"
    cleaned = clean_for_tts(raw)
    assert cleaned == "Hey Sreekanta! How’s it going?"
    assert "smiling" not in cleaned.lower()
    assert "face" not in cleaned.lower()


def test_clean_for_tts_status_icons_and_markdown():
    """Verify checkmarks, markdown bold/headers, and formatting are cleaned."""
    raw = "✓ **Notepad is open.**\n### Status: Ready\n- Item 1\n- Item 2"
    cleaned = clean_for_tts(raw)
    assert "✓" not in cleaned
    assert "**" not in cleaned
    assert "###" not in cleaned
    assert "Notepad is open. Status: Ready Item 1 Item 2" == cleaned


def test_clean_for_tts_preserves_speakables():
    """Verify technical terms, percentages, and currencies are preserved."""
    raw = "Wi-Fi is at 20% on C++ and .NET. Cost is ₹500 or $50."
    cleaned = clean_for_tts(raw)
    assert "Wi-Fi" in cleaned
    assert "20%" in cleaned
    assert "C++" in cleaned
    assert ".NET" in cleaned
    assert "₹500" in cleaned or "$50" in cleaned


def test_clean_for_tts_code_blocks_and_links():
    """Verify code blocks are removed and links keep anchor text."""
    raw = "Here is the code: ```python\nprint('hello')\n``` Check out [Google](https://google.com) for more."
    cleaned = clean_for_tts(raw)
    assert "print" not in cleaned
    assert "Here is the code: Check out Google for more." == cleaned
