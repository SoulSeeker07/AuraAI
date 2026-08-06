# Aura AI Operating System — Platform Architecture Freeze

**Version:** `v0.15.0-core-platform` + `Milestone 16 (Cognitive Orchestration Layer)`  
**Status:** 🔒 FROZEN PLATFORM CONSTITUTION  
**Last Updated:** August 2026  

---

## 🏛️ Layered Architecture Overview

Aura AI operates as a modular, 5-layer AI Operating System. Component boundaries and contracts are strictly enforced.

```text
Application Layer
─────────────────────────────────────────────────────────────────
GUI Client | CLI Client | API Server

Cognitive Orchestration Layer (Milestone 16)
─────────────────────────────────────────────────────────────────
MasterOrchestrator  |  DecisionEngine  |  SupervisorAgent  |  TaskDecomposer
PlannerRegistry     |  BackendRegistry |  ResultMerger     |  AgentSession
ExecutionBudget     |  Observation     |  Artifact         |  ExecutionResult

Planning Layer (Role-Based)
─────────────────────────────────────────────────────────────────
DesktopPlanner  |  ResearchPlanner  |  CodingPlanner  |  BrowserPlanner

Execution Layer (Backend Adapters)
─────────────────────────────────────────────────────────────────
Desktop Engine  |  Groq  |  Gemini  |  Antigravity CLI  |  Claude Code  |  Aider

Infrastructure Layer
─────────────────────────────────────────────────────────────────
Memory 2.0  |  Desktop Context  |  Capability Graph  |  Event Bus
Diagnostics |  Verification     |  Security Protocols
```

---

## 🔒 Frozen Core Platform APIs (`src/core/`)

Contributors **MUST NOT** alter the core signatures or introduce duplicate abstractions for the following frozen platform APIs located in `src/core/`:

| API / Class | Primary File | Description |
| :--- | :--- | :--- |
| `MasterOrchestrator` | [`src/core/orchestration/master_orchestrator.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/master_orchestrator.py) | Master entry point executing the 7-stage cognitive pipeline. |
| `DecisionEngine` | [`src/core/orchestration/decision_engine.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/decision_engine.py) | Pre-execution cognitive reasoning, risk evaluation, and budget policy enforcement. |
| `SupervisorAgent` | [`src/core/orchestration/supervisor_agent.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/supervisor_agent.py) | High-level cognitive supervisor delegating subtasks to domain role planners. |
| `TaskDecomposer` | [`src/core/orchestration/task_decomposer.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/task_decomposer.py) | Goal parsing into Directed Acyclic Graphs (DAG) of subtasks. |
| `PlannerRegistry` | [`src/core/orchestration/planner_registry.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/planner_registry.py) | Single centralized registry for domain role planners. |
| `BackendRegistry` | [`src/core/backends/backend_registry.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/backend_registry.py) | Single centralized registry for execution backends and dynamic scoring. |
| `AgentSession` | [`src/core/orchestration/agent_session.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/agent_session.py) | OS Process context thread carrying goal, budget, state, observations, and artifacts. |
| `ExecutionBudget` | [`src/core/orchestration/agent_session.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/agent_session.py) | Execution constraints: time limits, cost limits, local-only, and offline modes. |
| `Observation` | [`src/core/orchestration/observation.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/observation.py) | Standardized structured observation model returned by planners and backends. |
| `Artifact` | [`src/core/orchestration/artifact.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/artifact.py) | Universal output model (files, patches, reports, screenshots, citations). |
| `BasePlanner` | [`src/core/planning/base_planner.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/planning/base_planner.py) | Abstract contract implemented by all role planners. |
| `BaseBackendAdapter` | [`src/core/backends/base_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/base_backend.py) | Abstract contract implemented by all backend execution engines. |

---

## 📜 Architecture Decision Records (ADRs) & Release Gate

All major architectural design choices are formally documented in [`docs/adr/`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/docs/adr/):
- **[ADR 0001: 5-Layer AI Operating System Architecture](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/docs/adr/0001-5-layer-architecture.md)**
- **[ADR 0002: Cognitive Orchestration Layer & Groq Executive Role](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/docs/adr/0002-cognitive-orchestration.md)**
- **[ADR 0003: Unified RuntimeSession Hierarchy](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/docs/adr/0003-runtime-session.md)**
- **[ADR 0004: System-Wide WorkerManager Subsystem](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/docs/adr/0004-worker-manager.md)**
- **[ADR 0005: Software Engineering Supervisor & Antigravity Worker](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/docs/adr/0005-antigravity-supervisor.md)**
- **[ADR 0006: Configurable SafetyPolicy Engine](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/docs/adr/0006-safety-policy.md)**

Every future milestone must satisfy the **[Definition of Done](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/docs/DEFINITION_OF_DONE.md)** and pass manual acceptance gates in **[Runtime Acceptance](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/docs/RUNTIME_ACCEPTANCE.md)** before merging into release branches.

---


## 🚫 Non-Negotiable Architectural Rules

1. **Zero Duplicate Registries**:
   - There is **ONE** `PlannerRegistry` (`src/core/orchestration/planner_registry.py`).
   - There is **ONE** `BackendRegistry` (`src/core/backends/backend_registry.py`).
   - **Do NOT** create parallel registries in `src/routing/` or `src/execution/`.

2. **Zero Duplicate Orchestrators**:
   - There is **ONE** `MasterOrchestrator` (`src/core/orchestration/master_orchestrator.py`).
   - **Do NOT** create alternative master orchestrators or workflow wrappers outside `src/core/`.

3. **Backend Separation**:
   - Backends are **executors**, NOT planners.
   - For example, `Antigravity CLI`, `Claude Code`, `Aider`, and `Groq` are registered inside `BackendRegistry`, never inside `PlannerRegistry`.

4. **Extension over Invention**:
   - When adding a feature, ask: *"Can this be implemented by extending existing contracts?"*
   - If yes, implement a new `BaseBackendAdapter` or `BasePlanner` without modifying the core pipeline contracts.

5. **The "No New Core" Rule**:
   - If a feature can be implemented by extending:
     - `BasePlanner`
     - `BaseBackendAdapter`
     - `DecisionEngine`
     - `MasterOrchestrator`
     - `AgentSession`
     - `Observation`
     - `Artifact`
   - **DO NOT** create a new core abstraction. Extend the existing ones.


---

## 🔌 Extension Guides

### 1. How to Add a New Execution Backend Adapter
To add a new coding, research, or browser backend (e.g. `Claude Code` or `Playwright`):
1. Inherit from `BaseBackendAdapter` in [`src/core/backends/base_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/base_backend.py).
2. Place the file inside `src/core/backends/adapters/`.
3. Implement `name`, `capabilities`, `describe()`, `health_check()`, and `execute()`.
4. Register the adapter in `BackendRegistry.get_instance().register(YourAdapter())`.

### 2. How to Add a New Domain Role Planner
1. Inherit from `BasePlanner` in [`src/core/planning/base_planner.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/planning/base_planner.py).
2. Implement `can_handle()`, `create_plan()`, `optimize_plan()`, `execute_plan()`, and `explain_plan()`.
3. Register the role in `PlannerRegistry.get_instance().register("role_name", YourPlanner())`.

---

## 📌 Versioning & Change Policy
- **Minor Updates (`v0.15.x`)**: Maintenance, bug fixes, performance improvements, documentation.
- **Breaking API Changes**: Require formal RFC, architecture review, and major version bump.
