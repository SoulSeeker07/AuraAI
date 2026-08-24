# AuraAI — Canonical Runtime Wiring

> **The single source of truth for what actually executes when a user sends a message.**
> Last updated: August 2026 — Foundation Wiring & Truth Pass

---

## The Active Request Path

This is the **only path** that runs in production. Every other subsystem is either
a provider to this path, a future integration, or classified separately below.

```text
User Input (CLI / GUI / Voice)
           │
           ▼
    AuraCore.process_request()
           │
           ▼
    MasterOrchestrator.process_request_async()
           │
           │
  ┌────────┴─────────────────────────────────────────────────┐
  │                  7-STAGE PIPELINE                         │
  │                                                           │
  │  Stage 1: Memory Recall                                   │
  │      └─ Memory.py (SQLite, key-value facts)               │
  │                                                           │
  │  Stage 2: Decision Engine                                 │
  │      └─ IntentType classification (keyword-heuristic)     │
  │                                                           │
  │  Stage 3: Task Decomposition                              │
  │      └─ TaskDecomposer → TaskGraph DAG (heuristic)        │
  │                                                           │
  │  Stage 4: Supervisor Delegation                           │
  │      └─ SupervisorAgent → PlannerRegistry                 │
  │                                                           │
  │  Stage 5: Backend Dispatch                                │
  │      └─ BackendRegistry.select_best_backend(capability)   │
  │                                                           │
  │  Stage 6: Result Fusion                                   │
  │      └─ ResultMerger                                      │
  │                                                           │
  │  Stage 7: Memory Write                                    │
  │      └─ Memory.extract_facts() → Memory.upsert_fact()     │
  └───────────────────────────────────────────────────────────┘
           │
           ▼
    ExecutionResult → Response
```

---

## Active Backends (BackendRegistry)

These backends are registered at startup and serve live requests:

| Backend | Capabilities | Status | Quality |
|:---|:---|:---|:---|
| `DesktopEngineBackend` | `desktop`, `desktop_control`, `app_open/close`, `window.*`, `app.launch` | ✅ ACTIVE | Production-quality Win32 integration |
| `DefaultNativeDesktopAdapter` | `desktop`, `chat`, `system_info` | ✅ ACTIVE | Routes to DesktopEngineBackend |
| `InputBackendAdapter` | `input.*`, `keyboard`, `mouse`, `click`, `type`, `hotkey` | ✅ ACTIVE | Win32 SendInput synthetic input simulation |
| `TerminalBackendAdapter` | `terminal.*`, `shell`, `run_command`, `command` | ✅ ACTIVE | PowerShell execution & session management |
| `ScreenActionBackendAdapter` | `screen_action`, `screen.*`, `computer_use` | ✅ ACTIVE | Closed-loop vision grounding & action |
| `NotificationBackendAdapter` | `notification.*`, `notify.*`, `toast`, `alert`, `reminder` | ✅ ACTIVE | Windows toast, dialogs, audio cues |
| `SchedulerBackendAdapter` | `scheduler.*`, `schedule`, `cron`, `timer` | ✅ ACTIVE | Timers, intervals, and cron automation |
| `EmailBackendAdapter` | `email.*`, `mail`, `send_email` | ✅ ACTIVE | IMAP/SMTP email automation |
| `CalendarBackendAdapter` | `calendar.*`, `tasks.*`, `event`, `todo` | ✅ ACTIVE | SQLite event and task manager |
| `OfficeBackendAdapter` | `office.*`, `document`, `spreadsheet`, `word`, `excel` | ✅ ACTIVE | Office document generation & printing |
| `DockerBackendAdapter` | `docker.*`, `container`, `compose` | ✅ ACTIVE | Docker container lifecycle automation |
| `MCPBackendAdapter` | `mcp.*`, `tool_server` | ✅ ACTIVE | Model Context Protocol client |
| `SettingsBackendAdapter` | `settings.*`, `dark_mode`, `wallpaper` | ✅ ACTIVE | Windows personalization & startup apps |
| `SoftwareBackendAdapter` | `software.*`, `pip.*`, `npm.*`, `install` | ✅ ACTIVE | Winget, pip, npm package management |
| `SecurityBackendAdapter` | `security.*`, `privacy.*`, `firewall`, `vpn` | ✅ ACTIVE | Defender, Firewall, temp cleanup |
| `CodingBackendAdapter` | `coding`, `code.analyze`, `code.edit`, `code.report` | ✅ ACTIVE | Routes to EngineeringManager (Foundation Pass) |
| `MemoryBackend` | `memory_read`, `memory_write`, `memory.read`, `memory.write` | ✅ ACTIVE | SQLite fact store |
| `DefaultGeminiResearchAdapter` | `research`, `knowledge.query`, `summarize` | ⚠️ SCAFFOLDED | Stub responses in default path |
| `PlaywrightBrowserAdapter` | `browser.*`, `shopping.*` | ✅ ACTIVE | Playwright DOM & browser engine |

---

## Coding Backend — Current Behavior (Post Foundation Pass)

The coding backend (`CodingBackendAdapter`) routes through `src/engineering/EngineeringManager` and `AntigravityCodingBridge` with live World Model perception.

**What it does (M20 Complete):**
```text
code.generate → Antigravity (agy plan) with Groq fallback + Live IDE/World Context + WorkspacePolicy
code.analyze  → EngineeringManager.understand_code() / analyze_repository() (AST)
code.edit     → EngineeringManager.code_editor.edit_file() (with backup + rollback)
code.debug    → Antigravity workspace diagnosis + targeted BugRepair loop
code.report   → EngineeringManager.get_quality_report()
```

**Context Perception:**
- Injects live `Active Editor File` parsed fail-closed from visible editor windows (Antigravity IDE / VS Code) via `WorkspaceProvider` and `EditorTracker`.
- Injects live git status, project root, and targeted symbol resolution from `WorldModel`.

**Contract:** Never returns `success=True` unless a file was inspected, generated, modified, or a real verified analysis was returned. Strict `WorkspacePolicy.authorize_write()` gate enforced on all file mutations.

---

## Milestone Status Definitions

- **COMPLETE**: Implemented, connected to the intended live path, and covered by integration/regression verification.
- **SCAFFOLDED**: Substantial implementation exists, but production live-path integration or verification is incomplete.
- **PENDING**: Not yet implemented to the milestone's acceptance criteria.

---

## Module Lifecycle Classification

```text
ACTIVE       — On the live request path. Used in production every request.
SCAFFOLDED   — Code complete. Not wired to live path. Ready to connect.
LEGACY       — Superseded by newer architecture. Kept for reference.
DISCONNECTED — Real code. Not connected. A future milestone will reconnect it.
DEPRECATED   — Will be removed.
```

| Module | File(s) | Classification | Notes |
|:---|:---|:---|:---|
| `MasterOrchestrator` | `src/core/orchestration/master_orchestrator.py` | **ACTIVE** | Pipeline entry point |
| `AgentSession` | `src/core/orchestration/agent_session.py` | **ACTIVE** | Created per request |
| `DecisionEngine` | `src/core/orchestration/decision_engine.py` | **ACTIVE** | Stage 2 |
| `TaskDecomposer` | `src/core/orchestration/task_decomposer.py` | **ACTIVE** | Heuristic DAG |
| `SupervisorAgent` | `src/core/orchestration/supervisor_agent.py` | **ACTIVE** | Stage 4 |
| `BackendRegistry` | `src/core/backends/backend_registry.py` | **ACTIVE** | Backend dispatch |
| `DesktopEngineBackend` | `src/core/backends/adapters/desktop_backend.py` | **ACTIVE** | Win32, production-quality |
| `MemoryBackend` | `src/core/backends/adapters/memory_backend.py` | **ACTIVE** | SQLite facts |
| `Memory` | `Memory.py` | **ACTIVE** | Foundation fact store |
| `PromptBuilder` / Identity | `src/core/system/prompt_builder.py` | **ACTIVE** | Loaded at startup |
| `EventBus` | `src/core/event_bus.py` | **ACTIVE** | Sync pub/sub (47 lines) |
| `CodingBackendAdapter` | `src/core/backends/adapters/antigravity_backend.py` | **ACTIVE** | Routes to EngineeringManager |
| `EngineeringManager` | `src/engineering/engineering_manager.py` | **ACTIVE** | Called by CodingBackend |
| `CodeEditor` | `src/engineering/code_editor.py` | **ACTIVE** | Called by CodingBackend |
| `ASTManager` | `src/engineering/ast_manager.py` | **ACTIVE** | Called by CodingBackend |
| `CognitiveMemoryEngine` | `src/memory/cognitive_memory.py` | **ACTIVE** | M17 — 8 typed memory stores, recall, decay, consolidation. |
| `CapabilityRegistry` | `src/core/capabilities/capability_registry.py` | **ACTIVE** | M19 — 5 providers, DAG validation, ActionRisk governance. |
| `WorldModel` | `src/brain/world_model.py` | **ACTIVE** | M18 — Multi-provider world model with incremental updates. |
| `AntigravityCodingBridge` | `src/engineering/antigravity_bridge.py` | **ACTIVE** | M20 — Code generation via agy CLI with WorkspacePolicy gate. |
| `ResearchEngine` | `src/research/research_engine.py` | **ACTIVE** | M21 — Live retrieval, evidence grounding, citation preservation, zero-refetch recall, network security. |
| `VoiceManager` / `VoiceEngineBackend` | `src/voice/voice_manager.py`, `src/core/backends/adapters/voice_backend.py` | **ACTIVE** | M22 — Live STT/TTS pipeline, circuit breaker, Google/Whisper/Vosk fallback, DevicePrivacyEngine gating. |
| `VisionManager` / `VisionEngineBackend` | `src/vision/vision_manager.py`, `src/core/backends/adapters/vision_backend.py` | **ACTIVE** | M22 — Screen capture, OCR, UI grounding coordinates, sensitive-window default-BLOCK. |
| `DevicePrivacyEngine` | `src/desktop/native/security/device_privacy.py` | **ACTIVE** | M22 — Pre-acquisition permission gating for mic, screen, and camera; fail-closed enforcement. |
| `DaemonRuntime` / `DaemonEngineBackend` | `src/daemon/daemon_runtime.py`, `src/core/backends/adapters/daemon_backend.py` | **ACTIVE** | M23 — Bounded worker pool, scheduler loop, durable states, cancellation, crash recovery. |
| `AutonomyGovernanceEngine` | `src/daemon/governance.py` | **ACTIVE** | M23 — Parameter-bound, time-bound cryptographic HMAC authorization tokens & risk tiers. |
| `DaemonStateStore` | `src/daemon/state_store.py` | **ACTIVE** | M23 — SQLite persistence for jobs, idempotency claims, and crash recovery (RECOVERY_REQUIRED). |
| `PlaywrightBrowserAdapter` | `src/core/backends/adapters/browser_backend.py` | **ACTIVE** | Playwright DOM & browser engine. Capability contracts scaffolded. |
| `WorkflowEngine` | `src/workflows/workflow_engine.py` | **DISCONNECTED** | Instantiated at startup via `core/aura_core.py` with `agent_runtime=None`. `WorkflowEngineAdapter` in `src/brain/aca/engine_adapters.py` is a stub (hardcoded success, `self._engine` unused). `src/workflows/` not reconnected as part of M24. |
| `AgentRuntime` | `src/agents/agent_runtime.py` | **LEGACY** | Superseded by MasterOrchestrator pipeline. Not on live path. |
| `ReflectionEngine` | `src/brain/executive/reflection.py` | **DISCONNECTED** | Rule-based recovery patterns. Not connected to live result handling. |
| `LearningEngine` | `src/brain/executive/learning.py` | **DISCONNECTED** | LearnedItem objects created but not persisted to SQLite. |
| `MultiAgent collaboration` | `src/agents/collaboration.py` | **DISCONNECTED** | Not called from live path. |
| `EventRuntime` / `EventInterpreter` / `AutonomyPolicyGate` / `TriggerScheduler` / Watchers | `src/autonomy/` | **ACTIVE** | M24 — AuraEvent contract, ingest/dedup/correlate/dispatch pipeline, AutonomyPolicyGate (ALLOWED/RATE_LIMITED/APPROVAL_REQUIRED/BLOCKED), immutable causal trace chain (event_id → correlation_id → assessment_id → policy_decision_id → plan_id → execution_id → observation_id). |
| `ExpertDomainRouter` / `SecurityExpert` / `NetworkExpert` / `FinancialExpert` / `SoftwareExpert` / `PlanDAGCompiler` | `src/experts/` | **ACTIVE** | M25 — 4 domain experts + router + compiler. Opt-in via `expert_routing_enabled=True` in MasterOrchestrator (Stage 2.9). Confidence-ranked routing with ≥0.50 threshold, graceful fallback to general planner. |

---

## What ReasoningEngine and TaskDecomposer Actually Do

These are frequently misunderstood as AI-driven. They are heuristic.

**`ReasoningEngine.analyze()`** — keyword matching:
```python
should_search = any(w in goal_lower for w in ["research", "search", ...])
should_parallel = any(w in goal_lower for w in ["and", ",", "while", ...])
```

**`TaskDecomposer.decompose()`** — keyword-based DAG:
- Detects multi-clause goals via string matching
- Assigns `PlannerRole` based on keywords ("code" → CODING, "search" → RESEARCH)
- Does NOT use an LLM for task decomposition

Both now have access to Memory + World Model context (M17/M18 complete), but the core decomposition logic remains heuristic.

---

## Memory System (M17 Complete)

The `Memory.py` facade wraps `CognitiveMemoryEngine` which provides:

**Foundation (always active):**
- Store `(category, key, value)` facts in SQLite
- Extract facts from conversation text via regex patterns
- Recall facts by category or keyword search
- Inject recalled facts into Stage 1 of the pipeline

**Cognitive Memory (M17 — all active):**
- 8 typed memory stores: Working, Short-Term, Long-Term, Episodic, Semantic, Procedural, Preference, Project
- Multi-factor recall scoring by importance + recency
- Decay engine for stale memory retention
- Consolidation engine for duplicate merging
- Project-scoped memory isolation per project root path

---

## World Model (M18 Complete)

`src/brain/world_model.py` — multi-provider environment model.

**Provider slots (10 defined, active providers wired):**
```text
DesktopProvider        — active windows, screen state
RepositoryProvider     — git repos, branches, commits, diffs
KnowledgeGraphProvider — concepts, entities, relationships
DependencyProvider     — package and module dependencies
SymbolGraphProvider    — classes, functions, call graphs
MemoryProvider         — Cognitive Memory interface (M17)
ResearchProvider       — research results and citations
BrowserProvider        — open tabs, visited pages
NetworkProvider        — local services, ports, processes
CalendarProvider       — events, deadlines, meetings
```

**APIs:** `WorldModel.query(entity)`, `WorldModel.snapshot()`, incremental state updates.

---

## Security Subsystem & Cryptographic Authorization (Phases 1–4 Complete)

`src/desktop/native/security/` — full kernel, network, and cryptographic security boundary.

**Components:**
```text
CryptographicApprovalAuthority — Central process authorization with HMAC-SHA256 parameter-bound tickets
NetworkPolicyEngine            — 3-tier egress policy, hop-by-hop redirect verification & DNS rebinding checks
WindowsEventAuditSink          — OS-managed Windows Event Log sink emitting canonical 11-field audit stream
AuditWriterService             — Dedicated out-of-process worker maintaining monotonic sequence and hash-chain authority
DPAPIKeyManager                — Windows DPAPI master secret encryption at rest + HKDF-SHA256 process key derivation
```

**Boundary Invariants:**
1. All host-context package managers (`pip`, `npm`, `winget`) enforce strict registry pinning and environment variable isolation.
2. Production audit submission operates on a fail-closed policy (`allow_embedded_fallback=False`), barring silent downgrades to unverified local files.
3. Full 9-module test suite passes 150/150 tests.

---

## Guardrail Rules (from ARCHITECTURE.md)

1. All user requests enter via `AuraCore.process_request()` — single entry point
2. No domain backend (`src/desktop`, `src/browser`, `src/research`, `src/engineering`) may import from `src.brain.aca`
3. Only `ExecutionCoordinator` invokes execution engines via `EngineRegistry` & `EngineAdapters`
4. All ACA stages read/write through `Blackboard` (`CognitiveState`)

---

## What to Read Next

- [`roadmap.md`](roadmap.md) — milestone plan and dependency chain
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — layer contracts and ACA pipeline diagram
- [`SYSTEM_CLASSIFICATION.md`](SYSTEM_CLASSIFICATION.md) — full module classification index

---

*Last Updated: August 20, 2026*
