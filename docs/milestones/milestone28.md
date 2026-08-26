# Milestone 28 — Dynamic CodeAct Runtime, HUD Overlays & Integrated Aura OS (`v0.32.0`)

## Goal
Milestone 28 completes the transition of AuraAI into an **Integrated Autonomous Desktop Operating System**, providing dynamic Python CodeAct execution in a hardened sandbox, live HUD overlay widgets for system and task monitoring, an integrated Retrieval-Augmented Generation (RAG) knowledge service, and sandboxed test isolation under Windows Job Objects.

---

## 1. Core Architectural Pillars

| Pillar | Focus Area | Deliverables & Verified Architectural Invariants | Key Components |
| :--- | :--- | :--- | :--- |
| **P1** | **Dynamic CodeAct Execution Engine** | Code-as-action paradigm replacing rigid tool calling; multiline code fence extraction; AST safety validation; self-healing closed-loop repair on runtime errors; tool sandbox abstraction. | [`src/codeact/`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/codeact/), [`src/tools/`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/tools/) |
| **P2** | **Desktop HUD & Overlay Architecture** | Non-intrusive, semi-transparent PySide6 HUD widgets; Frameless window management; persistent coordinate positioning; live telemetry streaming via real backend bridge. | [`src/gui/widgets/`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/gui/widgets/), [`src/gui/real_backend_bridge.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/gui/real_backend_bridge.py) |
| **P3** | **Sandboxed Pytest Test Isolation** | Privileged isolation via Windows Job Object and `AuraSandboxUser` (`RestrictedUserSandbox`); CPU/memory ceilings (512MB RAM cap); cache & temp redirection; credential scrubbing (`TD-008` resolved). | [`src/engineering/test_runner.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/engineering/test_runner.py), [`tests/test_engineering_sandboxed_runner.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/test_engineering_sandboxed_runner.py) |
| **P4** | **Knowledge Retrieval & RAG Service** | Semantic search and document indexing using ChromaDB/SQLite; embedding generation; automated document chunking; context-grounded retrieval for complex queries. | [`src/knowledge/rag_service.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/knowledge/rag_service.py), [`src/knowledge/retrieval_engine.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/knowledge/retrieval_engine.py) |
| **P5** | **Real Backend Bridge & Unified Launchers** | Real backend signal forwarding; event-driven GUI updates; zero-lag state synchronization; one-click batch launcher scripts (`aura.bat`, `run_chat.bat`, `run_status_hud.py`, `run_personal_os_hud.py`). | [`aura.bat`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/aura.bat), [`src/gui/real_backend_bridge.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/gui/real_backend_bridge.py) |

---

## 2. Deep Dive: Dynamic CodeAct Execution Runtime

Rather than constraining the LLM to pre-defined JSON tool schemas, the **CodeAct Engine** allows the agent to draft executable Python scripts directly. These scripts interact with native OS APIs and specialized tools in a sandboxed execution context:

1. **`DynamicCodeActExecutor`**:
   - Executes synthesized Python scripts against a bounded `CodeSandbox`.
   - Captures stdout/stderr, returned variables, and execution status.
   - Closed-loop self-repair on `SyntaxError`, `NameError`, or runtime exceptions up to `max_retries=3`.

2. **Drafters (`GroqDrafter` & `AgyDrafter`)**:
   - High-speed code generation using Groq LLaMA models or Antigravity bridge.
   - Robust multiline standalone-fence parsing (`extract_code_block`) supporting embedded markdown and nested fences.
   - JSON-encoded string decoding to prevent unescaped triple-quote syntax errors.

3. **Tool Sandbox (`src/tools/`)**:
   - `FileTool`: Safe file read/write/list operations within workspace boundaries.
   - `CodeSandbox`: Namespace-isolated Python execution environment with injected helper tools and standard utilities.

---

## 3. Deep Dive: HUD Overlay Architecture

The HUD subsystem introduces modern, semi-transparent desktop widgets designed to overlay the user's workspace without stealing focus or disrupting active workflows:

```text
┌────────────────────────────────────────────────────────┐
│                   PySide6 HUD Layer                    │
│ ┌──────────────────────┐    ┌────────────────────────┐ │
│ │ SystemMonitorOverlay │    │     WeatherOverlay     │ │
│ │ (CPU, RAM, Net, GPU) │    │ (Temp, Forecast, Icon) │ │
│ └──────────────────────┘    └────────────────────────┘ │
│ ┌──────────────────────┐    ┌────────────────────────┐ │
│ │ AgentTaskStatusHUD   │    │  PersonalOSDashboard   │ │
│ │ (Active DAG Subtasks)│    │ (Daily Briefing & Logs)│ │
│ └──────────────────────┘    └────────────────────────┘ │
│ ┌────────────────────────────────────────────────────┐ │
│ │             ChatWindowOverlay (Floating)           │ │
│ └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
                           ▲
                           │ PyQt Signals / Slots
┌────────────────────────────────────────────────────────┐
│                   RealBackendBridge                    │
│ (Telemetry Polling, Event Subscriptions, State Cache)  │
└────────────────────────────────────────────────────────┘
                           ▲
┌────────────────────────────────────────────────────────┐
│                   AuraCore Subsystems                  │
│ (SystemMonitor, MemoryManager, TriggerScheduler, etc.) │
└────────────────────────────────────────────────────────┘
```

### Key Overlays:
- **`SystemMonitorOverlay`**: Live CPU, memory, disk, and network throughput charts.
- **`WeatherOverlay`**: Local weather conditions and ambient temperature display.
- **`AgentTaskStatusOverlay`**: Real-time visualization of running subtasks, cognitive state, and step completion.
- **`PersonalOSDashboardOverlay`**: Aggregated daily briefing, priority tasks, and scheduled triggers.
- **`ChatWindowOverlay`**: Floating glassmorphic conversational interface with voice and text inputs.

---

## 4. Verification & Test Coverage

- **CodeAct Test Suite**: `tests/test_codeact/` (43/43 passing)
- **Engineering Sandboxed Runner Suite**: `tests/test_engineering_sandboxed_runner.py` (5/5 passing)
- **RAG & File Services Suite**: `tests/unit/test_rag_and_file_services.py` (passing)
- **GUI & HUD Overlay Suite**: `tests/unit/gui/` (passing)
- **Platform Regression Total**: 225+ deterministic tests 100% passing across all milestones.
