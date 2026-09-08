# ADR 0008: Isolated Background Subagent Runtime & Non-Blocking Task Execution

**Status**: Implemented / Complete (Persistent AsyncRuntime verified live in CLI and GUI CommandWorker)
**Date**: 2026-09-07
**Author**: Aura Engineering Core
**Context**: Post-v1.0 Capability Expansion & Autonomous Background Workers

---

## 1. Context & Problem Statement

In the current AuraAI architecture (v1.0.0), user requests are processed through AuraCore and MasterOrchestrator via process_request_async(). While Aura possesses:
- A multi-agent decomposition layer (SupervisorAgent, PlannerRegistry, TaskDecomposer)
- Scoped worker definitions (TaskWorker with CodingProfile, ResearchProfile, TestProfile, BrowserProfile)
- Standardized worker output schemas (WorkerResult, TaskWorkingMemory)
- Subsystem tracking state machines (WorkerManager, RuntimeSession, EngineeringSession)

the primary interaction model remains **request-response synchronous (await-blocking)**.

When MasterOrchestrator delegates a complex, long-running goal (e.g., executing an engineering task, running tests, or performing multi-site research), the orchestrator blocks the active conversation turn until execution completes. The user cannot continue chatting, refining requirements, or querying status in the primary chat session while the worker operates. Furthermore, TaskWorker instances lack an independent, multi-turn LLM reasoning loop (ReAct loop) isolated from the parent dialogue context.

---

## 2. Falsifiable Architectural Audit: Current State vs. Target State

| Capability Mechanic | Current Codebase Implementation | Status | Target Subagent Architecture |
| :--- | :--- | :---: | :--- |
| **Task Decomposition** | src/core/orchestration/supervisor_agent.py, task_decomposer.py | [x] Built | High-level goal decomposed into bounded subtasks. |
| **Scoped Worker Profiles** | src/core/orchestration/task_worker.py (allowed_tools, filesystem scopes) | [x] Built | Strict tool and capability sandboxing per worker. |
| **Structured Output** | WorkerResult in task_worker.py (actions_taken, observations, verification, artifacts, errors) | [x] Built | Clean hand-off to orchestrator without raw console noise. |
| **Non-Blocking Dispatch** | MasterOrchestrator.dispatch_background_subagent() via asyncio.create_task() | [x] Built | Dispatch via asyncio.create_task(), return immediate acknowledgment to chat loop (<50ms). |
| **Context Isolation** | TaskWorker ReAct loop with private self.messages & TaskWorkingMemory | [x] Built | Each subagent runs its own bounded multi-turn ReAct loop with ephemeral history. |
| **Completion Notification** | FocusManager enqueue_notification() + EventBus subagent.completed | [x] Built | FocusManager / EventBus pushes completion card or injects proactive update into chat/GUI with secret redaction. |

---

## 3. Decision

We will implement an **Isolated Background Subagent Runtime** conforming to the Antigravity subagent pattern through a phased 3-piece implementation:

### Piece 1: Non-Blocking Background Dispatch
- Extend MasterOrchestrator to support an asynchronous execution branch (_dispatch_background_subagent).
- Wrap the long-running worker coroutine in asyncio.create_task() (or worker thread pool for CPU/blocking steps).
- Immediately register the active worker with WorkerManager (status='RUNNING', progress telemetry).
- Immediately yield/return a non-blocking acknowledgment message to the user:
  > 'I have dispatched worker [Worker Name] in the background to handle [Task]. You can continue chatting or ask me anything else while it runs.'
- Introduce a concurrency semaphore (SubagentRateLimiter) to prevent background LLM workers and foreground user turns from colliding on Groq/Gemini free-tier rate limits, leveraging KeyPool rotation.

### Piece 2: Completion -> Live Chat & GUI Notification
- Hook worker completion into the existing event pipeline (EventBus / FocusManager).
- When a TaskWorker transitions to SUCCESS or FAILED, format its WorkerResult into a concise summary artifact card.
- Dispatch an event (EventType.SUBAGENT_COMPLETED) to notify the user:
  - If using CLI: queue for next prompt turn or display via overlay/HUD.
  - If using GUI: proactively inject the completion card into the chat timeline.

### Piece 3: Isolated Multi-Turn LLM Context per Worker
- Equip TaskWorker with an autonomous, scoped ReAct loop (Perceive -> Reason -> Act -> Observe -> Verify).
- Seed the worker prompt context with only:
  1. The assigned subtask description and goal criteria.
  2. Bounded filesystem / environment context.
  3. The worker assigned subset of tools (profile.allowed_tools).
- The worker intermediate turns (reading files, testing, diffing) stay strictly within its private ephemeral history array (TaskWorkingMemory), keeping the primary chat window completely clean.
- All mutating actions remain strictly governed by ExecutionPolicy and CryptographicApprovalAuthority (no security bypasses for background tasks).

---

## 4. Build Order & Prioritization

`	ext
+-------------------------------------------------------------+
| Step 1: Non-Blocking Background Dispatch (WorkerManager)     |
| -> Enables immediate chat unblocking                         |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 2: Completion Notification (FocusManager / EventBus)   |
| -> Surfaces WorkerResult to chat/GUI when finished           |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Step 3: Isolated Multi-Turn LLM Context (TaskWorker ReAct)  |
| -> Full multi-step autonomy with scoped Groq context         |
+-------------------------------------------------------------+
`

---

## 5. Consequences & Invariants

1. **No False Self-Reporting**: Aura agents must never self-report subagent completion without falsifiable verification against WorkerManager or physical system state.
2. **Rate Limit Protection**: Background subagents must not exhaust provider API quotas or starve foreground user dialogue.
3. **Auditability**: All worker actions, tool calls, and observations must be persisted in session.timeline and GoalStore for post-hoc audit.
