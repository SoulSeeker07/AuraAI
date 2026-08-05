# Architecture & Layer Boundaries Specification

Aura AI enforces strict architectural layer boundaries to prevent unintended component coupling, guarantee testability, and support clean multi-agent orchestration.

---

## 1. Architectural Layer Hierarchy

```
Layer 6: Applications & Clients    (gui, cli, main.py, aura.py)
               │
Layer 5: Master Orchestrator        (master_orchestrator.py - Milestone 16)
               │
Layer 4: Specialized Planners      (DesktopPlanner, ResearchPlanner, CodingPlanner, BrowserPlanner)
               │
Layer 3: Domain Subsystems         (desktop, research, coding, browser, execution)
               │
Layer 2: Provider Backends         (Groq, Gemini, Antigravity CLI, Native Engine)
               │
Layer 1: Core Foundation           (event_bus, logger, config, base contracts)
```

---

## 2. Forbidden Import Contracts

The system validates import rules via AST static analysis (`scripts/generate_dep_graph.py`) and `.importlinter`:

1. **`core` Layer Isolation**:
   - `core` MUST NOT import `desktop`, `research`, `coding`, `browser`, `gui`, or `frontend`.
2. **`desktop` Layer Boundary**:
   - `desktop` MUST NOT import `gui`, `frontend`, or `research` directly.
3. **Planner Isolation**:
   - `src/desktop/planner/` re-export stubs MUST NOT use `from src.` imports.
4. **Package Hygiene Rule**:
   - Source files in `src/` MUST NOT use `from src.X import` or `import src.X`. They must use relative imports (`from .module import X`) or top-level package imports (`from core.planning import X`).

---

## 3. Architecture Manifest (`config/architecture.json`)

The single source of truth for architectural layer metadata is stored in `config/architecture.json` and validated on every `aura.py --doctor` run.

```json
{
  "architecture_version": 3,
  "minimum_supported": 3,
  "layers": [
    {
      "name": "core",
      "level": 1,
      "description": "Fundamental contracts, logger, event bus, base types",
      "depends_on": [],
      "forbidden": ["desktop", "gui", "frontend", "research", "coding", "browser"]
    },
    {
      "name": "desktop",
      "level": 2,
      "description": "Windows native desktop managers and execution pipeline",
      "depends_on": ["core"],
      "forbidden": ["gui", "frontend", "research"]
    }
  ]
}
```
