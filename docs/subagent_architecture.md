# AuraAI Subagent Architecture: Isolated Autonomous Background Workers

## Overview

This specification details the architecture for **Antigravity-Style Subagents** within AuraAI.

A **subagent** is an isolated, autonomous AI worker that the primary orchestrator spawns to execute a specific, bounded task in the background without cluttering or blocking the main conversation.

---

## 1. Core Mechanics

### A. Context Isolation
- The subagent receives its own isolated context window and message history array.
- It performs multi-step file reads, AST inspection, code modifications, or terminal commands within its own turn loop.
- Hundreds of lines of intermediate logs, diffs, and tool outputs remain inside the worker's private ephemeral working memory (TaskWorkingMemory) and are **not dumped into the primary user dialogue**.

### B. Delegated Task Execution
- The primary orchestrator (SupervisorAgent / MasterOrchestrator) evaluates high-level user goals and decomposes them into bounded subtasks.
- Each subtask is assigned to a TaskWorker equipped with a dedicated capability profile:
  - CodingProfile: tools for editing, AST checking, code analysis, testing.
  - ResearchProfile: tools for web search, document queries, content extraction.
  - TestProfile: tools for test discovery and test runner execution.
  - BrowserProfile: tools for isolated web navigation and extraction.

### C. Unblocked Interaction (Non-Blocking Dispatch)
- Rather than synchronously awaiting a subagent's full execution lifecycle in the main chat turn, MasterOrchestrator dispatches the worker asynchronously (syncio.create_task()).
- Control immediately returns to the user with a concise status acknowledgment.
- The user can continue conversing, asking questions, or issuing other commands while the subagent runs concurrently in the background.

### D. Structured Hand-Off
- Once execution terminates, the subagent returns a standardized, structured WorkerResult object:
  - worker_name: Unique worker identifier.
  - status: SUCCESS | FAILED | CANCELLED.
  - ctions_taken: Count of executed actions.
  - observations: Key observations extracted during execution.
  - erification: Falsifiable verification proofs (tests passed, files written).
  - rtifacts: Created or modified files, logs, or reports.
  - errors: Specific failure points or exceptions encountered.
  - duration: Wall-clock execution time.

---

## 2. Architectural Blueprint & Component Map

`mermaid
sequenceDiagram
    autonumber
    actor User
    participant Chat as Primary Chat (CLI / GUI)
    participant Orch as MasterOrchestrator
    participant WM as WorkerManager
    participant Sub as TaskWorker (Background Subagent)
    participant LLM as Groq / Gemini (Isolated Session)
    participant FM as FocusManager / EventBus

    User->>Chat: Deploy capability counter
    Chat->>Orch: process_request_async()
    Orch->>Orch: Decompose task -> SubTask
    Orch->>WM: register_worker(worker_id, RUNNING)
    Orch->>Sub: asyncio.create_task(execute_task())
    Orch-->>Chat: Dispatched worker in background. Chat unblocked!
    Chat-->>User: Instant response (Interaction unblocked)

    par Background Subagent Execution
        Sub->>LLM: Isolated prompt (Subtask + allowed tools)
        LLM-->>Sub: Tool call (read_file / edit_file)
        Sub->>Sub: Execute tool within permission profile
        Sub->>LLM: Observation (private to worker)
        Sub->>Sub: Run verification tests (pytest)
        Sub->>WM: update_progress(100%, COMPLETED)
        Sub->>FM: dispatch_event(SUBAGENT_COMPLETED, WorkerResult)
    and User continues interacting
        User->>Chat: What is the weather today?
        Chat->>Orch: process_request_async()
        Orch-->>Chat: Live weather report
    end

    FM-->>Chat: Proactive injection or notification of WorkerResult
    Chat-->>User: Worker finished successfully! (2 files modified, tests passed)
`

---

## 3. The 3-Piece Implementation Plan

### Piece 1: Non-Blocking Background Dispatch
- **Target File**: src/core/orchestration/master_orchestrator.py
- **Mechanism**:
  - Introduce dispatch_subagent_background(subtask, profile) -> str
  - Leverage syncio.create_task() to run the worker loop detached from the immediate request-response stream.
  - Register the task in WorkerManager.get_instance().
  - Maintain an API concurrency limiter (SubagentRateLimiter) to prevent concurrent Groq free-tier rate exhaustion.

### Piece 2: Completion -> Live Notification Pipeline
- **Target Files**: src/core/orchestration/worker_manager.py, src/core/focus/focus_manager.py, src/events/event_bus.py
- **Mechanism**:
  - Define EventType.SUBAGENT_COMPLETED and EventType.SUBAGENT_FAILED.
  - When worker execution completes, emit the event with the full WorkerResult.
  - In CLI: record the notification in session state; display as an alert card or header banner on next prompt.
  - In GUI: dynamically push the finished worker card into the message stream.

### Piece 3: Isolated Multi-Turn LLM Context (TaskWorker ReAct Loop)
- **Target Files**: src/core/orchestration/task_worker.py, src/core/orchestration/task_working_memory.py
- **Mechanism**:
  - Each TaskWorker maintains a private messages: list[dict] array.
  - System prompt restricts scope strictly to the worker profile and target subtask.
  - Workers run an autonomous loop bounded by 	ime_budget_seconds and max_turns.
  - Tool invocations are verified using VERIFIER_REGISTRY before being accepted as valid steps.
  - Enforce cryptographic approval authority on all mutating actions.

---

## 4. Verification & Testing Strategy

1. **Unit Tests**:
   - 	est_subagent_background_dispatch_returns_promptly: Verify orchestrator returns an acknowledgment without awaiting worker completion.
   - 	est_subagent_context_isolation: Verify primary chat context does not contain intermediate worker tool calls or logs.
   - 	est_subagent_completion_event_fired: Verify WorkerResult fires SUBAGENT_COMPLETED and updates WorkerManager.
2. **Integration Verification**:
   - Live execution with unmocked background worker performing a scoped task while primary chat responds to foreground queries.
