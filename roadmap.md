# AuraAI — Master Roadmap

> **Build Aura's shared intelligence first → then capabilities → then autonomy → then OS → then human interaction.**

---

## Roadmap Rule

> A milestone is considered **COMPLETE** only when its implementation, integration, tests, documentation,
> and acceptance criteria are all satisfied. Percentage completion is not used.
> Dependencies indicate required architecture, not necessarily a strict serial implementation order.
> Independent sub-work may proceed in parallel where noted.

---

## Status Definitions

| Status | Meaning |
| :--- | :--- |
| `COMPLETE` | Implementation + Tests + Integration + Documentation + Acceptance criteria all satisfied |
| `IN PROGRESS` | Active development. Some acceptance criteria remain incomplete |
| `READY` | All dependencies satisfied. Implementation can begin immediately |
| `PLANNED` | Dependencies not yet complete. Scheduled but not yet started |
| `BLOCKED` | Cannot proceed until a named dependency is resolved |
| `DEFERRED` | Intentionally postponed. Not currently on the critical path |

---

## Critical Path — Parallel Execution Model

```text
                        M17
                  Cognitive Memory
                        │
          ┌─────────────┴─────────────┐
          │                           │
          ▼                           ▼
    Memory Providers            M18 World Model
    (M17 deliverable)          (Workspace · Repo · Graph)
          │                           │
          └─────────────┬─────────────┘
                        │
                        ▼
                       M19
                Capability & Tool Runtime
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
         M20           M21           M22
       Coding        Research      Browser
          │             │             │
          └─────────────┼─────────────┘
                        │
                        ▼
                       M23
                  MCP Ecosystem
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
         M24           M25           M26
       Events        Experts      Personal OS
          │             │             │
          └─────────────┼─────────────┘
                        │
                        ▼
                       M27
              Autonomous Engineering
                        │
                        ▼
                       M28
                     Aura OS
                        │
               ┌────────┴────────┐
               ▼                 ▼
              M29               M30
         Natural Interaction   Aura GUI
```

> **M17 and M18 may be developed in parallel.** M18's Workspace, Repository, and Graph providers
> do not require Cognitive Memory to be complete — only the MemoryProvider integration point does.
>
> **M24, M25, M26 may be developed in parallel** once M23 is complete, with a final integration point
> before M27 begins.

---

## Version Mapping

Milestone IDs and software version numbers are decoupled.
A milestone may ship across one or more releases.

| Milestone | Release | Phase | Status |
| :--- | :--- | :--- | :--- |
| M01-M10 | `v0.1.0`-`v0.10.0` | Phase 0 — Foundation | `COMPLETE` |
| M11–M16 | `v0.11.0`–`v0.19.0` | Phase 0 — Foundation | `COMPLETE` |
| M17 | `v0.20.0` | Phase 1 — Shared Intelligence | `COMPLETE` |
| M18 | `v0.21.0` | Phase 1 — Shared Intelligence | `IN PROGRESS` |
| M19 | `v0.22.0` | Phase 2 — Capability Foundation | `READY` |
| M20 | `v0.23.0` | Phase 3 — Intelligence Expansion | `PLANNED` |
| M21 | `v0.24.0` | Phase 3 — Intelligence Expansion | `PLANNED` |
| M22 | `v0.25.0` | Phase 3 — Intelligence Expansion | `PLANNED` |
| M23 | `v0.26.0` | Phase 4 — External Capabilities | `PLANNED` |
| M24 | `v0.27.0` | Phase 5 — Autonomy | `PLANNED` |
| M25 | `v0.28.0` | Phase 5 — Autonomy | `PLANNED` |
| M26 | `v0.29.0` | Phase 5 — Autonomy | `PLANNED` |
| M27 | `v0.30.0` | Phase 6 — Autonomous Engineering | `PLANNED` |
| M28 | `v1.0.0` | Phase 7 — Aura OS (Native Desktop Engine) | `OPERATIONAL (Foundation Live)` |
| M29 | `v1.1.0` | Phase 8 — Natural Interaction (Continuous Voice) | `OPERATIONAL (Foundation Live)` |
| M30 | `v1.2.0` | Phase 9 — Aura GUI (Command Center) | `PLANNED` |

---

---

# PHASE 0 — Foundation & Runtime Convergence
## M01–M16 · See individual statuses below

> This section is the **Foundation Evidence Index** — an auditable record of what each milestone
> built, what it solved, and what it enables. It is not a specification; it is a verification record.

> **Architectural Health (post August 2026 audit):**
> ```text
> Operational (wired, runs on live path):  ~40%
> Scaffolded (code exists, not wired):     ~45%
> Stub / minimal:                          ~10%
> Missing entirely:                         ~5%
> ```
> This reflects the state of the full system (M01–M30 scope), not Phase 0 alone.
> Phase 0 modules are largely complete; the percentage gap is in Phase 1–9 scaffolding.
> See [`RUNTIME.md`](RUNTIME.md) for the canonical live-path wiring map.

---

### M01 — Core Foundation

**Status:** `COMPLETE`

**Purpose:**
Establish the single entry point for all user requests and the runtime boot sequence.
Every subsystem depends on this layer initializing correctly.

**Implemented:**
- `aura.py` — canonical launcher and process entry point
- `main.py` — runtime initialization and dependency wiring
- `src/core/app.py` — `AuraCore` application lifecycle manager
- `src/core/config.py` — configuration loading and environment management
- `src/core/settings.py` — runtime settings and tunable parameters
- `src/core/logger.py` — structured logging foundation

**Acceptance criteria:**
- Aura starts from `python aura.py` without errors
- Configuration loads from `.env` correctly
- All core modules initialize in dependency order
- Graceful shutdown on `SIGINT`

**Enables:** M02 (Capability Router), all subsequent phases

---

### M02 — Capability Router

**Status:** `COMPLETE`

**Purpose:**
Route user requests to the correct subsystem rather than forwarding everything to an LLM.
This is the first intelligence layer — classify before executing.

**Implemented:**
- `src/routing/capability_router.py` — primary routing logic
- `src/core/router.py` — route registration and dispatch
- `src/brain/intent_router.py` — intent-based routing
- `src/brain/intent_analyzer.py` — intent classification
- `src/brain/capability_selector.py` — capability matching from intent

**Acceptance criteria:**
- Code requests route to engineering subsystem
- Research requests route to research subsystem
- Desktop requests route to desktop subsystem
- Unknown intents handled gracefully without crashes

**Depends on:** M01
**Enables:** M05 (Tool Execution Engine), M09 (Agent Runtime)

---

### M03 — Memory 2.0

**Status:** `COMPLETE — FOUNDATION ONLY`

> **Wiring audit note:** M03 implements a flat `(category, key, value)` SQLite fact store.
> It is operational and wired to the live pipeline (Stage 1 recall, Stage 7 write).
> It does **not** implement typed memory stores, scoring, decay, or consolidation.
> Those are M17 (Cognitive Memory) deliverables that build on this foundation.

**Purpose:**
Persistent intelligent memory that allows Aura to remember facts, conversations,
and user context across sessions. Foundation for all future memory work.

**Implemented:**
- `Memory.py` — top-level memory interface and session management
- `src/memory/conversations.py` — conversation history persistence
- `src/memory/database.py` — SQLite schema and connection management
- `src/memory/models.py` — memory data models
- `Memory.db` — SQLite persistent store
- `src/brain/context_manager.py` — active context tracking
- `src/brain/context_builder.py` — context assembly for LLM calls

**Acceptance criteria:**
- Facts stated by user persist across sessions
- Conversation history retrievable by session ID
- Memory does not grow unbounded (basic pruning implemented)
- Context injected into LLM prompts correctly

**Depends on:** M01
**Enables:** M17 (Cognitive Memory)

---

### M04 — Workspace Awareness

**Status:** `COMPLETE`

**Purpose:**
Continuous awareness of the user's active desktop environment, open projects,
and file system state. Aura must know where the user is working.

**Implemented:**
- `src/workspace/` — workspace management package
- `src/desktop/` — desktop state tracking
- `src/core/screen_context.py` — active screen context capture
- `src/core/live_screen.py` — live screen state monitor
- `src/core/window_manager.py` — window tracking and management

**Acceptance criteria:**
- Active application detected within 1s of focus change
- Current working directory tracked per project
- File changes in open projects detected via polling/watcher

**Depends on:** M01
**Enables:** M15 (Desktop Intelligence), M18 (World Model)

---

### M05 — Tool Execution Engine

**Status:** `COMPLETE`

**Purpose:**
Unified pipeline for executing all tools and capabilities with consistent input/output
contracts, error handling, and result formatting.

**Implemented:**
- `src/execution/` — execution engine package
- `src/agents/execution_graph.py` — execution dependency graph
- `src/agents/execution_history.py` — execution trace and history
- `src/brain/execution_coordinator.py` — cross-subsystem execution coordination
- `src/brain/execution_state.py` — execution state machine
- `src/brain/execution_map_generator.py` — dynamic execution plan generation
- `src/brain/execution_map_validator.py` — plan validation before execution

**Acceptance criteria:**
- Tool calls succeed and return typed results
- Failed tools produce structured error objects, not exceptions
- Execution history queryable per session
- Retry logic applied to transient failures

**Depends on:** M01, M02
**Enables:** M09 (Agent Runtime), M19 (Capability Registry)

---

### M06 — Plugin Ecosystem

**Status:** `COMPLETE`

**Purpose:**
Fully modular system where every capability can be packaged and registered as a plugin.
Prevents the core from growing monolithically.

**Implemented:**
- `src/core/plugin_manager.py` — plugin lifecycle management
- `src/agents/plugin_system.py` — agent-level plugin integration
- `plugins/` — plugin directory (external plugins)
- `src/core/system/` — system-level capability catalog

**Acceptance criteria:**
- New plugin registers without modifying core files
- Plugin discovered automatically at startup from `plugins/` directory
- Plugin can be enabled/disabled at runtime
- Plugin failure does not crash the core runtime

**Depends on:** M01, M05
**Enables:** M19 (Capability Registry)

---

### M07 — Vision System

**Status:** `COMPLETE`

**Purpose:**
Visual understanding capabilities — Aura can see, read, and interpret the desktop
through OCR, element detection, and screenshot analysis.

**Implemented:**
- `src/vision/` — vision system package
- `src/agents/vision/` — vision agent integration
- `src/agents/vision_agent.py` — vision-enabled agent

**Acceptance criteria:**
- Screenshot captured on demand
- Text extracted from screenshot via OCR
- UI element positions detected
- Vision output usable as context for subsequent decisions

**Depends on:** M01, M05
**Enables:** M15 (Desktop Intelligence)

---

### M08 — Voice Infrastructure

**Status:** `COMPLETE`

**Purpose:**
Core audio operating subsystem. Wake word detection, speech-to-text, text-to-speech,
microphone lifecycle management, and audio streaming bridge.
This is **infrastructure** — not a conversational system. See M29 for the interaction layer.

**Implemented:**
- `src/voice/voice_manager.py` — voice subsystem orchestrator and lifecycle
- `src/voice/stt_manager.py` — speech-to-text engine management
- `src/voice/tts_manager.py` — text-to-speech engine and audio output
- `src/voice/wake_word.py` — wake word detection and threshold management
- `src/voice/vad.py` — voice activity detection
- `src/voice/audio_manager.py` — microphone arbitration and audio pipeline
- `src/voice/interruption_manager.py` — audio interruption and barge-in primitive
- `src/voice/models.py` — voice data models
- `src/voice/providers/` — STT/TTS provider adapters
- `src/agents/voice/` — voice agent integration
- `src/agents/voice_agent.py` — voice-enabled agent

**Acceptance criteria:**
- Wake word triggers Aura within 500ms
- STT transcribes speech to text with acceptable WER
- TTS produces audio output from text
- Microphone released when not in use
- Audio pipeline does not block other subsystems

**Depends on:** M01, M05
**Enables:** M29 (Natural Interaction Layer — upgrades this foundation)

---

### M09 — Agent Runtime

**Status:** `COMPLETE — LEGACY`

> **Wiring audit note:** `AgentRuntime` was superseded by the `MasterOrchestrator` COL pipeline
> in M16. The code is real and complete, but it is not on the active request path.
> Classification: **LEGACY**. Not a candidate for expansion until architecture alignment is planned.

**Purpose:**
Goal-oriented agent framework. Agents can plan, execute multi-step tasks,
track progress, recover from failures, and operate with defined permissions.

**Implemented:**
- `src/agents/agent_runtime.py` — agent lifecycle and execution loop
- `src/agents/agent_registry.py` — agent registration and discovery
- `src/agents/agent_context.py` — per-agent context and state
- `src/agents/base_agent.py` — base agent contract
- `src/agents/planner.py` — agent-level task planning
- `src/agents/planner_agent.py` — planning-specialized agent
- `src/agents/task.py` — task model and lifecycle
- `src/agents/task_manager.py` — task queue and scheduling
- `src/agents/task_model.py` — task data model
- `src/agents/goal.py` — goal model and tracking
- `src/agents/goal_memory.py` — goal persistence
- `src/agents/permission_manager.py` — per-agent permission enforcement
- `src/agents/approval_manager.py` — human-in-the-loop approval gates
- `src/agents/safety_layer.py` — safety policy enforcement
- `src/agents/recovery_manager.py` — failure recovery strategies
- `src/agents/observability.py` — agent execution observability
- `src/agents/orchestrator.py` — multi-agent coordination
- `src/agents/routing.py` — agent-to-agent routing
- `src/agents/scheduler.py` — agent execution scheduling
- `src/agents/process_manager.py` — agent process lifecycle

**Acceptance criteria:**
- Agent can complete a multi-step task from a single natural language goal
- Failed steps trigger recovery without crashing the agent
- Agent respects permission boundaries
- Human approval gate fires correctly for high-risk actions
- Execution trace available after task completion

**Depends on:** M01, M02, M05
**Enables:** M12 (Multi-Agent Intelligence), M16 (Cognitive Orchestration)

---

### M10 — Workflow Engine

**Status:** `COMPLETE — DISCONNECTED`

> **Wiring audit note:** The `WorkflowEngine` framework is real and complete (14 modules).
> However it is not on the active request path — no active workflows exist in production,
> and the `agent_runtime` parameter in `TriggerManager` is typically `None`.
> Classification: **DISCONNECTED**. Will be reconnected at M24 (Event Runtime).

**Purpose:**
Persistent automation platform. Users define and run multi-step workflows
with triggers, conditions, loops, and variables.

**Implemented:**
- `src/workflows/workflow_engine.py` — workflow execution core
- `src/workflows/workflow_executor.py` — step-by-step workflow executor
- `src/workflows/workflow_manager.py` — workflow CRUD and lifecycle
- `src/workflows/workflow_scheduler.py` — time-based workflow scheduling
- `src/workflows/workflow_builder.py` — programmatic workflow construction
- `src/workflows/workflow_graph.py` — workflow as directed graph
- `src/workflows/workflow_history.py` — execution history and replay
- `src/workflows/workflow_step.py` — individual step model and execution
- `src/workflows/trigger_manager.py` — event and schedule trigger management
- `src/workflows/condition_engine.py` — conditional logic evaluation
- `src/workflows/loop_engine.py` — loop and iteration support
- `src/workflows/variable_manager.py` — workflow variable scoping
- `src/workflows/models.py` — workflow data models
- `src/workflows/templates/` — reusable workflow templates

**Acceptance criteria:**
- Workflow defined in code or configuration runs end-to-end
- Scheduled workflows fire at correct times
- Workflow resumes after interruption from last completed step
- Variables scoped correctly between steps

**Depends on:** M01, M05, M09
**Enables:** M22 (Event Runtime foundation), M24 (Event Runtime)

---

### M11 — Knowledge Intelligence (RAG 2.0)

**Status:** `COMPLETE`

**Purpose:**
Searchable knowledge base that understands repositories, documents, notes, and codebases.
Moves Aura beyond LLM parametric knowledge to grounded retrieval.

**Implemented:**
- `src/knowledge/` — knowledge base package
- `src/brain/knowledge_router.py` — knowledge routing and source selection
- `src/brain/aura_search_system.py` — unified search across knowledge sources
- `src/brain/search_cache.py` — search result caching
- `src/brain/source_ranker.py` — source confidence and relevance ranking
- `knowledge/` — knowledge YAML files (6 domain files)
- `src/core/system/` — CapabilityCatalog, CommandCatalog, IdentityLoader, PromptBuilder

**Acceptance criteria:**
- Repository indexed and searchable by semantic query
- Knowledge sources ranked by relevance and confidence
- Cache prevents redundant re-indexing
- Search results injected into LLM context correctly

**Depends on:** M01, M03, M05
**Enables:** M14 (Research Intelligence), M18 (World Model)

---

### M12 — Multi-Agent Intelligence

**Status:** `COMPLETE`

**Purpose:**
Specialized AI agents that collaborate to complete complex tasks.
Agents coordinate, share context, and delegate sub-tasks.

**Implemented:**
- `src/agents/collaboration.py` — inter-agent collaboration protocol
- `src/agents/integration.py` — cross-agent integration layer
- `src/agents/dependency_manager.py` — agent task dependency tracking
- `src/agents/progress_manager.py` — multi-agent progress aggregation
- `src/agents/skill_system.py` — agent skill registration and matching
- `src/agents/learning_agent.py` — learning-capable agent base
- `src/brain/brain_integration.py` — brain-level multi-agent coordination
- `src/brain/response_coordinator.py` — aggregated response coordination

**Acceptance criteria:**
- Task requiring two specialized agents completes end-to-end
- Sub-tasks delegated to correct agent by skill matching
- Agent results merged into coherent final response
- Agent failures handled without cascading to unrelated agents

**Depends on:** M09
**Enables:** M13 (Engineering Intelligence), M14 (Research Intelligence)

---

### M13 — Engineering Intelligence

**Status:** `IN PROGRESS` *(repaired in Foundation Wiring & Truth Pass)*

> **Wiring audit note (pre-pass):** The coding backend (`AntigravityBackendAdapter`) previously
> returned `success=True` with hardcoded file names on every invocation — a mock that
> contaminated execution traces, memory, and planner decisions.
>
> **Foundation Truth Pass fix:** The backend (`CodingBackendAdapter`) now routes through
> `EngineeringManager` for real analysis and file editing. It returns honest
> `success=False` for generation requests until M20 (Coding Intelligence 2.0).
> See `tests/test_coding_backend_wiring.py` for verification tests.

**Purpose:**
Software development agent with code reading, editing, AST analysis,
bug fixing, and git operations.

**Implemented (subsystem — wired to backend in Truth Pass):**
- `src/engineering/engineering_manager.py` — main orchestrator (20 sub-modules)
- `src/engineering/code_editor.py` — file editing with backup and rollback
- `src/engineering/ast_manager.py` — AST-based code analysis
- `src/engineering/bug_repair.py` — bug repair loop with validation
- `src/engineering/test_engine.py` — test execution
- `src/engineering/repository_manager.py` — repository state tracking
- `src/engineering/symbol_graph.py` — symbol and call graph
- `src/engineering/dependency_graph.py` — module dependencies
- `src/core/backends/adapters/antigravity_backend.py` — `CodingBackendAdapter` (replaces mock)
- `src/agents/coding_agent.py` — AST-based coding agent (scaffolded)

**Remaining for COMPLETE:**
- LLM-guided code generation (deferred to M20)
- Full acceptance criteria verification against real coding tasks
- Integration tests passing in CI

**Acceptance criteria (partial — Truth Pass):**
- Coding backend never returns `success=True` with hardcoded file names
- File analysis returns real AST data for a given Python file path
- File editing via `CodeEditor` with backup and rollback works correctly
- `test_coding_backend_wiring.py` — all tests pass

**Depends on:** M11, M12
**Enables:** M20 (Coding Intelligence 2.0), M27 (Autonomous Engineering — foundation)

---

### M14 — Research Intelligence

**Status:** `COMPLETE`

**Purpose:**
Research agent for web search, evidence extraction, source evaluation,
and synthesis of findings into structured reports.

**Implemented:**
- `src/research/research_engine.py` — core research execution loop
- `src/research/research_planner.py` — research plan generation
- `src/research/research_plan.py` — plan model and steps
- `src/research/research_context.py` — research session context
- `src/research/search_manager.py` — search provider management
- `src/research/provider_interface.py` — search provider contract
- `src/research/providers/` — search provider adapters
- `src/research/content_fetcher.py` — web content retrieval
- `src/research/evidence_extractor.py` — evidence extraction from content
- `src/research/evidence_merger.py` — multi-source evidence merging
- `src/research/reasoning_layer.py` — evidence reasoning and synthesis
- `src/research/conflict_detector.py` — contradicting source detection
- `src/research/citation_builder.py` — citation generation
- `src/research/citation_formatter.py` — citation formatting
- `src/research/citation_models.py` — citation data models
- `src/research/cache_manager.py` — research cache
- `src/research/metrics.py` — research quality metrics
- `src/research/models.py` — research data models
- `src/brain/research_agent.py` — brain-level research agent
- `src/brain/research_decision.py` — research routing decisions
- `src/brain/research_integration.py` — research-brain integration
- `src/brain/deep_research_manager.py` — long-form deep research
- `src/brain/live_search_engine.py` — live web search integration
- `src/agents/research/` — research agent specializations
- `src/agents/research_agent.py` — research-capable agent

**Acceptance criteria:**
- Research query produces structured report with citations
- Conflicting sources flagged and noted in output
- Cache prevents re-fetching the same URLs within session
- Deep research loop runs multiple search rounds until evidence threshold met

**Depends on:** M11, M12
**Enables:** M21 (Research Intelligence 2.0)

---

### M15 — Desktop Intelligence

**Status:** `COMPLETE`

**Purpose:**
Complete integration of desktop components — Aura can interact with the
Windows desktop, applications, and system using vision and automation.

**Implemented:**
- `src/desktop/` — desktop subsystem
- `src/agents/desktop/` — desktop-specialized agents
- `src/agents/desktop_agent.py` — desktop interaction agent
- `src/agents/browser_agent.py` — browser-integrated desktop agent
- `src/core/live_screen.py` — live desktop state capture
- `src/core/hotkeys.py` — global hotkey management
- `src/core/overlay_manager.py` — desktop overlay rendering

**Acceptance criteria:**
- Aura can open, focus, and control application windows
- Screenshot → vision → action loop completes for a defined UI task
- Global hotkey activates Aura overlay within 200ms
- Desktop context (active app, window title) captured correctly

**Depends on:** M04, M07, M09
**Enables:** M26 (Personal OS foundation)

---

### M16 — Cognitive Orchestration Layer

**Status:** `COMPLETE`

**Purpose:**
The central decision-making and cognitive runtime of Aura. Implements the 5-stage
ACA pipeline: Perception → DMM → Planning → Execution → Reflection/Learning.
Every user request flows through this layer.

**Implemented:**
- `src/brain/aca/` — ACA cognitive pipeline package
- `src/core/orchestration/master_orchestrator.py` — MasterOrchestrator (top-level)
- `src/core/orchestration/decision_engine.py` — DecisionEngine
- `src/core/orchestration/runtime_session.py` — RuntimeSession
- `src/core/orchestration/agent_session.py` — AgentSession
- `src/core/orchestration/worker_manager.py` — WorkerManager
- `src/core/orchestration/task_decomposer.py` — TaskDecomposer
- `src/core/orchestration/supervisor_agent.py` — SupervisorAgent
- `src/core/orchestration/software_engineering_supervisor.py` — SESupervisor
- `src/core/orchestration/execution_policy.py` — execution policy and safety
- `src/core/orchestration/artifact.py` — Artifact model
- `src/core/orchestration/observation.py` — Observation model
- `src/core/orchestration/world_snapshot.py` — world state snapshot
- `src/core/orchestration/world_diff.py` — state diff computation
- `src/core/orchestration/world_state_observer.py` — state observer
- `src/core/orchestration/world_timeline.py` — world state timeline
- `src/core/orchestration/planner_registry.py` — planner registration
- `src/core/orchestration/reasoning_engine.py` — reasoning integration
- `src/core/orchestration/result_merger.py` — multi-result merging
- `src/core/orchestration/session_replay.py` — session replay
- `src/core/orchestration/pipeline_error.py` — pipeline error handling
- `src/core/orchestration/reference_resolver.py` — reference resolution
- `src/core/orchestration/ownership_tracker.py` — artifact ownership
- `src/core/orchestration/confirmation.py` — human confirmation gate
- `src/core/orchestration/domain_sessions.py` — domain-specific sessions
- `src/core/orchestration/engineering_session.py` — engineering session
- `src/core/orchestration/task_working_memory.py` — task working memory
- `src/core/backends/` — execution backend adapters
- `src/brain/decision_engine.py` — brain-level decision engine
- `src/brain/goal_analyzer.py` — goal analysis and decomposition
- `src/brain/conversation_engine.py` — conversation lifecycle
- `src/brain/world_model.py` — ACA world model (foundation)
- `src/brain/verification.py` — output verification
- `src/brain/reflection.py` — reflection stub
- `src/brain/learning.py` — learning engine (conservative)
- `src/core/event_bus.py` — EventBus (async event broadcasting)

**Acceptance criteria:**
- All requests enter via `AuraCore.process_request()` single entry point
- No domain backend imports from `src.brain.aca` (guardrail enforced)
- Only `ExecutionCoordinator` invokes execution engines via `EngineRegistry`
- All stages read/write through `Blackboard` (`CognitiveState`)
- RuntimeSession created and closed correctly per request
- Artifacts tracked with ownership
- Reflection stage fires after every execution

**Architecture note:** See [`ARCHITECTURE.md`](ARCHITECTURE.md) for layer contracts
and [`docs/ARCHITECTURE_FREEZE.md`](docs/ARCHITECTURE_FREEZE.md) for frozen guardrails.

**Depends on:** M01–M15
**Enables:** All Phase 1+ milestones

---

---

# FOUNDATION WIRING & TRUTH PASS

> **Status: `COMPLETE`** (August 2026)

A stabilization gate between Phase 0 and Phase 1. Not a feature milestone.
Its job: ensure every Phase 0 item marked operational actually works through
Aura's real runtime before intelligence layers are built on top.

**Completed in this pass:**

| Action | Result |
| :--- | :--- |
| Corrected M13 status from `COMPLETE` to `IN PROGRESS` | Coding backend was a mock. Now routes to `EngineeringManager`. |
| Corrected M09 status to `COMPLETE — LEGACY` | `AgentRuntime` is not on the live path |
| Corrected M03 status to `COMPLETE — FOUNDATION ONLY` | Flat fact store, not cognitive memory |
| Corrected M10 status to `COMPLETE — DISCONNECTED` | Real framework, no active workflows |
| Created [`RUNTIME.md`](RUNTIME.md) | Canonical live-path wiring map |
| Created `tests/test_coding_backend_wiring.py` | 5 tests verifying honest coding backend |

**Gate condition:** M17 (Cognitive Memory) may only begin after this pass is verified.

---

---

# PHASE 1 — Shared Intelligence

> M17 and M18 may be developed partially in parallel.
> M18's Repository, Workspace, and Graph providers do not require Cognitive Memory to complete.
> The MemoryProvider inside M18 is the integration point that requires M17.

---

### M17 — Cognitive Memory

**Status:** `COMPLETE`
**Priority:** 🟢 Verified Live

Turn Aura's existing persistence into a genuine cognitive memory system with typed memory stores,
scoring, decay, consolidation, and project-scoped recall.

```text
Cognitive Memory
├── Working Memory       — active context in the current session
├── Short-Term Memory    — recent interactions and outputs (last ~hours)
├── Long-Term Memory     — persistent facts and entities across sessions
├── Episodic Memory      — timestamped "what happened when" narrative
├── Semantic Memory      — concepts, entities, and relationships
├── Procedural Memory    — learned workflows and how-to sequences
├── Preference Memory    — user style, formatting, tooling choices
├── Project Memory       — per-project context, decisions, history
└── Memory Recall        — relevance-ranked, scored retrieval
```

**Acceptance criteria:**
- All 8 memory types stored and retrievable independently
- Recall returns ranked results by recency + importance score
- Memory decay reduces importance score of stale entries over time
- Consolidation merges semantically duplicate memories
- Conflict resolution logs contradicting facts rather than silently overwriting
- Explicit deletion supported via API
- Project memory is isolated per project root path
- Aura correctly answers *"What were we working on yesterday?"* from episodic store

**End state:**
> User: *"Continue what we were doing yesterday."*
> Aura knows exactly what "what" refers to.

**Existing foundations:** `Memory.py`, `src/memory/`, `src/brain/aca/learning.py`,
`Memory.db` (SQLite schema), `src/brain/context_manager.py`

**Depends on:** M16
**Enables:** M18 (MemoryProvider integration), M19, and all subsequent phases

---

### M18 — Adaptive Computer Interaction Runtime & World Model

**Status:** `COMPLETE`
**Priority:** 🔴 Critical

The central, unified representation of the user's environment.
Not a separate brain — the **single source of truth** every subsystem reads from.

```text
                     WORLD MODEL
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
   Workspace          Repository          Memory
       ▼                  ▼                  ▼
    Files             Symbols            History
    Projects          Dependencies       Decisions
       │                  │                  │
       └──────────────────┼──────────────────┘
                          ▼
                        Aura
```

**Providers** (feed the model — none become independent brains):

```text
DesktopProvider        — active windows, screen state
RepositoryProvider     — git repos, branches, commits, diffs
KnowledgeGraphProvider — concepts, entities, and relationships
DependencyProvider     — package and module dependencies
SymbolGraphProvider    — classes, functions, call graphs
MemoryProvider         — Cognitive Memory interface (requires M17)
ResearchProvider       — research results and citations
BrowserProvider        — open tabs, visited pages, extracted content
NetworkProvider        — local services, ports, running processes
CalendarProvider       — events, deadlines, meetings
```

**Acceptance criteria:**
- `WorldModel.query(entity)` returns all known facts about an entity from all providers
- Provider failures degrade gracefully — model stays partially available
- World Model updated incrementally as state changes (no full rebuild required)
- MemoryProvider integrated with M17 cognitive stores
- `WorldModel.snapshot()` produces a serializable state representation

**End state:**
> Aura understands: *"What exists, how everything is related, and what has happened."*

**Existing foundations:** `src/brain/world_model.py`, `src/workspace/`,
`knowledge_graph.py`, `symbol_graph.py`, `dependency_graph.py`, `desktop_context.py`

**Depends on:** M16 (full), M17 (MemoryProvider integration point only)
**Enables:** M19

---

---

# PHASE 2 — Capability Foundation

---

### M19 — Capability & Tool Runtime

**Status:** `PLANNED`
**Priority:** 🔴 Critical

The bridge between Aura's intelligence and the outside world.
Every capability — native, MCP, or API — is registered here with a uniform contract.

```text
              AURA
                │
        Capability Registry
                │
      ┌─────────┼─────────┐
      ▼         ▼         ▼
   Native      MCP      API / Future
   Tools      Tools      Adapters
```

**Capability contract (every registered capability carries):**

| Field | Type | Purpose |
| :--- | :--- | :--- |
| `name` | `str` | Unique dotted identifier e.g. `filesystem.read` |
| `description` | `str` | Human-readable purpose |
| `input_schema` | `JSONSchema` | Typed input contract |
| `output_schema` | `JSONSchema` | Typed output contract |
| `risk_level` | `enum` | `low / medium / high / critical` |
| `permissions` | `list[str]` | Required grants before execution |
| `availability` | `enum` | `online / offline / conditional` |
| `execution_backend` | `str` | Where it runs (local / remote / subprocess) |
| `authentication` | `str` | Auth requirements or `none` |
| `cost` | `str` | Estimated cost class (free / low / metered) |
| `latency` | `str` | Expected latency (instant / fast / slow) |

**Example capabilities:**
```text
filesystem.read         filesystem.write
github.search           github.pr.create
browser.open            browser.extract
memory.recall           memory.store
workspace.search        terminal.execute
research.query          calendar.read
```

**Execution flow after M19:**
```text
User request
      ↓
Candidate capabilities (First Layer)
      ↓
Capability ranking
      ↓
Permission check
      ↓
Orchestrator
      ↓
Execution
      ↓
Result contract
      ↓
Verification
```

**Acceptance criteria:**
- All existing tools registered as capabilities with full metadata
- `CapabilityRegistry.discover()` returns all registered capabilities
- Permission check blocks execution for insufficient grants
- Execution result conforms to `output_schema` or raises typed error
- Audit log entry written for every capability invocation
- MCP adapter slot defined (implementation deferred to M23)

**Depends on:** M17, M18
**Enables:** M20, M21, M22 (parallel), M23

---

---

# PHASE 3 — Intelligence Expansion

> M20, M21, M22 may be developed in parallel — all depend on M19 only.

---

### M20 — Coding Intelligence 2.0

**Status:** `PLANNED`
**Priority:** 🔴 High

Coding now has access to Memory + World Model + Capability Registry.
Aura becomes a genuine engineering agent, not merely a coding assistant.

```text
Instead of:  User → Code request → Edit file

Aura does:
Understand request
       ↓
Understand project (World Model)
       ↓
Understand architecture and dependencies
       ↓
Recall previous decisions (Memory)
       ↓
Plan change
       ↓
Generate patch
       ↓
Run tests (Capability Registry)
       ↓
Evaluate result
       ↓
Repair loop if tests fail
       ↓
Verify and finalize
```

**Acceptance criteria:**
- Aura produces a correct code change for a specified task using project context
- Previous architectural decisions recalled and respected
- Tests run automatically after each edit attempt
- Failed tests trigger up to N repair iterations before escalating
- Output: modified files + test results + decision rationale

**Existing foundations:** `src/agents/coding_agent.py`, `src/agents/coding/`,
`src/engineering/`, `src/brain/execution_map_generator.py`

**Depends on:** M19
**Enables:** M27 (Autonomous Engineering)

---

### M21 — Research Intelligence 2.0

**Status:** `PLANNED`
**Priority:** 🔴 High

Research becomes contextual — Aura knows what it's researching *for* before
it searches a single page.

```text
Question
 ↓
Research plan (informed by World Model + Memory)
 ↓
Search (via Capability Registry)
 ↓
Source collection and confidence scoring
 ↓
Evidence extraction and cross-check
 ↓
Synthesis
 ↓
Project-specific recommendation
 ↓
Store findings in Memory
```

**Example:**
> *"Research the best authentication architecture for Aura."*
> Aura already knows: Aura's current architecture, language/framework,
> existing dependencies, previous decisions, and security requirements.

**Acceptance criteria:**
- Research report includes project-specific recommendation section
- Sources ranked by confidence and recency
- Findings stored in Semantic Memory for future recall
- Contradicting sources flagged explicitly
- Long-running deep research loop runs at least 3 search rounds before synthesis

**Existing foundations:** `src/research/` (18 modules), `src/brain/deep_research_manager.py`

**Depends on:** M19
**Enables:** M25 (Expert Systems foundation), M27

---

### M22 — Browser Intelligence

**Status:** `PLANNED`
**Priority:** 🟠 High

Aura gets a full web interaction layer. All browser actions run through
Capability Registry + Permission System + Verification.
**No separate browser architecture — browser is a set of registered capabilities.**

```text
Browser Capabilities
├── browser.navigate      — load URL
├── browser.search        — web search
├── browser.read          — extract page content
├── browser.extract       — structured data extraction
├── browser.click         — UI element interaction
├── browser.fill          — form filling
├── browser.download      — file download
├── browser.upload        — file upload
└── browser.observe       — page state observation
```

**Acceptance criteria:**
- Web page content extracted correctly from a given URL
- Form fill and submit works for a defined test page
- Downloads routed to configured download directory
- All browser actions pass through permission check
- Browser session isolated per agent task

**Existing foundations:** `src/browser/`, `src/agents/browser_agent.py`,
`src/brain/page_reader.py`, `src/brain/web_search.py`

**Depends on:** M19
**Enables:** M23, M26 (Personal OS browser integration)

---

---

# PHASE 4 — External Capabilities

---

### M23 — MCP Ecosystem

**Status:** `PLANNED`
**Priority:** 🟠 High

MCP becomes useful here because Aura already has the Capability Registry to consume it.
MCP is one standardized supply mechanism — not a dependency of the core architecture.

```text
Aura Capability Registry
          │
       MCP Adapter
          │
 ┌────────┼─────────┐
 ▼        ▼         ▼
GitHub   Google    Custom
 MCP      MCP       MCP
```

**Build:**
```text
MCP Client
MCP Server Manager
Tool Discovery
Tool Schema Parser → maps to Capability contract
MCP Capability Adapter
Authentication
Permission Mapping
Connection Manager
Error Handling
Audit Logging
```

**Aura-native MCP servers (build first):**
```text
aura-workspace-mcp    — files, projects, workspace state
aura-memory-mcp       — cognitive memory read/write
aura-architecture-mcp — knowledge graph, symbol graph
aura-coding-mcp       — code analysis and editing
```

**External MCP servers (later, in priority order):**
```text
GitHub · Google Drive · Calendar · Gmail · Notion · Canva
```

**Zapier MCP — not a milestone:**
> Zapier is an optional external MCP gateway. Add only when SaaS integrations
> are needed that aren't worth building directly. It plugs into the MCP layer
> without touching Aura's core architecture.

**Acceptance criteria:**
- MCP tool discovered and registered as a Capability automatically
- MCP tool invoked through same `CapabilityRegistry.execute()` interface as native tools
- MCP server connection failure handled gracefully (tool marked unavailable)
- At least one Aura-native MCP server operational (e.g. `aura-workspace-mcp`)

**Depends on:** M20, M21, M22
**Enables:** M24, M25, M26

---

---

# PHASE 5 — Autonomy

> M24, M25, and M26 may be developed in parallel once M23 is complete.
> Final integration before M27 requires all three.
>
> Expert Systems (M25) do **not** depend on Event Runtime (M24).
> Their actual dependency is Memory + World Model + Research + Capability Runtime.

---

### M24 — Event Runtime

**Status:** `PLANNED`
**Priority:** 🔴 Very High

This is where Aura stops being purely reactive.

```text
Before:  User → Aura → Action

After:
                    EVENT RUNTIME
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
    Schedule           Event            Condition
       ▼                 ▼                 ▼
    9:00 AM          Email arrived     Build failed
       │                 │                 │
       └─────────────────┼─────────────────┘
                         ▼
                       Aura
                         ▼
                      Decide
                         ▼
                     Execute
```

**Build:**
```text
Event bus (extend existing EventBus)
Schedule manager
Condition evaluator
Trigger registry
Event queue
Worker pool
Retry logic
State persistence across restarts
```

**Examples:**
- *"Every morning summarize my project status."*
- *"When the build fails, investigate it."*
- *"When a new GitHub issue appears, categorize it."*

**Acceptance criteria:**
- Scheduled trigger fires at correct time with < 5s jitter
- Event trigger fires within 2s of observed event
- Condition trigger evaluates correctly before firing
- Worker failure retried N times before escalating
- Event runtime state survives process restart

**Existing foundations:** `src/core/event_bus.py`, `src/workflows/trigger_manager.py`,
`src/workflows/workflow_scheduler.py`

**Depends on:** M23
**Enables:** M27 (Autonomous Engineering requires event loop)

---

### M25 — Professional Expert Systems

**Status:** `PLANNED`
**Priority:** 🟠 High

Specialized domain intelligence built on top of the shared Aura runtime.
**Not independent AIs — specialized planners sharing one runtime.**

```text
Expert Systems
├── Software Engineering  — architecture, refactoring, debugging
├── Network Engineering   — topology, diagnostics, security
├── Cybersecurity         — threat analysis, audit, hardening
├── Finance               — analysis, modeling, reporting
├── Project Management    — planning, tracking, risk
├── Research              — academic and technical research
└── Custom User Domains   — user-defined domain experts
```

Each expert uses the shared runtime:
```text
World Model + Memory + Research + Coding + Capability Registry + Orchestrator
```

> **Specialized knowledge + shared Aura intelligence.**

**Acceptance criteria:**
- Network Engineering expert produces correct diagnostics for a defined network scenario
- Security expert identifies CVEs relevant to a given dependency set
- Expert can be invoked by name from natural language
- Expert uses Memory to recall previous decisions in its domain
- Expert output format is domain-appropriate (not generic LLM response)

**Existing foundations:** `src/engineering/`, `src/agents/networking/`,
`src/agents/security/`, `src/agents/documentation/`

**Depends on:** M19, M20, M21 (does not require M24)
**Enables:** M27

---

### M26 — Personal Operating System

**Status:** `PLANNED`
**Priority:** 🟠 High

Aura starts actively managing the user's digital environment.

```text
                  AURA
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
   Projects      Files       Apps
       ▼           ▼           ▼
   Calendar     Browser      Email
       ▼           ▼           ▼
   Tasks        Research    Communication
```

**Managed domains:**
- Projects and tasks with status tracking
- Files and documents with tagging and search
- Calendar and deadlines with proactive reminders
- Communication and email summaries
- Knowledge and research results
- Application launching and focus management
- Automation of repeated daily workflows
- User preferences and personalization

> **Aura doesn't merely answer questions — it understands and manages the user's digital environment.**

**Acceptance criteria:**
- `"What do I need to do today?"` returns prioritized task list from calendar + tasks + memory
- File search across workspace returns relevant results within 1s
- Repeated workflow (e.g. morning standup prep) can be automated with one command
- Personal OS state persists across Aura restarts

**Existing foundations:** `src/core/app.py`, `src/core/hotkeys.py`,
`src/core/overlay_manager.py`, `src/workflows/workflow_scheduler.py`

**Depends on:** M23
**Enables:** M27

---

---

# PHASE 6 — Autonomous Engineering

---

### M27 — Autonomous Engineering Platform

**Status:** `PLANNED`
**Priority:** 🔴 High

Coding becomes fully autonomous — from issue to PR, with strict permissions at each step.

```text
Issue / requirement
 ↓
Understand (Memory + World Model)
 ↓
Research (Research Intelligence)
 ↓
Plan (architecture-aware)
 ↓
Implement (Coding Intelligence)
 ↓
Test
 ↓
Evaluate
 ↓
Repair loop (if tests fail)
 ↓
Review (human gate or automated)
 ↓
Commit / PR
```

> *"Aura, implement issue #142."*
> Aura takes it from **requirement → implementation → testing → PR**.

**Acceptance criteria:**
- Given a well-specified GitHub issue, Aura produces a correct implementation
- All changed files have corresponding test coverage
- Human approval gate fires before any commit
- PR description written automatically from implementation decisions
- Aura can explain every decision it made during the implementation

**Requires:** M20 (Coding), M21 (Research), M22 (Browser), M24 (Events), M25 (Experts), M26 (Personal OS)

**Existing foundations:** `src/core/orchestration/software_engineering_supervisor.py`,
`src/core/orchestration/master_orchestrator.py`, `src/engineering/`

**Depends on:** M24, M25, M26
**Enables:** M28

---

---

# PHASE 7 — Aura OS

---

### M28 — Aura OS

**Status:** `PLANNED`
**Priority:** 🟣 Architectural milestone

Not simply a GUI layer — the culmination of every previous phase into one
persistent, unified AI runtime.

**Definition of Done:**

> Aura operates as a persistent local AI environment that maintains intelligence,
> capabilities, memory, world knowledge, tasks, workers, events, permissions,
> and state recovery across sessions — all through one unified runtime.

**Aura OS Runtime components:**

```text
Aura Runtime
├── Persistent process       — survives session restarts
├── Configuration system     — environment-aware config loading
├── Capability manager       — live capability registry
├── Memory manager           — cognitive memory lifecycle
├── World Model              — continuously updated environment model
├── Task manager             — active and queued tasks
├── Event runtime            — schedules, triggers, conditions
├── Worker manager           — concurrent agent workers
├── Permission manager       — user-level permission grants
├── State persistence        — serialized runtime state
├── Logging                  — structured, queryable logs
├── Recovery                 — restart from last known good state
└── Update/version system    — runtime upgrades without downtime
```

**Aura OS startup sequence:**

```text
Start
 ↓
Load configuration
 ↓
Load state from persistence
 ↓
Initialize capability registry
 ↓
Load cognitive memory
 ↓
Build world model
 ↓
Start event runtime
 ↓
Start worker manager
 ↓
Ready (all subsystems live)
```

**Acceptance criteria:**
- Aura process survives OS user session restart and resumes from saved state
- All subsystems initialize in correct order without deadlock
- Capability registry populated before any worker starts
- Memory loaded before world model starts building
- Event runtime fires first pending events within 10s of startup
- Worker manager handles N concurrent workers without resource starvation
- Recovery mode starts from last checkpoint if clean startup fails

**Depends on:** M27
**Enables:** M29, M30

---

---

# PHASE 8 — Natural Interaction

---

### M29 — Natural Interaction Layer

**Status:** `PLANNED`
**Priority:** 🟠 Experience milestone

> **M29 upgrades M08. It does not rebuild M08.**

```text
M08 — Voice Infrastructure (COMPLETE)
           ↓
           ↓ (foundation)
           ↓
M29 — Natural Interaction Layer
```

M08 delivered: wake word · STT · TTS · microphone lifecycle · audio streaming bridge.
M29 adds: full conversational interaction, real-time interruption, and natural turn-taking.

**Voice interaction pipeline (M29):**

```text
Wake (M08 wake_word.py)
 ↓
Listen (M08 STT with streaming)
 ↓
Understand intent (cognitive pipeline)
 ↓
Detect user interruption (barge-in)
 ↓
Stream response
 ↓
Speak (M08 TTS)
 ↓
Detect next user turn
 ↓
Resume or close session
```

**New capabilities added by M29:**

```text
Full Duplex             — simultaneous listen and speak
Barge-in               — user can interrupt Aura mid-sentence
Echo Cancellation      — prevent feedback loop
Conversation State     — track multi-turn context
Interaction Manager    — session lifecycle and natural pauses
Natural Turn-Taking    — detect when user is done speaking
Streaming STT/TTS      — real-time transcription and synthesis
```

**Acceptance criteria:**
- User can interrupt Aura mid-sentence and Aura stops within 200ms
- Multi-turn conversation maintains context across at least 10 turns
- Echo cancellation active when TTS and microphone run simultaneously
- Turn detection correctly identifies end of user speech without cutoff
- Interaction manager closes session gracefully on extended silence

**Depends on:** M28 (Aura OS provides the runtime context for interaction)
**Existing foundation:** `src/voice/` (full M08 module set)

---

---

# PHASE 9 — Aura GUI

---

### M30 — Aura Command Center

**Status:** `PLANNED`
**Priority:** 🟠 Experience milestone

A visualization of Aura's intelligence — **not the place where the intelligence lives.**

```text
Aura Command Center
│
├── Conversation          — current and historical dialogue
├── Live Workers          — active agent workers and status
├── Engineering Dashboard — code tasks, PRs, test results
├── Browser View          — embedded browser or preview
├── Timeline              — chronological event and decision log
├── Memory Viewer         — browsable cognitive memory
├── World Model Explorer  — interactive entity and relationship graph
├── Task Monitor          — queued, active, and completed tasks
├── Event Monitor         — scheduled and triggered events
├── Capability Monitor    — registered capabilities and usage
└── Voice Controls        — voice session controls and transcription
```

> The GUI shows what Aura is thinking, doing, and remembering.
> Intelligence does not live in the GUI.

**Acceptance criteria:**
- Live Workers panel updates in real-time as agents execute
- Memory Viewer allows search and browsing of all memory types
- World Model Explorer renders entity graph interactively
- Timeline shows complete chronological trace of decisions and actions
- All panels read from Aura OS APIs — no direct subsystem coupling

**Existing foundations:** `src/gui/`, `frontend/`, `apps/`, `src/core/overlay_manager.py`

**Depends on:** M28 (all data surfaces come from the Aura OS runtime)

---

---

## Full Milestone Index

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 0 — FOUNDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M01   Core Foundation
M02   Capability Router
M03   Memory 2.0
M04   Workspace Awareness
M05   Tool Execution Engine
M06   Plugin Ecosystem
M07   Vision System
M08   Voice Infrastructure         ← infrastructure only; see M29
M09   Agent Runtime
M10   Workflow Engine
M11   Knowledge Intelligence (RAG 2.0)
M12   Multi-Agent Intelligence
M13   Engineering Intelligence
M14   Research Intelligence
M15   Desktop Intelligence
M16   Cognitive Orchestration Layer


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1 — SHARED INTELLIGENCE       [parallel]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M17   Cognitive Memory              ← start here; enables MemoryProvider in M18
M18   World Model                   ← most providers parallelizable with M17


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2 — CAPABILITY FOUNDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M19   Capability & Tool Runtime     ← requires M17 + M18 complete


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3 — INTELLIGENCE EXPANSION    [parallel]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M20   Coding Intelligence 2.0       ← requires M19
M21   Research Intelligence 2.0     ← requires M19
M22   Browser Intelligence          ← requires M19


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 4 — EXTERNAL CAPABILITIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M23   MCP Ecosystem                 ← requires M20 + M21 + M22


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 5 — AUTONOMY                  [parallel]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M24   Event Runtime                 ← requires M23
M25   Professional Expert Systems   ← requires M19+M20+M21 (not M24)
M26   Personal OS                   ← requires M23


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 6 — AUTONOMOUS ENGINEERING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M27   Autonomous Engineering        ← requires M24 + M25 + M26


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 7 — AURA OS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M28   Aura OS                       ← requires M27


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 8 — NATURAL INTERACTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M29   Natural Interaction Layer     ← requires M28; upgrades M08

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 9 — AURA GUI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M30   Aura Command Center           ← requires M28
```

---

## Progress Overview

```text
Phase 0 — Foundation (M01–M16)          ████████████████████  16/16  COMPLETE
Phase 1 — Shared Intelligence (M17–M18) ██████████░░░░░░░░░░   1/2   IN PROGRESS (M17 COMPLETE, M18 ACTIVE)
Phase 2 — Capability Foundation (M19)   ░░░░░░░░░░░░░░░░░░░░   0/1   READY
Phase 3 — Intelligence Expansion        ░░░░░░░░░░░░░░░░░░░░   0/3   PLANNED
Phase 4 — External Capabilities (M23)   ░░░░░░░░░░░░░░░░░░░░   0/1   PLANNED
Phase 5 — Autonomy (M24–M26)            ░░░░░░░░░░░░░░░░░░░░   0/3   PLANNED
Phase 6 — Autonomous Engineering (M27)  ░░░░░░░░░░░░░░░░░░░░   0/1   PLANNED
Phase 7 — Aura OS (M28)                 ████████████████████   1/1   OPERATIONAL (Foundation Live)
Phase 8 — Natural Interaction (M29)     ████████████████████   1/1   OPERATIONAL (Foundation Live)
Phase 9 — Aura GUI (M30)                ░░░░░░░░░░░░░░░░░░░░   0/1   PLANNED
```

**Overall:** 19 / 30 foundational subsystems active. Next critical milestones: M18 (World Model) and M19 (Capability Runtime).

---

## Priority Queue — What to Build Next

| Priority | Milestone | Status | Hard Blocker |
| :--- | :--- | :--- | :--- |
| 1 | **M18** — World Model (Workspace & System Graph) | `IN PROGRESS` | None |
| 2 | **M19** — Capability & Tool Runtime | `READY` | M18 integration |
| 3 | **M20** — Autonomous Coding Agent | `PLANNED` | M19 |
| 4 | **M21** — Autonomous Research Agent | `PLANNED` | M19 |
| 5 | **M22** — Browser Intelligence (Playwright) | `PLANNED` | M19 |
| 6 | **M23** — MCP Ecosystem | `PLANNED` | M20 + M21 + M22 |
| 7 | **M25** — Professional Expert Systems | `PLANNED` | M19 + M20 + M21 |
| 8 | **M24** — Event Runtime & Autonomy | `PLANNED` | M23 |
| 9 | **M26** — Personal OS Proactive Automation | `PLANNED` | M23 |
| 10 | **M27** — Autonomous Engineering Loop | `PLANNED` | M24 + M25 + M26 |
| 11 | **M30** — Aura GUI Command Center & Vision | `PLANNED` | M28 |

---

## Architecture Constitution

Read [`ARCHITECTURE.md`](ARCHITECTURE.md) for layer contracts and the 5-stage ACA pipeline.
Read [`docs/ARCHITECTURE_FREEZE.md`](docs/ARCHITECTURE_FREEZE.md) for frozen guardrails
and contributor extension guidelines.

---

*Last Updated: August 2026*