# AuraAI — System Module Classification

> **Single source of truth for module lifecycle status.**
> Use this before expanding, refactoring, or wiring any module.
> Last updated: August 2026 — Foundation Wiring & Truth Pass

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

---

## Engineering Subsystem

| Module | File | Classification | Notes |
|:---|:---|:---|:---|
| `EngineeringManager` | `src/engineering/engineering_manager.py` | **ACTIVE** | Wired to CodingBackendAdapter in Truth Pass. |
| `CodeEditor` | `src/engineering/code_editor.py` | **ACTIVE** | File editing with backup + rollback. Called by backend. |
| `ASTManager` | `src/engineering/ast_manager.py` | **ACTIVE** | AST analysis. Called by backend. |
| `BugRepairLoop` | `src/engineering/bug_repair.py` | **SCAFFOLDED** | Real code. Not yet called from backend. M20 target. |
| `TestEngine` | `src/engineering/test_engine.py` | **SCAFFOLDED** | Real code. Not yet called from backend. M20 target. |
| `RefactoringEngine` | `src/engineering/refactoring_engine.py` | **SCAFFOLDED** | Real code. Will be used in M20. |
| `RepositoryManager` | `src/engineering/repository_manager.py` | **ACTIVE** | Optimized file scanning, called by EngineeringManager. |
| `SymbolGraph` | `src/engineering/symbol_graph.py` | **SCAFFOLDED** | Real code. Will feed M18 World Model. |
| `DependencyGraph` | `src/engineering/dependency_graph.py` | **SCAFFOLDED** | Real code. Will feed M18 World Model. |
| `GitIntelligence` | `src/engineering/git_intelligence.py` | **SCAFFOLDED** | Real code. Will be wired in M20. |
| `EngineeringMemory` | `src/engineering/engineering_memory.py` | **SCAFFOLDED** | Will integrate with M17 Cognitive Memory. |
| `EngineeringPlanner` | `src/engineering/engineering_planner.py` | **SCAFFOLDED** | Will be used in M20. |
| `QualityEngine` | `src/engineering/quality_engine.py` | **SCAFFOLDED** | Available via code.report capability. |

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
| `VoiceManager` | `src/voice/voice_manager.py` | **SCAFFOLDED** | 9-state machine. Needs live runtime verification. |
| `STTManager` | `src/voice/stt_manager.py` | **SCAFFOLDED** | STT engine management. Provider-dependent. |
| `TTSManager` | `src/voice/tts_manager.py` | **SCAFFOLDED** | TTS engine. Provider-dependent. |
| `WakeWordManager` | `src/voice/wake_word.py` | **SCAFFOLDED** | Wake word detection. Sensitivity configured. |
| `VoiceActivityDetector` | `src/voice/vad.py` | **SCAFFOLDED** | VAD. Threshold configured. |
| `InterruptionManager` | `src/voice/interruption_manager.py` | **SCAFFOLDED** | Barge-in primitive. Not integration-tested. |
| `AudioManager` | `src/voice/audio_manager.py` | **SCAFFOLDED** | Microphone arbitration. Not integration-tested. |

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
| `WorkflowEngine` | `src/workflows/workflow_engine.py` | **DISCONNECTED** | Framework is real. No active workflows. Reconnects at M24. |
| `TriggerManager` | `src/workflows/trigger_manager.py` | **DISCONNECTED** | `agent_runtime` param is typically `None`. |
| `WorkflowScheduler` | `src/workflows/workflow_scheduler.py` | **DISCONNECTED** | Will reconnect at M24. |
| All other `src/workflows/` | `src/workflows/` | **DISCONNECTED** | Real code. Reconnects at M24 (Event Runtime). |

---

## Recently Completed — No Longer Missing

> **Update (August 18, 2026):** The following items were previously listed as MISSING.
> They are now implemented and classified above in their respective subsystem sections.

| Module | Status | Milestone |
|:---|:---|:---|
| Cognitive Memory stores (8 typed stores) | **ACTIVE** | M17 ✅ |
| World Model (multi-provider environment model) | **ACTIVE** | M18 ✅ |
| `CapabilityRegistry` (Universal capability contracts) | **ACTIVE** | M19 ✅ |
| Coding Intelligence 2.0 (AST + Antigravity bridge + repair loop) | **ACTIVE** | M20 ✅ |
| Research & Knowledge Hardening (Evidence grounding, zero-refetch, SSRF filter) | **ACTIVE** | M21 ✅ |
| Multimodal Voice & Vision (Privacy gating, coordinate grounding, multi-engine fallback) | **ACTIVE** | M22 ✅ |
| Autonomous Daemon & Background Operations (Durable state, crash recovery, HMAC tokens) | **ACTIVE** | M23 ✅ |
| Security Hardening Track (Phases 1–4, DPAPI, HKDF, Isolated Audit Writer IPC) | **ACTIVE** | Core Security ✅ |

## Missing — Future Milestones

| Module | Classification | Milestone |
|:---|:---|:---|
| Event Runtime (autonomous triggers, condition evaluators, event loops) | **MISSING** | M24 |
| Professional Expert Systems (Specialized planners for NetEng, Security, Finance) | **MISSING** | M25 |
| Personal OS (Proactive task & schedule management, daily workflows) | **MISSING** | M26 |
| Autonomous Engineering Platform (End-to-end issue to PR pipeline) | **MISSING** | M27 |
| Aura OS Runtime (Unified persistent OS environment) | **MISSING** | M28 |
| Natural Interaction Layer (Full duplex, interruption/barge-in, echo cancellation) | **MISSING** | M29 |
| Aura GUI Command Center (Complete desktop HUD & system visualization) | **MISSING** | M30 |

---

## Decision Rules

Before expanding any module:

1. **Check its classification** in this document
2. If `LEGACY` — do not add new features. Understand why it was superseded first.
3. If `DISCONNECTED` — do not reconnect until the milestone that specifies the reconnection
4. If `SCAFFOLDED` — safe to develop, but confirm the wiring plan before starting
5. If `ACTIVE` — changes affect live behavior. Test before and after.

---

*Last Updated: August 18, 2026*
*Maintained in sync with [`RUNTIME.md`](RUNTIME.md) and [`roadmap.md`](roadmap.md)*
