# ADR 0001: 5-Layer AI Operating System Architecture

* **Status:** Accepted  
* **Date:** 2026-08-05  
* **Author:** Sreekanta YR  

## Context & Problem Statement
Prior versions of AI assistants functioned as monoliths or unstructured script runners where natural language prompts directly triggered raw shell commands or ad-hoc API calls. As the system expanded across desktop control, deep research, browser automation, and software engineering, a strict architectural hierarchy was required to guarantee stability, testability, and safety.

## Decision
Enforce a strict 5-layer architectural hierarchy with contract-tested boundaries:

```text
Layer 5: Application Layer       (gui, cli, main.py, aura.py)
Layer 4: Cognitive Orchestration  (MasterOrchestrator, DecisionEngine, SupervisorAgent)
Layer 3: Planning Layer           (DesktopPlanner, ResearchPlanner, CodingPlanner, BrowserPlanner)
Layer 2: Provider Backends        (Groq, Gemini, Antigravity CLI, Native Desktop Engine)
Layer 1: Infrastructure           (Memory, Desktop Context, Event Bus, SafetyPolicy)
```

### Key Import Rules:
1. Higher layers can call lower layers; lower layers MUST NOT import upper layers.
2. `core` must never import `desktop`, `browser`, `research`, or `gui`.
3. Files in `src/` must use top-level or relative imports and never `from src.`.

## Alternatives Considered
* **Flat Subsystem Structure**: Rejected due to high risk of circular dependencies and unmanageable coupling as capabilities expanded.
* **Direct Monolithic Agent Loops**: Rejected because natural language reasoning becomes mixed with OS execution logic.

## Consequences
* **Positive**: Clean separation of concerns, deterministic contract testing (`python aura.py --verify`), isolated unit testing, and scalable capability expansion.
* **Negative**: Requires strict discipline when adding cross-layer features.
