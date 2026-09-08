from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest

from brain.intent_router import IntentRouter
from core.aura_core import AuraCore, DETERMINISTIC_LOCAL_INTENTS


@pytest.fixture
def mock_memory():
    mem = MagicMock()
    mem.extract_facts.return_value = []
    return mem


@pytest.fixture
def router(mock_memory):
    return IntentRouter(memory=mock_memory)


def test_research_keywords_pruned_under_agent_loop(router, monkeypatch):
    monkeypatch.setenv("AURA_ENABLE_AGENT_LOOP", "1")

    cognitive_queries = [
        "analyze trends in market data",
        "explain how quicksort works",
        "compare postgres vs sqlite",
        "how to optimize sql queries",
        "latest stock market earnings overview",
        "deep analysis of transformer attention",
    ]
    for q in cognitive_queries:
        intent = router.detect(q)
        assert intent.name == "provider_chat", f"Query '{q}' routed to '{intent.name}', expected 'provider_chat'"


def test_shell_command_regexes_pruned_under_agent_loop(router, monkeypatch):
    monkeypatch.setenv("AURA_ENABLE_AGENT_LOOP", "1")

    shell_queries = [
        "in C:\\projects, run command: pytest",
        "in the terminal, run dir",
        "run command: git status",
        "in d:\\work, execute command: npm test",
    ]
    for q in shell_queries:
        intent = router.detect(q)
        assert intent.name == "provider_chat", f"Query '{q}' routed to '{intent.name}', expected 'provider_chat'"


def test_desktop_action_heuristics_pruned_under_agent_loop(router, monkeypatch):
    monkeypatch.setenv("AURA_ENABLE_AGENT_LOOP", "1")

    desktop_queries = [
        "open notepad",
        "launch calculator",
        "run git status",
        "git push",
        "close chrome",
    ]
    for q in desktop_queries:
        intent = router.detect(q)
        assert intent.name == "provider_chat", f"Query '{q}' routed to '{intent.name}', expected 'provider_chat'"


def test_autonomous_browser_heuristics_pruned_under_agent_loop(router, monkeypatch):
    monkeypatch.setenv("AURA_ENABLE_AGENT_LOOP", "1")

    browser_queries = [
        "go to https://news.ycombinator.com and read the top story",
        "search python tutorials on google",
        "go to https://github.com/trending",
        "browse to wikipedia and check quantum computing",
        "in amazon search for wireless headphones",
    ]
    for q in browser_queries:
        intent = router.detect(q)
        assert intent.name == "provider_chat", f"Query '{q}' routed to '{intent.name}', expected 'provider_chat'"


@pytest.mark.parametrize("flag_value", ["0", "1"])
def test_deterministic_fastpaths_retained(router, monkeypatch, flag_value):
    monkeypatch.setenv("AURA_ENABLE_AGENT_LOOP", flag_value)

    fast_path_expectations = [
        ("what time is it", "local_time"),
        ("what is the time", "local_time"),
        ("what is today's date", "local_time"),
        ("battery status", "battery_status"),
        ("battery percentage", "battery_status"),
        ("wifi status", "wifi_status"),
        ("turn on wifi", "wifi_control"),
        ("turn off wifi", "wifi_control"),
        ("bluetooth status", "bluetooth_status"),
        ("turn on bluetooth", "bluetooth_control"),
        ("turn off bluetooth", "bluetooth_control"),
        ("network status", "network_status"),
        ("system status", "system_status"),
        ("restart aura", "restart_aura"),
        ("confirm tkt_12345678", "confirm_ticket"),
        ("deny tkt_12345678", "confirm_ticket"),
        ("approve all tickets", "confirm_ticket"),
        ("stop listening", "voice_control"),
        ("start listening", "voice_control"),
        ("play kannada top songs", "play_music"),
        ("turn on the bedroom light", "smarthome_control"),
        ("create folder named project_docs on desktop", "folder_creation"),
        ("open weather hud", "hud_overlay"),
        ("say hello aura", "say_phrase"),
        ("solved captcha", "resume_browser"),
    ]
    for query, expected_intent in fast_path_expectations:
        intent = router.detect(query)
        assert intent.name == expected_intent, (
            f"[Flag={flag_value}] Query '{query}' routed to '{intent.name}', expected '{expected_intent}'"
        )
        assert intent.name in DETERMINISTIC_LOCAL_INTENTS, (
            f"Intent '{intent.name}' for query '{query}' is not in DETERMINISTIC_LOCAL_INTENTS!"
        )


def test_legacy_parity_when_agent_loop_disabled(router, monkeypatch):
    monkeypatch.setenv("AURA_ENABLE_AGENT_LOOP", "0")

    # Research keywords trigger autonomous_browser
    intent = router.detect("analyze trends in market data")
    assert intent.name == "autonomous_browser"

    # Shell command triggers desktop_action
    intent = router.detect("in C:\\projects, run command: pytest")
    assert intent.name == "desktop_action"
    assert intent.data.get("verb") == "run"

    # Terminal command triggers desktop_action
    intent = router.detect("in the terminal, run dir")
    assert intent.name == "desktop_action"
    assert intent.data.get("verb") == "run"

    # Desktop app launch triggers desktop_action
    intent = router.detect("open notepad")
    assert intent.name == "desktop_action"

    # URL / site triggers autonomous_browser
    intent = router.detect("go to https://news.ycombinator.com")
    assert intent.name == "autonomous_browser"


@pytest.mark.asyncio
async def test_auracore_fastpath_boundary_enforcement(monkeypatch):
    core = AuraCore.get_instance()
    monkeypatch.setenv("AURA_ENABLE_AGENT_LOOP", "1")

    # 1. Deterministic local intents resolve immediately (< 15ms, no LLM call)
    test_queries = [
        ("what time is it", "Current time: 10:00 AM"),
        ("play lofi beats", "Opening YouTube search for lofi beats"),
        ("turn on the light", "Tapo light turned on"),
        ("create folder test_dir on desktop", "Folder created"),
    ]
    for q, ans in test_queries:
        with patch.object(core.conversation_engine, "_answer_local_intent", return_value=ans) as mock_local:
            resp = await core.get_ai_response(q, session_id="sess_boundary_test")
            assert mock_local.called, f"Expected _answer_local_intent to be called for '{q}'"
            assert resp == ans

    # 2. Cognitive query bypasses _answer_local_intent and reaches AgentLoop
    mock_msg = SimpleNamespace(
        content="Market trends synthesized via AgentLoop native model reasoning.",
        tool_calls=None,
    )
    mock_choice = SimpleNamespace(message=mock_msg)
    mock_res = SimpleNamespace(choices=[mock_choice])

    with patch.object(core.conversation_engine, "_answer_local_intent") as mock_local, \
         patch.object(core, "_call_groq_streaming", return_value=mock_res, create=True), \
         patch("ai.key_pool.KeyPool.execute_with_failover", return_value=mock_res):
        resp = await core.get_ai_response("analyze trends in market data", session_id="sess_boundary_test")
        assert not mock_local.called
        assert "Market trends synthesized via AgentLoop" in resp


def test_default_flag_active(router, monkeypatch):
    """Verify that when AURA_ENABLE_AGENT_LOOP is unset, is_agent_loop_enabled() returns True
    and the router behaves identically to enabled mode (pruning heuristics and routing to provider_chat)."""
    from core.orchestration.agent_loop import is_agent_loop_enabled

    monkeypatch.delenv("AURA_ENABLE_AGENT_LOOP", raising=False)

    assert is_agent_loop_enabled() is True

    # Real router verification under unset flag:
    # 1. Cognitive queries must route to provider_chat (AgentLoop), not autonomous_browser
    intent = router.detect("analyze trends in market data")
    assert intent.name == "provider_chat"

    # 2. Shell queries must route to provider_chat, not desktop_action
    intent_shell = router.detect("in C:\\projects, run command: pytest")
    assert intent_shell.name == "provider_chat"

    # 3. Deterministic queries must remain unaffected
    intent_time = router.detect("what time is it")
    assert intent_time.name == "local_time"


def test_deterministic_intents_constant_coverage():
    critical_intents = {
        "local_time", "live_weather", "battery_status",
        "bluetooth_status", "bluetooth_control",
        "wifi_status", "wifi_control",
        "network_status", "system_status",
        "confirm_ticket", "voice_control", "restart_aura",
        "memory_summary", "remember_fact", "profile_lookup",
        "skills_lookup", "goals_lookup", "preferences_lookup", "projects_lookup",
        "brightness_control", "audio_control",
        "task_complete", "tasks.complete", "reminders_query",
        "play_music", "smarthome_control", "folder_creation",
        "hud_overlay", "overlay_toggle", "say_phrase",
        "open_file", "rag_query", "resume_browser", "capability_status",
    }
    assert critical_intents.issubset(DETERMINISTIC_LOCAL_INTENTS), (
        f"Missing intents in DETERMINISTIC_LOCAL_INTENTS: {critical_intents - DETERMINISTIC_LOCAL_INTENTS}"
    )


def test_no_shadowed_module_imports_in_conversation_engine():
    """Universal static AST regression guard: asserts that across all functions and methods
    in conversation_engine.py, no inner import or assignment shadows ANY module-level import.
    This prevents UnboundLocalError and static lexical scope poisoning across the file."""
    import ast
    from pathlib import Path

    src_path = Path(__file__).resolve().parents[2] / "src" / "brain" / "conversation_engine.py"
    tree = ast.parse(src_path.read_text(encoding="utf-8"))

    module_imports = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for n in node.names:
                module_imports.add(n.asname or n.name)
        elif isinstance(node, ast.ImportFrom):
            for n in node.names:
                module_imports.add(n.asname or n.name)

    shadowed_imports = []
    shadowed_stores = []
    shadowed_params = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_name = node.name

            # Check parameter declarations (ast.arg)
            all_args = list(node.args.posonlyargs + node.args.args + node.args.kwonlyargs)
            if node.args.vararg:
                all_args.append(node.args.vararg)
            if node.args.kwarg:
                all_args.append(node.args.kwarg)

            for arg in all_args:
                if arg.arg in module_imports:
                    shadowed_params.append((fn_name, arg.arg, arg.lineno))

            for child in ast.walk(node):
                if child is not node and isinstance(child, (ast.Import, ast.ImportFrom)):
                    for n in child.names:
                        name = n.asname or n.name
                        if name in module_imports:
                            shadowed_imports.append((fn_name, name, child.lineno))
                elif isinstance(child, ast.Name) and child.id in module_imports and isinstance(child.ctx, ast.Store):
                    shadowed_stores.append((fn_name, child.id, child.lineno))

    assert not shadowed_imports, (
        f"Found inner imports shadowing module-level imports in conversation_engine.py: {shadowed_imports}. "
        "Inner imports statically poison lexical scope and cause UnboundLocalError."
    )
    assert not shadowed_stores, (
        f"Found assignments storing to module-level imported names in conversation_engine.py: {shadowed_stores}."
    )
    assert not shadowed_params, (
        f"Found function parameters shadowing module-level imported names in conversation_engine.py: {shadowed_params}."
    )


def test_unmocked_local_intent_execution():
    """Execution regression guard: invokes real, unmocked _answer_local_intent() across a
    representative sample of branches to prove no UnboundLocalError or NameError occurs at runtime."""
    import uuid
    from pathlib import Path
    from brain.models import Intent

    core = AuraCore.get_instance()
    engine = core.conversation_engine
    test_id = uuid.uuid4().hex[:8]
    temp_folder_name = f"test_reg_{test_id}"

    sample_intents = [
        Intent("local_time", {}),
        Intent("battery_status", {}),
        Intent("folder_creation", {"folder_name": temp_folder_name, "location": "workspace"}),
        Intent("brightness_control", {"raw": "set brightness to 50%"}),
        Intent("audio_control", {"raw": "volume status"}),
    ]

    for intent in sample_intents:
        res = engine._answer_local_intent(intent)
        assert res is not None and len(str(res).strip()) > 0, f"Intent '{intent.name}' returned empty result"

    # Clean up test folder if created
    p = Path(temp_folder_name)
    if p.exists():
        p.rmdir()