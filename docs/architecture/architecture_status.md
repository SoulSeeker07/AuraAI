# AuraAI Architecture Status (`v0.33.0`)

This document provides an overview of all AuraAI subsystems, architectural layers, and their current operational state.

---

## Subsystem Operational Status

| Subsystem | Status | Notes |
|:---|:---|:---|
| **Aura Brain (ACA)** | ✅ Stable | 7-stage cognitive pipeline (`MasterOrchestrator`), DMM, Strategy, Policy, Reflection |
| **Domain Expert Systems** | ✅ Stable | 4 specialized experts (Cybersecurity, Network, Software, Finance), Stage 2.9 routing |
| **Dynamic CodeAct Engine** | ✅ Stable | Code-as-action execution, AST validation, sandbox execution, closed-loop repair |
| **Smart Home & IoT Subsystem** | ✅ Stable | Home Assistant WebSocket/REST + local Tapo/Kasa KLAP AES-CBC-128 crypto |
| **PySide6 Desktop HUD Overlays** | ✅ Stable | Jarvis Rings, Chat Window, System Monitor, Weather, Agent Task Status, Personal OS Dashboard |
| **Capability & Backend Registry** | ✅ Stable | 24 registered backend adapters, 8 capability providers (80+ capabilities), dynamic discovery |
| **Native Win32 Desktop Engine** | ✅ Stable | 17 direct Win32 managers (Input, Terminal, ScreenAction, Window, File, Audio, Power, etc.) |
| **Cognitive Memory** | ✅ Stable | 8 typed stores (Working, Episodic, Semantic, Procedural, Preference, Project) + Recall + Decay |
| **Knowledge & RAG Service** | ✅ Stable | Semantic retrieval, ChromaDB/SQLite vector store, document chunking & parsing |
| **Autonomous Daemon & Triggers** | ✅ Stable | `TriggerScheduler`, `EventRuntime`, cron/interval triggers, crash recovery, HMAC governance |
| **Personal Operating System** | ✅ Stable | `DailyContextEngine`, sub-second `WorkspaceSearchEngine`, `RequestSource` isolation |
| **Autonomous Engineering Platform** | ✅ Stable | Closed-loop bug fixing, AST fault localization, safety ceiling, byte-exact rollback |
| **Sandboxed Pytest Test Runner** | ✅ Stable | Windows Job Object + `AuraSandboxUser` isolation, privilege dropping (`TD-008` resolved) |

---

## Acceptance Gates & Test Coverage

| Phase / Milestone | Status | Verified Acceptance Gates | Test Suite |
|:---|:---|:---|:---|
| **Phase 0 — Foundation (M01–M16)** | ✅ COMPLETE | 16/16 foundation milestones, 7-stage cognitive orchestrator, 17 native Win32 managers | `tests/` |
| **Phase 1 — Shared Intelligence (M17–M18)** | ✅ COMPLETE | Cognitive Memory (8 typed stores) & World Model | `tests/memory/`, `tests/unit/` |
| **Phase 2 — Capability Foundation (M19)** | ✅ COMPLETE | Dynamic capability registry, ActionRisk taxonomy | `tests/test_capability_registry.py` |
| **Phase 3 — Intelligence Expansion (M20–M22)** | ✅ COMPLETE | Coding Intelligence 2.0, Research Hardening, Multimodal Voice & Vision | `tests/test_codeact/`, `tests/unit/` |
| **Phase 4 — Autonomy & Daemon (M23)** | ✅ COMPLETE | Autonomous Daemon, crash recovery, HMAC governance | `tests/unit/test_auracore_autonomy.py` |
| **Phase 5 — Domain Expertise & Autonomy (M24–M25)** | ✅ COMPLETE | Event runtime, triggers, 4 domain experts, PlanDAGCompiler | `tests/unit/test_plandag_compiler.py` |
| **Phase 6 — Personal OS (M26)** | ✅ COMPLETE | DailyContextEngine, WorkspaceSearchEngine, TriggerScheduler | `tests/test_personal_os_g*.py` (21 tests) |
| **Phase 7 — Autonomous Engineering (M27)** | ✅ COMPLETE | Fault localization, safety ceiling, byte-exact rollback, PR assembler | `tests/test_engineering_g*.py` (35 tests) |
| **Phase 8 — Integrated Aura OS & HUDs (M28)** | ✅ COMPLETE | CodeAct runtime, PySide6 HUD overlays, Sandboxed pytest runner, RAG service | `tests/test_engineering_sandboxed_runner.py`, `tests/test_codeact/` |
| **Phase 9 — Smart Home & Ambient HUDs (M29)** | ✅ COMPLETE | HA client/ws, Tapo KLAP AES-CBC-128 driver, SmartHome backend & provider, Jarvis rings | `tests/test_smarthome_backend.py`, `tests/test_ha_client.py`, `tests/test_jarvis_rings.py` |

---

## Test Suite Summary

- **Total Deterministic Regression Tests**: 250+ tests (100% Passing)
- **CodeAct Sandbox Tests**: 43/43 Passing
- **Smart Home & IoT Tests**: 10+ Passing
- **Engineering Sandboxed Runner Tests**: 5/5 Passing
- **Personal OS Acceptance Tests**: 21/21 Passing
- **Engineering Platform Acceptance Tests**: 35/35 Passing
- **Desktop & Native Manager Tests**: 90/90 Passing

---

## Architectural Invariants & Security Guardrails

1. **Single Cognitive Entry Point**: All requests flow through `AuraCore.process_request()`.
2. **Strict Privilege Dropping**: Test execution and untrusted code run in `RestrictedUserSandbox` under Windows Job Objects.
3. **Protected Safety Ceiling**: Automated patches cannot modify security governance, write gates, or safety policies (`PROTECTED_SAFETY_CEILING`).
4. **Zero Split-Brain Memory**: All subsystems share the unified `MemoryManager` and SQLite memory store.
5. **Fail-Closed Human Merge Gate**: Destructive Git operations (`merge_to_main`, `git_push_force`) require out-of-band HMAC cryptographic ticket redemption.
