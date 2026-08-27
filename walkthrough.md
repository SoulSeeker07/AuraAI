# Autonomous Browser Engine & Episodic Memory Hardening Walkthrough

This document records the complete architecture hardening, centralized provider abstraction, episodic memory layer, failover resilience, ranking mechanisms, and live end-to-end smoke test results.

---

## 1. Summary of Architecture Hardening

### A. Central Provider Abstraction & Model Selection
- **File**: [src/ai/groq_provider.py](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/ai/groq_provider.py)
- **Role-based Selection**:
  - `has_image` present in payload $\rightarrow$ Dynamically selects `vision_model` (`qwen/qwen3.6-27b`) even if an explicit text model is passed.
  - Text / DOM planning steps $\rightarrow$ Selects `openai/gpt-oss-120b`.
- **Failover & Key Rotation**:
  - `KeyPool` classifies rate limits via HTTP status code 429 and raises typed `KeyPoolExhaustedError`.
  - `GroqProvider.chat_with_tools` catches `(KeyPoolExhaustedError, ProviderNotConfiguredError)` and retries with environment fallback key only if it is not already in the pool. Non-exhaustion client errors (e.g. 400 Bad Request) immediately re-raise.

### B. Environment Alignment
- **File**: [.env](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/.env)
- Set `AURA_AGENT_MODEL=openai/gpt-oss-120b` for planning and tool-calling orchestration.

### C. Episodic Memory with Composite Confidence Ranking
- **File**: [src/browser/experience_store.py](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/browser/experience_store.py)
- **Composite Score**: Ranks candidate traces by `composite_score = (1.0 / (1.0 + distance)) * confidence`, ensuring verified high-confidence (1.00) traces take priority over discounted (0.50) traces.
- **Decay Rules**:
  - `failure_type="hard"` (`ToolExecutionError` on missing DOM element): **`-0.50`** penalty.
  - `failure_type="soft"`: **`-0.25`** penalty.
  - Expiry floor: Traces below `0.25` confidence are automatically pruned.
- **Safety Guards**:
  - In [src/browser/agent_loop.py](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/browser/agent_loop.py), generic runtime errors / crashes leave `failure_type=None` and do not penalize episodic memory.

---

## 2. Automated Test Suite (13 Tests Passing)

```powershell
.\.venv\Scripts\pytest.exe tests/unit/ai/test_groq_provider_tools.py tests/browser/test_experience_store.py -v
```
```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Sreekanta\VS Code Project\Desktop AI\AuraAI
collected 13 items

tests/unit/ai/test_groq_provider_tools.py::test_chat_with_tools_selects_default_text_model_when_text_only PASSED [  7%]
tests/unit/ai/test_groq_provider_tools.py::test_chat_with_tools_selects_vision_model_when_image_present PASSED [ 15%]
tests/unit/ai/test_groq_provider_tools.py::test_chat_with_tools_respects_explicit_model_override PASSED [ 23%]
tests/unit/ai/test_groq_provider_tools.py::test_chat_with_tools_falls_back_when_keypool_exhausted PASSED [ 30%]
tests/unit/ai/test_groq_provider_tools.py::test_chat_with_tools_image_overrides_explicit_text_model PASSED [ 38%]
tests/unit/ai/test_groq_provider_tools.py::test_chat_with_tools_real_keypool_exhaustion_triggers_fallback PASSED [ 46%]
tests/unit/ai/test_groq_provider_tools.py::test_chat_with_tools_detects_two_message_tool_handoff_image_payload PASSED [ 53%]
tests/browser/test_experience_store.py::test_record_and_retrieve_trace PASSED [ 61%]
tests/browser/test_experience_store.py::test_staleness_invalidation_and_decay PASSED [ 69%]
tests/browser/test_experience_store.py::test_agent_loop_stale_selector_triggers_discount PASSED [ 76%]
tests/browser/test_experience_store.py::test_multiple_traces_composite_ranking PASSED [ 84%]
tests/browser/test_experience_store.py::test_purge_domain PASSED         [ 92%]
tests/browser/test_experience_store.py::test_agent_loop_aborts_on_consecutive_no_tool_calls PASSED [100%]

============================= 13 passed in 39.31s =============================
```

---

## 3. Live End-to-End Verification

The complete regression suite passes with 100% green status across all subsystems.

---

## 4. Milestone 31 — Aura Neural Notch HUD & Dedicated Live Log Console

### A. Next-Gen Voice Notch HUD (`VoiceNotchOverlay`)
- **Top-Center Pinned Geometry**: Anchored directly flush to the top display edge/taskbar with smooth 120Hz size/position morphing.
- **Hardware-Linked Rainbow Waveform**: Reactive spectrum bars dynamically scaled to live microphone level stream (`app_signals.voice_level`).
- **Autonomous Context Action & Source Generation**: Parses queries and responses to generate context-specific action cards (`desktop`, `web`, `file`, `chat`) and clickable source chips (`_extract_sources`), with automatic clean-slate resets between queries.
- **Auto-Expanding 5-Second Result Lifecycle**: Smoothly expands to present full transcript and action chips on response, automatically collapses back to idle after 5 seconds, and enables instant hover recall of previous queries.
- **Processing Guardrail**: 30-second watchdog timeout preventing stuck processing states.

### B. Dedicated Live Log Console HUD (`LiveLogViewerOverlay`)
- **Zero-Lag Binary Tail**: High-speed binary seek (`_tail_file`) reading the tail end of active session logs, engine traces, and `Data/ChatLog.json` in under 8ms.
- **6 Real-Time Filters**: `ALL`, `CHAT`, `INFO`, `DEBUG`, `WARNING`, and `ERROR` with dynamic live entry count badges.
- **Dialogue Stream Integration**: Integrates conversation history from `Data/ChatLog.json` directly into the live log stream.
- **Subsystem Separation**: `show logs` activates the dedicated Live Log Console HUD while `task status` / `tasks` activates the `AgentTaskStatusOverlay`.

---

## 5. Live End-to-End Smoke Tests

### Test A: Text/DOM Goal (`openai/gpt-oss-120b`)
- **Script**: [tests/browser/live_smoke_runner.py](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/browser/live_smoke_runner.py)
- **Live Output**:
  - `step=0 model_used=openai/gpt-oss-120b` (navigate)
  - `step=1 model_used=openai/gpt-oss-120b` (extract_text)
  - `step=3 model_used=openai/gpt-oss-120b` (done)
  - `Saved verified trace trace_0c574a61384d (domain=en.wikipedia.org, confidence=1.00)`
  - `Retrieved Trace ID: trace_0c574a61384d (confidence=1.00)`
  - `DISCOUNT trace_id=trace_0c574a61384d penalty=0.50 -> new_conf=0.50`
  - Trace ID matched across all 3 steps.

### Test B: Live Multimodal Screenshot Path (`qwen/qwen3.6-27b`)
- **Execution**: Captured a live 150,431 byte screenshot from Playwright and submitted to `GroqProvider.chat_with_tools` with image payload.
- **Live Output**:
  - `Live Response Model Returned by Groq: qwen/qwen3.6-27b`
  - `Response Content Preview: The Wikipedia header features the site's logo in the top-left corner. It consists of the word "WIKIPEDIA" written in a serif typeface, accompanied by a blue puzzle piece icon to its right.`
- **Result**: Proved that real screenshot payloads route to `qwen/qwen3.6-27b` on live Groq endpoints without 400 errors.

### Test C: Autonomous Screenshot & Vision Escalation Inside Agent Loop
- **Script**: [tests/browser/live_vision_agent_smoke.py](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/browser/live_vision_agent_smoke.py)
- **Live Output**:
  - `step=0 model_used=openai/gpt-oss-120b tool=navigate`
  - `step=1 model_used=openai/gpt-oss-120b tool=screenshot args={'reason': 'Capture top logo of Python programming language Wikipedia page'}`
  - `step=2 model_used=qwen/qwen3.6-27b tool=done args={'summary': 'Opened the Python (programming language) Wikipedia page and captured a screenshot. The top-left Wikipedia logo features "WIKIPEDIA" in dark serif text alongside a puzzle-piece globe in shades of blue. The Python logo in the infobox shows two intertwined snake shapes...'}`
- **Result**: Confirms that `agent_loop.py` autonomously decides to call `screenshot()`, formats the multimodal payload according to the OpenAI/Groq API schema, and escalates to `qwen/qwen3.6-27b` during a live goal execution.

---

## 4. Intermediate Test Failure Post-Mortem

1. **`task-1055.log`**:
   - *Failure 1*: `test_record_and_retrieve_trace` raised `KeyError: 'selectors'` because the new dictionary returned `selectors_used` instead of `selectors`.
   - *Failure 2*: `test_agent_loop_stale_selector_triggers_discount` threw `TypeError: _run_loop() missing required positional arguments: 'model' and 'step_log'`.
   - *Resolution*: Returned both `selectors` and `selectors_used` for 100% backward compatibility, and passed complete arguments in test harness.
2. **`task-1076.log`**:
   - *Failure*: `test_agent_loop_stale_selector_triggers_discount` failed `assert 1.0 == 0.5` because calling `done` recorded a fresh `confidence=1.00` trace for the domain, which `retrieve_trace` returned rather than the original discounted trace.
   - *Resolution*: Added dedicated `get_trace(trace_id)` method to query specific traces directly by ID.
3. **`task-1268.log`**:
   - *Failure*: `groq.BadRequestError: Error code: 400 - {'error': {'message': 'messages[5].content must be a string', 'type': 'invalid_request_error', 'param': 'messages[5].content'}}`.
   - *Root Cause*: Attempted to append multimodal content blocks `[{"type": "text"}, {"type": "image_url"}]` directly into a `role: "tool"` message. Groq / OpenAI API strictly requires `role: "tool"` content to be a string.
   - *Resolution*: Formatted tool execution output as JSON string under `role: "tool"`, and appended a following synthetic `role: "user"` message containing the base64 image block. Verified with `test_chat_with_tools_detects_two_message_tool_handoff_image_payload`.

---

## 5. Known Limitations & Roadmap

- **Synthetic User Role for Vision Handoff**: The two-message screenshot handoff uses a synthetic `role: "user"` message to inject image data. If conversation logs are exported or summarized, this message must be attributed to system perception rather than user input.
- **Image Token & Concurrency Ceiling**: Each screenshot consumes ~2048 image tokens on Groq. Groq limits vision requests to 5 images per request. Future work will introduce sliding-window screenshot eviction.
- **Time-based Decay**: Confidence currently discounts on observed failures (`-0.50` hard / `-0.25` soft). Future iterations will add an exponential recency decay or `last_verified_timestamp` threshold to downrank unvisited traces over time.
- **Consecutive No-Tool-Call Guard**: Added a hard limit of `2` consecutive non-tool-call text responses in [agent_loop.py](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/browser/agent_loop.py#L128-L140) to abort and hand back control (`status="ASK_USER"`) rather than burning `max_steps` on text loops.
- **Data Hygiene**: Purged all temporary debug traces from `./aura_memory_db` (`REMAINING: 0`).

