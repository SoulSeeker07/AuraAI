# Aura Runtime Specification v1
Location: `docs/AURA_RUNTIME_SPECIFICATION_V1.md`

This document specifies the strict architectural boundaries, single responsibility principles, and execution contracts of the Aura AI Operating System. No module is permitted to exceed its defined scope.

---

## 🧠 Core Pipeline Stages & Components

### 1. DecisionEngine
- **Description**: Classifies the high-level intent and capability routing of a user's natural language goal.
- **Input**: Natural language query string (goal text) and active session context.
- **Output**: An intent classification (e.g. `IntentType.DESKTOP_ACTION`, `IntentType.BROWSER`) and a capability marker.
- **Ownership Scope**:
  - Mapping inputs to the high-level intent categories.
  - Negotiating intent-to-capability routing.
- **Prohibitions (Cannot)**:
  - Decompose tasks or construct execution DAGs.
  - Interact with or query memory databases directly.
  - Invoke execution backends or execute actions.
  - Call LLM API providers directly.

**Forbidden Actions**:
- Launch applications
- Perform OS-level window management
- Access Memory directly
- Execute LLM calls
- Directly modify RuntimeSession state

### 2. TaskDecomposer
- **Description**: Analyzes intent outcomes and decomposes complex user instructions into sequentially chained subtasks.
- **Input**: User goal text and the decision outcome from the DecisionEngine.
- **Output**: A structured `TaskGraph` containing dependencies and capabilities.
- **Ownership Scope**:
  - Sentence clause-splitting (e.g., separating sequential operations).
  - Binding subtasks to correct `PlannerRole` and capabilities.
  - Sequencing subtask dependency paths.
- **Prohibitions (Cannot)**:
  - Recall or query conversational memory.
  - Call external LLM APIs.
  - Interact with physical operating system windows or tools.

**Forbidden Actions**:
- Access Memory subsystem
- Launch applications
- Perform browser navigation
- Execute LLM calls

### 3. MasterOrchestrator
- **Description**: Central coordinator directing the cognitive stage workflow.
- **Input**: Raw natural language goal, preferred planner, execution budget.
- **Output**: The final structured `ExecutionResult`.
- **Ownership Scope**:
  - Directing request execution flow from Stage 1 through Stage 7.
  - Intercepting and resolving user answers to pending confirmations before intent parsing.
  - Handling telemetry, session metrics logging, and result merging.
- **Prohibitions (Cannot)**:
  - Perform domain-specific operations (e.g., launching apps or calling Playwright).
  - Define custom intent classification rules or hardcode regexes.

**Forbidden Actions**:
- Directly invoke backends
- Modify Memory
- Execute LLM calls
- Perform OS-level operations

### 4. ReferenceResolver
- **Description**: Resolves ambiguous conversational pronouns against active context and timeline history.
- **Input**: Raw user goal text and active context snapshot dictionary.
- **Output**: Resolved goal text with concrete names substituting pronouns (e.g. `"open it"` → `"open Chrome"`).
- **Ownership Scope**:
  - Resolving pronouns (`it`, `that`, `them`, `this`, `the app`).
  - Probing focused win32 handles, timeline history, and resource ownership tracking.
- **Prohibitions (Cannot)**:
  - Launch applications or close windows.
  - Interact with web browser engines.
  - Invoke LLMs.

**Forbidden Actions**:
- Launch apps
- Perform browser navigation
- Access Memory

### 5. Memory Subsystem
- **Description**: Manages long-term preference facts and short-term conversation logs.
- **Input**: Facts/messages to write, or lookup query terms.
- **Output**: Retained facts list or formatted context snippet.
- **Ownership Scope**:
  - SQLite facts table storage and vector-like similarity searches.
  - Context snippet construction matching query keywords.
- **Prohibitions (Cannot)**:
  - Summarize sessions (session summary is owned by `RuntimeSession`).
  - Execute actions or plan steps.
  - Mutate state during read-only recall phases.

**Forbidden Actions**:
- Launch applications
- Perform OS-level changes
- Directly modify RuntimeSession

### 6. DesktopBackend
- **Description**: Platform adapter for native OS operations.
- **Input**: A targeted capability (e.g., `app_open`, `window.minimize`) and named arguments.
- **Output**: Verifiable `DesktopResult` / `ExecutionResult`.
- **Ownership Scope**:
  - Running native Windows API calls (win32gui, WScript key simulation).
  - Evaluating safety policies against desktop targets.
- **Prohibitions (Cannot)**:
  - Direct browser page navigation or web searches.
  - Write to or read from the user preference Memory database directly.
  - Decide user intent.

**Forbidden Actions**:
- Launch browsers
- Access Memory
- Perform intent classification

### 7. BrowserBackend
- **Description**: Platform adapter for Playwright browser automation.
- **Input**: Browser-specific capability (e.g., `browser.navigate`, `browser.click`) and page target arguments.
- **Output**: Structured `ExecutionResult` with observations.
- **Ownership Scope**:
  - Controlling active Chrome tabs, extracting elements, and scraping pages.
- **Prohibitions (Cannot)**:
  - Launch Chrome as a native OS-level application (launching is delegated to Desktop).
  - Interact with non-browser OS windows (e.g., notepad, calculator).
  - Write to or read from the Memory database directly.

**Forbidden Actions**:
- Launch applications
- Access Memory
- Perform OS-level operations

### 8. RuntimeSession / AgentSession
- **Description**: Tracks the timeline, events, and metrics of a single execution flow.
- **Input**: Timeline events and metrics.
- **Output**: Current session snapshot and execution logs.
- **Ownership Scope**:
  - Recording transient timeline logs.
  - Creating first-class `SessionSummaryArtifact` reports.
- **Prohibitions (Cannot)**:
  - Persist long-term facts across separate process invocations.

**Forbidden Actions**:
- Store persistent facts
- Modify Memory
- Directly influence other backends
