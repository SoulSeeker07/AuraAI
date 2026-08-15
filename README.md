# Aura AI

**The Autonomous AI Operating System Platform**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
[![Platform Version](https://img.shields.io/badge/version-v0.21.0--continuous--voice-green.svg)](RELEASE.md)
[![Platform Progress](https://img.shields.io/badge/milestones-Phase%200%2B1%20Operational-green.svg)](roadmap.md)
[![Architecture Status](https://img.shields.io/badge/cognitive--architecture-active-blue.svg)](docs/AURA_ARCHITECTURE_CONNECTION.md)
[![Runtime Acceptance](https://img.shields.io/badge/runtime--acceptance-verified-brightgreen.svg)](docs/RUNTIME_ACCEPTANCE.md)
[![Build Status](https://img.shields.io/badge/tests-89%2F89%20passed-brightgreen.svg)](docs/engineering.md)

Aura AI is a modular, high-reliability **AI Operating System Platform** built on the **Aura Cognitive Architecture (ACA)** — a staged cognitive runtime that unifies voice perception, natural language decision-making, planning, desktop OS automation, execution, reflection, and long-term memory into a single coordinated system.

> **Aura is an AI Operating System rather than a chatbot.** It separates cognition from execution. The ACA acts as the cognitive runtime — understanding goals, reasoning about context, planning execution maps, coordinating specialized engines, verifying outcomes, reflecting on failures, and learning from interactions. Desktop operations are handled by the Native Desktop Engine (Win32), continuous voice by the low-latency Speech System (AuraWake + Google STT + Piper TTS), research by Gemini/Wikipedia/DuckDuckGo, and software engineering by the Engineering Engine.

---

## 🚀 Development Status

```text
Operational Subsystems (Live on Physical System)
├── Continuous Voice Loop — OPERATIONAL (AuraWake + Multi-Accent Google STT / Whisper + Piper TTS + Barge-in)
├── Native Desktop Engine — OPERATIONAL (Win32 window manager, 2-tier app resolver, Start Menu, Antigravity IDE)
├── Cognitive Pipeline — OPERATIONAL (MasterOrchestrator 7-stage request reasoning pipeline + Groq LLM)
└── Long-Term Memory — OPERATIONAL (SQLite fact store, dynamic slot filling, conversational fact recall)

Active Critical Path
├── M17 Cognitive Memory — COMPLETE
├── M18 World Model (Workspace & System Graph) — IN PROGRESS
├── M19 Capability & Tool Runtime — READY
├── M20 Autonomous Coding Agent — PLANNED
├── M21 Autonomous Research Agent — PLANNED
└── M22 Browser Intelligence (Playwright) — PLANNED

Future Platform Milestones
├── M23 MCP Ecosystem
├── M24 Event Runtime & Autonomy
├── M25 Expert Systems
├── M26 Personal OS
├── M27 Autonomous Engineering
├── M28 Aura OS Core
├── M29 Natural Interaction 2.0
└── M30 Aura GUI & Multimodal Screen Perception
```

---

## 🏛️ System Architecture

Aura operates as an AI Operating System where the **Aura Cognitive Architecture (ACA)** serves as the cognitive runtime — the only component that "thinks" — while execution is delegated to specialized engines.

```text
                          USER
                            │
                            ▼
                     AuraCore Runtime
                            │
                            ▼
              ┌──────────────────────────┐
              │  Aura Cognitive Arch.    │
              │  (ACA) — Executive Brain │
              └──────────────────────────┘
                            │
    ┌─────────────────────────────────────────────────────┐
    │                                                     │
    ▼                                                     ▼
Stage 0: Context & World Understanding            Goal Manager
    │                                                     │
    ▼                                                     │
Stage 1: DMM (Decision Making Module)                     │
    │   ├── Goal Understanding                            │
    │   ├── Memory Retrieval                              │
    │   ├── Capability Retrieval                          │
    │   ├── Confidence Gate                               │
    │   └── Fusion Engine → DecisionContext               │
    │                                                     │
    ▼                                                     │
Policy Engine (Governance)                                │
    │                                                     │
    ▼                                                     │
Stage 2: Planning & Strategy                              │
    │   ├── Planner (Groq → ExecutionMap)                 │
    │   ├── TaskGraph (DAG for parallel execution)        │
    │   └── Validator                                     │
    │                                                     │
    ▼                                                     │
RuntimeSession (Source of Truth)                          │
    │                                                     │
    ▼                                                     │
Stage 3: Execution Coordination                           │
    │   ├── Desktop Engine                                │
    │   ├── Browser Engine                                │
    │   ├── Research Engine                               │
    │   ├── Engineering Engine                            │
    │   ├── Voice / Vision / Memory                       │
    │   └── Verification                                  │
    │                                                     │
    ▼                                                     │
Artifact Manager (Everything creates artifacts)           │
    │                                                     │
    ▼                                                     │
Stage 4: Reflection & Learning                            │
    │                                                     │
    ▼                                                     │
Response (with session, goal, artifacts)                  │
```

---

## 🧠 Aura Cognitive Architecture (ACA)

The ACA is the cognitive center of Aura — the only component that "thinks." Everything else simply executes.

### The Golden Rule

> **The Executive Brain thinks. The Planner organizes. The Engines execute. Reflection validates. Learning improves.**

### 5-Stage Cognitive Pipeline

| Stage | Component | Responsibility |
|-------|-----------|----------------|
| **0** | Context Manager + World Model | Collects everything Aura knows (RAM) + tracks the computer state |
| **1** | DMM (FusionEngine + ConfidenceGate) | Understands goals, selects capabilities, fuses into DecisionContext |
| **2** | Planner + TaskGraph + Validator | Produces structured ExecutionMap as a DAG, validates it |
| **3** | Execution Coordinator + Verification | Delegates to engines, verifies outcomes |
| **4** | Reflection + Learning | Self-evaluates, learns conservatively |

### New Architectural Pieces

| Piece | File | Purpose |
Stage 1: Intent & Decision Reasoning               Memory Engine
    │
    ▼
Stage 2: Goal & Task Decomposer
    │
    ▼
Stage 3: Supervisor Planner Integration
    │
    ▼
Stage 4: Execution Coordinator
    │   ├─ Native Desktop Engine
    │   ├─ Playwright Browser Engine
    │   ├─ Research Engine
    │   └─ Professional Expert Systems
    ▼
Stage 5: Verification & Self-Healing
    │
    ▼
Stage 6: Activity Trace & User Feedback
```

---

## 🧠 Core Capabilities

### 🧠 Cognitive Architecture
- **5-Stage Cognitive Pipeline**: Perception → Decision → Planning → Execution → Reflection/Learning
- **Shared Blackboard**: All stages read/write one shared working memory
- **Per-Domain Confidence**: Goal, entity, memory, capability, safety — not one number
- **Policy Governance**: Independent security/permission layer before planning
- **Long-Term Goals**: Goal Manager tracks progress across multiple requests
- **Parallel Execution**: TaskGraph DAG enables parallel engine execution
- **Artifact-Centric**: Everything Aura creates becomes an artifact

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

## ⚡ Permanent Aura System Invariants

Every layer of Aura adheres to three mandatory system invariants:

```text
PERCEPTION:
Normalize wording, never invent intent.

EXECUTION:
Recover transient failures, never fabricate success.

VERIFICATION:
Accept success only when independently observed evidence proves the goal.
```

---

## ⚡ Real Implementation & Wiring Audit (M18 – M25 Verified)

> **Implementation Guarantee:** Physical implementations are verified on a real Windows machine; explicit simulation fallbacks exist only for headless/non-GUI environments.

The table below outlines what is **physically wired to live system backends** versus what operates with **governance policy / fallback behavior**:

| Component / Capability | Implementation Status | Real Physical Wiring Details | Fallback / Policy Behavior |
| :--- | :--- | :--- | :--- |
| **Continuous Voice Loop & Speech** | 🟢 **REAL WIRED** | `AuraWakeDetector` (real-time mic energy/spectral wake detection), `GoogleSTTEngine` (`en-in` with `FasterWhisper` offline fallback + 4-layer anti-hallucination defense), `PiperTTS` (chunked local playback with `EdgeTTS` fallback), 5.0s conversational follow-up window, and Alexa-style barge-in & thinking interruption. | Degrades gracefully to Faster-Whisper on network drop, Edge-TTS on local Piper missing, and silence rejection on background noise. |
| **Desktop Native Engine** | 🟢 **REAL WIRED** | Real Win32 APIs (`FindWindow`, `SetForegroundWindow`, `ShowWindow`, `os.startfile`, `pyautogui`, `pyperclip`) + 2-Tier App Resolver (Fast-path aliases + fuzzy matching), Start Menu (`VK_LWIN`) toggle, Antigravity IDE focus, and WhatsApp UWP/web fallback. | In non-GUI/headless mode, safely logs simulated observation; returns clear honest error if app is missing. |
| **Long-Term Memory** | 🟢 **REAL WIRED** | SQLite persistent fact store (`Memory.db`), dynamic slot extraction, category-based indexing, and natural conversational fact recall (*"Your name is Sreekanta"*). | Falls back to active working memory if query fact is not in database. |
| **Cognitive Pipeline** | 🟢 **REAL WIRED** | 7-stage `MasterOrchestrator` (Stage 1 Memory Recall $\rightarrow$ Stage 2 Decision Engine $\rightarrow$ Stage 3 Task Decomposition $\rightarrow$ Stage 4 Supervisor Delegation $\rightarrow$ Stage 5 Backend Dispatch $\rightarrow$ Stage 6 Result Fusion $\rightarrow$ Stage 7 Memory Write) connected to Groq LLM. | Low confidence or unresolvable multi-target intents halt as honest `CLARIFICATION_REQUIRED`. |
| **Research Engine** | 🟡 **SCAFFOLDED** | Wikipedia provider, DuckDuckGo scraper, Trust-level scoring, conflict resolution, and citation generators built and unit-tested. | Ready for full autonomous multi-step web research integration in M21. |
| **Engineering & AST Engine** | 🟡 **SCAFFOLDED** | `EngineeringManager`, `CodeEditor` (with backups & rollback), `ASTManager` syntax validator, and code analyzers operational. | Deterministic code editing active; full LLM multi-file generation scheduled for M20. |

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

### 4. Test the Cognitive Architecture
```bash
# Run ACA test suite (8 tests)
.venv\Scripts\python.exe scripts/test_aca.py

# Run Executive Runtime test suite (12 tests)
.venv\Scripts\python.exe scripts/test_aura_brain_runtime.py
```

---

## 📚 Platform Documentation

Detailed technical guides and architecture specifications are available in the [`docs/`](docs/) directory:

- 🚀 [**Getting Started**](docs/getting-started.md) — Installation, environment setup, and launcher guide.
- 🏗️ [**Architecture Connection**](docs/AURA_ARCHITECTURE_CONNECTION.md) — How everything is connected end-to-end.
- 📊 [**Architecture Audit**](docs/AURA_ARCHITECTURE_AUDIT.md) — What's connected vs. what's missing.
- 🧠 [**AuraBrain Executive Runtime**](docs/AURABRAIN_EXECUTIVE_RUNTIME.md) — The cognitive runtime specification.
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