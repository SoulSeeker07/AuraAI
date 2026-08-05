# AuraAI Core Runtime Architecture Freeze (v17.0)

This document formalizes the **Core Runtime Architecture Freeze** for AuraAI. The core abstractions, contracts, and orchestration pipelines documented below constitute the immutable platform kernel. 

> ⚠️ **Platform Contract Rule**: **Do not redesign or rewrite these core classes. Extend them.**

---

## 🏛️ Frozen Platform Contracts & Core Abstractions

| Component | Module Location | Responsibility | Extension Pattern |
| :--- | :--- | :--- | :--- |
| **`MasterOrchestrator`** | `src/core/orchestration/master_orchestrator.py` | 7-Stage Cognitive Orchestration Pipeline entry point. | Register new planners/backends; do not alter pipeline stages. |
| **`DecisionEngine`** | `src/core/orchestration/decision_engine.py` | Intent classification, risk assessment, budget evaluation, 5-question planner decision tree. | Add new `IntentType` enum values; do not alter evaluation flow. |
| **`DecisionTrace`** | `src/core/orchestration/decision_engine.py` | Captures step-by-step reasoning steps, policy applied, and confidence. | Add metadata fields to `to_dict()`. |
| **`SupervisorAgent`** | `src/core/orchestration/supervisor_agent.py` | Delegator routing requests to role planners registered in `PlannerRegistry`. | Add new planner role mappings. |
| **`PlannerRegistry`** | `src/core/orchestration/planner_registry.py` | Central registry for role planners (`desktop`, `browser`, `coding`, `research`). | Call `register_planner()` to add custom role planners. |
| **`BackendRegistry`** | `src/core/backends/backend_registry.py` | Central registry for backend adapters (`Native Desktop Engine`, `Playwright Browser Engine`, etc.). | Implement `BaseBackendAdapter` and call `register_adapter()`. |
| **`AgentSession`** | `src/core/orchestration/agent_session.py` | Aura Operating System Process context carrying observations, artifacts, budget, and metrics. | Add context fields to `to_dict()`. |
| **`ExecutionBudget`** | `src/core/orchestration/agent_session.py` | Time, cost, concurrency, and policy constraints. | Configure via input parameters. |
| **`WorldSnapshot`** | `src/core/orchestration/world_snapshot.py` | Real-time OS process and window state snapshot (`DesktopStateSnapshot`). | Add new context models to `WorldSnapshotProvider`. |
| **`WorldDiff` / `WorldDiffEngine`** | `src/core/orchestration/world_diff.py` | Calculates real-time state deltas (new/closed processes, new/closed tabs, window focus). | Extend diff metrics. |
| **`WorldTimeline`** | `src/core/orchestration/world_timeline.py` | Chronological event log tracking OS and browser state changes over time. | Call `WorldTimeline.get_instance().record_event()`. |
| **`BrowserContext`** | `src/browser/world_model.py` | Real-time browser tab context, domain mapping, and semantic category inference. | Extend `BrowserTab` metadata fields. |
| **`ResourceOwnershipTracker`** | `src/core/orchestration/ownership_tracker.py` | Tracks ownership (`ResourceOwner.AURA` vs `ResourceOwner.USER`) and creation reasons. | Register new resource types via `register_resource()`. |
| **`SessionReplay`** | `src/core/orchestration/session_replay.py` | Trajectory reconstruction and human-readable explanation engine. | Extend explanation formats. |

---

## 🎯 Architectural Principles & Laws

1. **State Reuse First**:
   `Inspect World → Reuse State → Modify State → Create New State`
   Always inspect existing windows, tabs, processes, and sessions before spawning new ones.

2. **Ownership Protection**:
   Aura tags every created resource with `ResourceOwner.AURA`. Pre-existing items default to `ResourceOwner.USER`. When asked to *"Close everything you opened"*, Aura closes **only** Aura-owned resources.

3. **Deterministic Self-Knowledge**:
   Every request automatically receives the **Self-Knowledge Context Layer** (`aura_identity`, `capability_catalog`, `planner_catalog`, `world_state`, `world_diff`, `resource_ownership`).

4. **100% Explainability**:
   Every `AgentSession` records a `DecisionTrace` and `WorldTimeline` events, allowing Aura to answer *"Why did you do that?"* or *"Why didn't you close Spotify?"*.

---

## 🚀 Future Milestone Extension Strategy

All future development extends these frozen contracts rather than rewriting orchestrators or registries:

- **Milestone 17 (Cognitive Memory)**: Implements `MemoryPlanner` registered in `PlannerRegistry`.
- **Milestone 18 (World Knowledge Graph)**: Integrates into `WorldSnapshot` and `DecisionEngine`.
- **Milestone 19 (CLI & Agent Adapters)**: Implements `BaseBackendAdapter` for Claude Code, Aider, OpenHands in `BackendRegistry`.
- **Milestone 20 (Browser Intelligence)**: Extends `BrowserGoalPlanner` and `BrowserContext`.

---

*Architectural Freeze Approved & Established — AuraAI v17.0 Runtime Kernel*
