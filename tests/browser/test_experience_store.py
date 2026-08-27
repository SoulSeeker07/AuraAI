"""
tests/browser/test_experience_store.py
======================================
Unit tests verifying BrowserExperienceStore:
- Trace recording and metadata serialization
- Episodic trace retrieval with domain and query matching
- Staleness invalidation and confidence decay math
- Expiry threshold when confidence drops below floor
"""

import tempfile
import pytest
from browser.experience_store import BrowserExperienceStore


@pytest.fixture
def temp_store():
    tmpdir = tempfile.mkdtemp()
    store = BrowserExperienceStore(persist_dir=tmpdir)
    yield store
    import shutil
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass


def test_record_and_retrieve_trace(temp_store):
    trace_id = temp_store.record_trace(
        domain="amazon.in",
        goal="search for mechanical keyboard on amazon",
        action_sequence=[
            {"tool": "navigate", "args": {"url": "https://www.amazon.in/s?k=mechanical+keyboard"}},
            {"tool": "click", "args": {"selector": "text=Mechanical Gaming Keyboard"}},
        ],
        selectors_used=["text=Mechanical Gaming Keyboard"],
        success=True,
        confidence=1.0,
        summary="Navigated and selected keyboard",
    )
    assert trace_id.startswith("trace_")

    # Exact domain retrieval
    match = temp_store.retrieve_trace("amazon.in", "buy mechanical keyboard")
    assert match is not None
    assert match["domain"] == "amazon.in"
    assert match["confidence"] == 1.0
    assert len(match["action_sequence"]) == 2
    assert match["selectors"] == ["text=Mechanical Gaming Keyboard"]


def test_staleness_invalidation_and_decay(temp_store):
    trace_id = temp_store.record_trace(
        domain="flipkart.com",
        goal="add s24 ultra to cart in flipkart",
        action_sequence=[
            {"tool": "navigate", "args": {"url": "https://www.flipkart.com"}},
            {"tool": "click", "args": {"selector": "text=Add to Cart"}},
        ],
        selectors_used=["text=Add to Cart"],
        success=True,
        confidence=1.0,
        summary="Added item",
    )

    # 1. Soft mismatch failure: 1.0 -> 0.75 (-0.25)
    temp_store.discount_trace(trace_id, failure_type="soft", reason="Navigation timeout")
    t1 = temp_store.retrieve_trace("flipkart.com", "add s24 ultra in flipkart", min_confidence=0.5)
    assert t1 is not None
    assert pytest.approx(t1["confidence"], 0.01) == 0.75

    # 2. Hard structural failure: 0.75 -> 0.25 (-0.50)
    temp_store.discount_trace(trace_id, failure_type="hard", reason="Could not find element matching 'Add to Cart'")
    t2_strict = temp_store.retrieve_trace("flipkart.com", "add s24 ultra in flipkart", min_confidence=0.5)
    assert t2_strict is None  # filtered out by min_confidence 0.5

    t2_lenient = temp_store.retrieve_trace("flipkart.com", "add s24 ultra in flipkart", min_confidence=0.25)
    assert t2_lenient is not None
    assert pytest.approx(t2_lenient["confidence"], 0.01) == 0.25

    # 3. Third failure: drops below 0.25 floor -> expiry and complete deletion
    temp_store.discount_trace(trace_id, failure_type="soft", reason="Second timeout")
    t3 = temp_store.retrieve_trace("flipkart.com", "add s24 ultra in flipkart", min_confidence=0.0)
    assert t3 is None


def test_agent_loop_stale_selector_triggers_discount(monkeypatch, temp_store):
    from unittest.mock import MagicMock
    from browser.agent_loop import _run_loop
    from browser.browser_tools import ToolExecutionError
    from browser.safety_gate import SafetyGate

    # Monkeypatch singleton store to use temp_store
    monkeypatch.setattr("browser.experience_store.BrowserExperienceStore._instance", temp_store)

    trace_id = temp_store.record_trace(
        domain="amazon.in",
        goal="buy mechanical keyboard",
        action_sequence=[{"tool": "click", "args": {"description": "Stale Nonexistent Button"}}],
        selectors_used=["Stale Nonexistent Button"],
        success=True,
        confidence=1.0,
    )
    assert temp_store.retrieve_trace("amazon.in", "buy mechanical keyboard")["confidence"] == 1.0

    # Mock tool call from model suggesting the stale selector
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_123"
    mock_tool_call.function.name = "click"
    mock_tool_call.function.arguments = '{"description": "Stale Nonexistent Button"}'

    mock_msg_1 = MagicMock()
    mock_msg_1.content = None
    mock_msg_1.tool_calls = [mock_tool_call]

    mock_tool_done = MagicMock()
    mock_tool_done.id = "call_456"
    mock_tool_done.function.name = "done"
    mock_tool_done.function.arguments = '{"summary": "Finished"}'

    mock_msg_2 = MagicMock()
    mock_msg_2.content = None
    mock_msg_2.tool_calls = [mock_tool_done]

    mock_resp_1 = MagicMock()
    mock_resp_1.choices = [MagicMock(message=mock_msg_1)]

    mock_resp_2 = MagicMock()
    mock_resp_2.choices = [MagicMock(message=mock_msg_2)]

    responses = [mock_resp_1, mock_resp_2]

    def fake_chat_with_tools(*args, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr("ai.groq_provider.GroqProvider.chat_with_tools", fake_chat_with_tools)

    # Mock tools to raise ToolExecutionError for stale selector
    mock_tools = MagicMock()
    mock_tools.click.side_effect = ToolExecutionError("Could not find an element matching 'Stale Nonexistent Button'")
    mock_tools.page.url = "https://www.amazon.in"

    mock_session = MagicMock()
    mock_session.headless = True

    gate = SafetyGate()
    step_log = []
    messages = [{"role": "user", "content": "buy mechanical keyboard"}]

    result = _run_loop(
        session=mock_session,
        tools=mock_tools,
        gate=gate,
        goal="buy mechanical keyboard",
        messages=messages,
        model="qwen/qwen3.6-27b",
        max_steps=3,
        step_log=step_log,
        candidate_trace_id=trace_id,
    )

    # Assert hard discount (-0.50) was executed on the candidate trace in episodic memory
    retrieved = temp_store.retrieve_trace("amazon.in", "buy mechanical keyboard", min_confidence=0.4)
    assert retrieved is not None
    assert pytest.approx(retrieved["confidence"], 0.01) == 0.50

