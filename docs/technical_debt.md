# Technical Debt & Architecture Remediation Registry

This document tracks identified architectural debt, interim compatibility shims, and scheduled remediation tasks.

---

## 1. `EventRuntime` Dual-API & Legacy Trigger Compatibility Shim
* **Location**: [`src/autonomy/event_runtime.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/autonomy/event_runtime.py), [`src/autonomy/trigger_scheduler.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/autonomy/trigger_scheduler.py)
* **Status**: ✅ **RESOLVED** (`c1b7be8`)
* **Resolution**:
  1. Extracted `TriggerScheduler` daemon into dedicated [`src/autonomy/trigger_scheduler.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/autonomy/trigger_scheduler.py) — owns `start()`/`stop()`, `emit_event()`, `fire_trigger()`, `_scheduler_loop()`, `_execute_trigger_task()`, concurrency policy enforcement, and coordinator dispatch.
  2. Cleaned `EventRuntime` to pure telemetry ingestion: dropped `registry`, `coordinator`, `policy`, `**kwargs` from constructor; removed `emit_event()`, `_scheduler_loop()`, `_fire_trigger()`, `_execute_trigger_task()`, `_running` setter. Constructor now fails loudly on unexpected kwargs.
  3. Updated `PersonalOSRuntime` to instantiate `TriggerScheduler(registry=..., coordinator=..., policy=...)` instead of `EventRuntime(...)`.
  4. Migrated `tests/unit/test_event_runtime.py` trigger lifecycle tests to `TriggerScheduler`.
  5. **Regression**: 73/73 tests passed (M23+M24 full suite, 37.86s).

---

## 2. Desktop Application Name Resolution & Parameter Propagation
* **Location**: [`src/brain/executive/dmm.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/brain/executive/dmm.py), [`src/core/backends/adapters/desktop_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/desktop_backend.py)
* **Status**: **PARTIALLY RESOLVED (Source-level fix applied; defense-in-depth guard retained)**
* **Context**: `_map_direct_url` in DMM previously constructed launch steps without an explicit `parameters["app_name"]`, causing backend token fallback. In addition, `_understand_goal` contained dead `"goal" in locals()` control flow.
* **Current Implementation**:
  1. Source-level fix applied in `_map_direct_url` to explicitly set `parameters={"app_name": "browser", "operation": "launch_default_browser"}`.
  2. Added `"browser": "chrome"` and `"web browser": "chrome"` to `_APP_ALIASES`.
  3. Cleaned `_understand_goal` to return `(text, modifiers)` directly.
  4. Retained the defense-in-depth token filter in `desktop_backend.py` as a safety guard.

---

## 3. `ExecutionStatus` vs `ExecutionResult` Data Contract Coexistence
* **Location**: [`src/desktop/native/`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/), [`src/core/capabilities/models.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/capabilities/models.py)
* **Status**: **ACTIVE DEBT**
* **Context**: Native desktop managers return `NativeResult` / `ExecutionStatus` structures from earlier implementation phases, whereas core orchestration and adapters consume canonical `ExecutionResult` / `ActionResult`.
* **Remediation Plan**:
  1. Standardize desktop native manager return types on `ExecutionResult`.
  2. Deprecate `ExecutionStatus` enum in favor of canonical `PlanValidationResult` and `ExecutionResult` statuses.

---

## 4. Milestone 25 PlanDAG $\to$ TaskGraph Compiler
* **Location**: [`src/experts/`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/experts/), [`src/core/orchestration/task_decomposer.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/task_decomposer.py)
* **Status**: **DEFERRED (Manual DAG construction in place for tests)**
* **Context**: Milestone 25 Domain Experts produce structured `PlanDAG` reasoning graphs, whereas `MasterOrchestrator` executes `TaskGraph` / `SubTask` dependency trees.
* **Remediation Plan**:
  1. Build an automated `PlanDAGCompiler` to translate `PlanNode` and `PlanDAG` into `TaskGraph` subtasks with verified `input_artifacts` and `output_artifacts` dependency bindings.

---

## 5. Multi-Intent / Compound Goal Decomposition in DMM
* **Location**: [`src/brain/executive/dmm.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/brain/executive/dmm.py)
* **Status**: **ACTIVE ARCHITECTURAL GAP**
* **Context**: DMM evaluates modifier flags via a waterfall `if-elif` chain in `_build_execution_map`. For compound goals containing multiple actions (e.g. `"open notepad and write hello world"`), the first matching branch (app launch) consumes the request and produces launch/verify steps, silently dropping downstream intents (e.g. typing text).
* **Remediation Plan**:
  1. Implement multi-intent segmentation in `DMM._understand_goal` to extract sequential intent clauses.
  2. Update `_build_execution_map` to assemble composite execution plans linking multiple intent steps (e.g., Launch App $\to$ Focus Window $\to$ Type Text).

---

## 6. `PersonalOSRuntime` Orphaned Execution Loop & Container Retirement
* **Location**: [`src/core/orchestration/personal_os_runtime.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/personal_os_runtime.py), [`core/aura_core.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/core/aura_core.py), [`clients/cli_client.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/clients/cli_client.py)
* **Status**: **ORPHANED HARNESS (Candidate for Retirement)**
* **Context**: Production user requests route through `AuraCore` $\to$ `ACABrain` $\to$ `MasterOrchestrator`. Reachability verification confirmed zero production calls to `PersonalOSRuntime.execute_goal()`. Currently, `PersonalOSRuntime` serves only as a container holding singleton references to `memory_manager` and `voice_loop` (used by `clients/cli_client.py`), and as a harness for Milestone 26 test scripts.
* **Remediation Plan**:
  1. Migrate `voice_loop` and `memory_manager` lifecycle ownership directly onto `AuraCore` (e.g. `aura_core.voice_loop`, `aura_core.memory_manager`).
  2. Update `clients/cli_client.py` (`voice on` / `voice off`) to interact directly with `aura_core.voice_loop`.
  3. Port valuable multi-turn / app-launch scenarios from `test_personal_os_runtime.py` to `MasterOrchestrator` regression suites.
  4. Deprecate and delete `PersonalOSRuntime` and its standalone un-orchestrated execution loop.

