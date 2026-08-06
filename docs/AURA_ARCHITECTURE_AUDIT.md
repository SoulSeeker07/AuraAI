# Aura Architecture — Complete Feature & Runtime Audit (v0.19 ACA)

> **CORE PRINCIPLE:**  
> **"The architecture is largely complete. The runtime is not."**

This document provides a realistic, evidence-backed audit of the **Aura Cognitive Architecture (ACA)** vs. **Runtime Reality**.

---

## 🧊 Architecture Freeze Directive

> [!IMPORTANT]
> **The ACA architecture is now frozen.**
> Do not create new cognitive modules, planners, schemas, or runtime layers unless explicitly approved. All engineering effort must focus on runtime convergence, event-driven execution, continuous world-state updates, real engine integration, production telemetry, and end-to-end validation. Every commit must increase the percentage of real user requests executed exclusively through the ACA pipeline.

---

## 📊 High-Level Maturity Assessment

| Layer | Score | Status / Technical Reality |
| ----- | ----- | -------------------------- |
| **Architecture** | **98%** | Excellent, coherent 5-stage cognitive pipeline design |
| **Cognitive Runtime** | **90%** | Solid foundation: Blackboard (`CognitiveState`), `Thought`, Strategy, Policy, Planner, TaskGraph, RuntimeSession, Artifacts |
| **Runtime Integration** | **60%** | Good progress; `ExecutionCoordinator` resolves engines via `EngineRegistry` & `engine_adapters.py`, legacy bypasses isolated in allow-list |
| **Product Integration** | **45%** | Real CLI, Voice, GUI, Browser, Desktop, Engineering, and Research converging on the same runtime |
| **Production Readiness** | **25–30%** | Reliability, retries, error recovery, telemetry, monitoring, performance, long-running sessions, and real-world edge cases |

---

## 📋 ACA Migration Tracker

The CI guardrails explicitly isolate legacy engine instantiations outside `ExecutionCoordinator`. Each exception in `tests/architecture/test_guardrails.py` is governed by a strict contract specifying a reason, owner, and milestone:

| Component / File Path | Reason | Owner | Milestone | Status |
| --------------------- | ------ | ----- | --------- | ------ |
| `src/agents/browser_agent.py` | Legacy browser agent direct engine instantiation | Browser Team | v0.20 | 🟡 ACA Pending |
| `src/core/backends/adapters/browser_backend.py` | Legacy adapter direct browser engine call | Integration Team | v0.20 | 🟡 ACA Pending |
| `src/desktop/native/desktop_execution_engine.py` | Native desktop execution engine legacy bootstrap | Desktop Team | v0.20 | 🟡 ACA Pending |
| `src/engineering/engineering_manager.py` | Legacy engineering sub-engines direct instantiation | DevOps Team | v0.20 | 🟡 ACA Pending |
| `src/vision/vision_plugin.py` | Legacy vision plugin direct instantiation | Vision Team | v0.20 | 🟡 ACA Pending |

*Rule: An exception is removed from the allow-list only after it is refactored to route through `ExecutionCoordinator` / `EngineRegistry`.*

---

## 🏥 Runtime Health & Capability Discovery

`EngineRegistry` tracks engine health states and self-advertising capabilities to enable dynamic DMM fallbacks and resilient execution:

```text
DesktopEngine     ──► READY     │ Capabilities: [launch_app, focus_window, type_text, click, screenshot]
BrowserEngine     ──► READY     │ Capabilities: [navigate, search, download, fill_form, extract_dom]
ResearchEngine    ──► BUSY      │ Capabilities: [deep_search, synthesize, cite_sources]
EngineeringEngine ──► RUNNING   │ Capabilities: [ast_parse, refactor_symbol, run_tests, fix_bug]
VoiceEngine       ──► OFF       │ Capabilities: [stt_listen, tts_speak]
VisionEngine      ──► OFF       │ Capabilities: [ocr_extract, ui_element_detect]
MemoryEngine      ──► READY     │ Capabilities: [query_facts, store_exchange, search_embeddings]
```

*Resilience Example:* When DMM detects `ResearchEngine` is `BUSY` or `FAILED`, it dynamically falls back to `BrowserEngine.search`.

---

## 🔍 Detailed Component Audit

### ✅ REAL — Fully Implemented Architecture

| Component | Status | Evidence |
|-----------|--------|----------|
| **AuraCore (OS Kernel)** | ✅ REAL | Entrypoint: `process_request()` → `ACABrain.process()` |
| **Blackboard (`CognitiveState`)** | ✅ REAL | Shared working memory — all stages read/write |
| **ContextManager (Stage 0)** | ✅ REAL | Collects conversation, memory, workspace state |
| **WorldModel (Stage 0)** | ✅ REAL | Tracks focused window, apps, git branch, browser tabs |
| **GoalAnalyzer (Stage 1)** | ✅ REAL | Decomposes requests into goals and sub-goals |
| **CapabilitySelector (Stage 1)** | ✅ REAL | Queries self-advertising engine capabilities |
| **FusionEngine (Stage 1)** | ✅ REAL | Fuses all retrieval into `Thought` (`DecisionContext`) |
| **ConfidenceGate (Stage 1)** | ✅ REAL | Per-domain confidence scores + clarification |
| **GoalManager** | ✅ REAL | Long-term goal tracking with progress, sessions, artifacts |
| **PolicyEngine** | ✅ REAL | Governance — blocks dangerous requests (tested) |
| **StrategyEngine (Stage 1.5)** | ✅ REAL | Determines high-level approach (e.g. reuse open app vs launch) |
| **ACAPlanner (Stage 2)** | ✅ REAL | Consumes `Thought` & Strategy → produces `ExecutionGraph` |
| **TaskGraph / ExecutionGraph** | ✅ REAL | DAG with topological sort for parallel execution |
| **ExecutionMapValidator (Stage 2)** | ✅ REAL | Validates engines, actions, URLs, dangerous commands |
| **RuntimeSession** | ✅ REAL | Source of truth — lifecycle, progress, artifacts |
| **EngineRegistry** | ✅ REAL | Centralized lookup & health monitoring (`EngineRegistry.get_instance().resolve()`) |
| **Engine Adapters** | ✅ REAL | `src/brain/aca/engine_adapters.py` implementing unified `Engine` interface for 9 engines |
| **ExecutionCoordinator (Stage 3)** | ✅ REAL | Delegates steps via EngineRegistry / callbacks / orchestrator |
| **VerificationEngine (Stage 3)** | ✅ REAL | Checks each verification criterion |
| **ArtifactManager** | ✅ REAL | Collects artifacts from execution |
| **ReflectionEngine (Stage 4)** | ✅ REAL | Recovery patterns, user notification |
| **LearningEngine (Stage 4)** | ✅ REAL | Conservative — only explicit facts/preferences/behaviors |

### 🧪 TEST SUITE CLASSIFICATION

| Test Suite | Type | Description |
| ---------- | ---- | ----------- |
| `tests/architecture/test_guardrails.py` | Architecture Guardrails | Enforces structural constraints & `ENGINE_ALLOWLIST` contracts via AST |
| `tests/e2e/test_aca_runtime_scenarios.py` | Runtime Integration Tests | Validates ACA → `ExecutionCoordinator` → `EngineRegistry` → `EngineAdapters` pipeline |
| `tests/e2e/test_real_e2e_acceptance.py` | Physical OS E2E Tests | Validates physical OS side effects (Windows HWND creation, process destruction, disk I/O) |

---

## 🚀 5-Sprint Convergence Roadmap

### Sprint 1 – Runtime Convergence (Phase 1 Complete)
* Route **every** user request through ACA.
* Refactor all 5 legacy bypasses (`browser_agent.py`, `browser_backend.py`, `desktop_execution_engine.py`, `engineering_manager.py`, `vision_plugin.py`).

### Sprint 2 – Real Engine Integration
* Wire production backends (Desktop, Browser, Research, Engineering, Voice, Vision) through `EngineAdapters`.
* Expose self-advertising capability lists (`engine.capabilities`) and health status (`READY`, `BUSY`, `FAILED`, `DISABLED`, `OFF`).

### Sprint 3 – Continuous Decision Loop
* Evolve from single-pass planning to continuous execution: `Observe → Think → Plan → Execute Step → Observe → Update World → Re-plan → Execute Next Step`.
* Re-query `WorldModel.refresh()` after each execution step (updating world state mid-task).

### Sprint 4 – Adaptive Learning
* Learn strictly from verified execution successes and confirmed user preferences.

### Sprint 5 – Autonomous Workflows & Event Bus
* Multi-session execution, background task continuation, and event-driven decoupled triggers via `EventBus` (`EventBus.publish()`).