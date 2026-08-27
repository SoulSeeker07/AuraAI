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

## 2. Automated Test Suite (12 Tests Passing)

```powershell
.\.venv\Scripts\pytest.exe tests/unit/ai/test_groq_provider_tools.py tests/browser/test_experience_store.py -v
```
```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Sreekanta\VS Code Project\Desktop AI\AuraAI
collected 12 items

tests/unit/ai/test_groq_provider_tools.py::test_chat_with_tools_selects_default_text_model_when_text_only PASSED [  8%]
tests/unit/ai/test_groq_provider_tools.py::test_chat_with_tools_selects_vision_model_when_image_present PASSED [ 16%]
tests/unit/ai/test_groq_provider_tools.py::test_chat_with_tools_respects_explicit_model_override PASSED [ 25%]
tests/unit/ai/test_groq_provider_tools.py::test_chat_with_tools_falls_back_when_keypool_exhausted PASSED [ 33%]
tests/unit/ai/test_groq_provider_tools.py::test_chat_with_tools_image_overrides_explicit_text_model PASSED [ 41%]
tests/unit/ai/test_groq_provider_tools.py::test_chat_with_tools_real_keypool_exhaustion_triggers_fallback PASSED [ 50%]
tests/browser/test_experience_store.py::test_record_and_retrieve_trace PASSED [ 58%]
tests/browser/test_experience_store.py::test_staleness_invalidation_and_decay PASSED [ 66%]
tests/browser/test_experience_store.py::test_agent_loop_stale_selector_triggers_discount PASSED [ 75%]
tests/browser/test_experience_store.py::test_multiple_traces_composite_ranking PASSED [ 83%]
tests/browser/test_experience_store.py::test_purge_domain PASSED         [ 91%]
tests/browser/test_experience_store.py::test_agent_loop_aborts_on_consecutive_no_tool_calls PASSED [100%]

============================= 12 passed in 13.60s =============================
```

---

---

## 3. Live End-to-End Smoke Tests

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

---

## 5. Known Limitations & Roadmap

- **Time-based Decay**: Confidence currently discounts on observed failures (`-0.50` hard / `-0.25` soft). Future iterations will add an exponential recency decay or `last_verified_timestamp` threshold to downrank unvisited traces over time.
- **Consecutive No-Tool-Call Guard**: Added a hard limit of `2` consecutive non-tool-call text responses in [agent_loop.py](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/browser/agent_loop.py#L128-L140) to abort and hand back control (`status="ASK_USER"`) rather than burning `max_steps` on text loops.
- **Data Hygiene**: Purged all temporary debug traces from `./aura_memory_db` (`REMAINING: 0`).
