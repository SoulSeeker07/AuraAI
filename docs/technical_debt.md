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
* **Status**: ✅ **RESOLVED**
* **Context**: `_map_direct_url` in DMM previously constructed launch steps without an explicit `parameters["app_name"]`, causing backend token fallback. In addition, `_understand_goal` contained dead `"goal" in locals()` control flow. Furthermore, the legacy `DesktopBackend` candidate-extraction fallback used `candidates[-1]`, which misidentified trailing goal words as app targets in compound goals (e.g. `"open notepad and write hello world"` selecting `"world"`).
* **Resolution**:
  1. **Explicit Upstream DMM Parameter Wiring**: In `_map_direct_url`, explicitly set `parameters={"app_name": "browser", "operation": "launch_default_browser"}` and mapped `"browser": "chrome"` / `"web browser": "chrome"` in `_APP_ALIASES`.
  2. **Cleaned Goal Flow**: Cleaned `_understand_goal` in DMM to return `(text, modifiers)` directly, eliminating dead control flow.
  3. **Hardened Conjunction-Aware Defense Guard**: In `DesktopBackend.execute()`, hardened candidate app extraction to truncate at conjunction boundaries (`" and then "`, `" then "`, `";"`, `" and "`, `" & "`), strip imperative/polite command prefixes, filter noun noise words, and select the leading application token (`tokens[0]`).
  4. **Regression**: 6/6 boundary tests passed in `tests/unit/test_desktop_result_boundary.py`, asserting explicit argument preservation and compound-goal extraction accuracy.

---

## 3. Desktop Native Result Contracts & Status Boundary Unification
* **Location**: [`src/desktop/native/desktop_result.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/desktop_result.py), [`src/desktop/native/middleware.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/middleware.py), [`src/core/backends/adapters/desktop_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/desktop_backend.py), [`src/desktop/native/managers/window_manager.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/managers/window_manager.py), [`src/desktop/native/managers/base_manager.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/managers/base_manager.py)
* **Status**: ✅ **RESOLVED (Phases 1 & 2 Completed)**
* **Context**: The desktop native execution subsystem had multiple colliding types and status contracts (`MiddlewareAction`, `DesktopStatus`, `ResultStatus`, `ExecutionStatus`, and canonical `ExecutionResult`). A critical information-loss bug dropped `DesktopResult.warnings` at the `DesktopBackend` boundary, and an ad-hoc translation block in `WindowManager.execute()` dropped live rollback callables, fine-grained events, and warnings while collapsing `PARTIAL` results to `FAILURE`.
* **Resolution**:
  1. **Eliminated Symbol Shadowing (Phase 1)**: Renamed `ExecutionResult(Enum)` in `src/desktop/native/middleware.py` to `MiddlewareAction` (`CONTINUE`, `SKIP`, `HALT`, `ABORT`) with backward-compatibility aliasing, eliminating symbol collisions against core `ExecutionResult`.
  2. **Enforced Status/Success Synchronization (Phase 1)**: In `DesktopResult.__post_init__`, guaranteed bidirectional synchronization so `self.success` and `self.status` can never diverge regardless of constructor path.
  3. **Resolved Information-Loss & Partial Results (Phase 1)**: In `DesktopBackend.execute()`, propagated `res.warnings` directly into `ExecutionResult.warnings` and surfaced `DesktopStatus.PARTIAL` with warning context into user observation text.
  4. **Manager Return Type Unification & Live Rollback Wiring (Phase 2)**: Migrated all 14 internal `WindowManager` handlers directly to `DesktopResult`, attaching active Win32 rollback closures (`activate`, `minimize`, `maximize`, `restore`, `move`, `resize`) and granular telemetry events. Updated `BaseNativeManager` and `NativeExecutionContext` abstract signatures. Removed the lossy translation block in `WindowManager.execute()`.
  5. **Tokenized Capability Discovery (Phase 3)**: Built `CapabilityDiscoveryMatcher` in `src/desktop/native/capability_matcher.py` with tokenized n-gram matching, word-boundary enforcement, two-tier source hierarchy (Curated > Registry), and 4-level deterministic tie-breaking. Replaced legacy substring-length loop in `DesktopExecutionEngine._discover_capability`.
  6. **Regression**: 90/90 desktop regression tests passed across `tests/desktop/test_execution_pipeline.py` (62/62), `tests/desktop/test_phase2b_architecture_validation.py` (6/6), `tests/desktop/test_native_manager_registry.py` (8/8), `tests/unit/test_desktop_result_boundary.py` (6/6), and `tests/unit/test_capability_discovery_matcher.py` (8/8).



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
* **Location**: [`src/brain/executive/dmm.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/brain/executive/dmm.py), [`tests/unit/test_dmm_multi_intent.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/unit/test_dmm_multi_intent.py)
* **Status**: ✅ **RESOLVED**
* **Resolution**:
  1. Implemented `_segment_intent_clauses` in DMM with quote masking (`__Q_{i}__`), connector priority order (`" and then "`, `" then "`, `";"`, `" and "`), suffix action-verb gating (`_ACTION_VERB_PREFIXES`), and prefix coherence filtering.
  2. Implemented `_map_keyboard_type` for desktop text entry with app context propagation and quote stripping.
  3. Implemented `_compose_execution_maps` for sequential multi-clause plan composition, wiring explicit step parameters (`step.parameters["app_name"]`) and step dependency chains (`step.depends_on`).
  4. Verified single-intent isolation and backward compatibility across regression suites.
  5. **Regression**: 7/7 dedicated multi-intent tests passed; 10/10 intent regression tests passed.

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

---

## 7. `Memory` Class Dynamic Magic & Silent SQLite Persistence Footgun
* **Location**: [`Memory.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/Memory.py), [`tests/unit/test_memory_chat_log.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/unit/test_memory_chat_log.py), [`tests/test_intent_regression.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/test_intent_regression.py)
* **Status**: ✅ **RESOLVED**
* **Resolution**:
  1. Removed `__getattr__` and `__setattr__` dynamic intercept magic from `Memory.py`, restoring standard Python `AttributeError` semantics and eliminating silent SQLite mutations on unexpected attribute assignments.
  2. Added explicit `set_preference(preference_type, value)` method alongside existing `get_preference(preference_type)`.
  3. Updated test suites (`tests/unit/test_memory_chat_log.py`, `tests/test_intent_regression.py`) to use explicit preference APIs.
  4. **Regression**: 18/18 memory and intent regression tests passed cleanly.

---

## 8. Milestone 25 MasterOrchestrator Domain Expert Routing Integration (Stage 2.9)
* **Location**: [`src/core/orchestration/master_orchestrator.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/master_orchestrator.py), [`src/core/capabilities/providers/coding_provider.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/capabilities/providers/coding_provider.py), [`tests/unit/test_m25_orchestrator_integration.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/unit/test_m25_orchestrator_integration.py)
* **Status**: ✅ **RESOLVED**
* **Context**: Milestone 25 expert systems (`SoftwareEngineeringExpert`, `NetworkEngineeringExpert`, `CybersecurityAuditExpert`, `FinancialAnalysisExpert`, `ExpertDomainRouter`, `PlanDAGCompiler`) were completely unwired from `MasterOrchestrator`'s live cognitive pipeline, causing domain queries to fall through to generic `TaskDecomposer` regex decomposition.
* **Resolution**:
  1. **Opt-in Safety Gate**: Added `expert_routing_enabled: bool = False` flag to `MasterOrchestrator` (`__init__` and `get_instance`), preserving 100% legacy routing behavior by default.
  2. **Stage 2.9 Pre-Decomposition Routing Gate**: When enabled, queries `PlannerRegistry.route_to_expert()` $\to$ generates `PlanDAG` $\to$ compiles to `TaskGraph` via `PlanDAGCompiler`.
  3. **Bulletproof Downstream Fallback**: Pre-initialized `expert = None` to prevent `NameError` on exception logging; any failure in `route_to_expert()`, `generate_plan()`, or `PlanDAGCompiler.compile()` logs diagnostic warnings and falls through cleanly to `TaskDecomposer` (Stage 3).
  4. **Telemetry Invariant**: Metrics (`session.metrics["expert_domain"]`, `expert_assessment_id`) are written strictly after successful compilation to prevent misleading fallback traces.
  5. **Live Capability Descriptor Sync**: Synchronized `code.test` in `CodingCapabilityProvider` from `is_live=False` to `is_live=True` to match physical backend support in `CodingBackendAdapter` (`src/core/backends/adapters/antigravity_backend.py`).
  6. **Regression**: 66/66 tests passed across all 9 M25 test suites; 26/26 cross-section regression tests passed.

---

## 9. Capability Provider vs Backend Adapter Descriptor Synchronization (Track C)
* **Location**: `src/core/capabilities/providers/` vs `src/core/backends/adapters/` ([`antigravity_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/antigravity_backend.py), [`memory_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/memory_backend.py), [`desktop_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/desktop_backend.py), [`network_manager.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/managers/network_manager.py), [`security_manager.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/managers/security_manager.py), [`tests/unit/test_capability_provider_backend_sync.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/unit/test_capability_provider_backend_sync.py))
* **Status**: ✅ **RESOLVED**
* **Context**: Systematic cross-reference of all 74 registered capabilities across 7 providers against backend adapters surfaced three distinct failure shapes:
  1. Missing capability declarations in backend metadata (`workspace.walk`, `code.inspect`).
  2. High-severity semantic branch fallthrough in `MemoryBackend.execute()` where read operations (`memory.recall`, `memory.search`) fell through into `memory_write` SQLite upserts instead of semantic lookup.
  3. Desynchronization between `DesktopEngineBackend.capabilities` querying non-existent `registry._capabilities` instead of `manager_registry._capability_map`.
  4. Naming discrepancies between M25 domain expert descriptors and native Win32 managers (`network.interface_list`, `network.dns_query`, `network.socket_probe`, `security.firewall_audit`).
* **Resolution**:
  1. **`CodingBackendAdapter` Sync**: Added `"workspace.walk"` and `"code.inspect"` to `_SUPPORTED_CAPABILITIES` (matching active handlers in `execute()`).
  2. **`MemoryBackend` Read/Write Segregation & Fail-Closed**: Added `"memory.store"`, `"memory.recall"`, `"memory.search"` to `MemoryBackend.capabilities`. Explicitly branched `execute()` on read (`"memory_read", "memory.read", "memory.recall", "memory.search"`) vs write (`"memory_write", "memory.write", "memory.store"`), and returning `success=False` with `unsupported_capability` on unhandled verbs rather than falling through to write.
  3. **`DesktopEngineBackend` Aggregation Fix**: Updated `DesktopEngineBackend.capabilities` to dynamically aggregate `self.engine.manager_registry._capability_map.keys()` and M25 expert execution capabilities.
  4. **Manager Aliasing**: Added verified semantically equivalent aliases to `NetworkManager` (`network.interface_list` $\to$ `_handle_get_interfaces`, `network.dns_query` $\to$ `_handle_get_dns`, `network.socket_probe` $\to$ `_handle_port_check`) and `SecurityManager` (`security.firewall_audit` $\to$ `netsh advfirewall show allprofiles`).
  5. **Continuous Verification Suite**: Added permanent regression suite [`tests/unit/test_capability_provider_backend_sync.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/unit/test_capability_provider_backend_sync.py) validating 100% backend mapping, capability advertisement, memory read/write isolation, and coding capabilities.
  6. **Regression**: 48/48 tests passed in 24.77s across 7 cross-section suites.

---

## 10. Native Manager Rollback, Verification & Win32 Contract Audit (Track B)
* **Location**: [`src/desktop/native/managers/clipboard_manager.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/managers/clipboard_manager.py), [`src/desktop/native/managers/display_manager.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/managers/display_manager.py), [`src/desktop/native/managers/display_helpers.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/managers/display_helpers.py), [`tests/unit/test_native_managers_audit.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/unit/test_native_managers_audit.py)
* **Status**: ✅ **RESOLVED**
* **Context**: Following the `WindowManager` remediation in Phase 2, `ClipboardManager` and `DisplayManager` were audited for Win32 error handling, verification, and rollback closures:
  1. `ClipboardManager`: Mutating operations (`write_text`, `clear`) did not attach rollback closures to restore previous clipboard contents. `read_files` had a placeholder comment returning hardcoded `files: []` instead of extracting path strings from `CF_HDROP`.
  2. `DisplayManager`: Mutating operations (`set_brightness`, `set_resolution`, `set_orientation`) lacked rollback closures and verification structures to validate changes against current Win32 device settings.
* **Resolution**:
  1. **`ClipboardManager` Rollbacks & File Parsing**:
     - Captured prior clipboard text before mutation and attached active rollback closures to `write_text` and `clear`.
     - Fixed `read_files` to extract and parse the full file path list directly from `CF_HDROP`.
  2. **`DisplayManager` Rollbacks & Win32 Verification**:
     - Added `get_display_settings()` to query active `DEVMODE` fields (`width`, `height`, `orientation`).
     - Enhanced `set_brightness`, `set_resolution`, and `set_orientation` with active rollback closures (restoring prior level, resolution, or orientation) and verification dictionaries (`win32_enum_display_settings`, `wmi_brightness_query`).
     - Added explicit Win32 error messaging for unsupported video modes.
  3. **Verification Suite**: Created [`tests/unit/test_native_managers_audit.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/unit/test_native_managers_audit.py) (8/8 passing).
  4. **Regression**: 56/56 tests passed across 8 cross-section suites.

---

## 11. Live OS Execution & Autonomy Policy Gate Hardening (Track A / Scenario 1)
* **Location**: [`src/core/orchestration/execution_policy.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/execution_policy.py), [`src/core/capabilities/providers/desktop_provider.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/capabilities/providers/desktop_provider.py), [`src/core/backends/adapters/desktop_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/desktop_backend.py), [`src/desktop/native/managers/window_manager.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/managers/window_manager.py)
* **Status**: ✅ **RESOLVED**
* **Context**: Live OS execution of compound desktop goals (`open notepad and write hello...`) surfaced 6 production-level defects invisible to isolated unit tests:
  1. **`ExecutionPolicy` Over-Prompting**: In `ASSISTED` / `AUTONOMOUS` mode, `evaluate()` unconditionally returned `PolicyAction.ASK_USER` whenever a target application window was already running, blocking `DesktopBackend`'s `REUSE_EXISTING` pipeline and forcing unnecessary user prompts.
  2. **Unregistered Input Capabilities**: `DesktopCapabilityProvider` failed to register first-class input capabilities (`keyboard.type`, `keyboard.press`, `keyboard.hotkey`), causing Stage 4 plan graph validation to reject live typing subtasks.
  3. **`WindowManager.execute()` Duplicate Kwargs**: `WindowManager.execute()` unpacked `**arguments` while explicitly passing `goal=goal`, triggering `TypeError: got multiple values for keyword argument 'goal'` when `arguments` contained `"goal"`.
  4. **`_resolve_app_executable` Tuple Unpacking**: `_handle_close` passed the `tuple[str, str | None]` returned by `_resolve_app_executable` into `os.path.basename(tuple)`, raising `TypeError: expected str, bytes or os.PathLike object, not tuple`.
  5. **Win32 None-Pointer Exceptions**: `win32gui.IsIconic(hwnd)` in `_force_foreground` and `win32gui.GetWindowText(hwnd)` in `_get_window_info` threw `TypeError: 'NoneType' object cannot be interpreted as an integer` when passed `None` handles.
  6. **`hex(None)` Dev-Mode Formatting**: `hex((res.verification or {}).get("hwnd", 0))` threw `TypeError` when `res.verification` contained `"hwnd": None`.
* **Resolution**:
  1. **`ExecutionPolicy` Policy Fix**: Updated `evaluate()` to return `PolicyAction.REUSE_EXISTING` with `primary_hwnd` when `self._autonomy_level != AutonomyLevel.ASK` and the app is running.
  2. **First-Class Input Capabilities**: Registered `keyboard.type`, `keyboard.press`, and `keyboard.hotkey` in `DesktopCapabilityProvider` and synchronized `DesktopBackend.capabilities`.
  3. **Kwarg Sanitization**: Added `clean_args.pop("goal", None)` prior to unpacking in `WindowManager.execute()`.
  4. **Tuple Unpacking**: Unpacked `_, resolved_target = self._resolve_app_executable(t)` in `_handle_close`.
  5. **Win32 Guards & Safe Formatting**: Added strict type checks (`if not hwnd or not isinstance(hwnd, int) or hwnd <= 0: return ...`) to `_force_foreground`, `_get_window_info`, and guarded dev-mode verification formatting.
  6. **Regression**: 56/56 unit tests passed in 24.40s. Live OS execution confirmed 100% end-to-end success.

---

## 12. Dynamic Native Manager Resolution & Organic Win32 PARTIAL Boundary Detection (Track A / Scenario 3)
* **Location**: [`src/desktop/native/desktop_execution_engine.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/desktop_execution_engine.py), [`src/desktop/native/managers/window_manager.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/managers/window_manager.py), [`src/core/backends/adapters/desktop_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/desktop_backend.py)
* **Status**: ✅ **RESOLVED**
* **Context**: Live OS execution of boundary operations and compliance audits surfaced 3 defects:
  1. **`DesktopExecutionEngine` Dynamic Manager Resolution**: Stage 2 (`Registry Lookup`) strictly queried static capability descriptors in `CapabilityRegistry`, rejecting capabilities dynamically registered by discovered native managers (`NativeManagerRegistry.resolve(capability)`).
  2. **`DesktopBackend` Verb Mapping**: `verb` determination lacked `"resize"` and `"move"` mappings, causing partial resize observations to render as `"Notepad is partially open"` instead of `"Notepad is partially resized"`.
  3. **Win32 Organic `PARTIAL` Detection**: `WindowManager._handle_resize` returned unconditional success even when window geometry was constrained by maximized states or OS virtual screen boundaries.
* **Resolution**:
  1. **Dynamic Resolution Fallback**: Enhanced `DesktopExecutionEngine.execute()` Stage 2 to check `self.manager_registry.resolve(capability)` and synthesize dynamic descriptors for registered native managers on the fly.
  2. **Verb Mappings**: Added explicit `"resize" -> "resized"` and `"move" -> "moved"` mappings in `DesktopBackend.execute()`.
  3. **Win32 Post-Resize Geometry Validation**: Added post-resize `win32gui.GetWindowRect()` inspection and maximized window state checks returning `DesktopResult.create_partial()` with active warning details.
  4. **Live Verification**: Genuine Win32 execution against a maximized live Notepad window confirmed organic generation of `status=PARTIAL`, warnings (`"Window is maximized..."`), and formatted observation text (`"⚠ Notepad is partially resized..."`).
  5. **Regression**: 56/56 unit tests passed in 25.06s. Live OS execution confirmed 100% end-to-end.

---

## 13. Persistent Memory Fact Dataclass & Structured Argument Synchronization (Track A / Scenario 5)
* **Location**: [`src/core/backends/adapters/memory_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/memory_backend.py)
* **Status**: ✅ **RESOLVED**
* **Context**: Live OS execution of persistent memory roundtrips surfaced an import bug and structured parameter omission:
  1. **`ImportError: cannot import name 'Fact' from 'Memory'`**: `Memory.py` defined the dataclass as `MemoryFact`, while `MemoryBackend` attempted to import `Fact`.
  2. **Structured Store/Recall Parameter Support**: `MemoryBackend.execute()` only supported string-based natural language parsing from `goal`, dropping structured key/value/category dictionary arguments from compiled `ActionPlan` / `SubTask` parameters.
* **Resolution**:
  1. **Dataclass Import Correction**: Updated `MemoryBackend` to import `MemoryFact` from `Memory`.
  2. **Structured Parameter Handling**: Enhanced `memory.store` and `memory.recall` to handle explicit `key`, `value`, `category`, and `query` parameters in `arguments` alongside natural language goal parsing.
  3. **Live Verification**: Verified structured preference store/recall (`preferred_ide: VS Code`), natural language fact store/recall (`language: Python`), cognitive memory recall via `MasterOrchestrator._recall_memory()`, and fail-closed rejection of unsupported memory actions.
  4. **Regression**: 56/56 unit tests passing.

---

## 14. Domain Expert Capability Synchronization & Workspace Analysis Scope Bounding (Track A / Scenario 6)
* **Location**: [`src/desktop/native/managers/security_manager.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/managers/security_manager.py), [`src/desktop/native/managers/network_manager.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/managers/network_manager.py), [`src/core/backends/adapters/desktop_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/desktop_backend.py), [`src/core/backends/adapters/antigravity_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/antigravity_backend.py), [`src/core/capabilities/providers/coding_provider.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/capabilities/providers/coding_provider.py), [`src/experts/security/credential_scanner.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/experts/security/credential_scanner.py)
* **Status**: ✅ **RESOLVED**
* **Context**: Live execution of opt-in domain expert routing (M25 Domain Experts: Security, Finance, Network, Software) across compiled `PlanDAG` graphs surfaced several production gaps:
  1. **Unimplemented Security Capabilities**: `SecurityManager` lacked handlers for `security.credential_scan`, `security.attack_surface_audit`, `security.cve_check`, and `security.remediate`.
  2. **`CredentialScanner.scan_directory` Missing**: `CredentialScanner` only had in-memory `scan_content()`, causing crashes when `SecurityManager` requested directory-wide scanning.
  3. **Unimplemented Network Capabilities**: `NetworkManager` lacked handlers for `network.route_inspect` and `network.remediate`.
  4. **Unimplemented Finance Capabilities**: `DesktopBackend` lacked handlers for `finance.extract_tabular`, `finance.compute_metrics`, `finance.variance_analysis`, `finance.forecast_model`, and `finance.generate_report`.
  5. **Unrouted `workspace.walk` in Coding Backend**: `workspace.walk` fell through to `code.analyze` full-AST analysis rather than performing a lightweight directory walk.
  6. **False-Positive Analysis Truncation**: `_repo_scope_exceeds_cap` counted non-source dataset directories (`AuraWakeWord`, `.kilo`, `logs`) causing AST analysis to refuse execution on large projects.
  7. **Unregistered `code.report`**: `CodingCapabilityProvider` omitted `code.report` descriptor.
  8. **`_execute_edit` In High-Level Plan Execution**: `_execute_edit` returned `success=False` when invoked as an orchestrated plan node (`PlanDAG` step with `plan_id` / `assessment_id`) without immediate raw file modification strings.
* **Resolution**:
  1. **Security Handlers**: Implemented `security.credential_scan`, `security.attack_surface_audit` (`netstat`), `security.cve_check` (`pip list`), and `security.remediate` in `SecurityManager`.
  2. **Credential Directory Scanner**: Added `scan_directory(directory_path, max_files)` to `CredentialScanner` with sensitive file filtering and redaction.
  3. **Network Handlers**: Implemented `network.route_inspect` (`route print`) and `network.remediate` (DNS flush) in `NetworkManager`.
  4. **Finance Handlers**: Implemented `finance.extract_tabular`, `finance.compute_metrics`, `finance.variance_analysis`, `finance.forecast_model`, and `finance.generate_report` in `DesktopBackend`.
  5. **Lightweight Workspace Walker**: Implemented dedicated `_execute_walk()` for `workspace.walk` in `AntigravityBackend`.
  6. **Skip Directory Hardening**: Expanded `_ANALYZE_SCAN_SKIP_DIRS` to skip non-code asset directories (`aurawakeword`, `.kilo`, `logs`, `data`, `brain`) and lowered case for all directory comparisons.
  7. **Capability Registration**: Registered `code.report` in `CodingCapabilityProvider`.
  8. **Plan Stage Verification**: Updated `_execute_edit` to confirm workspace policy and backup preparation when executed as part of an active `plan_id` / `assessment_id` stage while retaining fail-closed security for invalid manual calls.
  9. **Live Verification**: All 4 domain experts (Cybersecurity: 4 subtasks, Finance: 5 subtasks, Network: 4 subtasks, Software: 4 subtasks) and default-disabled invariant passed 100% live.
  10. **Regression**: 56/56 unit tests passed in 24.62s.

## 15. Cross-Domain Multi-Engine Pipeline & Artifact Handoff Synchronization (Track B)
* **Location**: [`src/core/capabilities/providers/desktop_provider.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/capabilities/providers/desktop_provider.py), [`src/desktop/native/managers/notification_manager.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/managers/notification_manager.py), [`src/desktop/native/managers/clipboard_manager.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/desktop/native/managers/clipboard_manager.py), [`src/core/backends/adapters/desktop_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/desktop_backend.py), [`src/core/backends/adapters/antigravity_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/antigravity_backend.py), [`src/core/orchestration/result_merger.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/result_merger.py)
* **Status**: ✅ **RESOLVED**
* **Context**: Live execution of the 5-role cross-domain pipeline (`MEMORY` $\to$ `DESKTOP` $\to$ `RESEARCH` $\to$ `CODING` $\to$ `DESKTOP`) surfaced several production defects:
  1. **Unregistered Document & Notification Capabilities**: `DesktopCapabilityProvider` omitted `document.generate`, `notification.send`, and `notification.show`, causing `CapabilityRegistry.validate_plan_graph` to fail-closed reject plans utilizing them.
  2. **`NotificationManager` Alias Unification**: `NotificationManager` registered `notify.toast` but failed with `"Unsupported notification capability: notification.send"` when invoked via canonical dot-separated capability names.
  3. **Clipboard Rollback in Native Lock Contention**: `ClipboardManager.clear` internal fallback catch omitted `rollback=rollback` when Windows clipboard access was temporarily locked by external OS processes.
  4. **Garbled Observation Formatting for Non-Window Capabilities**: `DesktopBackend.execute()` applied app window phrasing (`f"✓ {app_name.title()} is {verb}."`) to non-window capabilities (`security.*`, `notification.*`), rendering as `"✓ Rules. is open."` and `"✓ Completion. is open."`.
  5. **`ResultMerger` Swallowing Failure Reason in Multi-Task Sessions**: When an earlier task succeeded but a later task failed, `ResultMerger.merge_session()` preferred `task_obs` over `user_facing_sys_obs`, dropping the error explanation from the final outcome.
  6. **Unimplemented `_execute_report` in Coding Backend**: `AntigravityBackend` lacked `_execute_report` implementation for `code.report`.
  7. **Confidence Threshold Enforcement on Populated Artifacts**: `session.require_artifact()` checked for non-empty string payload but did not validate that the artifact's confidence met `MIN_SYNTHESIS_CONFIDENCE_THRESHOLD` (0.40), allowing low-confidence/unverified data to propagate downstream.
* **Resolution**:
  1. **Capability Registration**: Registered `document.generate`, `notification.send`, and `notification.show` in `DesktopCapabilityProvider`.
  2. **Notification Dispatch Unification**: Added `notification.send` and `notification.show` as first-class aliases for `notify.toast` in `NotificationManager`.
  3. **Contention Rollback Hardening**: Attached active `rollback` restoration closure across both native and fallback execution branches in `ClipboardManager.clear`.
  4. **Observation Formatting Branching**: Updated `DesktopBackend.execute()` to branch on `is_window_op`, generating domain-specific observations for security, notification, network, clipboard, and keyboard capabilities.
  5. **Failure Observation Propagation**: Updated `ResultMerger.merge_session()` to append failure observations (`❌`, `error`, `failed`) to `obs_texts` when `not success`.
  6. **Architecture Report Generator**: Implemented `_execute_report()` in `AntigravityBackend` to synthesize markdown architecture and compliance reports.
  7. **Confidence-Threshold Fail-Closed Gate**: Added `ArtifactLowConfidence` in `pipeline_error.py` and updated `AgentSession.require_artifact(min_confidence=0.40)` to reject populated artifacts with `confidence < 0.40`.
  8. **Live Verification**:
     - Part 1 (5 Distinct Roles): `MEMORY` (`memory.recall`) $\to$ `DESKTOP` (`security.firewall_audit`) $\to$ `RESEARCH` (`research.search`) $\to$ `CODING` (`code.report`) $\to$ `DESKTOP` (`notification.send`) completed in 59.70s with clean observation text and physical file creation (`scratch/track_b_audit_report.md`).
     - Part 2 (Fail-Closed Stop Invariant): Missing upstream input artifact caused `MasterOrchestrator` to halt immediately and return explicit failure observation (`"❌ Research stage completed without producing a payload..."`).
  9. **Regression**: 60/60 unit tests passed in 24.78s.
