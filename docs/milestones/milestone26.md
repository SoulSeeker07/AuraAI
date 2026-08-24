# Milestone 26 — Personal Operating System (`v0.30.0`)

## Goal
Milestone 26 establishes AuraAI as a **Personal Operating System**, introducing proactive daily context synthesis, sub-second workspace search indexing, autonomous background event trigger scheduling, and persistent OS state management under strict request source classification and governance.

---

## 1. Five Verified Acceptance Gates

| Gate | Focus Area | Deliverables & Verified Architectural Invariants | Test File |
| :--- | :--- | :--- | :--- |
| **G1** | **Request Source Classification & Governance** | `RequestSource` enum (`HUMAN_INTERACTIVE`, `TRIGGER_AUTONOMOUS`, `DAEMON_BACKGROUND`, `AGENT_DELEGATED`); `ContextVar`-scoped autonomy level isolation (`_autonomy_level_ctx`) resolving race conditions in concurrent request execution; strict domain ceiling enforcement (`trigger_allowed_domains`). | `tests/test_personal_os_g1.py` (7 tests) |
| **G2** | **Proactive Daily Context Synthesis** | `DailyContextEngine` assembling daily briefings (calendar events, priority tasks, stale file detection, recent research) with caching and `PersonalOSBackend` routing through `MasterOrchestrator`. | `tests/test_personal_os_g2.py` (4 tests) |
| **G3** | **Sub-Second Workspace Search** | `WorkspaceSearchEngine` with in-memory inverted index and SQLite document cache delivering sub-100ms query latency; live incremental file synchronization via `FileSystemWatcher`. | `tests/test_personal_os_g3.py` (5 tests) |
| **G4** | **Autonomous Trigger Engine** | `TriggerScheduler` executing cron, interval, and event triggers with template parameter interpolation (`TriggerTemplateRegistry`) and fail-closed cryptographic audit logging. | `tests/test_personal_os_g4.py` (3 tests) |
| **G5** | **OS State Persistence & Migration** | `PersonalOSStateStore` managing SQLite-backed state transitions, schema version bumps, and reboot recovery with zero state loss. | `tests/test_personal_os_g5.py` (2 tests) |

---

## 2. Core Architectural Components

1. **`RequestSource` & Autonomy Level Isolation**:
   - Defined in [`src/core/orchestration/request_source.py`](file:///D:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/request_source.py) and [`src/core/orchestration/execution_policy.py`](file:///D:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/orchestration/execution_policy.py).
   - Replaced mutable singleton state with request-scoped `ContextVar[AutonomyLevel]`.
   - Autonomous background tasks cannot silently inherit human confirmation exemptions.

2. **`DailyContextEngine` & Personal OS State Store**:
   - Defined in [`src/personal_os/daily_context.py`](file:///D:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/personal_os/daily_context.py) and [`src/personal_os/state_store.py`](file:///D:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/personal_os/state_store.py).
   - Persists user preferences, active priorities, and operational state across restarts.

3. **`WorkspaceSearchEngine`**:
   - Defined in [`src/personal_os/workspace_search.py`](file:///D:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/personal_os/workspace_search.py).
   - Combines BM25-style inverted indexing with SQLite metadata caching and live watcher event feeds.
