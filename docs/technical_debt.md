# Technical Debt & Architecture Remediation Registry

This document tracks identified architectural debt, interim compatibility shims, and scheduled remediation tasks.

---

## 1. `EventRuntime` Dual-API & Legacy Trigger Compatibility Shim
* **Location**: [`src/autonomy/event_runtime.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/autonomy/event_runtime.py)
* **Status**: **ACTIVE DEBT (Compatibility Shim)**
* **Context**: `EventRuntime` was rewritten in Milestone 24 Phase 2 as the single-choke-point telemetry ingest engine (`ingest(AuraEvent)` $\to$ `DeduplicationEngine` $\to$ `CorrelationEngine` $\to$ `EventInterpreter`). However, earlier subsystems (`PersonalOSRuntime`) and unit tests (`tests/unit/test_event_runtime.py`) expect an older constructor accepting `registry`, `coordinator`, `policy`, and invoking `emit_event()`.
* **Current Implementation**: A compatibility shim exists in `EventRuntime` exposing `emit_event()`, `_scheduler_loop()`, and `_execute_trigger_task()` alongside the canonical `ingest()` method.
* **Remediation Plan**:
  1. Extract trigger evaluation into a dedicated `TriggerScheduler` or `TriggerLifecycleManager` daemon.
  2. Migrate `PersonalOSRuntime` to instantiate the dedicated scheduler and interact with `EventRuntime` solely via canonical `ingest(AuraEvent)` records.
  3. Refactor `tests/unit/test_event_runtime.py` to target `TriggerScheduler` directly, restoring `EventRuntime` to pure telemetry ingestion without execution logic.

---

## 2. Desktop Application Name Resolution & Parameter Propagation
* **Location**: [`src/core/orchestration/personal_os_runtime.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/personal_os_runtime.py), [`src/core/backends/adapters/desktop_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/desktop_backend.py), [`src/brain/executive/dmm.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/brain/executive/dmm.py)
* **Status**: **STOPGAP IN PLACE (Source-level fix pending)**
* **Context**: When `DecisionMakingModule` or `PersonalOSRuntime._step_to_action` translates abstract user goals (e.g. `"open notepad and write hello world"`), the resulting step parameter dictionary sometimes omits an explicit `parameters["app_name"]` or defaults to the action verb (`"open_app"`).
* **Current Implementation**: A defense-in-depth token filter in `desktop_backend.py` intercepts generic verb strings (`"open_app"`, `"app_open"`, `"launch"`, `"application"`) and extracts application candidates from the raw goal.
* **Remediation Plan**:
  1. Update `PersonalOSRuntime._step_to_action` and `DMM._understand_goal` to explicitly extract and populate `parameters["app_name"] = app_entity` at plan generation time.
  2. Retain the `desktop_backend.py` guard purely as a secondary defensive fallback.

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
