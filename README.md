# Aura AI

**The AI Operating Platform**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform Version](https://img.shields.io/badge/version-v0.15.0--core--platform-green.svg)](RELEASE.md)
[![Architecture Freeze](https://img.shields.io/badge/architecture-frozen-blue.svg)](docs/ARCHITECTURE_FREEZE.md)
[![Build Status](https://img.shields.io/badge/tests-passed-brightgreen.svg)](docs/engineering.md)

Aura AI is a modular, high-reliability **AI Operating Platform** built to unify autonomous planning, native OS control, deep research, and multi-backend LLM execution into a cohesive engineering system.

Read the official [Platform Architecture Constitution](docs/ARCHITECTURE_FREEZE.md) for frozen APIs and contributor extension rules.


---

## 🏛️ System Architecture

Aura enforces a strict 6-layer architectural hierarchy with contract-tested boundaries and declarative capability router manifests.

```
┌─────────────────────────────────────────────────────────────┐
│                    Master Orchestrator                      │
│                  (Unified Coordination)                     │
└─────────────────────────────────────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
┌──────▼──────┐         ┌──────▼──────┐         ┌──────▼──────┐
│  Desktop    │         │  Research   │         │   Coding    │
│  Planner    │         │  Planner    │         │   Planner   │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
┌──────▼──────┐         ┌──────▼──────┐         ┌──────▼──────┐
│ Native OS   │         │ Deep Reason │         │ Engineering │
│ Engine      │         │ Engine      │         │ Engine      │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       └───────────────────────┼───────────────────────┘
                               │
             ┌─────────────────┴─────────────────┐
             │                                   │
   ┌─────────▼─────────┐               ┌─────────▼─────────┐
   │ Backend Registry  │               │ Capability Router │
   │ (Groq/Gemini/CLI) │               │   (Adaptive)      │
   └───────────────────┘               └───────────────────┘
```

---

## ✨ Features Overview

### 🖥️ Native Desktop Engine
- **Hardware & OS Control**: Windows-native managers for window placement, active clipboard monitoring, display metrics, audio streams, power management, and network interfaces.
- **Contract Enforcement**: Every native manager implements standard lifecycle hooks (`initialize()`, `execute()`, `verify()`, `rollback()`, `health_check()`).

### 🔍 Autonomous Research Engine
- **Query Decomposition**: Breaks complex research topics into parallel execution sub-queries.
- **Evidence Evaluation**: Performs trust scoring, conflict resolution, recency weighting, and multi-style citation generation (APA, MLA, IEEE).

### 🤖 Multi-Backend LLM Routing
- **Declarative Backends**: Built-in adapters for Groq, Gemini 2.0 Flash, Antigravity CLI, and Desktop Native Engine.
- **Adaptive Negotiation**: Dynamic capability matching with moving-average latency, success rate, and load tracking (`negotiate_capabilities()`).

### ⚙️ Engineering & Diagnostics (`aura.py`)
- **Aura Doctor (`--doctor`)**: 22 automated system diagnostic checks for dependencies, API keys, memory footprint, startup time, and circular imports.
- **Aura Inspector (`--inspect`)**: Real-time CLI telemetry dashboard displaying active planners, backends, capability availability, and event throughput.
- **Verification Runner (`--verify`)**: One-command CI runner enforcing Ruff linting, Black formatting, Isort import order, Mypy type checking, and architecture tests.

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

### 3. Running Diagnostics & Applications
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
- 🗺️ [**Platform Roadmap**](docs/roadmap.md) — Complete roadmap from Core Platform to AI Operating System.

---

## 📜 Version History & Releases

For detailed release notes and milestone milestones, consult [`RELEASE.md`](RELEASE.md).

- **`v0.15.0-core-platform`** *(Current)* — Engineering platform stabilization, canonical launcher, manifests, backend registry, doctor, inspector, and CI pipeline.
- **`v0.16.0`** *(Upcoming)* — Master Orchestrator, multi-planner coordination, and agent collaboration.

---

## 🤝 Contributing

Contributions follow strict architectural contracts:
1. Files in `src/` must never use `from src.` import prefixes.
2. Lower architectural layers (`core`) must not import upper layers (`desktop`, `gui`).
3. Run `python aura.py --verify` prior to submitting pull requests.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for full details.

---

## 📄 License

This project is licensed under the MIT License — see the [`LICENSE`](LICENSE) file for details.