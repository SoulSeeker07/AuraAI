# Aura AI

**The Autonomous AI Operating System Platform**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
[![Platform Version](https://img.shields.io/badge/version-v1.0.0--holographic--ai--core-green.svg)](RELEASE.md)
[![Codebase](https://img.shields.io/badge/source-600%2B%20files%20%7C%205%2C800%2B%20KB-brightgreen.svg)](src/)
[![Security Model](https://img.shields.io/badge/security-DPAPI%20%7C%20HMAC--SHA256%20%7C%20Job%20Object%20Sandbox-blue.svg)](docs/security.md)
[![Regression Suite](https://img.shields.io/badge/regression-260%2B%20passing%20%7C%20100%25-brightgreen.svg)](tests/)

Aura AI is a modular, high-reliability **AI Operating System Platform** built on the **Aura Cognitive Architecture (ACA)** — a staged cognitive runtime that unifies voice perception, natural language decision-making, planning, desktop OS automation, dynamic Python CodeAct execution, smart home IoT control, live PySide6 HUD overlays, reflection, and long-term memory into a single coordinated system.

> **Aura is an AI Operating System rather than a chatbot.** It separates cognition from execution. The ACA acts as the cognitive runtime — understanding goals, reasoning about context, planning execution maps, coordinating specialized engines, verifying outcomes, reflecting on failures, and learning from interactions. Desktop operations are handled by the 17 Native Desktop Managers (Win32), CodeAct execution by the sandboxed Python CodeAct engine, smart home IoT by the Home Assistant & Tapo integration, continuous voice by the low-latency Speech System (AuraWake + Google STT + Piper TTS), workspace telemetry by live HUD widgets, Holographic Command Center by PySide6 Core GUI, and software engineering by the Autonomous Engineering Platform.

---

## 🚀 Development Status & Milestone Progress

```text
Operational Subsystems (Live on Physical System)
├── Core Runtime Pipeline — OPERATIONAL (7-stage MasterOrchestrator, 57KB cognitive core)
├── Native Desktop Engine — OPERATIONAL (17 Native Managers: Input, Terminal, ScreenAction, Window, File, Audio, Power, etc.)
├── Unified Backend Registry — OPERATIONAL (24 Live Backend Adapters including SmartHome)
├── Universal Capability Registry — OPERATIONAL (8 Domain Providers with 80+ Capabilities)
├── Dynamic CodeAct Engine (M28) — OPERATIONAL (Code-as-action, AST validation, sandbox execution, closed-loop repair)
├── Smart Home & IoT Engine (M29) — OPERATIONAL (Home Assistant WebSocket/REST + Tapo/Kasa KLAP AES-CBC-128 crypto)
├── PySide6 Desktop HUD Overlays (M28/M29/M31) — OPERATIONAL (Voice Notch Dynamic Island, Dedicated Live Log Console, Jarvis Rings, Chat Window, System Monitor, Weather, Agent Task Status, Personal OS Dashboard, Matrix, System Status)
├── Aura Holographic Neural Notch HUD (M31) — OPERATIONAL (Always-on-top flush taskbar mount, hardware waveform, context action cards, 5s auto-collapse result lifecycle)
├── Dedicated Live System Logs Console (M31) — OPERATIONAL (Zero-lag 64KB binary seek tailing, 6 real-time category filters with dynamic badge counters)
├── Holographic AI Core GUI & Command Center (M30) — OPERATIONAL (RealBackendBridge, Reactive DAG Visualizer, Tactical Telemetry, Token Tracker)
├── Cognitive Memory Importers (M30) — OPERATIONAL (Claude JSON + ChatGPT ZIP/JSON parsers, Fuzzy Deduplication, Retrieval Gate, Consolidation)
├── Cognitive Memory (M17) — COMPLETE (8 typed stores: Working, Episodic, Semantic, Procedural, Preference, Project + Decay + Consolidation)
├── World Model (M18) — COMPLETE (Multi-provider environment model with workspace, repository, and memory integration)
├── Coding Intelligence 2.0 (M20) — COMPLETE (AST analysis, code editor with rollback, Antigravity bridge, automated repair loop)
├── Research & Knowledge Hardening (M21) — COMPLETE (Evidence grounding, citation preservation, zero-refetch memory recall, SSRF protection)
├── Multimodal Voice & Vision (M22) — COMPLETE (Pre-capture DevicePrivacyEngine fail-closed, sensitive-window default-BLOCK, UI grounding)
├── Autonomous Daemon & Background Operations (M23) — COMPLETE (Durable state machine, crash recovery, cancellation, cryptographic HMAC governance)
├── Event Runtime & Autonomous Intent Execution (M24) — COMPLETE (AuraEvent contract, signal correlation, situational awareness, closed-loop triggers)
├── Professional Expert Systems & Cognitive Routing (M25) — COMPLETE (Cybersecurity, Network, Software, Finance, PlanDAGCompiler, Stage 2.9 routing)
├── Personal Operating System (M26) — COMPLETE (DailyContextEngine, sub-second WorkspaceSearchEngine, TriggerScheduler, RequestSource isolation)
├── Autonomous Engineering Platform (M27) — COMPLETE (Closed-loop repair, AST fault localization, safety ceiling, byte-exact rollback, PR assembler)
├── Sandboxed Pytest Test Runner (M28) — COMPLETE (Windows Job Object + RestrictedUserSandbox privilege dropping, TD-008 resolved)
└── Core Platform Regression Suite — 260+ PASSING (100% Green)
```

### Codebase Metrics

| Metric | Value |
|:---|:---|
| **Platform Version** | `v1.1.0-neural-notch` |
| **Native Desktop Managers** | 17 Win32 managers |
| **Backend Adapters** | 24 registered adapters |
| **Capability Providers** | 8 registered providers (80+ capabilities) |
| **Desktop HUD Overlays** | 10 live PySide6 widgets |
| **Aura Neural Notch HUD** | Always-on flush Dynamic Island with live hardware spectrum |
| **Live Log Console** | High-speed binary seek tailing with 6 category filters |
| **Holographic Core GUI** | Full Command Center with DAG Visualizer & Telemetry |
| **Domain Experts** | 4 specialized experts (Cybersecurity, Network, Software, Finance) |
| **Milestones Complete** | M01–M31 (31/31 baseline complete) |
| **Core Regression Suite** | 260+ passing (100% Green) |

---

## 🏛️ System Architecture

Aura operates as an AI Operating System where the **Aura Cognitive Architecture (ACA)** serves as the cognitive runtime — the only component that "thinks" — while execution is delegated to specialized, sandboxed engines.

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
Policy Engine & Cryptographic Authority                    │
     │   ├── HMAC-SHA256 Human-in-the-Loop Gate            │
     │   ├── Strict Executable Allowlists                  │
     │   └── Dynamic System Root Protection                │
     │                                                     │
     ▼                                                     │
Stage 2: Planning & Strategy                              │
     │   ├── Planner (ExecutionMap DAG)                    │
     │   ├── TaskGraph (DAG for parallel execution)        │
     │   └── Validator                                     │
     │                                                     │
     ▼                                                     │
RuntimeSession (Source of Truth)                          │
     │                                                     │
     ▼                                                     │
Stage 3: Execution Coordination (20 Backend Adapters)     │
     │   ├── Terminal / Shell Execution Engine             │
     │   ├── Input Simulation (SendInput Mouse/Keyboard)   │
     │   ├── Screen Action Engine (Vision Grounding)       │
     │   ├── Desktop Native Engine (17 Win32 Managers)     │
     │   ├── Productivity Plugins (Email/Calendar/Office)  │
     │   ├── DevOps Plugins (Docker, MCP Client)           │
     │   └── Verification & Rollback                       │
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

## 🖥️ The 17 Native Desktop Managers & 20 Backend Engines

Aura AI implements 17 direct Win32/native managers in `src/desktop/native/managers/` and 20 backend adapters in `src/core/backends/`:

| Subsystem | Native Manager | Backend Adapter | Key Live Capabilities |
|:---|:---|:---|:---|
| **Input Simulation** | `InputManager` | `InputBackendAdapter` | Pure Win32 ctypes `SendInput` mouse movement, clicks, drag, scroll, key events, hotkeys, and UTF-16 surrogate pairs. |
| **Terminal & CLI** | `TerminalManager` | `TerminalBackendAdapter` | PowerShell/CMD synchronous & asynchronous execution, session lifecycle, env vars, CWD tracking, and stdin streaming. |
| **Screen & Computer Use** | `ScreenActionManager` | `ScreenActionBackendAdapter` | Full screen capture, coordinate grounding, synthetic action dispatch, and verification loop. |
| **Window Control** | `WindowManager`, `AdvancedWindowManager` | `DesktopEngineBackend` | Enumerate windows, focus, minimize, maximize, snap grids, pin topmost, and adjust window opacity. |
| **Filesystem** | `FileManager` | `FilesystemPlugin` | CRUD, recursive list, file info, size calculation, grep-like content search, archive compression/extraction, and watching. |
| **Notifications & Audio** | `NotificationManager`, `AudioManager` | `NotificationBackendAdapter` | Native Windows toast popups, Win32 `MessageBoxW`, audio sound cues (`winsound`), volume control, and scheduled alerts. |
| **Task Scheduler** | `SchedulerManager` | `SchedulerBackendAdapter` | One-shot timers, interval schedules, cron patterns, and cancellation. |
| **System Settings** | `SettingsManager` | `SettingsBackendAdapter` | Windows Registry (`winreg`) toggles, dark mode switching, startup app management, and timezone queries. |
| **Software & Packages** | `SoftwareManager` | `SoftwareBackendAdapter` | Installed applications enumeration, `winget` installation, uninstallation, and update checks. |
| **System Security** | `SecurityManager` | `SecurityBackendAdapter` | Windows Firewall profile inspection, Defender status, UAC elevation level checks, and lock workstation. |
| **DevOps & Containers** | `DockerPlugin` | `DockerBackendAdapter` | Container list, start, stop, restart, image management, and inspection via Docker CLI. |
| **MCP Integration** | `MCPPlugin` | `MCPBackendAdapter` | Model Context Protocol server registration, listing, and tool invocation. |
| **Productivity** | `EmailPlugin`, `CalendarPlugin`, `OfficePlugin` | `EmailBackendAdapter`, `CalendarBackendAdapter`, `OfficeBackendAdapter` | IMAP/SMTP email handling, SQLite-backed calendar events and task management, DOCX/XLSX generation. |
| **System Diagnostics** | `DisplayManager`, `PowerManager`, `NetworkManager` | `DesktopEngineBackend` | Display resolution, DPI scaling, multi-monitor topology, battery percentage, charging state, NIC list, and ping tests. |

---

## 🛡️ Security Architecture & Human-in-the-Loop Governance

Aura AI implements a **Defense-in-Depth Security Framework** to govern autonomous AI execution:

1. **Cryptographic HMAC-SHA256 Human Approval Gate:**
   - High-risk operations (e.g. process termination, system modifications, non-allowlisted executables) return an un-signed `ticket_id` and halt autonomous execution.
   - Only the out-of-band Human UI/CLI channel possessing the internal HMAC secret can generate a valid signature.
   - LLM self-supplied tokens or replay attacks are strictly rejected via constant-time comparison (`hmac.compare_digest`).
2. **Hash-Chained Cryptographic Audit Ledger:**
   - Append-only, SHA-256 Merkle-style hash-chained and HMAC-signed audit ledger.
   - Mathematical chain verification API to detect any log tampering, modification, insertion, or history truncation.
3. **Strict Developer Tool Allowlist:**
   - Autonomous CLI execution is strictly scoped to approved developer tools (`git`, `pytest`, `python`, `node`, `npm`, `cargo`, `ruff`, etc.).
   - General-purpose shell interpreters (`powershell`, `pwsh`, `cmd`, `bash`) are excluded from autonomous execution to prevent nested-shell bypasses.
4. **Network Egress Policy:**
   - Domain-level egress filtering with allow/deny lists for outbound network requests.
5. **OS Process Sandboxing:**
   - Dedicated `AuraSandboxUser` with kernel NTFS DACLs, Win32 Job Objects, Docker isolation, and workspace jail.
6. **De-Obfuscation Pipeline:**
   - Normalizes PowerShell backtick escapes, token split quotes, and string concatenations prior to evaluation.
7. **Dynamic System Root Protection:**
   - Dynamically resolves `%SystemDrive%`, `%WINDIR%`, `%ProgramFiles%`, and `%USERPROFILE%` at runtime to block relative wildcard deletion attacks in system roots.

---

## 🧠 Cognitive Memory System (M17)

Aura's memory is not a simple key-value store — it's a multi-layered cognitive memory system:

```text
Cognitive Memory
├── Working Memory       — active context in the current session
├── Short-Term Memory    — recent interactions and outputs
├── Long-Term Memory     — persistent facts and entities across sessions
├── Episodic Memory      — timestamped "what happened when" narrative
├── Semantic Memory      — concepts, entities, and relationships
├── Procedural Memory    — learned workflows and how-to sequences
├── Preference Memory    — user style, formatting, tooling choices
├── Project Memory       — per-project context, decisions, history
└── Memory Recall        — relevance-ranked, scored retrieval with decay
```

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

### 3. Running Automated Tests
```bash
# Collect and run the full test suite (1,350 tests)
.\.venv\Scripts\python.exe -m pytest tests/ -v

# Run specific security and capability tests
.\.venv\Scripts\python.exe -m pytest tests/test_all_new_capabilities.py tests/test_capability_registry.py -v
```

---

## 📊 Milestone Progress

```text
━━━ COMPLETE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M01–M16   Phase 0 — Foundation                    16/16 milestones ✅
M17       Cognitive Memory                        ✅
M18       World Model                             ✅
M19       Capability & Tool Runtime               ✅
M20       Coding Intelligence 2.0                 ✅
M21       Research & Knowledge Hardening          ✅
M22       Multimodal Voice & Vision               ✅
M23       Autonomous Daemon & Background Ops      ✅
M24       Event Runtime & Autonomous Triggers     ✅
M25       Professional Expert Systems             ✅
M26       Personal OS Proactive Automation        ✅
M27       Autonomous Engineering Platform         ✅
M28       Dynamic CodeAct & Desktop HUD Overlays  ✅

━━━ UPCOMING ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M29       Multi-User & Enterprise Governance      PLANNED
M30       Ambient Voice & Spatial Audio           PLANNED
```

See [docs/roadmap.md](docs/roadmap.md) and [docs/milestones/](docs/milestones/) for detailed specifications.

---

## 📄 License

**AuraAI Proprietary Software License Version 1.0**  
Copyright (c) 2026 Sreekanta YR. All Rights Reserved.