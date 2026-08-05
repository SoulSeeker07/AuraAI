# Milestone 16 — Intelligent Multi-Agent Coordination & Orchestration

## Goal
Transform Aura from a collection of isolated capabilities into a cohesive, adaptive AI operating platform. Milestone 16 introduces **Intelligent Multi-Agent Coordination**, acting as the central decision-making brain that decomposes goals, selects role-based planners, routes to optimal execution backends, executes independent subtasks in parallel, merges multi-modal results, and updates unified memory.

---

## Core Architectural Principles

1. **Infrastructure Freeze (`v0.15.0-core-platform`)**:
   - Core platform infrastructure is stable. Only bug fixes, documentation, performance, and compatibility updates allowed under `v0.15.x`.
   - Milestone 16 builds **on top** of existing registries and engines without refactoring core contracts.

2. **Role-Based Planners vs. Execution Backends**:
   - **Planners (Roles)**: `Desktop Planner`, `Research Planner`, `Coding Planner`, `Browser Planner`. Planners express intent and required capabilities.
   - **Backends (Executors)**: `Antigravity CLI`, `Claude Code`, `Aider`, `Groq`, `Gemini`, `Native Desktop Engine`. Backends fulfill specific capabilities.
   - *Key Distinction*: `Antigravity CLI` is a **Coding Backend**, NOT a Planner. Planners are backend-agnostic.

3. **Unified Execution Flow**:
   ```text
   User Goal
       │
   Phase 1: Intent & Task Decomposition (Task Graph + Required Capabilities)
       │
   Phase 2: Planner Selection (Desktop, Research, Coding, Browser Planners)
       │
   Phase 3: Backend Selection (Score, Latency, Cost, Health -> Choose Backend)
       │
   Phase 4: Parallel Execution (Concurrent Planner Execution)
       │
   Phase 5: Result Fusion (Observations, Files, Citations, Unified Traces)
       │
   Phase 6: Unified Memory Update (Conversation, Execution, Desktop, Research)
       │
   Final Response
   ```

---

## Detailed Roadmap Phases

### Phase 1 — Intent & Task Decomposition
- **Focus**: Parse user goals into structured dependency graphs (Task Graphs) and required capability sets.
- **Components**:
  - `IntentClassifier`: Multi-intent detection & disambiguation.
  - `TaskDecomposer`: Breaks down complex goals into DAG subtasks with dependency links.
  - `CapabilityRequirementsMap`: Maps subtasks to abstract capability contracts.

### Phase 2 — Planner Selection (Role-Based)
- **Focus**: Route decomposed tasks to domain-specific role planners.
- **Components**:
  - `PlannerRegistry`: Central registry of role-based planners.
  - `DesktopPlanner`: Windows desktop interaction & automation.
  - `ResearchPlanner`: Live search, academic, and codebase RAG analysis.
  - `CodingPlanner`: Code modification, refactoring, linting, and testing.
  - `BrowserPlanner`: Web page navigation, interaction, and data extraction.

### Phase 3 — Backend Routing & Selection
- **Focus**: Dynamically map required capabilities to optimal backend providers.
- **Components**:
  - `BackendRegistry`: Extensible registry for backends (Groq, Gemini, Antigravity CLI, Native Desktop Engine, Aider, etc.).
  - `BackendScorer`: Dynamic scoring based on Capability Fit, Latency, Cost, and Health/Availability.
  - `FallbackRouter`: Graceful fallback if primary backend is unreachable or degraded.

### Phase 4 — Parallel Execution Engine
- **Focus**: Execute non-dependent planners concurrently to minimize end-to-end latency.
- **Components**:
  - `ConcurrentTaskExecutor`: Async graph runner for independent DAG nodes.
  - `ExecutionMonitor`: Real-time state tracking and cancellation propagation across parallel branches.

### Phase 5 — Result Fusion & Response Synthesis
- **Focus**: Consolidate outputs from multiple backends into a coherent response.
- **Components**:
  - `ResultMerger`: Aggregates observations, file changes, search citations, and visual artifacts.
  - `UnifiedTraceLogger`: Generates an end-to-end execution trace for auditability and debugging.

### Phase 6 — Unified Memory Integration
- **Focus**: Persist outcomes across all domain memories through a single unified API.
- **Components**:
  - `UnifiedMemoryAdapter`: Interface to update Conversation Memory, Execution Memory, Desktop Memory, and Research Memory atomically.

---

## First Deliverable: End-to-End Orchestration Demo

**Target Scenario**:
> *"Research Python 3.14 changes, summarize them, open my VS Code project, create a markdown report, and ask Antigravity to update the affected files."*

**Verification Criteria**:
1. Correct intent decomposition into Research + Desktop + Coding subtasks.
2. Concurrent execution of Research Planner (Web/RAG) and Desktop Planner (VS Code launcher).
3. Backend routing: Gemini/Groq for Research, Native Engine for Desktop, Antigravity CLI for Coding.
4. Cohesive result fusion with unified trace output.
5. Successful memory update across all memory layers.
