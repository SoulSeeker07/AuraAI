# Aura AI Platform Roadmap

Aura evolves systematically through modular engineering milestones toward a full AI Operating System.

---

## Evolution Timeline

```text
Phase 0 — Foundation (M01–M16)          ████████████████████  16/16  COMPLETE
Phase 1 — Shared Intelligence (M17–M18) ████████████████████   2/2   COMPLETE
Phase 2 — Capability Foundation (M19)   ████████████████████   1/1   COMPLETE
Phase 3 — Intelligence Expansion        ████████████████████   3/3   COMPLETE (M20 + M21 + M22)
Phase 4 — Autonomy & Daemon (M23)       ████████████████████   1/1   COMPLETE
Phase 5 — Autonomy (M24–M26)            ░░░░░░░░░░░░░░░░░░░░   0/3   PLANNED
Phase 6 — Autonomous Engineering (M27)  ░░░░░░░░░░░░░░░░░░░░   0/1   PLANNED
Phase 7 — Aura OS (M28)                 ░░░░░░░░░░░░░░░░░░░░   0/1   PLANNED
Phase 8 — Natural Interaction (M29)     ░░░░░░░░░░░░░░░░░░░░   0/1   PLANNED
Phase 9 — Aura GUI (M30)               ░░░░░░░░░░░░░░░░░░░░   0/1   PLANNED
```

---

## Current Platform Status (`v0.27.0-autonomous-daemon`)

### Completed Milestones (M01–M23)

- ✅ **M01–M16 — Core Foundation & Orchestration**: MasterOrchestrator 7-stage cognitive pipeline, 17 native Win32 desktop managers, 23 backend adapters, unified RuntimeSession.
- ✅ **M17 — Cognitive Memory**: 8 typed memory stores (Working, Short-Term, Long-Term, Episodic, Semantic, Procedural, Preference, Project) with decay, consolidation, and project-scoped isolation.
- ✅ **M18 — World Model**: Unified multi-provider environment representation (Workspace, Repository, Dependency, Symbol, Memory, Desktop).
- ✅ **M19 — Capability & Tool Runtime**: Dynamic `CapabilityRegistry`, 5 domain providers, `ActionRisk` taxonomy, and DAG cycle detection.
- ✅ **M20 — Coding Intelligence 2.0**: AST parsing, `CodeEditor` with physical byte-for-byte rollback, `AntigravityCodingBridge`, active IDE perception, and automated repair loop.
- ✅ **M21 — Research & Knowledge Hardening**: Evidence grounding (`claim_id` $\leftrightarrow$ `citation_key` $\leftrightarrow$ URL), citation preservation through `ResultMerger`, zero-refetch memory recall, and SSRF/egress filtering.
- ✅ **M22 — Multimodal Voice & Vision**: `DevicePrivacyEngine` pre-acquisition gating, sensitive-window default-BLOCK (credential dialogs), coordinate grounding, and multi-engine speech fallback.
- ✅ **M23 — Autonomous Daemon & Background Operations**: Bounded worker pool, SQLite `DaemonStateStore`, interval/cron scheduling, cooperative cancellation, crash recovery (`RECOVERY_REQUIRED`), and HMAC autonomy governance.
- ✅ **Security Hardening Track (Phases 1–4)**: DPAPI master keys, HKDF-SHA256 derivation, out-of-process `AuditWriterService` over authenticated Windows Named Pipe IPC, and Windows Event Log OS sink.

---

## Target Milestones (Upcoming)

### Milestone 24 — Event Runtime & Autonomous Triggers (`v0.28.0`) [PLANNED]
- 🎯 Asynchronous EventBus triggers (file system, process, network, time)
- 🎯 Condition evaluator engine for trigger firing
- 🎯 Persistent event queue and background reactive workers

### Milestone 25 — Professional Expert Systems (`v0.29.0`) [PLANNED]
- 🎯 Specialized domain planners: Software Engineering, Network Engineering, Cybersecurity, Finance
- 🎯 Domain-specific analysis heuristics and structured deliverables

### Milestone 26 — Personal Operating System (`v0.30.0`) [PLANNED]
- 🎯 Proactive daily agenda, calendar tracking, file organization
- 🎯 Repetitive desktop workflow automation

### Milestone 27 — Autonomous Engineering Platform (`v0.31.0`) [PLANNED]
- 🎯 Autonomous issue-to-PR development loop with human-in-the-loop gates

### Milestone 28 — Aura OS Runtime (`v1.0.0`) [PLANNED]
- 🎯 Fully integrated persistent AI operating system environment

### Milestone 29 — Natural Interaction Layer (`v1.1.0`) [PLANNED]
- 🎯 Full-duplex conversational voice, real-time barge-in interruption, acoustic echo cancellation

### Milestone 30 — Aura Command Center GUI (`v1.2.0`) [PLANNED]
- 🎯 Comprehensive desktop dashboard and visual cognitive monitor

---

*Last Updated: August 18, 2026 — See master [roadmap.md](../roadmap.md) for full specifications.*
