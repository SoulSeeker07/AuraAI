# Aura AI

**The Autonomous AI Operating System Platform**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
[![Platform Version](https://img.shields.io/badge/version-v0.18.0--runtime--stabilization-green.svg)](RELEASE.md)
[![Platform Progress](https://img.shields.io/badge/milestones-17%2F26%20Complete-green.svg)](roadmap.md)
[![Architecture Status](https://img.shields.io/badge/cognitive--orchestration-frozen-blue.svg)](docs/ARCHITECTURE_FREEZE.md)
[![Runtime Acceptance](https://img.shields.io/badge/runtime--acceptance-verified-brightgreen.svg)](docs/RUNTIME_ACCEPTANCE.md)
[![Build Status](https://img.shields.io/badge/tests-100%25%20passed-brightgreen.svg)](docs/engineering.md)

Aura AI is a modular, high-reliability **AI Operating System Platform** built to unify cognitive orchestration, autonomous planning, native OS execution, deep research, and long-running engineering sessions into a unified operating runtime.

> **Aura is an AI Operating System rather than a chatbot.** It separates cognition from execution. Groq acts as the Executive Coordinator, deciding *what* should happen, while specialized supervisors and workers perform the work. Desktop operations are handled by the Native Desktop Engine, browser tasks by Playwright, research by Gemini, and software engineering by Antigravity CLI. Long-running tasks are managed through `RuntimeSessions` and `WorkerManager`, enabling progress tracking, pause/resume, explainability, and safe execution.

Read the official [Platform Architecture Constitution](docs/ARCHITECTURE_FREEZE.md) for frozen APIs and runtime extension rules, and consult [Runtime Acceptance](docs/RUNTIME_ACCEPTANCE.md) for manual release gates.


---

## 🏛️ System Architecture

Aura operates as an AI Operating System where **Groq serves as the Executive Cognitive Coordinator (Project Manager)** while execution is delegated to long-running domain supervisors and specialized workers (`Antigravity CLI`, `Playwright Browser`, `Native Desktop Engine`, `Gemini Research Engine`).

```text
                                  USER
                                    │
                                    ▼
                         Aura Decision Engine
                        (Executive Brain - Groq)
                         Cognitive Coordinator
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
  Desktop Operator           Browser Operator           Research Analyst
(Native Desktop Engine)     (Playwright Engine)        (Gemini Research)
                                    │
                                    ▼
                     Software Engineering Supervisor
                                    │
                                    ▼
                     WorkerManager / RuntimeSession
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            AntigravityWorker  PytestWorker   GitDiffWorker
             (Lead Engineer)     (Pytest)      (Ruff & Git)
```

---

## 🧠 Core Subsystems & Runtime Architecture

### 👔 Cognitive Orchestration & Executive Coordination
- **Groq as Executive Coordinator**: Groq acts exclusively as the Project Manager — understanding user intent, allocating resources, supervising execution streams, and summarizing completed artifacts without directly outputting raw code snippets into chat.
- **Zero-LLM Control Interception**: Deterministic handling of system controls (`"status?"`, `"How's it going?"`, `"Show active workers"`, `"Pause engineering"`, `"Resume engineering"`, `"Cancel worker X"`) resolved instantly via `WorkerManager` without LLM calls.

### 🛠️ Software Engineering Supervisor & Antigravity CLI
- **`EngineeringSession` State Machine**: Stateful single source of truth for software development tasks, inheriting from `RuntimeSession` to track progress, modified files, test outputs (`pytest`), and artifacts.
- **Concurrent Validation Workers**: Asynchronous execution of `PytestWorker`, `RuffWorker`, and `GitDiffWorker` alongside `Antigravity CLI` for real-time validation.

### 🛡️ Configurable SafetyPolicy Engine
- **Application & OS Protection**: Hardened policy engine (`src/execution/safety_policy.py` & `config/safety_policy.yaml`) protecting critical IDE and OS processes (`Code.exe`, `vscode`, `explorer.exe`, `System`) from termination or destructive manipulation.

### 🌐 System-Wide WorkerManager & Unified Session Hierarchy
- **`RuntimeSession` Base Architecture**: Universal session abstraction for all long-running domain tasks (`EngineeringSession`, `BrowserSession`, `DesktopSession`, `ResearchSession`).
- **Worker Management**: Centralized registration, monitoring, pause, resume, and cancellation across all domain workers.

---

## ✨ Features Overview

### 🖥️ Native Desktop Engine
- **Hardware & OS Control**: Windows-native managers for window placement, active clipboard monitoring, display metrics, audio streams, power management, and network interfaces.
- **Safety Bounds**: SafetyPolicy pre-execution checks enforce protected process rules before calling Win32 APIs.

### 🔍 Autonomous Research Engine
- **Query Decomposition**: Breaks complex research topics into parallel execution sub-queries.
- **Evidence Evaluation**: Performs trust scoring, conflict resolution, recency weighting, and multi-style citation generation (APA, MLA, IEEE).

### 🤖 Multi-Backend LLM & Engine Routing
- **Declarative Backends**: Built-in adapters for Groq, Gemini 2.0 Flash, Antigravity CLI, Playwright Browser Engine, and Desktop Native Engine.
- **Adaptive Negotiation**: Dynamic capability negotiation with moving-average latency, success rate, and load tracking (`negotiate_capabilities()`).

---

## ⚡ Quick Start

### 1. Prerequisites
- **OS**: Windows 10 / 11
- **Python**: Version 3.11
- **Virtual Environment**: Recommended `.venv`

### 2. Installation
```bash
# Clone repository
git clone https://github.com/SoulSeeker07/AuraAI.git
cd AuraAI

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Running System & Applications
```bash
# Run system diagnostic doctor
python aura.py --doctor

# Inspect system status dashboard
python aura.py --inspect

# Execute CI pipeline verification
python aura.py --verify

# Launch interactive CLI client
python aura.py --cli

# Launch GUI desktop interface
python aura.py --gui
```

---

## 📚 Platform Documentation

Detailed technical guides and architecture specifications are available in the [`docs/`](docs/) directory:

- 🚀 [**Getting Started**](docs/getting-started.md) — Installation, environment setup, and launcher guide.
- 🏗️ [**Architecture & Layers**](docs/architecture.md) — Architectural manifest, layer boundaries, and import contracts.
- 🧠 [**Planner System**](docs/planners.md) — Specialized domain planners and declarative schemas.
- 🔌 [**Backend Registry**](docs/backends.md) — Multi-model routing engine and adaptive capability negotiation.
- 🖥️ [**Desktop Native Engine**](docs/desktop.md) — Native Windows managers, execution pipeline, and safety contracts.
- 🔍 [**Research Engine**](docs/research.md) — Autonomous evidence evaluation, conflict resolution, and citations.
- 🛠️ [**Engineering & Diagnostics**](docs/engineering.md) — Aura Doctor, Inspector dashboard, and CI verification pipeline.
- 🧩 [**Plugin Ecosystem**](docs/plugins.md) — Modular plugin registry and declarative auto-discovery.
- 🗺️ [**Platform Roadmap**](roadmap.md) — Complete roadmap from Era 1 Foundation to Era 3 Aura OS.

---

## 🤝 Contributing

Contributions follow strict architectural contracts:
1. Files in `src/` must never use `from src.` import prefixes when imported internally.
2. Lower architectural layers (`core`) must not import upper layers (`desktop`, `gui`).
3. Run `python aura.py --verify` prior to submitting pull requests.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for full details.

---

## 📄 License

This software is proprietary and confidential — see the [`LICENSE`](LICENSE) file for complete terms:

**AuraAI Proprietary Software License Version 1.0**  
Copyright (c) 2026 Sreekanta YR. All Rights Reserved.