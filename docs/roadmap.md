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
Phase 10 — Multi-User & Enterprise Sinks░░░░░░░░░░░░░░░░░░░░   0/1   PLANNED (M30)
```

---

## Current Platform Status (`v0.33.0-smarthome-ambient-hud`)

### Completed Milestones (M01–M29)

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

---

## Target Milestones (Future Roadmap)

### Milestone 30 — Multi-User & Enterprise Policy Governance (`v1.0.0`) [PLANNED]
- 🎯 **Multi-User & Enterprise Policy Governance**: Multi-tenant memory partitions, role-based capability permissions, and corporate compliance telemetry sinks.
- 🎯 **Persistent System Daemon**: Low-overhead Windows system service lifecycle (`AuraService`) with zero-downtime hot reloading.
- 🎯 **Ambient Voice & Audio Spatial Interaction**: Wake-word activation (`AuraWake`), streaming STT/TTS pipeline, and conversational turn-taking with ambient barge-in support.

---

*For detailed specifications, see [docs/milestones/](milestones/).*

