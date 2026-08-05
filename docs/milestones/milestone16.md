# Milestone 16 — Cognitive Orchestration Layer

## Goal
Transform Aura into a cohesive, adaptive AI operating platform. Milestone 16 introduces the **Cognitive Orchestration Layer**, acting as Aura's executive brain that evaluates budget limits, recalls memory, reasons and checks safety policies via a `DecisionEngine`, decomposes goals via a `Cognitive Supervisor`, routes to optimal backends, executes subtasks in parallel within an `AgentSession`, merges `Observation` and `Artifact` models, and persists outcomes.

---

## Core Operating System Primitives

1. **Agent Session (`AgentSession`)**:
   - Acts as Aura's **Operating System Process** ([`src/core/orchestration/agent_session.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/agent_session.py)).
   - Carries session ID, goal, execution budget, memory context, observations, artifacts, trace, and metrics across the pipeline.

2. **Execution Budget (`ExecutionBudget`)**:
   - Enforces execution limits: `max_time_seconds`, `max_cost_usd`, `max_backends`, `allow_parallel`, `local_only`, and `offline_mode`.

3. **Observation Model (`Observation`)**:
   - Standardized observation model ([`src/core/orchestration/observation.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/observation.py)) returned by all role planners and backends instead of arbitrary dictionaries.

4. **Unified Artifact Store (`Artifact`)**:
   - Standardized artifact model ([`src/core/orchestration/artifact.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/artifact.py)) capturing created files, markdown reports, patches, screenshots, and citations.

5. **Decision Engine (`DecisionEngine`)**:
   - Executive decision engine ([`src/core/orchestration/decision_engine.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/decision_engine.py)) handling reasoning, risk checks, budget enforcement, and memory policies.

---

## Architecture & Single Sources of Truth

- **Master Orchestrator**: [`src/core/orchestration/master_orchestrator.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/master_orchestrator.py)
- **Planner Registry**: [`src/core/orchestration/planner_registry.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/planner_registry.py)
- **Backend Registry**: [`src/core/backends/backend_registry.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/backend_registry.py)
- **Antigravity CLI Adapter**: [`src/core/backends/adapters/antigravity_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/antigravity_backend.py)

---

## 7-Stage Cognitive Execution Pipeline

```text
Goal + ExecutionBudget
    │
Stage 1: Memory Recall (Context pre-fetch)
    │
Stage 2: Executive Decision Engine (Reasoning, Risk, Budget, Policy)
    │
Stage 3: Task Graph Decomposition (TaskDecomposer DAG generation)
    │
Stage 4: Cognitive Supervisor Delegation (SupervisorAgent -> Role Planners)
    │
Stage 5: Backend Selection & Parallel Execution (BackendRegistry -> Adapters)
    │
Stage 6: Result Fusion & Observation Merging (ResultMerger -> AgentSession)
    │
Stage 7: Unified Memory Write (Persist outcomes)
```

---

## End-to-End Orchestration Demo

**Run Command**:
```bash
.venv\Scripts\python examples/orchestration_demo.py
```

---

## Status & Freeze Summary

**Status:** ✅ COMPLETE (100%)

The core contracts for the Cognitive Orchestration Layer are frozen:
- `AgentSession` & `ExecutionBudget`
- `Observation` & `Artifact`
- `DecisionEngine` & `SupervisorAgent`
- `PlannerRegistry` & `BackendRegistry`
- `MasterOrchestrator` & `ResultMerger`

Future milestones will build domain capabilities (Coding, Browser, Research, Event-driven runtime) on top of this stable foundation.

