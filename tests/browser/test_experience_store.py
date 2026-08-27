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

    # Mock session & gate
    mock_session = MagicMock()
    mock_session.headless = False

    step_log = []
    res = _run_loop(
        session=mock_session,
        messages=[{"role": "user", "content": "buy mechanical keyboard"}],
        tools=mock_tools,
        gate=SafetyGate(),
        goal="buy mechanical keyboard",
        model="openai/gpt-oss-120b",
        max_steps=5,
        step_log=step_log,
        candidate_trace_id=trace_id,
    )

    # Assert original candidate trace confidence was discounted by 0.50 due to hard ToolExecutionError
    discounted = temp_store.get_trace(trace_id)
    assert discounted is not None
    assert discounted["confidence"] == 0.50


def test_multiple_traces_composite_ranking(temp_store):
    # Record trace 1 with degraded confidence 0.40 on exact query keywords
    t1 = temp_store.record_trace(
        domain="github.com",
        goal="search python repository",
        action_sequence=[{"tool": "navigate", "args": {"url": "https://github.com"}}],
        selectors_used=["search-box"],
        confidence=0.40,
    )

    # Record trace 2 with high confidence 1.00 on slightly paraphrased keywords
    t2 = temp_store.record_trace(
        domain="github.com",
        goal="find python projects on github",
        action_sequence=[{"tool": "navigate", "args": {"url": "https://github.com/search"}}],
        selectors_used=["search-input"],
        confidence=1.00,
    )

    # Query: "search python repository"
    # Even though t1 has higher lexical overlap, t2's 1.00 confidence vs t1's 0.40 degraded confidence
    # produces a higher composite score (0.85+ vs 0.40), properly preferring the reliable trace.
    best = temp_store.retrieve_trace("github.com", "search python repository", min_confidence=0.3)
    assert best is not None
    assert best["trace_id"] == t2
    assert best["confidence"] == 1.00


def test_purge_domain(temp_store):
    temp_store.record_trace(
        domain="reddit.com",
        goal="check python subreddit",
        action_sequence=[{"tool": "navigate", "args": {"url": "https://reddit.com/r/python"}}],
        selectors_used=[],
        confidence=1.00,
    )
    assert temp_store.retrieve_trace("reddit.com", "check python subreddit") is not None

    deleted_count = temp_store.purge_domain("reddit.com")
    assert deleted_count >= 1
    assert temp_store.retrieve_trace("reddit.com", "check python subreddit") is None


def test_agent_loop_aborts_on_consecutive_no_tool_calls(monkeypatch):
    from unittest.mock import MagicMock
    from browser.agent_loop import _run_loop
    from browser.safety_gate import SafetyGate

    mock_msg = MagicMock()
    mock_msg.content = "I am thinking about what to do next..."
    mock_msg.tool_calls = None  # No tool calls

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=mock_msg)]
    mock_resp.model = "openai/gpt-oss-120b"

    mock_chat = MagicMock(return_value=mock_resp)
    monkeypatch.setattr("ai.groq_provider.GroqProvider.chat_with_tools", mock_chat)

    mock_session = MagicMock()
    mock_session.headless = True
    mock_tools = MagicMock()
    mock_tools.page.url = "https://example.com"

    step_log = []
    res = _run_loop(
        session=mock_session,
        messages=[{"role": "user", "content": "test goal"}],
        tools=mock_tools,
        gate=SafetyGate(),
        goal="test goal",
        model="openai/gpt-oss-120b",
        max_steps=10,
        step_log=step_log,
    )

    # Must abort cleanly on 2 consecutive no-tool turns with ASK_USER status
    assert res["status"] == "ASK_USER"
    assert "I am thinking" in res["summary"]
    # Proves the loop aborted early at 2 calls rather than running all 10 max_steps
    assert mock_chat.call_count == 2

