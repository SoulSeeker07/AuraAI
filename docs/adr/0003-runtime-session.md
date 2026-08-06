# ADR 0003: Unified RuntimeSession Hierarchy

* **Status:** Accepted  
* **Date:** 2026-08-06  
* **Author:** Sreekanta YR  

## Context & Problem Statement
Each subsystem previously maintained ad-hoc state tracking mechanisms. Engineering had `EngineeringSession`, desktop operations used ephemeral dictionary logs, and browser automation relied on transient memory variables. This prevented unified system-wide monitoring, pausing, resuming, or cancellation.

## Decision
Create an abstract dataclass base `RuntimeSession` (`src/core/orchestration/runtime_session.py`) inherited by all domain execution sessions:
- `EngineeringSession` (domain: `"engineering"`)
- `BrowserSession` (domain: `"browser"`)
- `DesktopSession` (domain: `"desktop"`)
- `ResearchSession` (domain: `"research"`)

Every `RuntimeSession` exposes standard fields (`session_id`, `domain`, `goal`, `status`, `progress`, `workers`, `timeline`, `artifacts`) and standard methods (`pause()`, `resume()`, `cancel()`, `update_progress()`).

## Alternatives Considered
* **Ad-hoc Subsystem Logs**: Rejected due to inconsistency across CLI/GUI dashboards and inability to pause or resume non-engineering tasks.
* **Global Singleton State**: Rejected due to state corruption when multiple domain operations run concurrently.

## Consequences
* **Positive**: Unified status monitoring, consistent lifecycle management (`pause`, `resume`, `cancel`), standardized telemetry formatting for CLI/GUI dashboards.
* **Negative**: All new domain sessions must conform to the `RuntimeSession` schema.
