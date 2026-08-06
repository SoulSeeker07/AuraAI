# Aura Architecture — How Everything Is Connected (v0.19 ACA)

> **CORE PRINCIPLE:**  
> **"The architecture is largely complete. The runtime is not."**  
> Every user request flows through a single cognitive runtime.

---

## 🧊 Architecture Freeze Directive

> [!IMPORTANT]
> **The ACA architecture is now frozen.**
> Do not create new cognitive modules, planners, schemas, or runtime layers unless explicitly approved. All engineering effort must focus on runtime convergence, event-driven execution, continuous world-state updates, real engine integration, production telemetry, and end-to-end validation. Every pull request must increase the percentage of real user requests executed exclusively through the ACA pipeline.

---

## 🔁 Continuous Agent Decision Loop

Aura operates as a continuous decision and re-planning loop rather than a single-pass static planner:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            1. OBSERVE (Perception)                          │
│     ContextManager collects context │ WorldModel updates OS state           │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       2. THINK & STRATEGIZE (DMM + Strategy)                │
│     GoalAnalyzer ──→ CapabilitySelector (queries engine.capabilities)      │
│     FusionEngine fuses retrieval into Thought (DecisionContext)            │
│     StrategyEngine evaluates approach (e.g. reuse open app vs launch new)  │
│     PolicyEngine validates safety & governance                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        3. PLAN & EXECUTE SINGLE STEP                        │
│     ACAPlanner generates ExecutionGraph (DAG with parallel branches)       │
│     ExecutionCoordinator checks Engine Health (READY/BUSY/FAILED)          │
│     ExecutionCoordinator resolves EngineAdapter via EngineRegistry          │
│     Engine executes step 1                                                  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      4. OBSERVE MID-STEP & RE-PLAN                          │
│     WorldModel.refresh() updates OS state (e.g. Chrome=Closed → Running)   │
│     Did step fail or state change? ─── YES ──► Re-plan strategy / fallback  │
│                                  │                                          │
│                                  NO                                         │
│                                  ▼                                          │
│     More steps remaining? ────────── YES ───► Loop to execute next step     │
│                                  │                                          │
│                                  NO                                         │
│                                  ▼                                          │
┌─────────────────────────────────────────────────────────────────────────────┐
│                       5. VERIFY, REFLECT & LEARN                            │
│     VerificationEngine validates outcome │ ArtifactManager creates artifacts │
│     ReflectionEngine evaluates recovery │ LearningEngine saves facts        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🧠 Full Architecture Connection Diagram

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER (CLI / GUI / Voice)                       │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AuraCore Runtime (OS Kernel)                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  process_request() / process_via_executive_brain()                   │  │
│  └──────────────────────────────────┬────────────────────────────────────┘  │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Aura Cognitive Architecture (ACA)                        │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                   BLACKBOARD (Shared CognitiveState)                 │  │
│  │  user_input │ context │ world │ goal │ capabilities │ confidence     │  │
│  │  decision_context (Thought) │ strategy │ execution_graph │ validation │  │
│  │  coordination │ verification │ reflection │ learned │ artifacts      │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────── STAGE 0: PERCEPTION ─────────────────────────────────┐   │
│  │  ContextManager ──→ ContextSnapshot                                 │   │
│  │  WorldModel ──────→ WorldState (refreshed after every step)         │   │
│  └──────────────────────────┬───────────────────────────────────────────┘   │
│                             │                                             │
│  ┌─────────────── GOAL MANAGER (Long-Term Goals) ──────────────────────┐   │
│  │  GoalManager ──→ Goal (status, progress, sessions, artifacts)       │   │
│  └──────────────────────────┬───────────────────────────────────────────┘   │
│                             │                                             │
│  ┌─────────────── STAGE 1: DMM (DECISION) ─────────────────────────────┐   │
│  │  GoalAnalyzer ──→ GoalAnalysis                                       │   │
│  │  CapabilitySelector ──→ Queries engine.capabilities dynamically      │   │
│  │  MemoryRetrieval ──→ MemoryFacts                                     │   │
│  │  ConfidenceGate ──→ per-domain scores                                │   │
│  │  FusionEngine ──→ Thought (DecisionContext)                          │   │
│  └──────────────────────────┬───────────────────────────────────────────┘   │
│                             │                                             │
│  ┌─────────────── STAGE 1.5: STRATEGY ─────────────────────────────────┐   │
│  │  StrategyEngine ──→ Evaluates high-level reasoning & fallback rules │   │
│  └──────────────────────────┬───────────────────────────────────────────┘   │
│                             │                                             │
│  ┌─────────────── POLICY ENGINE (Governance) ──────────────────────────┐   │
│  │  PolicyEngine ──→ Approved? (safety, permissions, policies)         │   │
│  └──────────────────────────┬───────────────────────────────────────────┘   │
│                             │                                             │
│  ┌─────────────── STAGE 2: PLANNING ───────────────────────────────────┐   │
│  │  ACAPlanner ──→ ExecutionGraph (DAG with parallel execution branches)│   │
│  │  ExecutionMapValidator ──→ ValidationResult                          │   │
│  └──────────────────────────┬───────────────────────────────────────────┘   │
│                             │                                             │
│  ┌─────────────── RUNTIME SESSION (Source of Truth) ───────────────────┐   │
│  │  RuntimeSession ──→ status, progress, artifacts, pause/resume       │   │
│  └──────────────────────────┬───────────────────────────────────────────┘   │
│                             │                                             │
│  ┌─────────────── STAGE 3: EXECUTION COORDINATION ────────────────────┐   │
│  │  ExecutionCoordinator ──→ Checks Health (READY/BUSY/FAILED) &        │   │
│  │                           resolves via EngineRegistry / Adapters     │   │
│  │  VerificationEngine ──→ VerificationReport                           │   │
│  └──────────────────────────┬───────────────────────────────────────────┘   │
│                             │                                             │
│  ┌─────────────── ARTIFACT MANAGER (Everything creates artifacts) ─────┐   │
│  │  ArtifactManager ──→ ResearchArtifact, CodeArtifact, etc.           │   │
│  └──────────────────────────┬───────────────────────────────────────────┘   │
│                             │                                             │
│  ┌─────────────── STAGE 4: REFLECTION & LEARNING ──────────────────────┐   │
│  │  ReflectionEngine ──→ ReflectionOutcome                              │   │
│  │  LearningEngine ──→ LearnedItems (conservative)                      │   │
│  └──────────────────────────┬───────────────────────────────────────────┘   │
│                             │                                             │
│  ┌─────────────── RESPONSE ────────────────────────────────────────────┐   │
│  │  ACAResponse ──→ text + session + goal + artifacts                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           EngineRegistry (Health Monitoring & Capability Discovery)         │
│  EngineRegistry.get_instance().resolve(name)                                │
│  Engine health: [ READY | BUSY | FAILED | DISABLED | OFF ]                  │
│  Self-advertising capabilities: engine.capabilities                         │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Engine Adapters (src/brain/aca/engine_adapters.py)     │
│  DesktopEngineAdapter │ BrowserEngineAdapter │ ResearchEngineAdapter        │
│  EngineeringEngineAdapter │ VoiceEngineAdapter │ VisionEngineAdapter        │
│  MemoryEngineAdapter │ WorkflowEngineAdapter │ PluginEngineAdapter          │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Native Subsystem Implementations                     │
│  DesktopExecutionEngine │ Playwright BrowserEngine │ ResearchEngine        │
│  EngineeringManager │ VoiceManager │ VisionManager │ Memory2.0              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Event-Driven Decoupling (`EventBus`)

In addition to synchronous execution, system events are published to `EventBus`:

```text
Desktop / Browser / System Event (e.g. "Chrome launched with HWND 12345")
  │
  ▼
EventBus.publish("app_opened", {app: "chrome", hwnd: 12345})
  │
  ├──► WorldModel.update() ──→ Updates process & window state
  ├──► RuntimeSession ────────→ Updates active step status
  ├──► ReflectionEngine ──────→ Evaluates recovery / fallback options
  ├──► User Interfaces ───────→ Notifies GUI & Voice clients
  └──► LearningEngine ────────→ Records confirmed interaction patterns
```

---

## 📖 Canonical Architectural Terminology

To eliminate terminology drift across docs, code, and discussions, Aura strictly adheres to the following canonical terms:

| Canonical Term | Definition | Maps To / Replaces |
| -------------- | ---------- | ------------------ |
| **Blackboard** | Shared mutable state for perception, planning, coordination, and reflection. | `CognitiveState` dataclass |
| **Thought** | Fused decision context containing goal, context, world, memory, safety, and confidence. | `DecisionContext` schema |
| **StrategyEngine** | High-level reasoning stage determining optimal approach before step-by-step planning. | Strategy Stage (Stage 1.5) |
| **ACAPlanner** | Converts `Thought` and `Strategy` into execution graphs. | `ACAPlanner` module |
| **ExecutionGraph** | Directed Acyclic Graph (DAG) supporting parallel execution branches. | Evolved `ExecutionMap` / `TaskGraph` |

---

## 🔒 Governance & Connection Rules

1. **Architecture Freeze**: The ACA architecture is frozen. No new cognitive layers or schemas without explicit approval. Focus 100% on runtime convergence.
2. **Single Entrypoint**: All user requests enter through `AuraCore.process_request()`.
3. **Single Cognitive Runtime**: ACA is the sole cognitive orchestrator. Direct engine calls bypassing ACA are prohibited.
4. **Shared Blackboard**: All stages read from and write to `Blackboard` (`CognitiveState`).
5. **Long-Term Goals**: Every execution is tied to a `Goal` managed by `GoalManager`.
6. **Governance Gate**: `PolicyEngine` validates safety before planning.
7. **Strategy vs Planner**: `StrategyEngine` determines approach; `ACAPlanner` generates `ExecutionGraph` steps.
8. **Execution Coordinator & Engine Adapters**: `ExecutionCoordinator` is the ONLY allowed caller to resolve engines via `EngineRegistry` / `engine_adapters.py`.
9. **Engine Health & Discovery**: `EngineRegistry` tracks engine health (`READY`, `BUSY`, `FAILED`, `DISABLED`, `OFF`) and queries `engine.capabilities`.
10. **Mid-Step World Refresh**: `WorldModel.refresh()` updates OS state after each step in the continuous decision loop.
11. **CI Guardrail Allow-List**: Direct engine instantiations outside `ExecutionCoordinator` are isolated in `ENGINE_ALLOWLIST` with explicit `reason`, `owner`, and `milestone` metadata.