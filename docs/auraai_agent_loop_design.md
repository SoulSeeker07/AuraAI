# AuraAI — Goal/Step Agent Loop: Architecture Design

**Status:** Design Draft & Phase 1 Specification  
**Location:** `docs/auraai_agent_loop_design.md`  
**Scope:** Replaces the fire-once execution tail of `aura_core.py` with a persistent, verified, bounded agent loop. Does **not** touch `CodeAct`'s internal static-check retry, `UnifiedToolDispatcher`'s risk/ticket logic, or `CapabilityRegistry` — those are reused as-is, not rebuilt.

---

## 1. Design Principle

**There is no new classifier deciding "is this a simple query or an agentic goal."**  
That would recreate the exact bug this effort fixes: a pre-decision made before reasoning, which can misclassify.

Instead: **every request becomes a `Goal`.** The loop is the same code path for "what's the weather in Tokyo" and "refactor this module and run the tests." The difference between them is not which path they take — it's how many iterations the loop needs before `verify()` says done. A trivial query is a `Goal` that completes in one iteration, with a single LLM call and a single SQLite write. The overhead of that is single-digit milliseconds — not worth avoiding, and not worth building a second code path to avoid.

Narrow optimizations like `is_diagram_query` / `enable_tools=False` remain in `process_request()` to skip tool schema overhead when provably unneeded; the loop wraps around them.

---

## 2. Non-Goals

- **Not replacing `UnifiedToolDispatcher`.** It already does risk classification, approval tickets, and execution dispatch correctly. The loop *calls* `UnifiedToolDispatcher.dispatch()` as its Act step.
- **Not replacing CodeAct's static-check retry.** That's a correct, narrow-scoped retry loop for AST safety checks. It stays nested *inside* one Step's execution, invisible to the outer loop except as an Observation.
- **Coexistence Decision with `MasterOrchestrator`:** `MasterOrchestrator` and `AgentLoop` are distinct subsystems designed for different execution paradigms:
  - `MasterOrchestrator`: Pre-planned, static 7-stage DAG execution (`TaskGraph`, `SubTask`, `orchestration_tasks`) for autonomous background jobs, scheduled triggers (`TriggerScheduler`), and security governance audits.
  - `AgentLoop`: Dynamic, turn-by-turn ReAct reasoning (`Goal`, `Step`, `goal_steps`) for interactive user dialogue across CLI, GUI, and Voice.
  - Both share `Memory.db` (via `OrchestrationStore` connection management) and `UnifiedToolDispatcher`, but operate independently without sharing mutable in-memory pointers.
- **Not a rewrite of `aura_core.py`.** This introduces `src/core/orchestration/agent_loop.py` and `goal_state.py`, with surgical integration into `process_request()` and `get_ai_response()`.

---

## 3. Core Data Model

```python
# src/core/orchestration/goal_state.py

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import uuid


class GoalStatus(str, Enum):
    ACTIVE = "active"
    DONE = "done"
    FAILED = "failed"                # exhausted bounded attempts, could not verify
    AWAITING_USER = "awaiting_user"  # paused for clarification or approval ticket


class StepStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    OBSERVED = "observed"            # tool returned, not yet verified
    VERIFIED = "verified"            # observation matched expected outcome
    FAILED = "failed"                # tool errored OR verify() rejected it


@dataclass
class Step:
    step_id: str
    goal_id: str
    tool_name: str | None            # None for pure-reasoning / direct answer
    tool_args: dict
    status: StepStatus
    observation: str | None = None   # raw result, truncated for storage
    verify_reason: str | None = None # WHY verify passed/failed — feeds back to LLM
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Goal:
    goal_id: str
    session_id: str                  # ties back to AgentSession.session_id in aura_core / OrchestrationStore
    user_prompt: str
    status: GoalStatus
    steps: list[Step] = field(default_factory=list)
    max_steps: int = 8               # bounded execution ceiling
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @staticmethod
    def new(session_id: str, user_prompt: str) -> "Goal":
        return Goal(
            goal_id=f"goal_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            user_prompt=user_prompt,
            status=GoalStatus.ACTIVE,
        )
```

---

## 4. Persistence Architecture (Confirmed Single Store)

**Forensic Confirmation (§4 Resolved):**  
`src/core/orchestration/orchestration_store.py` (`OrchestrationStore`) manages SQLite persistence against `PROJECT_ROOT / "Memory.db"` with WAL mode (`PRAGMA journal_mode=WAL;`), busy timeout (`5000ms`), and thread-safe `RLock`.

**Investigation of Existing Tables:**
- `orchestration_sessions` & `orchestration_tasks`: Live tables populated by `MasterOrchestrator` during static DAG planning and crash-recovery (contains 8 sessions and 17 tasks from background/governance runs).
- `runtime_checkpoints`: Initialized by `RuntimeCheckpointManager` in `src/core/orchestration/runtime_checkpoint.py` (0 rows). There is no table named `orchestration_checkpoints`.
- **Relationship to `goals` / `goal_steps`**: `orchestration_tasks` models static DAG nodes (`task_id`, `dependencies_json`, `required_role`, `capability`, `risk_tier`). In contrast, `goal_steps` models the sequential, dynamic ReAct trajectory turns (`tool_name`, `tool_args`, `observation`, `verify_reason`) produced during real-time reasoning.
- **Session Identity & Concurrency Guardrail (Caller-Owned Sessions):**
  - Rather than relying on a shared singleton pointer, session identity is **caller-owned**:
    - **GUI (`MainWindow`):** Generates and holds `session_id = f"sess_gui_{uuid.hex[:8]}"`, regenerating a new one on window open and "+ New Chat". Passes `session_id` on every call.
    - **Voice (`ContinuousVoiceLoop`):** Generates and holds `session_id = f"sess_voice_{uuid.hex[:8]}"` per voice interaction session. Passes `session_id` on every call.
    - **Safety Net Fallback:** When `session_id is None` (e.g. ad-hoc test or standalone script), `AuraCore` generates an ephemeral `sess_ephemeral_{uuid.hex[:8]}` per request rather than adopting a stale singleton pointer.
  - This completely decouples `AgentLoop` from `MasterOrchestrator._last_session` and prevents cross-modality session bleed between voice and desktop.
- **Known Limitation — In-Memory Conversation History:** `AuraCore.conversation_history` is currently a single in-memory list on the core singleton. While `session_id` provides strict caller/goal isolation at the database and execution layer, conversational multi-turn context (`messages`) in `get_ai_response()` currently draws from this shared list until multi-tenant conversation memory is implemented in future milestones.
- **Strict Architectural Constraint (Single DB, No FK to Orchestration):** Do NOT open a new SQLite database file. `goals` and `goal_steps` reside directly inside `Memory.db`, leveraging `OrchestrationStore` connection management. However, `goals.session_id` has **no `FOREIGN KEY`** constraint to `orchestration_sessions` (which is populated exclusively by `MasterOrchestrator` DAGs); enforcing an FK would cause every single interactive turn to throw.

```sql
CREATE TABLE IF NOT EXISTS goals (
    goal_id         TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    user_prompt     TEXT NOT NULL,
    status          TEXT NOT NULL,
    max_steps       INTEGER NOT NULL DEFAULT 8,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goal_steps (
    step_id         TEXT PRIMARY KEY,
    goal_id         TEXT NOT NULL REFERENCES goals(goal_id) ON DELETE CASCADE,
    tool_name       TEXT,
    tool_args       TEXT NOT NULL,   -- JSON string
    status          TEXT NOT NULL,
    observation     TEXT,
    verify_reason   TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_goal_steps_goal_id ON goal_steps(goal_id);
CREATE INDEX IF NOT EXISTS idx_goals_session_id ON goals(session_id);
```

---

## 5. The Loop Lifecycle

```
    ┌──────────────┐
    │   Perceive   │ ── Assemble Goal + Step history + ambient context
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │    Reason    │ ── LLM call with full tool schema (no pre-classifier)
    └──────┬───────┘
           │
           ├─► is_final_answer? ──► GoalStatus.DONE
           ├─► needs_clarification? ──► GoalStatus.AWAITING_USER
           │
    ┌──────▼───────┐
    │     Act      │ ── UnifiedToolDispatcher.dispatch(name, args)
    └──────┬───────┘
           │
           ├─► confirmation_required? ──► GoalStatus.AWAITING_USER (ticket issued)
           │
    ┌──────▼───────┐
    │   Observe    │ ── Capture raw output / telemetry (bounded truncation)
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │    Verify    │ ── Pluggable capability verification: (bool, reason)
    └──────┬───────┘
           │
           ├─► Verified? ──► StepStatus.VERIFIED
           └─► Failed?   ──► StepStatus.FAILED ──► Reason (Adaptation loop)
```

### 5a. Pluggable Capability Verification

Verification is capability-aware, not a generic "did not throw":

- **`create_file_artifact`:** Checks `Path(output_path).exists() and Path(output_path).stat().st_size > 0`.
- **`browser_interact`:** Re-reads DOM / accessibility tree to confirm expected element mutation occurred.
- **`terminal_run_command`:** Checks `returncode == 0` and absence of shell error signatures.
- **`edit_file` / coding:** Re-parses AST for syntax errors and executes associated unit tests if defined.
- **Default fallback:** Explicit `(True, "no verification defined")`.

---

## 6. Execution Bounding

- `goal.max_steps` (default 8) bounds iterations within the `while` loop.
- **Repeated Failure Guard:** If two consecutive steps fail with identical `(tool_name, tool_args)`, force `GoalStatus.AWAITING_USER` instead of spinning.
- **SystemWatchdog:** Integrates with wall-clock time limit to prevent long-running hanging tools.

---

## 7. Integration Points in `aura_core.py`

1. **`process_request(user_goal, session_id=None, emitter=None)` (L1805–L1875):**  
   Accepts caller-owned `session_id`. When omitted, generates an ephemeral `sess_ephemeral_<uuid>` per call. Resolves active goal from `GoalStore`. If an existing goal in that session is in `AWAITING_USER`, the incoming user message resumes that goal. Otherwise, creates a new `Goal.new(session_id, user_prompt)`.
2. **`get_ai_response(user_message, enable_tools=True, session_id=None, emitter=None)` (L1510–L1620):**  
   Accepts caller-owned `session_id`. Replaces the fire-once single-pass return with `AgentLoop.run(goal, conversation_history)`.
   - `DONE`: Return final answer.
   - `AWAITING_USER`: Prompt user with ticket / clarification.
   - `FAILED`: Return structured summary of attempts and failure reasons across all steps, rather than a raw, uncontextualized exception.

---

## 8. IntentRouter Demotion

`IntentRouter` retains only deterministic, zero-latency safety pre-checks:
- Emergency stop / abort commands.
- Exact confirmation-string matching (`yes` / `no`).

All routing heuristics and domain if-ladders are retired in favor of model-driven reasoning over the complete tool schema.

---

## 9. Phased Rollout Plan

- **Phase 1 (Passive Plumbing - Complete):**  
  Implement `goal_state.py`, database tables in `Memory.db`, and `GoalStore`. Record `Goal` and `Step` entries passively around existing execution. Zero behavior change.
- **Phase 2 (Single-Capability Active Loop - Complete):**  
  Enable `AgentLoop` with active `verify()` for `create_file_artifact` and `browser_navigate_and_read` behind feature flag `AURA_ENABLE_AGENT_LOOP`. Eliminates simulated success in `browser_interact` by failing closed when no browser session is attached. Bypass `autonomous_browser` keyword hijacks in both `get_ai_response()` and `process_request()`.
  - *Known Operational Boundary*: `browser_interact` is fail-closed and honest, but dormant in production because `browser_navigate_and_read` is a one-shot reader that closes Chromium immediately, and zero production code paths currently populate `session.data["browser_session"]`.
- **Phase 3 (Universal Domain Expansion & Session Continuity):**  
  - **Prerequisite 1: General Session Lifecycle & State Persistence**:
    - *Per-Step Defect*: Line 435 of `AgentLoop.run()` currently reconstructs `session = AgentSession(...)` per turn within a call, silently wiping `session.data` across steps. Hoist `AgentSession` construction to the Goal level in `AgentLoop.run()`.
    - *Per-Call Reality & The Ephemeral Boundary*: `AgentLoop` itself is instantiated ephemerally per user request in `aura_core.py` (`get_ai_response()`). When a goal pauses in `AWAITING_USER` and the call returns, `AgentLoop` and its local `AgentSession` are garbage-collected. Live OS handles (Playwright `Browser`/`Page`) cannot be serialized to SQLite `Memory.db`.
    - *Singleton Isolation Invariant*: The `AgentSession` instance held by `AgentLoop.run()` is strictly private and goal-owned. It is constructed locally and MUST NEVER read from, write to, or alias `MasterOrchestrator._last_session`.
  - **Prerequisite 2: Long-Lived Live Resource Registry (`BrowserSessionManager`)**:
    - *Architecture*: Introduce `BrowserSessionManager` as a singleton registry keyed by `goal_id`. Because live browser processes are long-lived OS resources, they are held in `BrowserSessionManager`, surviving across separate ephemeral `AgentLoop` instantiations between `AWAITING_USER` and user resumption.
    - *Cross-Paradigm Cap & Eviction*: Because `UnifiedToolDispatcher` is shared between `AgentLoop` and `MasterOrchestrator`, the 1-browser desktop resource cap is enforced inside `BrowserSessionManager`. If any caller (interactive loop or scheduled background task) requests an active browser while an idle/paused session holds one, the older session is gracefully detached and closed, leaving an eviction tombstone.
    - *Tombstones & UX Distinction*: When a session is evicted or reaped, `BrowserSessionManager` records an explicit tombstone:
      - `ttl_expired`: Returns `"Your browser session was closed after 15 minutes of inactivity while awaiting confirmation. Please re-run your request."`
      - `bumped_by_new_goal`: Returns `"Your browser session was closed because a new browser task was started. Please re-run your request."`
      - `never_established`: Returns `"No active browser session was established for this goal. Live browser interaction requires navigating to a page first."`
    - *Watchdog & TTL Reaper Owner*: Register a periodic reaper job on AuraAI's existing daemon, `TriggerScheduler` (in `src/autonomy/trigger_scheduler.py`, already started by `AuraCore`), augmented by opportunistic sweeps on every `BrowserSessionManager` access. If an `AWAITING_USER` goal exceeds 15 minutes without resumption, its Chromium instance is reaped.
    - *Deterministic Teardown*: `finally` cleanup block in `AgentLoop.run()` explicitly notifies `BrowserSessionManager.close_session(goal.goal_id)` when a Goal resolves to `DONE` or `FAILED`.
  - **Prerequisite 3: Deep DOM/A11Y Mutation Verifiers**:
    - Implement independent DOM-state re-reading on top of the live page handle retrieved from `BrowserSessionManager` (verifying form inputs, URL navigations, and DOM elements actually mutated).
  - **Engineering Verifiers**:
    - Implement capability verifiers for `terminal_run_command` (exit code verification, shell stderr parsing) and `edit_file` (AST syntax tree validation).
- **Phase 4 (IntentRouter Deprecation):**  
  Prune remaining domain classification branches from `IntentRouter`, ensuring all requests enter the loop directly.
