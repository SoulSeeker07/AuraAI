# AuraAI — System Module Classification

> **Single source of truth for module lifecycle status.**
> Use this before expanding, refactoring, or wiring any module.
> Last updated: September 2026 — Foundation Wiring, Autonomy & Truth Pass

---

## Classification Definitions

| Classification | Meaning |
|:---|:---|
| `ACTIVE` | On the live request path. Used in production on every request. |
| `SCAFFOLDED` | Code is complete and real. Not wired to the live path. Ready to connect. |
| `LEGACY` | Superseded by newer architecture. Code is preserved for reference and possible reconnection. Do not expand. |
| `DISCONNECTED` | Real, complete code. Not on the live path. A specific future milestone will reconnect it. |
| `DEPRECATED` | Will be removed. Do not add dependencies on this code. |
| `MISSING` | Does not yet exist. Scheduled for a specific milestone. |

---

## Core Runtime

| Module | File | Classification | Notes |
|:---|:---|:---|:---|
| `AuraCore` | `src/core/app.py` | **ACTIVE** | Single entry point. All requests start here. |
| `NLUEngine` | `src/core/nlu/nlu_engine.py` | **ACTIVE** | Stage 0 Perception Layer. Text normalization, entity extraction, ambiguity detection. |
| `EntityExtractor` | `src/core/nlu/entity_extractor.py` | **ACTIVE** | Stage 0 Perception. App, path, query entity extraction. |
| `AmbiguityDetector` | `src/core/nlu/ambiguity_detector.py` | **ACTIVE** | Stage 0 Perception. Ambiguity detection & clarification prompts. |
| `MasterOrchestrator` | `src/core/orchestration/master_orchestrator.py` | **ACTIVE** | 7-stage pipeline. 1,192 lines. |
| `AgentSession` | `src/core/orchestration/agent_session.py` | **ACTIVE** | Created per request. Budget tracking. |
| `DecisionEngine` | `src/core/orchestration/decision_engine.py` | **ACTIVE** | Stage 2. Intent classification (heuristic). |
| `TaskDecomposer` | `src/core/orchestration/task_decomposer.py` | **ACTIVE** | Stage 3. Keyword-heuristic DAG. |
| `SupervisorAgent` | `src/core/orchestration/supervisor_agent.py` | **ACTIVE** | Stage 4. Planner delegation. |
| `WorkerManager` | `src/core/orchestration/worker_manager.py` | **ACTIVE** | Worker lifecycle. |
| `RuntimeSession` | `src/core/orchestration/runtime_session.py` | **ACTIVE** | Session state container. |
| `ResultMerger` | `src/core/orchestration/result_merger.py` | **ACTIVE** | Stage 6. Multi-result fusion. |
| `ReasoningEngine` | `src/core/orchestration/reasoning_engine.py` | **ACTIVE** | Pre-decomposition heuristic reasoning. |
| `ExecutionPolicy` | `src/core/orchestration/execution_policy.py` | **ACTIVE** | Safety policy enforcement per action. |
| `FocusManager` | `src/core/focus_manager.py` | **ACTIVE** | Multi-task context switching, SQLite WAL backing, interrupt routing (M32). |
| `MacroCompiler` | `src/execution/macro_compiler.py` | **ACTIVE** | Zero-token deterministic UI macro compilation (M34). |
| `VisualWorkingMemory` | `src/core/visual_memory.py` | **ACTIVE** | Ring buffer visual grounding memory (M33/M35). |
| `Artifact` | `src/core/orchestration/artifact.py` | **ACTIVE** | Artifact model for output tracking. |
| `WorldSnapshot` | `src/core/orchestration/world_snapshot.py` | **ACTIVE** | Snapshot of world state per session. |
| `EventBus` | `src/core/event_bus.py` | **ACTIVE** | Synchronous pub/sub. 47 lines. |
| `PromptBuilder` / `IdentityLoader` | `src/core/system/` | **ACTIVE** | YAML-backed identity. Loaded at startup. |

---

## Backend Adapters (BackendRegistry)

| Module | File | Classification | Notes |
|:---|:---|:---|:---|
| `BackendRegistry` | `src/core/backends/backend_registry.py` | **ACTIVE** | Capability routing table. |
| `DesktopEngineBackend` | `src/core/backends/adapters/desktop_backend.py` | **ACTIVE** | Win32 integration. Production-quality. |
| `DefaultNativeDesktopAdapter` | `src/core/backends/backend_registry.py` | **ACTIVE** | Routes to DesktopEngineBackend. |
| `CodingBackendAdapter` | `src/core/backends/adapters/antigravity_backend.py` | **ACTIVE** | Routes to EngineeringManager. Post-Truth-Pass. |
| `MemoryBackend` | `src/core/backends/adapters/memory_backend.py` | **ACTIVE** | SQLite fact store integration. |
| `DefaultGeminiResearchAdapter` | `src/core/backends/backend_registry.py` | **SCAFFOLDED** | Stub responses. Research not on pipeline path. |
| `PlaywrightBrowserAdapter` | `src/core/backends/adapters/browser_backend.py` | **ACTIVE** | Live Playwright & L1/L2 DOM/URL verification & recovery. |
| `ObservationModels` | `src/core/orchestration/observation_models.py` | **ACTIVE** | Evidence-backed Observation, ExpectedState, VerificationReport models. |
| `ActivityTraceRenderer` | `src/core/orchestration/activity_trace_renderer.py` | **ACTIVE** | CLI 3-level activity trace presentation layer. |
| `UnifiedToolDispatcher` | `src/core/tools/unified_tool_dispatcher.py` | **ACTIVE** | Canonical 21-tool discrete execution dispatcher with HMAC ticket gating (TD-020). |
| `SmartHomeBackendAdapter` | `src/core/backends/adapters/smarthome_backend.py` | **ACTIVE** | Live via `UnifiedToolDispatcher.smarthome_control` & Home Assistant / Tapo. |
| `EmailBackendAdapter` | `src/core/backends/adapters/email_backend.py` | **ACTIVE** | Live via `UnifiedToolDispatcher.email_action` & EmailPlugin. |
| `CalendarBackendAdapter` | `src/core/backends/adapters/calendar_backend.py` | **ACTIVE** | Live via `UnifiedToolDispatcher.calendar_action` & CalendarPlugin. |

---

## Engineering Subsystem

| Module | File | Classification | Notes |
|:---|:---|:---|:---|
| `EngineeringManager` | `src/engineering/engineering_manager.py` | **ACTIVE** | Wired to CodingBackendAdapter in Truth Pass. |
| `AutonomousLoop` | `src/engineering/autonomous_loop.py` | **ACTIVE** | Closed-loop bug fixing, test-driven repair, and byte-exact rollback (M27). |
| `SafetyCeiling` | `src/engineering/safety_ceiling.py` | **ACTIVE** | `PROTECTED_SAFETY_CEILING` boundary enforcement (M27). |
| `PatchBundleAssembler` | `src/engineering/pr_assembler.py` | **ACTIVE** | Automated Git commit, branch, and PR payload assembly (M27). |
| `WorkspacePolicy` | `src/engineering/workspace_policy.py` | **ACTIVE** | Single-write gate and boundary enforcement (M27). |
| `ProjectIndex` | `src/workspace/project_index.py` | **ACTIVE** | Sub-millisecond trigram and AST symbol search (M35). |
| `DuplicateDetector` | `src/engineering/duplicate_detector.py` | **ACTIVE** | Structural AST duplicate detection and anti-drift validation (M35). |
| `CodeEditor` | `src/engineering/code_editor.py` | **ACTIVE** | File editing with backup + rollback. Called by backend. |
| `ASTManager` | `src/engineering/ast_manager.py` | **ACTIVE** | AST analysis. Called by backend. |
| `RepositoryManager` | `src/engineering/repository_manager.py` | **ACTIVE** | Optimized file scanning, called by EngineeringManager. |
| `BugRepairLoop` | `src/engineering/bug_repair.py` | **SCAFFOLDED** | Real code. Superseded by `autonomous_loop.py` in M27. |
| `TestEngine` | `src/engineering/test_engine.py` | **SCAFFOLDED** | Real code. |
| `RefactoringEngine` | `src/engineering/refactoring_engine.py` | **SCAFFOLDED** | Real code. |
| `SymbolGraph` | `src/engineering/symbol_graph.py` | **ACTIVE** | Feeds M18 World Model and M35 analysis. |
| `DependencyGraph` | `src/engineering/dependency_graph.py` | **ACTIVE** | Feeds M18 World Model. |
| `GitIntelligence` | `src/engineering/git_intelligence.py` | **ACTIVE** | Used by `pr_assembler.py` and workspace intelligence. |
| `EngineeringMemory` | `src/engineering/engineering_memory.py` | **ACTIVE** | Integrated with M17 Cognitive Memory. |
| `EngineeringPlanner` | `src/engineering/engineering_planner.py` | **ACTIVE** | Used in engineering supervisor planning. |
| `QualityEngine` | `src/engineering/quality_engine.py` | **ACTIVE** | Available via code.report capability. |

---

## Personal OS Subsystem (M26)

| Module | File | Classification | Notes |
|:---|:---|:---|:---|
| `DailyContextEngine` | `src/personal_os/daily_context.py` | **ACTIVE** | Proactive daily agenda synthesis, calendar, tasks, and environment context. |
| `PersonalOSStateStore` | `src/personal_os/state_store.py` | **ACTIVE** | SQLite-backed persistent state store for user routines and context. |
| `WorkspaceSearchEngine` | `src/personal_os/workspace_search.py` | **ACTIVE** | Inverted index sub-second fuzzy and prefix searching across project workspaces. |
| `TriggerScheduler` | `src/autonomy/trigger_scheduler.py` | **ACTIVE** | Autonomous background daemon dispatching cron, interval, and event-based tasks. |

---

## Integrated Aura OS, CodeAct & Desktop HUDs (M28–M30)

| Module | File | Classification | Notes |
|:---|:---|:---|:---|
| `DynamicCodeActExecutor` | `src/codeact/executor.py` | **ACTIVE** | Code-as-action execution engine, AST validation, sandbox execution. |
| `CodeSandbox` | `src/codeact/drafters.py` | **ACTIVE** | Subprocess containment, multiline fence parsing. |
| `SandboxedPytestRunnerAdapter` | `src/engineering/test_runner.py` | **ACTIVE** | Windows Job Object + `RestrictedUserSandbox` privilege dropping (TD-008). |
| `PySide6 HUD Overlays` | `src/gui/widgets/` | **ACTIVE** | Frameless widgets: SystemMonitor, Weather, AgentTaskStatus, PersonalOSDashboard, ChatWindow. |
| `SmartHomeBackendAdapter` | `src/core/backends/adapters/smarthome_backend.py` | **ACTIVE** | Home Assistant WS/REST + local Tapo KLAP AES-CBC-128 crypto driver (M29). |
| `Holographic AI Core GUI` | `src/gui/main_window.py` | **ACTIVE** | Full Command Center with real-time HUD telemetry, DAG Visualizer, and memory browser (M30). |
| `RealBackendBridge` | `src/gui/real_backend_bridge.py` | **ACTIVE** | Non-blocking Qt signal telemetry bus bridging core runtime state to HUD overlays. |

---

## Memory Subsystem

| Module | File | Classification | Notes |
|:---|:---|:---|:---|
| `Memory` | `Memory.py` | **ACTIVE** | Backward-compatible facade over CognitiveMemoryEngine. |
| `CognitiveMemoryEngine` | `src/memory/cognitive_memory.py` | **ACTIVE** | Central cognitive memory engine. SQLite-backed. |
| `WorkingMemoryManager` | `src/memory/working_memory.py` | **ACTIVE** | Active session context manager. |
| `EpisodicMemoryRecorder` | `src/memory/episodic_memory.py` | **ACTIVE** | Verified session event narrative recorder. |
| `SemanticMemoryStore` | `src/memory/semantic_memory.py` | **ACTIVE** | Concept knowledge graph store. |
| `ProceduralMemoryStore` | `src/memory/procedural_memory.py` | **ACTIVE** | Verified workflow procedure store. |
| `RecallEngine` | `src/memory/recall_engine.py` | **ACTIVE** | Multi-factor candidate scoring & ranking engine. |
| `ConsolidationEngine` | `src/memory/consolidation_engine.py` | **ACTIVE** | Verified post-execution memory consolidation. |
| `DecayEngine` | `src/memory/decay_engine.py` | **ACTIVE** | Retention decay evaluator. |
| `ProjectMemoryFilter` | `src/memory/project_isolation.py` | **ACTIVE** | Project-scoped memory isolation manager. |
| `ContextManager` | `src/brain/context_manager.py` | **ACTIVE** | Active context for LLM calls. |
| `ContextBuilder` | `src/brain/context_builder.py` | **ACTIVE** | Context assembly for prompts. |

---

## Brain / Executive

| Module | File | Classification | Notes |
|:---|:---|:---|:---|
| `AuraBrain` | `src/brain/aura_brain.py` | **ACTIVE** | Executive runtime coordinator (older pipeline layer). |
| `GoalAnalyzer` | `src/brain/goal_analyzer.py` | **ACTIVE** | Goal analysis and decomposition. |
| `CapabilitySelector` | `src/brain/capability_selector.py` | **ACTIVE** | First-layer capability candidate selection. |
| `ExecutionMapGenerator` | `src/brain/execution_map_generator.py` | **ACTIVE** | Dynamic execution plan construction. |
| `ExecutionCoordinator` | `src/brain/execution_coordinator.py` | **ACTIVE** | Cross-subsystem execution coordination. |
| `DMM` | `src/brain/executive/dmm.py` | **ACTIVE** | Decision + Memory Manager. Core decision system. |
| `ExecutiveBrain` | `src/brain/executive/executive_brain.py` | **ACTIVE** | Executive decision layer. |
| `ReflectionEngine` | `src/brain/executive/reflection.py` | **DISCONNECTED** | Rule-based recovery patterns. Not connected to live result flow. |
| `LearningEngine` | `src/brain/executive/learning.py` | **DISCONNECTED** | LearnedItems captured but not persisted to SQLite. |
| `WorldModel` | `src/brain/world_model.py` | **SCAFFOLDED** | Desktop context snapshot only. Becomes WorldStateProvider in M18. |

---

## Research Subsystem

| Module | File | Classification | Notes |
|:---|:---|:---|:---|
| `ResearchEngine` | `src/research/research_engine.py` | **SCAFFOLDED** | 18 modules. Works in isolation. Not on pipeline path. |
| Research providers | `src/research/providers/` | **SCAFFOLDED** | Conditional on API keys (Tavily, GitHub, Wikipedia). |

---

## Voice Subsystem

| Module | File | Classification | Notes |
|:---|:---|:---|:---|
| `VoiceManager` | `src/voice/voice_manager.py` | **ACTIVE** | 9-state machine with streaming TTS handoff and mid-stream steering. |
| `ContinuousVoiceLoop` | `src/voice/continuous_loop.py` | **ACTIVE** | Live full-duplex loop with streaming TTS, active pause/resume, and mid-stream steering. |
| `ResponseSteeringController` | `src/voice/response_steering.py` | **ACTIVE** | Turn boundary snapshotting, successor prompt synthesis, fail-safe 45s watchdog. |
| `ProsodyAwareChunker` | `src/voice/prosody_chunker.py` | **ACTIVE** | Streaming LLM token chunking on natural prosodic boundaries. |
| `ChunkedStreamPlayer` / `OrderedStreamSynthesizer` | `src/voice/tts_manager.py` | **ACTIVE** | Ordered streaming synthesis and zero-latency audio playback. |
| `AcousticEchoSuppressor` | `src/voice/echo_canceller.py` | **SCAFFOLDED** | Unit-tested acoustic echo attenuation with headphone bypass; hardware unverified. |
| `STTManager` | `src/voice/stt_manager.py` | **SCAFFOLDED** | STT engine management. Provider-dependent. |
| `TTSManager` | `src/voice/tts_manager.py` | **ACTIVE** | TTS engine with streaming chunked playback support. |
| `WakeWordManager` | `src/voice/wake_word.py` | **SCAFFOLDED** | Wake word detection. Sensitivity configured. |
| `VoiceActivityDetector` | `src/voice/vad.py` | **SCAFFOLDED** | VAD. Threshold configured. |
| `InterruptionManager` | `src/voice/interruption_manager.py` | **ACTIVE** | Barge-in and response steering primitive with PAUSED/STEERING states. |
| `AudioManager` | `src/voice/audio_manager.py` | **ACTIVE** | Microphone arbitration, software gating & AES reference tap. |

---

## Agent Runtime (Legacy Architecture)

| Module | File | Classification | Notes |
|:---|:---|:---|:---|
| `AgentRuntime` | `src/agents/agent_runtime.py` | **LEGACY** | Superseded by MasterOrchestrator COL. Do not expand. |
| `Planner` (agents) | `src/agents/planner.py` | **LEGACY** | Superseded by TaskDecomposer. |
| `Scheduler` (agents) | `src/agents/scheduler.py` | **LEGACY** | Superseded by WorkerManager. |
| `CodingAgent` | `src/agents/coding_agent.py` | **SCAFFOLDED** | AST-based analysis. Will be integrated in M20. |
| `ResearchAgent` | `src/agents/research_agent.py` | **SCAFFOLDED** | Will be integrated in M21. |
| `DesktopAgent` | `src/agents/desktop_agent.py` | **SCAFFOLDED** | Will be integrated. |
| `VoiceAgent` | `src/agents/voice_agent.py` | **SCAFFOLDED** | Will be integrated in M29. |
| `Collaboration` | `src/agents/collaboration.py` | **DISCONNECTED** | Not called from live path. |
| `LearningAgent` | `src/agents/learning_agent.py` | **DISCONNECTED** | Not called from live path. |

---

## Workflow Engine

| Module | File | Classification | Notes |
|:---|:---|:---|:---|
| `WorkflowEngine` | `src/workflows/workflow_engine.py` | **DISCONNECTED** | Framework is real. `WorkflowEngineAdapter` in ACA is a stub. `src/workflows/` was not reconnected as part of M24 — reconnection deferred to M26 (Personal OS). |
| `TriggerManager` | `src/workflows/trigger_manager.py` | **DISCONNECTED** | `agent_runtime` param is `None`. Not reconnected in M24. |
| `WorkflowScheduler` | `src/workflows/workflow_scheduler.py` | **DISCONNECTED** | Used internally by `WorkflowEngine`. Not on live request path. |
| All other `src/workflows/` | `src/workflows/` | **DISCONNECTED** | Real code. `src/autonomy/` is the M24 Event Runtime; `src/workflows/` reconnection deferred to M26. |

---

## Recently Completed — No Longer Missing

> **Update (September 08, 2026):** The following items were previously listed as MISSING or in-development.
> They are now implemented and classified in their respective subsystem sections.

| Module | Status | Milestone |
|:---|:---|:---|
| Cognitive Memory stores (8 typed stores) | **ACTIVE** | M17 ✅ |
| World Model (multi-provider environment model) | **ACTIVE** | M18 ✅ |
| `CapabilityRegistry` (Universal capability contracts) | **ACTIVE** | M19 ✅ |
| Coding Intelligence 2.0 (AST + Antigravity bridge + repair loop) | **ACTIVE** | M20 ✅ |
| Research & Knowledge Hardening (Evidence grounding, zero-refetch, SSRF filter) | **ACTIVE** | M21 ✅ |
| Multimodal Voice & Vision (Privacy gating, coordinate grounding, multi-engine fallback) | **ACTIVE** | M22 ✅ |
| Autonomous Daemon & Background Operations (Durable state, crash recovery, HMAC tokens) | **ACTIVE** | M23 ✅ |
| Event Runtime & Autonomous Intent Execution (AuraEvent, EventRuntime, Interpreter, PolicyGate, Watchers) | **ACTIVE** | M24 ✅ |
| Security Hardening Track (Phases 1–4, DPAPI, HKDF, Isolated Audit Writer IPC) | **ACTIVE** | Core Security ✅ |
| Professional Expert Systems (SecurityExpert, NetworkExpert, FinancialExpert, SoftwareExpert, ExpertDomainRouter, PlanDAGCompiler, Stage 2.9 MasterOrchestrator routing) | **ACTIVE** | M25 ✅ |
| Personal OS (DailyContextEngine, WorkspaceSearchEngine, TriggerScheduler, PersonalOSStateStore) | **ACTIVE** | M26 ✅ |
| Autonomous Engineering Platform (Closed-loop repair, AST fault localization, safety ceiling, byte-exact rollback, PR assembler) | **ACTIVE** | M27 ✅ |
| Dynamic CodeAct Runtime, Desktop HUD Overlays & Sandboxed Pytest Runner | **ACTIVE** | M28 ✅ |
| Smart Home / IoT Integration & Ambient Desktop HUD Overlays | **ACTIVE** | M29 ✅ |
| Holographic AI Core GUI & Unified Command Center | **ACTIVE** | M30 ✅ |
| Antigravity-Style Subagents (Isolated Background Workers, AsyncRuntime) | **ACTIVE** | M31 ✅ |
| Multi-Task FocusManager (Context switching, SQLite WAL backing, interrupt routing) | **ACTIVE** | M32 ✅ |
| Natural Interaction Layer & Response Steering (Duplex streaming TTS, pause/resume, response.steer) | **ACTIVE** | M33 ✅ |
| Verified UI Macro Compilation, Speculative Pre-Fetching & Proactive Watcher | **ACTIVE** | M34 ✅ |
| Multi-App Vision Grounding & Coordinate Architecture (Decoupled 3-stage coordinate pipeline, KeyPool failover) | **ACTIVE** | M35 ✅ |
| Win32 Desktop Actions Consolidation (AuraToolRegistry delegation to NativeManagerRegistry with fallbacks) | **ACTIVE** | TD-021 ✅ |

## Missing & Disconnected — Audited Gaps

| Module | Classification | Milestone / Status | Notes |
|:---|:---|:---|:---|
| Multi-User & Enterprise Policy Governance | **MISSING** | Future Enterprise Phase | RBAC, Active Directory/LDAP auth, remote telemetry sinks (Splunk, Datadog, Azure Sentinel), and multi-PC LAN mesh coordination ("Distributed Aura Nodes"). |
| `WorkflowEngine` Live Wiring (`src/workflows/`) | **DISCONNECTED** | Architecture Debt | Complete workflow engine exists, but `WorkflowEngineAdapter` in ACA remains an unwired stub returning static dicts; request path does not dispatch here. |
| Executive Reflection & Learning Persistence (`src/brain/executive/`) | **DISCONNECTED** | Architecture Debt | `ReflectionEngine.reflect()` is uncalled on failure paths; `LearningEngine` captures `LearnedItem` records only in ephemeral RAM, never persisting them to SQLite or prompt injection. |
| Hardware Acoustic Echo Suppression (AES) (`src/voice/echo_canceller.py`) | **SCAFFOLDED** | Voice Hardware Track | Algorithmic frequency-domain filtering and headphone bypass unit-tested; open-mic loudspeaker room-impulse calibration remains unverified on physical hardware. |

---

## Decision Rules

Before expanding any module:

1. **Check its classification** in this document
2. If `LEGACY` — do not add new features. Understand why it was superseded first.
3. If `DISCONNECTED` — do not reconnect until the milestone that specifies the reconnection
4. If `SCAFFOLDED` — safe to develop, but confirm the wiring plan before starting
5. If `ACTIVE` — changes affect live behavior. Test before and after.

---

*Last Updated: September 08, 2026*
*Maintained in sync with [`RUNTIME.md`](RUNTIME.md), [`roadmap.md`](roadmap.md), and [`docs/architecture/architecture_status.md`](docs/architecture/architecture_status.md)*
