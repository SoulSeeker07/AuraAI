# ADR 0004: System-Wide WorkerManager Subsystem

* **Status:** Accepted  
* **Date:** 2026-08-06  
* **Author:** Sreekanta YR  

## Context & Problem Statement
With multiple long-running operations across software development, web browsing, and desktop manipulation, the user and system need a single central authority to inspect running workers, pause background tasks, resume execution, or terminate runaway processes.

## Decision
Implement a central `WorkerManager` singleton (`src/core/orchestration/worker_manager.py`) tracking active domain sessions and workers:
- Provides zero-LLM status lookups (`get_status_summary()`).
- Exposes domain-level controls (`pause_domain()`, `resume_domain()`, `cancel_worker()`).
- Formats active worker telemetry for `AuraInspector` and CLI dashboards.

## Alternatives Considered
* **Distributed Subsystem State**: Rejected because checking active workers would require querying 4 different registries.
* **OS Task Manager Probing Only**: Rejected because OS process pids do not carry domain session context or percentage progress metadata.

## Consequences
* **Positive**: Instant non-LLM control responses, single point of truth for task monitoring, safe lifecycle operations.
* **Negative**: Supervisors and domain backends must register sessions with `WorkerManager` upon startup.
