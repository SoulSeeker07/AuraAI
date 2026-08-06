# Aura AI Operating System — Platform System Contract
Location: `docs/SYSTEM_CONTRACT.md`

**Version:** `v0.18.0-runtime-stabilization`  
**Status:** 📜 PLATFORM CONSTITUTION  

This document specifies the non-negotiable architectural principles, operational rules, and execution contracts of the Aura AI Operating System Platform.

---

## 🏛️ Core Architectural Principles

### 1. World State Inspection Priority
Aura AI **never assumes** OS, browser, workspace, or application state. It MUST inspect the live environment using `WorldSnapshot` and `WorldStateProbe` before planning or taking action.

### 2. Cognitive Separation of Powers
Groq acts exclusively as the **Executive Cognitive Coordinator (Project Manager)**. It understands intent, decomposes goals, and coordinates domain supervisors. Groq **NEVER** outputs raw Python code snippets or directly executes desktop/browser manipulation commands into user chat.

### 3. Delegated Engineering Execution
All software development, refactoring, and code synthesis tasks MUST be delegated to the `SoftwareEngineeringSupervisor` and executed via `Antigravity CLI` running in its own terminal/workspace session with asynchronous validation workers (`PytestWorker`, `RuffWorker`, `GitDiffWorker`).

### 4. Mandatory Unified RuntimeSession Usage
Every long-running operation across any domain (Engineering, Browser, Desktop, Research, Voice) MUST be encapsulated within a `RuntimeSession` subclass (`EngineeringSession`, `BrowserSession`, `DesktopSession`, `ResearchSession`) registered with `WorkerManager`.

### 5. Extension over Core Invention
New capabilities MUST extend existing contract registries (`PlannerRegistry`, `BackendRegistry`, `CapabilityRegistry`) by implementing `BasePlanner` or `BaseBackendAdapter`. Contributors MUST NOT create duplicate orchestrators or parallel registries in `src/routing/` or `src/execution/`.

### 6. Verifiable Execution Results
Every execution backend MUST return a structured `ExecutionResult` / `DesktopResult` carrying execution metrics, observations, artifacts, and verifiable status (`SUCCESS`, `FAILED`, `CANCELLED`).

### 7. Configurable Safety Enforcement
All native OS and window operations MUST respect `SafetyPolicy` (`config/safety_policy.yaml`). Protected applications (`Code.exe`, `vscode`, `explorer.exe`, `System`) MUST NOT be terminated without explicit user override.

### 8. Strict Quality & Release Gate
Every milestone and pull request MUST satisfy the **[Definition of Done](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/docs/DEFINITION_OF_DONE.md)** and pass all static analysis, linting, type-checking, architecture tests, and unit tests via `python aura.py --verify`.
