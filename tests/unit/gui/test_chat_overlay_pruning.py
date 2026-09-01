"""
Targeted Verification Suite for ChatWindowOverlay FIFO Card Pruning (Anti-Pattern #4).

Tests:
1. Appending >MAX_CARDS messages enforces strict bounded list size (MAX_CARDS + 1 stretch).
2. True FIFO Eviction: verifies that the OLDEST messages are purged first while newest are preserved.
3. Post-pruning lifecycle safety: verifies scroll, clear, and resize trigger zero dangling pointer/C++ deletion exceptions.
"""

import os
import sys
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QLabel
from gui.widgets.chat_window_overlay import ChatWindowOverlay, ChatOverlayMessageCard


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_chat_overlay_fifo_pruning_settles_at_max_cards(qapp):
    """
    Assert that adding 30 items with MAX_CARDS=10 settles at exactly 10 cards,
    with messages 0..19 evicted and messages 20..29 preserved in correct visual order.
    """
    overlay = ChatWindowOverlay()
    overlay.MAX_CARDS = 10  # Set low threshold for fast testing

    # Clear initial greeting
    overlay._clear_messages()
    assert overlay._messages_layout.count() == 2  # 1 standby message + 1 stretch

    # Append 30 sequential messages
    for i in range(30):
        overlay._append_card("user", f"Message {i}")

    # Total layout items should be exactly MAX_CARDS (10) + 1 trailing stretch spacer = 11
    assert overlay._messages_layout.count() == 11

    # Extract all ChatOverlayMessageCard text contents in layout order (0 to 9)
    card_texts = []
    for idx in range(10):
        item = overlay._messages_layout.itemAt(idx)
        assert item is not None
        widget = item.widget()
        assert isinstance(widget, ChatOverlayMessageCard)
        # Find the body QLabel inside the card
        body_labels = widget.findChildren(QLabel)
        # Message text is the last QLabel in the card
        msg_text = body_labels[-1].text()
        card_texts.append(msg_text)

    # 1. Assert exactly 10 cards exist
    assert len(card_texts) == 10

    # 2. Assert OLDEST messages (0..19) were evicted
    assert "Message 0" not in card_texts
    assert "Message 19" not in card_texts

    # 3. Assert remaining cards are strictly Message 20 through Message 29 in sequential order
    expected = [f"Message {i}" for i in range(20, 30)]
    assert card_texts == expected

    # 4. Assert newest message is at the bottom (index 9)
    assert card_texts[-1] == "Message 29"


def test_chat_overlay_post_pruning_lifecycle_safety(qapp):
    """
    Assert that post-prune operations (_scroll_to_bottom, _clear_messages, resize)
    execute safely without raising RuntimeError or accessing deleted QWidget pointers.
    """
    overlay = ChatWindowOverlay()
    overlay.MAX_CARDS = 5

    # Push 20 messages to trigger multiple pruning passes
    for i in range(20):
        overlay._append_card("agent", f"Log line {i}")

    # Process events to allow deleteLater() calls to complete
    QApplication.processEvents()

    # Verify scroll does not raise
    overlay._scroll_to_bottom()

    # Verify resize does not raise
    overlay.resize(800, 600)
    QApplication.processEvents()

    # Verify clear operates cleanly
    overlay._clear_messages()
    assert overlay._messages_layout.count() == 2  # 1 standby card + 1 stretch
