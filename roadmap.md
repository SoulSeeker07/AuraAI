# Aura AI Roadmap

A comprehensive roadmap for building Aura AI from an assistant into a complete AI Operating System through 26 milestones across 3 Eras.

## Project Overview

Aura is built as a modular AI Operating System rather than a chatbot. Each milestone extends the previous one without duplicating responsibilities. The project follows a 3-Era progression:

- **Era 1 — Foundation (Milestones 1–10)**: Core subsystems, OS execution pipeline, desktop perception, vision, voice, and workflow automation.
- **Era 2 — Intelligence & Orchestration (Milestones 11–16)**: RAG 2.0, multi-agent reasoning, engineering intelligence, research intelligence, desktop intelligence, and Cognitive Orchestration Layer (`AgentSession`, `ExecutionBudget`, `DecisionEngine`, `SupervisorAgent`, `Observation`, `Artifact`).
- **Era 3 — Capability Expansion & Runtime (Milestones 17–26)**: High-impact end-user capabilities built on top of the frozen core runtime without inventing new core abstractions.

### 🚩 Platform Maturity Progression

| Version | Milestone Title | Primary Scope | Status |
| :--- | :--- | :--- | :--- |
| `v0.16.0` | Cognitive Orchestration | DecisionEngine, Groq Executive Coordinator, SupervisorAgent | ✅ Stable |
| `v0.17.0` | Runtime Architecture | RuntimeSession Base, WorkerManager, SoftwareEngineeringSupervisor | ✅ Stable |
| `v0.18.0` | Runtime Stabilization | SafetyPolicy, Zero-LLM Interception, ADRs, Definition of Done | 🔒 **Frozen** |
| `v0.18.5` | Cleanup Sprint | Technical debt reduction, naming consistency, log refinement | ⏳ **In Progress** |
| `v0.19.0` | Cognitive Memory | Cross-domain persistent identity & conversational memory | 🎯 **Next** |
| `v0.20.0` | Voice Runtime | Streaming STT, Interruptible TTS, Barge-in, VAD, Mic Arbitration | 📋 Planned |
| `v0.21.0` | Browser Intelligence | Playwright session persistence & visual web reasoning | 📋 Planned |
| `v0.22.0` | GUI Runtime | Native Desktop GUI, overlay manager, interactive widgets | 📋 Planned |
| `v1.0.0`  | Aura OS Release | The First Stable AI Operating System Runtime | 🏁 Target Release |

**Current Status:** 18/26 Core Milestones & Runtime Extensions Complete (69.2% overall progress).

---


## 🏛️ Era 1 — Foundation (Milestones 1–10)
Establishes core capabilities, OS execution pipeline, desktop perception, vision, voice, and workflow automation.

### Milestone 1 — Aura Brain ⭐⭐⭐⭐⭐
The central intelligence of Aura as the request entry point.
**Status:** ✅ COMPLETE (100%)

### Milestone 2 — Capability Router ⭐⭐⭐⭐⭐
Routes requests to the correct subsystem instead of sending everything to an LLM.
**Status:** ✅ COMPLETE (100%)

### Milestone 3 — Memory 2.0 ⭐⭐⭐⭐⭐
Persistent intelligent memory that allows Aura to remember across sessions.
**Status:** ✅ COMPLETE (100%)

### Milestone 4 — Workspace Awareness ⭐⭐⭐⭐⭐
Continuous awareness of the user's desktop environment and workspace state.
**Status:** ✅ COMPLETE (100%)

### Milestone 5 — Tool Execution Engine ⭐⭐⭐⭐⭐
Unified execution pipeline for all tools and capabilities.
**Status:** ✅ COMPLETE (100%)

### Milestone 6 — Plugin Ecosystem ⭐⭐⭐⭐⭐
Fully modular system where every capability becomes a plugin.
**Status:** ✅ COMPLETE (100%)

### Milestone 7 — Vision System ⭐⭐⭐⭐⭐
Visual understanding capabilities for Aura to see and interpret the desktop.
**Status:** ✅ COMPLETE (100%)

### Milestone 8 — Voice System ⭐⭐⭐⭐⭐
Real-time conversational voice capability for Aura.
**Status:** ✅ COMPLETE (100%)

### Milestone 9 — Agent Runtime ⭐⭐⭐⭐⭐⭐
Goal-oriented agent capabilities that enable Aura to complete goals.
**Status:** ✅ COMPLETE (100%)

### Milestone 10 — Workflow Engine ⭐⭐⭐⭐⭐⭐
Persistent automation platform for users to create and manage complex workflows.
**Status:** ✅ COMPLETE (100%)

---

## 🧠 Era 2 — Intelligence & Orchestration (Milestones 11–16)
Teaches Aura how to think, delegate, plan, reason, coordinate backends, and fuse multi-modal results.

### Milestone 11 — Knowledge Intelligence (RAG 2.0) ⭐⭐⭐⭐⭐⭐
Searchable knowledge brain that understands repositories, documents, notes, and codebases.
**Status:** ✅ COMPLETE (100%)

### Milestone 12 — Multi-Agent Intelligence ⭐⭐⭐⭐⭐⭐
Specialized AI agents that collaborate to accomplish complex tasks.
**Status:** ✅ COMPLETE (100%)

### Milestone 13 — Engineering Intelligence ⭐⭐⭐⭐⭐⭐
Engineering-focused agent for software development tasks.
**Status:** ✅ COMPLETE (100%)

### Milestone 14 — Research Intelligence ⭐⭐⭐⭐⭐⭐
Research-focused agent for comprehensive research on any topic.
**Status:** ✅ COMPLETE (100%)

### Milestone 15 — Desktop Intelligence ⭐⭐⭐⭐⭐⭐⭐
Complete integration of desktop components into a cohesive desktop platform.
**Status:** ✅ COMPLETE (100%)

### Milestone 16 — Cognitive Orchestration Layer ⭐⭐⭐⭐⭐⭐⭐
The central decision-making and cognitive runtime of Aura (`AgentSession`, `ExecutionBudget`, `DecisionEngine`, `SupervisorAgent`, `Observation`, `Artifact`).
**Status:** ✅ COMPLETE (100%)

---

## 🚀 Era 3 — Capability Expansion (Milestones 17–26)
Builds powerful end-user capabilities on top of the frozen core runtime without inventing new core abstractions.

### Milestone 17.0 — System Knowledge & Identity Layer ⭐⭐⭐⭐⭐⭐⭐
Aura's permanent self-knowledge layer: who it is, everything it can do, how it routes work.
Includes `IdentityLoader`, `CapabilityCatalog`, `CommandCatalog`, `PromptBuilder`, and 6 knowledge YAML files.
Dynamic capability loading — new managers auto-register to the live catalog without prompt changes.
**Status:** ✅ COMPLETE (100%)  
*Modules*: `knowledge/` (6 YAML files), `src/core/system/` (4 Python modules).

### Milestone 17 — Cognitive Memory ⭐⭐⭐⭐⭐⭐⭐
Unifies conversation, execution, desktop, research, project, habit, and preference memory into a single persistent identity.
**Status:** 🟡 PARTIAL (40% Foundation Available)  
*Available Modules*: `Memory.py`, `src/memory/`, `agent_memory.py`, `engineering_memory.py`, SQLite schema.

### Milestone 18 — World Model ⭐⭐⭐⭐⭐⭐⭐
Unified graph representation of reality across desktop, projects, repos, research, browser, calendar, and memory.
**Status:** 🟡 PARTIAL (45% Foundation Available)  
*Available Modules*: `desktop_context.py`, `src/workspace/` (window tracker, file tracker, project detector), `knowledge_graph.py`, `symbol_graph.py`, `dependency_graph.py`.

### Milestone 19 — Coding Intelligence 2.0 ⭐⭐⭐⭐⭐⭐⭐
Deep multi-repo understanding, architecture analysis, bug localization, test generation, and refactoring via Antigravity, Claude Code, and Aider.
**Status:** 🟡 PARTIAL (50% Foundation Available)  
*Available Modules*: `antigravity_backend.py`, `repository_analyzer.py`, `ast_analyzer.py`, `code_editor.py`, `bug_fixer.py`, `git_intelligence.py`.

### Milestone 20 — Voice Runtime (Listen + Speak) ⭐⭐⭐⭐⭐⭐⭐
Complete audio operating subsystem: Wake word management, Streaming STT, Interruptible TTS (barge-in), Audio session management, VAD, Microphone arbitration, TTS queueing & cancellation.
**Status:** 🟡 PARTIAL (50% Foundation Available)  
*Available Modules*: `src/voice/` (`voice_manager.py`, `stt_engine.py`, `tts_engine.py`, `wake_word_detector.py`).


### Milestone 21 — Research Intelligence 2.0 ⭐⭐⭐⭐⭐⭐⭐
Deep iterative research loops, contradiction detection, evidence ranking, source confidence scoring, and long-running investigations.
**Status:** 🟡 PARTIAL (60% Foundation Available)  
*Available Modules*: `src/research/` (18 modules including `research_engine.py`, `reasoning_layer.py`, `evidence_merger.py`, `conflict_detector.py`, `citation_builder.py`).

### Milestone 22 — Event Runtime ⭐⭐⭐⭐⭐⭐⭐
Event-driven autonomous runtime triggering the DecisionEngine based on desktop, file, git, and system events.
**Status:** 🟡 PARTIAL (40% Foundation Available)  
*Available Modules*: `src/core/event_bus.py` (EventBus), `native_events.py`, `workflow_triggers.py`.

### Milestone 23 — Professional Expert Systems ⭐⭐⭐⭐⭐⭐⭐
Domain-specific expert planners (Networking Expert, Security Expert, DevOps Expert, Cloud Expert).
**Status:** 🟡 PARTIAL (40% Foundation Available)  
*Available Modules*: `src/engineering/` (`doctor.py`, `inspector.py`, `verify.py`), `network_manager.py`, `risk_analyzer.py`.

### Milestone 24 — Personal Operating System ⭐⭐⭐⭐⭐⭐⭐
Continuous background assistance managing user projects, habits, meetings, reminders, and daily workflows.
**Status:** 🟡 PARTIAL (35% Foundation Available)  
*Available Modules*: `src/core/app.py`, `hotkeys.py`, `overlay_manager.py`, `workflow_scheduler.py`.

### Milestone 25 — Autonomous Engineering Platform ⭐⭐⭐⭐⭐⭐⭐
End-to-end issue resolution loop: Receive Issue → Plan → Research → Code → Test → Review → Commit → Deploy → Monitor.
**Status:** 🟡 PARTIAL (45% Foundation Available)  
*Available Modules*: `doctor.py`, `verify.py`, `code_editor.py`, `bug_fixer.py`, `git_intelligence.py`, `MasterOrchestrator`.

### Milestone 26 — Aura OS ⭐⭐⭐⭐⭐⭐⭐
The complete AI Operating System layer sitting seamlessly on top of Windows and Linux.
**Status:** 🟡 PARTIAL (50% Foundation Available)  
*Available Modules*: `aura.py` (canonical launcher), `cli.py`, `main.py`, `src/core/app.py`, `docs/ARCHITECTURE_FREEZE.md`.

---

## 📊 Summary of Project Status

### Era 1: Foundation (Milestones 1–10)
| Milestone | Status | Codebase Modules |
| :--- | :--- | :--- |
| 1. Aura Brain | ✅ COMPLETE (100%) | `src/brain/aura_brain.py` |
| 2. Capability Router | ✅ COMPLETE (100%) | `src/routing/capability_router.py` |
| 3. Memory 2.0 | ✅ COMPLETE (100%) | `Memory.py`, `src/memory/` |
| 4. Workspace Awareness | ✅ COMPLETE (100%) | `src/workspace/workspace_manager.py` |
| 5. Tool Execution Engine | ✅ COMPLETE (100%) | `src/execution/execution_engine.py` |
| 6. Plugin Ecosystem | ✅ COMPLETE (100%) | `src/plugins/plugin_manager.py` |
| 7. Vision System | ✅ COMPLETE (100%) | `src/vision/vision_manager.py` |
| 8. Voice System | ✅ COMPLETE (100%) | `src/voice/voice_manager.py` |
| 9. Agent Runtime | ✅ COMPLETE (100%) | `src/agents/agent_manager.py` |
| 10. Workflow Engine | ✅ COMPLETE (100%) | `src/workflows/workflow_engine.py` |

**Era 1 Progress:** 10 / 10 Complete (100%)

### Era 2: Intelligence & Orchestration (Milestones 11–16)
| Milestone | Status | Codebase Modules |
| :--- | :--- | :--- |
| 11. Knowledge Intelligence (RAG 2.0) | ✅ COMPLETE (100%) | `src/knowledge/knowledge_base.py` |
| 12. Multi-Agent Intelligence | ✅ COMPLETE (100%) | `src/agents/agent_coordinator.py` |
| 13. Engineering Intelligence | ✅ COMPLETE (100%) | `src/engineering/` + `src/agents/` |
| 14. Research Intelligence | ✅ COMPLETE (100%) | `src/research/` + `src/brain/` |
| 15. Desktop Intelligence | ✅ COMPLETE (100%) | `src/desktop/native/` |
| 16. Cognitive Orchestration Layer | ✅ COMPLETE (100%) | `src/core/orchestration/` + `src/core/backends/` |

**Era 2 Progress:** 6 / 6 Complete (100%)

### Era 3: Capability Expansion (Milestones 17–26)
| Milestone | Status | Existing Foundations |
| :--- | :--- | :--- |
| **17.0. System Knowledge & Identity Layer** | ✅ COMPLETE (100%) | `knowledge/` (6 YAML), `src/core/system/` (4 modules) |
| 17. Cognitive Memory | 🟡 PARTIAL (40%) | `src/memory/`, `Memory.py`, `engineering_memory.py` |
| 18. World Model | 🟡 PARTIAL (45%) | `desktop_context.py`, `src/workspace/`, `knowledge_graph.py` |
| 19. Coding Intelligence 2.0 | 🟡 PARTIAL (50%) | `antigravity_backend.py`, `code_editor.py`, `ast_analyzer.py` |
| 20. Browser Intelligence | 🟡 PARTIAL (30%) | `page_reader.py`, `web_search.py`, `browser_context.py` |
| 21. Research Intelligence 2.0 | 🟡 PARTIAL (60%) | `src/research/` (18 modules ready for backend adapters) |
| 22. Event Runtime | 🟡 PARTIAL (40%) | `src/core/event_bus.py`, `native_events.py` |
| 23. Professional Expert Systems | 🟡 PARTIAL (40%) | `doctor.py`, `inspector.py`, `network_manager.py` |
| 24. Personal Operating System | 🟡 PARTIAL (35%) | `app.py`, `hotkeys.py`, `overlay_manager.py` |
| 25. Autonomous Engineering Platform | 🟡 PARTIAL (45%) | `doctor.py`, `verify.py`, `bug_fixer.py`, `MasterOrchestrator` |
| 26. Aura OS | 🟡 PARTIAL (50%) | `aura.py`, `cli.py`, `main.py`, `ARCHITECTURE_FREEZE.md` |

**Era 3 Progress:** 0 / 10 Complete (10 Partial Foundations Active)

---

## 📈 Progress Overview

```text
Era 1 — Foundation (Milestones 1–10)               ███████████████████  10/10 (100% complete)
Era 2 — Intelligence (Milestones 11–16)            ███████████████████  6/6   (100% complete)
Era 3 — Capability Expansion (Milestones 17–26)    █████████░░░░░░░░░░  10 Partial Foundations Active
```

**Overall Progress:** 16 / 26 Milestones Complete (61.5%), 10 / 10 Expansion Milestones with active foundational code.

---

## 🎯 Immediate Priority Expansion Order (Era 3)

1. **Research Intelligence 2.0 (Milestone 21)** ⭐⭐⭐⭐⭐⭐⭐ (60% foundation ready in `src/research/`)
   - Wire 18 existing research modules into `ResearchPlanner` adapter and `BackendRegistry` with live search keys.
2. **Coding Intelligence 2.0 (Milestone 19)** ⭐⭐⭐⭐⭐⭐⭐ (50% foundation ready in `src/agents/` and `src/core/`)
   - Expand `AntigravityBackendAdapter` and integrate multi-repo refactoring and test generation.
3. **World Model (Milestone 18)** ⭐⭐⭐⭐⭐⭐⭐ (45% foundation ready in `src/desktop/` and `src/workspace/`)
   - Consolidate desktop state, workspace tracker, and knowledge graph into a unified `WorldModel` query interface.
4. **Cognitive Memory (Milestone 17)** ⭐⭐⭐⭐⭐⭐⭐ (40% foundation ready in `src/memory/`)
   - Unify conversation memory, execution memory, and project memory into `AgentSession`.

---

## 📜 Platform Architecture Constitution
Read [`docs/ARCHITECTURE_FREEZE.md`](docs/ARCHITECTURE_FREEZE.md) for frozen platform contracts and contributor extension guidelines.

---

Last Updated: August 2026
