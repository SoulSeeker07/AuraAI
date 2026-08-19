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
* **Location**: [`src/experts/compiler.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/experts/compiler.py), [`src/experts/__init__.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/experts/__init__.py), [`tests/unit/test_plandag_compiler.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/unit/test_plandag_compiler.py)
* **Status**: ✅ **RESOLVED**
* **Resolution**:
  1. Implemented [`PlanDAGCompiler`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/experts/compiler.py) to translate structured `PlanDAG` reasoning graphs into executable `TaskGraph` dependency trees.
  2. Resolves domain $\to$ `PlannerRole` via universal `CapabilityRegistry.resolve_domain()`.
  3. Single-source parameter mapping: propagates `risk_level`, `timeout_seconds`, `expected_output_type`, `assessment_id`, `plan_id`, and `causal_context` directly through `subtask.parameters`.
  4. Deterministic artifact wiring: wires producer `output_artifacts = ["art_{node_id}"]` and consumer `input_artifacts = ["art_{dep}"]`.
  5. Strict fail-loud validation against cyclic dependencies, dangling node references, and unregistered capabilities.
  6. **Regression**: 124/124 tests passed across M23/M24/M25 suites.

---

## 5. Multi-Intent / Compound Goal Decomposition in DMM
* **Location**: [`src/brain/executive/dmm.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/brain/executive/dmm.py)
* **Status**: **ACTIVE ARCHITECTURAL GAP**
* **Context**: DMM evaluates modifier flags via a waterfall `if-elif` chain in `_build_execution_map`. For compound goals containing multiple actions (e.g. `"open notepad and write hello world"`), the first matching branch (app launch) consumes the request and produces launch/verify steps, silently dropping downstream intents (e.g. typing text).
* **Remediation Plan**:
  1. Implement multi-intent segmentation in `DMM._understand_goal` to extract sequential intent clauses.
  2. Update `_build_execution_map` to assemble composite execution plans linking multiple intent steps (e.g., Launch App $\to$ Focus Window $\to$ Type Text).

---

## 6. `PersonalOSRuntime` Container Retirement & Direct Ownership Migration
* **Location**: [`src/core/orchestration/personal_os_runtime.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/personal_os_runtime.py), [`core/aura_core.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/core/aura_core.py), [`clients/cli_client.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/clients/cli_client.py), [`src/brain/execution_coordinator.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/brain/execution_coordinator.py)
* **Status**: ✅ **RESOLVED**
* **Resolution**:
  1. **Direct Ownership in `AuraCore`**: Migrated `MemoryManager`, `ProviderManager`, `TriggerRegistry`, `TriggerScheduler`, `ContinuousVoiceLoop`, and `ExecutionCoordinator` to direct ownership under `AuraCore`.
  2. **Zero Split-Brain Memory**: Explicitly passed `memory_manager` into `ExecutionCoordinator` (`self.coordinator = ExecutionCoordinator(memory_manager=self.memory_manager)`), removing singleton runtime imports in `_provider_fallback()` and maintaining absolute single-source truth.
  3. **Explicit Autonomy Lifecycle**: `autonomy_enabled` defaults to `False` on `AuraCore`. Subsystem is explicitly managed via `AuraCore.start_autonomy()`, `AuraCore.stop_autonomy(drain_timeout)`, and `AuraCore.autonomy_active`.
  4. **CLI Integration**: Replaced legacy runtime voice loop access in `clients/cli_client.py` with `self.aura_core.voice_loop`, and exposed explicit `autonomy on`, `autonomy off`, and `autonomy status` commands.
  5. **Container Retirement & File Deletion**: Completely removed `PersonalOSRuntime` (`src/core/orchestration/personal_os_runtime.py`) and purged legacy container tests (`tests/unit/test_personal_os_runtime.py`, `tests/integration/test_personal_os_runtime_e2e.py`).
  6. **End-to-End Test Porting**: Ported multi-turn memory integration tests (`tests/memory/test_integration_voice_memory.py`, `tests/integration/test_e2e_cli_regression.py`, and `tests/test_continuous_loop_level2.py`) to run directly through `AuraCore` and `Memory`.
  7. **Regression Suite**: Added comprehensive test suite [`tests/unit/test_auracore_autonomy.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/unit/test_auracore_autonomy.py) and verified wiring in [`tests/memory/test_auracore_brain_init_wiring.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/memory/test_auracore_brain_init_wiring.py). All 50/50 regression tests passed.

