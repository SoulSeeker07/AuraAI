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
