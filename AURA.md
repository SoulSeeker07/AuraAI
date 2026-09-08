# Aura Project Instructions

## Environment
Python 3.11
Virtual environment: .venv

## Execution & Architecture
Use pytest for automated tests via `.\.venv\Scripts\pytest`.
Do not create new brain modules without explicit approval.
ExecutionCoordinator owns: execute → observe → verify → recover → goal_verify.

## Safety & Autonomy
Default autonomy mode is ASSISTED.
High-risk actions (file deletion, bulk edits, messaging) require user confirmation.
Critical-risk actions (purchases, checkout, credential submission) ALWAYS require explicit user confirmation.

## Browser Operations
Prefer DOM and accessibility tree observation.
Use screenshots only when DOM state is insufficient.
Never claim success from element interaction alone; require independent state verification.

## Verification & Recovery
Never claim goal success without independent physical observation.
Failed steps must attempt strategy recovery before declaring failure.
Capture pre-action state checkpoints before mutating operations.

## CLI Activity Rendering
Normal output should remain compact (`› Worked for X.Xs`).
Detailed execution traces must be expandable (`▼`).
Expose auditable action/observation traces; never expose private LLM chain-of-thought.

## Background Subagents (M31)
- Non-blocking asynchronous task execution via `asyncio.create_task()`.
- Activation triggers:
  - `/background <task>`
  - `run in background: <task>`
  - `dispatch subagent: <task>`
  - Programmatic: `parameters={"background": True, "profile": "coding"}`
- Context Isolation: Subagents execute within private `self.messages` and `TaskWorkingMemory` with zero leakage into the primary chat session.
- Two-Gate Defense-in-Depth:
  - Gate 1: Dispatch-time `ExecutionPolicy.evaluate_action()`. Confirmation-gated actions (`PolicyAction.ASK_USER` or `BLOCK`) reject immediately.
  - Gate 2: Action-time evaluation before every single tool action in the ReAct loop. If policy check fails or raises an exception, the worker fails closed.
- Credential Redaction: All provider keys, private keys, bearer tokens, and secrets are redacted via `sanitize_worker_output()` before reaching results, events, or notifications.
- Completion Notifications: On worker finish, `FocusManager.enqueue_notification()` delivers a non-blocking completion card and `EventBus` publishes `subagent.completed` / `subagent.failed`.

## Tool Dispatching & Safety Gating (M12 / M15 / TD-021)
- `UnifiedToolDispatcher` is the central gateway for all 15 interactive tools in the ReAct loop.
- Single Source of Truth: All tool risks derive strictly from `CapabilityRegistry` $\rightarrow$ `classify_action_risk()` $\rightarrow$ `ExecutionPolicy`. Never introduce ad-hoc tool overrides in `dispatch()`.
- Dynamic Action Risk Inspection: Compound tools (e.g. `desktop_control_window`, `desktop_launch_app`) must inspect arguments dynamically to map destructive actions (`action="close"`, shell binaries) to canonical high-risk capabilities (`close_window`, `terminal.execute`).
- Cryptographic Ticket Verification: All `ActionRisk.HIGH` and `CRITICAL` operations require single-use HMAC-SHA256 tickets from `CryptographicApprovalAuthority`. Upstream-redeemed tickets must check `auth.get_ticket(ticket_id).is_redeemed` downstream to prevent double-verification failures.

