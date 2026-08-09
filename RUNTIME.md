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
| `CodingBackendAdapter` | `coding`, `code.analyze`, `code.edit`, `code.report` | ✅ ACTIVE | Routes to EngineeringManager (Foundation Pass) |
| `MemoryBackend` | `memory_read`, `memory_write`, `memory.read`, `memory.write` | ✅ ACTIVE | SQLite fact store |
| `DefaultGeminiResearchAdapter` | `research`, `knowledge.query`, `summarize` | ⚠️ SCAFFOLDED | Stub responses in default path |
| `PlaywrightBrowserAdapter` | browser capabilities | ⚠️ SCAFFOLDED | Code exists, Playwright setup required |

---

## Coding Backend — Current Behavior (Post Foundation Pass)

The coding backend (`CodingBackendAdapter`) now routes to `src/engineering/EngineeringManager`.

**What it does:**
```text
code.analyze → EngineeringManager.understand_code() / analyze_repository()
code.edit    → EngineeringManager.code_editor.edit_file() (with backup + rollback)
code.report  → EngineeringManager.get_quality_report()
```

**What it does NOT do (deferred to M20):**
```text
LLM-guided code generation
"Write me a function that..."  → returns honest NOT_IMPLEMENTED
```

**Contract:** Never returns `success=True` unless a file was inspected, modified, or a real analysis was returned.

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
| `ResearchEngine` | `src/research/research_engine.py` | **SCAFFOLDED** | Real code. Not on pipeline path. |
| `VoiceManager` | `src/voice/voice_manager.py` | **SCAFFOLDED** | Infrastructure built. Runtime reliability unverified. |
| `PlaywrightBrowserAdapter` | `src/core/backends/adapters/browser_backend.py` | **SCAFFOLDED** | Playwright setup required. |
| `WorldModel` | `src/brain/world_model.py` | **SCAFFOLDED** | Desktop context snapshot. Will become WorldStateProvider in M18. |
| `WorkflowEngine` | `src/workflows/workflow_engine.py` | **DISCONNECTED** | Real framework. No active workflows. Will reconnect at M24. |
| `AgentRuntime` | `src/agents/agent_runtime.py` | **LEGACY** | Superseded by MasterOrchestrator pipeline. Not on live path. |
| `ReflectionEngine` | `src/brain/executive/reflection.py` | **DISCONNECTED** | Rule-based recovery patterns. Not connected to live result handling. |
| `LearningEngine` | `src/brain/executive/learning.py` | **DISCONNECTED** | LearnedItem objects created but not persisted to SQLite. |
| `MultiAgent collaboration` | `src/agents/collaboration.py` | **DISCONNECTED** | Not called from live path. |
| `CapabilityRegistry` | — | **MISSING** | M19 deliverable. Does not exist yet. |
| `MCP Client` | — | **MISSING** | M23 deliverable. |
| `Event Runtime` | — | **MISSING** | M24 deliverable. |
| `Expert Systems` | — | **MISSING** | M25 deliverable. |

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

Both will be replaced / augmented with Memory + World Model context in M17/M18.

---

## What Memory Does and Does Not Do

**Does:**
- Store `(category, key, value)` facts in SQLite
- Extract facts from conversation text via regex patterns
- Recall facts by category or keyword search
- Inject recalled facts into Stage 1 of the pipeline

**Does NOT:**
- Distinguish Working / Short-Term / Long-Term / Episodic / Semantic memory types
- Score memories by importance or recency
- Apply decay to stale memories
- Consolidate duplicate memories
- Isolate memory per project

M17 (Cognitive Memory) builds on this SQLite foundation to add all of the above.

---

## World Model Current State

`src/brain/world_model.py` — 177 lines.

**Currently tracks:**
```python
focused_window    # active OS window title
focused_pid       # process ID
applications      # running process list (up to 20)
git_branch        # current branch via subprocess("git branch --show-current")
is_live           # whether snapshot_provider is active
```

This is a **desktop context snapshot** (essentially M04 Workspace Awareness).
It becomes `WorldStateProvider` — the first provider — when M18 (World Model) is built.

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

*Generated: August 2026 — Foundation Wiring & Truth Pass*
