# ADR 0005: Software Engineering Supervisor & Antigravity Worker

* **Status:** Accepted  
* **Date:** 2026-08-06  
* **Author:** Sreekanta YR  

## Context & Problem Statement
Generating software code directly inside conversational LLM prompts leads to fragmented edits, syntax errors, missing test verification, and lack of IDE workspace integration. Software engineering requires a dedicated supervisor running in a real workspace.

## Decision
Create the `SoftwareEngineeringSupervisor` (`src/core/orchestration/software_engineering_supervisor.py`) operating on long-running `EngineeringSession` instances:
- Delegates code synthesis strictly to `Antigravity CLI` running in its own terminal/session.
- Launches concurrent asynchronous validation workers (`PytestWorker`, `RuffWorker`, `GitDiffWorker`).
- Opens target files in VS Code (`Code.exe`) within the user's workspace.
- Emits progress events to `WorkerManager`.

## Alternatives Considered
* **In-Memory Code Block Generation**: Rejected due to code truncation, missing dependency imports, and zero automated test verification.
* **Direct Shell Invocation of `git` / `pytest` without Supervisor**: Rejected because progress tracking and failure recovery become uncoordinated.

## Consequences
* **Positive**: Real file edits on disk, automated testing before completion, clean separation of conversation vs. engineering.
* **Negative**: Requires Antigravity CLI and validation tools to be installed in the local environment.
