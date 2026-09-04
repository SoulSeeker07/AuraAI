import asyncio
import pytest
from unittest.mock import MagicMock, patch
from core.capabilities.capability_registry import CapabilityRegistry
from core.capabilities.models import Capability
from core.orchestration.autonomy_mode import ActionRisk
from brain.intent_classifier import (
    IntentClassifier,
    ClassificationOutcome,
    ClassificationResult,
)


@pytest.fixture
def mock_registry():
    registry = MagicMock(spec=CapabilityRegistry)
    live_caps = [
        Capability(
            name="desktop.window.open",
            domain="desktop",
            description="Open desktop app",
            input_schema={
                "type": "object",
                "properties": {"app_name": {"type": "string"}},
                "required": ["app_name"],
            },
            risk_level=ActionRisk.LOW,
            is_live=True,
        ),
        Capability(
            name="coding.generate_code",
            domain="coding",
            description="Generate code",
            input_schema={
                "type": "object",
                "properties": {"prompt": {"type": "string"}},
                "required": ["prompt"],
            },
            risk_level=ActionRisk.MEDIUM,
            is_live=True,
        ),
        Capability(
            name="system.shell",
            domain="desktop",
            description="Execute shell command",
            input_schema={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
            risk_level=ActionRisk.LOW,
            is_live=True,
        ),
    ]
    registry.list.return_value = live_caps
    return registry


@pytest.fixture
def mock_provider_manager():
    pm = MagicMock()
    return pm


def _make_mock_tool_response(tool_name: str, arguments: str):
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = tool_name
    mock_tool_call.function.arguments = arguments

    mock_msg = MagicMock()
    mock_msg.tool_calls = [mock_tool_call]
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


@pytest.mark.asyncio
async def test_tool_schema_generation(mock_registry, mock_provider_manager):
    classifier = IntentClassifier(registry=mock_registry, provider_manager=mock_provider_manager)
    tools = classifier._build_tool_schema(mock_registry.list(require_live=True))

    # 3 domain capabilities + 2 universal tools (general_chat, clarification)
    assert len(tools) == 5
    fn_names = [t["function"]["name"] for t in tools]
    assert "desktop__window__open" in fn_names
    assert "coding__generate_code" in fn_names
    assert "system__shell" in fn_names
    assert "conversation__general_chat" in fn_names
    assert "system__clarification" in fn_names


@pytest.mark.asyncio
async def test_successful_capability_classification(mock_registry, mock_provider_manager):
    classifier = IntentClassifier(registry=mock_registry, provider_manager=mock_provider_manager)
    mock_provider_manager.chat_with_tools.return_value = _make_mock_tool_response(
        "system__shell", '{"command": "git status"}'
    )

    result = await classifier.classify("run git status")
    assert result.outcome == ClassificationOutcome.RESOLVED
    assert result.intent is not None
    assert result.intent.name == "system.shell"
    assert result.intent.data == {"command": "git status"}
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_general_chat_resolves_to_provider_chat(mock_registry, mock_provider_manager):
    classifier = IntentClassifier(registry=mock_registry, provider_manager=mock_provider_manager)
    mock_provider_manager.chat_with_tools.return_value = _make_mock_tool_response(
        "conversation__general_chat", '{"topic": "greeting"}'
    )

    result = await classifier.classify("hello there")
    assert result.outcome == ClassificationOutcome.RESOLVED
    assert result.intent is not None
    assert result.intent.name == "provider_chat"
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_system_clarification_tool_resolves_to_needs_clarification(mock_registry, mock_provider_manager):
    classifier = IntentClassifier(registry=mock_registry, provider_manager=mock_provider_manager)
    mock_provider_manager.chat_with_tools.return_value = _make_mock_tool_response(
        "system__clarification", '{"question": "Which repository or branch did you want to inspect?"}'
    )

    result = await classifier.classify("check the repo thing")
    assert result.outcome == ClassificationOutcome.NEEDS_CLARIFICATION
    assert result.intent is None
    assert result.clarification_prompt == "Which repository or branch did you want to inspect?"


@pytest.mark.asyncio
async def test_retry_on_malformed_json_succeeds_on_second_attempt(mock_registry, mock_provider_manager):
    classifier = IntentClassifier(registry=mock_registry, provider_manager=mock_provider_manager)

    # Attempt 1: broken JSON arguments
    resp_bad = _make_mock_tool_response("system__shell", '{"command": "git stat...')
    # Attempt 2: valid JSON arguments
    resp_good = _make_mock_tool_response("system__shell", '{"command": "git status"}')

    mock_provider_manager.chat_with_tools.side_effect = [resp_bad, resp_good]

    result = await classifier.classify("run git status")
    assert mock_provider_manager.chat_with_tools.call_count == 2
    assert result.outcome == ClassificationOutcome.RESOLVED
    assert result.intent is not None
    assert result.intent.name == "system.shell"
    assert result.intent.data == {"command": "git status"}


@pytest.mark.asyncio
async def test_retry_on_missing_required_parameter_succeeds_on_second_attempt(mock_registry, mock_provider_manager):
    classifier = IntentClassifier(registry=mock_registry, provider_manager=mock_provider_manager)

    # Attempt 1: missing required parameter "app_name"
    resp_missing = _make_mock_tool_response("desktop__window__open", '{}')
    # Attempt 2: corrected parameter
    resp_valid = _make_mock_tool_response("desktop__window__open", '{"app_name": "notepad"}')

    mock_provider_manager.chat_with_tools.side_effect = [resp_missing, resp_valid]

    result = await classifier.classify("open notepad")
    assert mock_provider_manager.chat_with_tools.call_count == 2
    assert result.outcome == ClassificationOutcome.RESOLVED
    assert result.intent is not None
    assert result.intent.name == "desktop.window.open"
    assert result.intent.data == {"app_name": "notepad"}


@pytest.mark.asyncio
async def test_exhausted_retries_returns_needs_clarification(mock_registry, mock_provider_manager):
    classifier = IntentClassifier(registry=mock_registry, provider_manager=mock_provider_manager)

    # Both attempts return invalid capability
    resp_bad1 = _make_mock_tool_response("unknown__tool", '{}')
    resp_bad2 = _make_mock_tool_response("still__unknown", '{}')

    mock_provider_manager.chat_with_tools.side_effect = [resp_bad1, resp_bad2]

    result = await classifier.classify("do a mystery action")
    assert mock_provider_manager.chat_with_tools.call_count == 2
    assert result.outcome == ClassificationOutcome.NEEDS_CLARIFICATION
    assert result.intent is None
    assert "clarify" in (result.clarification_prompt or "").lower()


@pytest.mark.asyncio
async def test_timeout_fails_closed(mock_registry, mock_provider_manager):
    classifier = IntentClassifier(
        registry=mock_registry,
        provider_manager=mock_provider_manager,
        timeout_seconds=0.2,
    )

    def slow_call(*args, **kwargs):
        import time
        time.sleep(0.5)
        return MagicMock()

    mock_provider_manager.chat_with_tools.side_effect = slow_call

    result = await classifier.classify("open notepad")
    assert result.outcome == ClassificationOutcome.FAILED_CLOSED
    assert result.intent is None


@pytest.mark.asyncio
async def test_provider_error_fails_closed(mock_registry, mock_provider_manager):
    classifier = IntentClassifier(registry=mock_registry, provider_manager=mock_provider_manager)
    mock_provider_manager.chat_with_tools.side_effect = RuntimeError("KeyPoolExhausted")

    result = await classifier.classify("open notepad")
    assert result.outcome == ClassificationOutcome.FAILED_CLOSED
    assert result.intent is None


@pytest.mark.asyncio
async def test_malformed_json_fails_closed_after_retries(mock_registry, mock_provider_manager):
    classifier = IntentClassifier(registry=mock_registry, provider_manager=mock_provider_manager)

    # Both attempts return malformed / unparseable JSON
    resp_bad1 = _make_mock_tool_response("system__shell", '{"command": broken')
    resp_bad2 = _make_mock_tool_response("system__shell", '{"command": {invalid')

    mock_provider_manager.chat_with_tools.side_effect = [resp_bad1, resp_bad2]

    result = await classifier.classify("run git status")
    assert mock_provider_manager.chat_with_tools.call_count == 2
    assert result.outcome == ClassificationOutcome.NEEDS_CLARIFICATION
    assert result.intent is None
    assert result.confidence <= 0.2


@pytest.mark.asyncio
async def test_low_confidence_triggers_retry(mock_registry, mock_provider_manager):
    # Capability requires "command". Attempt 1 missing parameter yields confidence 0.3 (< 0.7 threshold).
    # Attempt 2 yields valid parameter -> confidence 1.0.
    classifier = IntentClassifier(registry=mock_registry, provider_manager=mock_provider_manager, confidence_threshold=0.7)

    resp_low_conf = _make_mock_tool_response("system__shell", '{}')
    resp_high_conf = _make_mock_tool_response("system__shell", '{"command": "git diff"}')

    mock_provider_manager.chat_with_tools.side_effect = [resp_low_conf, resp_high_conf]

    result = await classifier.classify("diff the changes")
    assert mock_provider_manager.chat_with_tools.call_count == 2
    assert result.outcome == ClassificationOutcome.RESOLVED
    assert result.intent is not None
    assert result.intent.name == "system.shell"
    assert result.intent.data == {"command": "git diff"}
    assert result.confidence == 1.0


def test_candidate_pruner_handles_synonyms_for_non_anchored_capabilities():
    # Build 200 dummy capabilities to simulate a large registry
    dummy_caps = [
        Capability(
            name=f"custom_domain_{i}.generic_action_{j}",
            domain=f"custom_domain_{i}",
            description=f"Perform generic action {j} in domain {i}",
            is_live=True,
        )
        for i in range(20)
        for j in range(10)
    ]

    # Non-anchored capability 1: Voice TTS
    target_tts = Capability(
        name="audio_synthesizer.speak_text",
        domain="audio",
        description="Synthesize text to speech voice narration",
        tags=["voice", "tts", "speak"],
        is_live=True,
    )
    # Non-anchored capability 2: Weather forecast
    target_weather = Capability(
        name="meteorology.precipitation_monitor",
        domain="meteorology",
        description="Check rain and precipitation forecast",
        tags=["weather", "rain", "forecast"],
        is_live=True,
    )
    # Non-anchored capability 3: Smart home lighting
    target_dimmer = Capability(
        name="illumination.ambient_dimmer",
        domain="smarthome",
        description="Adjust light brightness and dim smart bulbs",
        tags=["lighting", "dim", "brightness"],
        is_live=True,
    )

    dummy_caps.extend([target_tts, target_weather, target_dimmer])

    # Assert these 3 targets are NOT in anchor list
    classifier = IntentClassifier()
    for cap in [target_tts, target_weather, target_dimmer]:
        assert not any(anchor in cap.name.lower() for anchor in classifier._CORE_ANCHOR_PATTERNS)

    # Query 1: "make it read the words out loud" (synonyms: read, words, aloud -> voice, tts, speak)
    selected_1 = classifier._select_candidate_capabilities("make it read the words out loud", dummy_caps, max_candidates=25)
    names_1 = [c.name for c in selected_1]
    assert len(selected_1) <= 25
    assert "audio_synthesizer.speak_text" in names_1

    # Query 2: "is it going to precipitate today?" (synonym: precipitate -> rain, weather, forecast)
    selected_2 = classifier._select_candidate_capabilities("is it going to precipitate today?", dummy_caps, max_candidates=25)
    names_2 = [c.name for c in selected_2]
    assert len(selected_2) <= 25
    assert "meteorology.precipitation_monitor" in names_2

    # Query 3: "make the room darker" (synonym: darker -> dim, brightness, bulb)
    selected_3 = classifier._select_candidate_capabilities("make the room darker", dummy_caps, max_candidates=25)
    names_3 = [c.name for c in selected_3]
    assert len(selected_3) <= 25
    assert "illumination.ambient_dimmer" in names_3
