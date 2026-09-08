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
Phase 5 — Domain Expertise & Autonomy   ████████████████████   2/2   COMPLETE (M24 + M25)
Phase 6 — Personal OS & Daily Workflows ████████████████████   1/1   COMPLETE (M26)
Phase 7 — Autonomous Engineering Loop   ████████████████████   1/1   COMPLETE (M27)
Phase 8 — Integrated Aura OS & HUDs     ████████████████████   1/1   COMPLETE (M28)
Phase 9 — Smart Home & Ambient HUDs     ████████████████████   1/1   COMPLETE (M29)
Phase 10 — Holographic Core & Subagents ████████████████████   2/2   COMPLETE (M30 + M31)
Phase 11 — Interaction, Focus & Vision  ████████████████████   4/4   COMPLETE (M32 + M33 + M34 + M35)
Phase 12 — Multi-User & Enterprise Sinks░░░░░░░░░░░░░░░░░░░░   0/1   PLANNED
```

---

## Current Platform Status (`v1.4.3-interactive-execution-governance-and-safety-hardening`)

### Completed Milestones (M01–M35)

- ✅ **M01–M16 — Core Foundation & Orchestration**: MasterOrchestrator 7-stage cognitive pipeline, 17 native Win32 desktop managers, 23 backend adapters, unified RuntimeSession.
- ✅ **M17 — Cognitive Memory**: 8 typed memory stores (Working, Short-Term, Long-Term, Episodic, Semantic, Procedural, Preference, Project) with decay, consolidation, and project-scoped isolation.
- ✅ **M18 — World Model**: Unified multi-provider environment representation (Workspace, Repository, Dependency, Symbol, Memory, Desktop).
- ✅ **M19 — Capability & Tool Runtime**: Dynamic `CapabilityRegistry`, 5 domain providers, `ActionRisk` taxonomy, and DAG cycle detection.
- ✅ **M20 — Coding Intelligence 2.0**: AST parsing, `CodeEditor` with physical byte-for-byte rollback, `AntigravityCodingBridge`, active IDE perception, and automated repair loop.
- ✅ **M21 — Research & Knowledge Hardening**: Evidence grounding (`claim_id` $\leftrightarrow$ `citation_key` $\leftrightarrow$ URL), citation preservation through `ResultMerger`, zero-refetch memory recall, and SSRF/egress filtering.
- ✅ **M22 — Multimodal Voice & Vision**: `DevicePrivacyEngine` pre-acquisition gating, sensitive-window default-BLOCK (credential dialogs), coordinate grounding, and multi-engine speech fallback.
- ✅ **M23 — Autonomous Daemon & Background Operations**: Bounded worker pool, SQLite `DaemonStateStore`, interval/cron scheduling, cooperative cancellation, crash recovery (`RECOVERY_REQUIRED`), and HMAC autonomy governance.
- ✅ **M24 — Event Runtime & Autonomous Intent Execution**: Canonical `AuraEvent` contract, `EventRuntime` deduplication & multi-signal correlation engine, `EventInterpreter` situational awareness, `AutonomyPolicyGate` cryptographic authorization, `FilesystemWatcher` & `ProcessMonitor` telemetry producers, and closed-loop autonomous execution.
- ✅ **M25 — Professional Expert Systems & Cognitive Routing**: 4 Domain Experts (Cybersecurity, Network Engineering, Software Engineering, Financial Analysis), `PlanDAGCompiler` reasoning-to-execution translation, Stage 2.9 opt-in router in `MasterOrchestrator`, fail-closed artifact/confidence threshold gates (`ArtifactLowConfidence`, `ArtifactPayloadMissing`), and domain-specific observation formatting.
- ✅ **Security Hardening Track (Phases 1–4)**: DPAPI master keys, HKDF-SHA256 derivation, out-of-process `AuditWriterService` over authenticated Windows Named Pipe IPC, and Windows Event Log OS sink.
- ✅ **M26 — Personal Operating System (`v0.30.0`)**: Proactive daily context synthesis (`DailyContextEngine`), sub-second workspace search index (`WorkspaceSearchEngine`), autonomous trigger dispatch (`TriggerScheduler`), `RequestSource` classification with `ContextVar`-scoped autonomy isolation, and persistent OS state store (`PersonalOSStateStore`).
- ✅ **M27 — Autonomous Engineering Platform (`v0.31.0`)**: Closed-loop bug fixing, test-driven repair, and PR assembly; protected safety ceiling (`PROTECTED_SAFETY_CEILING`); AST fault localization; single-write gate enforcement (`WorkspacePolicy`); binary byte-exact baseline snapshot/rollback; fail-closed human cryptographic merge gate (`PatchBundleAssembler.authorize_git_operation`).
- ✅ **M28 — Dynamic CodeAct Runtime, HUD Overlays & Integrated Aura OS (`v0.32.0`)**: Python Code-as-action execution engine (`DynamicCodeActExecutor`, `CodeSandbox`, multiline fence parsing, AST validation); Modern PySide6 desktop HUD overlays (`SystemMonitorOverlay`, `WeatherOverlay`, `AgentTaskStatusOverlay`, `PersonalOSDashboardOverlay`, `ChatWindowOverlay`); `RealBackendBridge` telemetry wiring; ChromaDB/SQLite RAG knowledge service (`RAGService`); Job Object-sandboxed pytest isolation (`SandboxedPytestRunnerAdapter`).
- ✅ **M29 — Smart Home / IoT Integration & Ambient Desktop HUD Interaction (`v0.33.0`)**: Home Assistant WebSocket/REST client (`HAWebSocketClient`, `HomeAssistantClient`); local TP-Link Tapo/Kasa KLAP AES-CBC-128 crypto device driver (`TapoClient`); unified `SmartHomeBackendAdapter` & `SmartHomeCapabilityProvider` with 12 registered capabilities; animated frameless HUD overlays (`JarvisRingsOverlay`, `ChatWindowOverlay`, `WeatherOverlay`, `SystemMonitorOverlay`, `PersonalOSDashboardOverlay`, `AgentTaskStatusOverlay`, `MatrixOverlay`, `SystemStatusOverlay`).
- ✅ **M30 — Holographic AI Core GUI & Unified Command Center (`v1.0.0`)**: Full Command Center with real-time HUD telemetry, reactive DAG visualizer, vector memory search & live inspector, Claude/ChatGPT conversation import pipeline, live weather & environmental service.
- ✅ **M31 — Isolated Background Subagents & Task HUD (`v1.0.1` / `v1.1.0`)**: Non-blocking subagent dispatch via detached `asyncio.create_task()`, ephemeral context isolation, two-gate defense-in-depth policy verification, secret redaction, and real-time Task Status HUD overlay.
- ✅ **M32 — Multi-Task FocusManager (`v1.0.2` / `v1.1.0`)**: Thread-safe SQLite WAL state backing, length-weighted fuzzy task deduplication, interrupt routing (HIGH/CRITICAL immediate focus switch vs LOW/MEDIUM queued notification cards), and automatic stale thread archival to Cognitive Memory.
- ✅ **M33 — Natural Interaction Layer & Response Steering (`v1.1.0`)**: Full duplex streaming TTS with prosody chunking, active pause/resume (`PAUSE_PHRASES` detection), event-driven mid-flight steering (`response.steer`), turn snapshotting, and zero-latency audio buffer purging.
- ✅ **M34 — Verified UI Macro Compilation, Speculative Pre-Fetching & Proactive Watcher (`v1.2.0`)**: Zero-token deterministic Python macro compilation from repeated verified traces ($\ge 3$ consecutive runs at $\ge 0.90$ confidence), sub-millisecond AST symbol pre-warming on editor focus, and staging-isolated background diagnostics watcher.
- ✅ **M35 — Multi-App Vision Grounding & Coordinate Architecture (`v1.4.1`)**: Decoupled 3-stage coordinate pipeline (DPI scaling, VLM downsample reversal, window offset translation), strict geometric boundary validation, KeyPool multi-key failover on 429 TPM burst limits, high-performance trigram `ProjectIndex`, and structural `DuplicateDetector`.

---

## Target Milestones (Future Roadmap)

### Phase 12 — Multi-User & Enterprise Policy Governance [PLANNED]
- 🎯 **Multi-User & Enterprise Policy Governance**: Multi-tenant memory partitions, role-based capability permissions (RBAC), and Active Directory / LDAP synchronization.
- 🎯 **Enterprise Compliance Sinks**: Real-time structured telemetry streaming to Splunk, Azure Sentinel, and Datadog audit collectors.
- 🎯 **Distributed Aura Nodes**: Multi-workstation peer-to-peer LAN mesh coordination and shared fleet policy enforcement.

---

*For detailed specifications, see [docs/milestones/](milestones/).*

