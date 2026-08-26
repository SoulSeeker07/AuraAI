# Changelog

All notable changes to Aura AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.33.0-smarthome-ambient-hud] - 2026-08-25

### Added
- **M29 — Smart Home / IoT Integration & Ambient Desktop HUD Interaction (COMPLETE)**: Physical ambient intelligence and bidirectional multi-device control.
- **Home Assistant Integration** (`src/integrations/smarthome/ha_client.py`, `src/integrations/smarthome/ha_ws.py`): Bidirectional WebSocket client with optimistic command execution, entity registry caching, and state rollback on failure.
- **TP-Link Tapo / Kasa KLAP Driver** (`src/integrations/smarthome/tapo_client.py`): Zero-cloud local device encryption driver implementing KLAP handshake, SHA-256 seed negotiation, and AES-CBC-128 crypto for Tapo L530 bulbs and smart plugs.
- **SmartHome Backend & Provider** (`src/core/backends/adapters/smarthome_backend.py`, `src/core/capabilities/providers/smarthome_provider.py`): 12 registered capabilities covering lights, switches, climate, cameras, and scenes with 4-tier risk classification and offline graceful degradation.
- **Ambient Desktop HUD Overlays** (`src/gui/widgets/`): Translucent PySide6 widgets including `JarvisRingsOverlay` (pulsing reactive orbital arcs), `ChatWindowOverlay` (floating conversational interface), `WeatherOverlay`, `SystemMonitorOverlay`, `PersonalOSDashboardOverlay`, `AgentTaskStatusOverlay`, `MatrixOverlay`, and `SystemStatusOverlay`.
- **Real Backend Bridge** (`src/gui/real_backend_bridge.py`): Non-blocking Qt signal telemetry bus bridging core runtime state and smart home events to HUD overlays.

### Fixed
- **Root-Folder Screenshot Leak & Single-Owner Lifecycle**: Consolidated all screen capture implementations (`desktop_agent.py`, `vision_backend.py`, `vision_manager.py`) under single-owner `ScreenshotManager`. Enforced canonical runtime storage (`Data/runtime/screenshots/`), collision-proof UUID naming (`timestamp + uuid[:6]`), fail-open `capture_scoped()` context manager with guarded deletion on verified consumer success, bounded failure retention pruning (20-file count cap / 24-hour age limit), and purged 14 legacy root screenshot artifacts.

---

## [0.32.0-dynamic-codeact-hud-os] - 2026-08-24

### Added
- **M28 — Dynamic CodeAct Runtime, HUD Overlays & Integrated Aura OS (COMPLETE)**: Transitioned AuraAI into an integrated autonomous operating system.
- **Dynamic CodeAct Execution Engine** (`src/codeact/executor.py`, `src/codeact/drafters.py`): Code-as-action paradigm replacing rigid tool calling; multiline code block parser; AST safety validator; closed-loop repair loop.
- **Sandboxed Test Isolation** (`src/engineering/test_runner.py`): Privileged test execution isolation using Windows Job Objects and `RestrictedUserSandbox` (512MB RAM cap, temp redirection, credential scrubbing; `TD-008` resolved).
- **RAG Knowledge Service** (`src/knowledge/rag_service.py`): ChromaDB/SQLite vector search, text chunking, and grounded context retrieval.

---

## [0.31.0-autonomous-engineering] - 2026-08-23

### Added
- **M27 — Autonomous Engineering Platform (COMPLETE)**: Closed-loop bug fixing, test-driven repair, and pull request assembly.
- **Protected Safety Ceiling**: `PROTECTED_SAFETY_CEILING` prevents unauthorized modification of security-critical subsystems.
- **AST Fault Localization & Single-Write Gate**: Precision line-level fault localization and binary byte-exact rollback.
- **Cryptographic Git Merge Gate**: Fail-closed human authorization gate (`PatchBundleAssembler.authorize_git_operation`).

---

## [0.30.0-personal-os] - 2026-08-22

### Added
- **M26 — Personal Operating System (COMPLETE)**: Proactive daily context synthesis, sub-second workspace search, and persistent OS state.
- **DailyContextEngine**: Multi-source daily context synthesis from calendar, tasks, recent activities, and environment.
- **WorkspaceSearchEngine**: Inverted index sub-second fuzzy and prefix searching across project workspaces.
- **TriggerScheduler**: Autonomous background trigger daemon dispatching cron, interval, and event-based tasks.
- **PersonalOSStateStore**: SQLite-backed persistent state store for user routines and context.

---

## [0.29.0-expert-systems] - 2026-08-20

### Added
- **M25 — Professional Expert Systems (COMPLETE)**: 4 specialized domain planners sharing one runtime, opt-in Stage 2.9 routing via `expert_routing_enabled=True` in `MasterOrchestrator`.
- **ExpertDomainRouter** (`src/experts/router.py`): Confidence-ranked routing with ≥0.50 threshold; graceful fallback to general planner on no match.
- **SecurityExpert** (`src/experts/security_expert.py`): Cybersecurity threat analysis, audit, and hardening planner.
- **NetworkExpert** (`src/experts/network_expert.py`): Network topology, diagnostics, and security planner.
- **FinancialExpert** (`src/experts/financial_expert.py`): Financial analysis, modeling, and reporting planner.
- **SoftwareExpert** (`src/experts/software_expert.py`): Architecture, refactoring, and debugging planner.
- **PlanDAGCompiler** (`src/experts/compiler.py`): Compiles expert domain assessments into structured execution DAGs.
- **ExpertRegistry** (`src/experts/expert_registry.py`): Centralized expert registration and lookup.
- **Stage 2.9 Routing**: `MasterOrchestrator` routes to `ExpertDomainRouter` before general decomposition when `expert_routing_enabled=True`; fail-closed confidence gates prevent low-confidence expert delegation.

---

## [0.28.0-event-runtime] - 2026-08-20

### Added
- **M24 — Event Runtime & Autonomous Intent Execution (COMPLETE)**: Aura transitions from reactive assistant to autonomous event-driven operating runtime. All components delivered under the 6-Phase architecture.
- **AuraEvent Contract** (`src/autonomy/events.py`): Canonical typed event envelope with `event_id`, `event_type`, `source`, `timestamp`, `payload`, `correlation_id`, `urgency`. Immutable, validated on ingestion.
- **EventRuntime Core** (`src/autonomy/event_runtime.py`): Single choke point for all autonomous telemetry. Ingest → normalize → deduplicate (semantic fingerprinting, sliding temporal window) → correlate (multi-signal `CorrelatedEventGroups`) → dispatch. Generates immutable `EventTraceRecord` as root of causal chain.
- **EventInterpreter** (`src/autonomy/interpreter.py`): Relevance & noise filter. Queries `WorldModel` for context. Synthesizes signals into `IntentType` goal DAGs before MasterOrchestrator dispatch. Never executes directly.
- **AutonomyPolicyGate** (`src/autonomy/policy_gate.py`): Immutable 4-tier risk decision gate: `ALLOWED` / `RATE_LIMITED` / `APPROVAL_REQUIRED` (HMAC ticket) / `BLOCKED`.
- **TriggerScheduler** (`src/autonomy/trigger_scheduler.py`) & **TriggerRegistry** (`src/autonomy/trigger_registry.py`): Cron, interval, and one-shot temporal triggers feeding the event pipeline.
- **Event Source Watchers** (`src/autonomy/watchers/`): `FilesystemWatcher` (high-volume deduplication), `ProcessMonitor` (failure correlation, exit code tracking).
- **Immutable Causal Trace Chain**: `event_id → correlation_id → assessment_id → policy_decision_id → plan_id → execution_id → observation_id` — every autonomous action is fully traceable.

---

## [0.27.0-autonomous-daemon] - 2026-08-18

### Added
- **M23 — Autonomous Daemon & Background Operations (COMPLETE)**: Complete autonomous daemon runtime with bounded worker pool, persistent scheduler, crash recovery, and autonomy governance.
- **Live Orchestration Path (G1)**: Full routing of background and scheduler goals through MasterOrchestrator to DaemonEngineBackend.
- **Asynchronous Worker Execution (G2)**: Bounded worker pool with durable state transitions (`SCHEDULED` $\rightarrow$ `CLAIMED` $\rightarrow$ `RUNNING` $\rightarrow$ `COMPLETED`).
- **Deterministic Scheduling & Triggers (G3)**: Interval, one-shot, and cron routines with timezone handling and offline catch-up policies.
- **Cooperative Cancellation & Safe Shutdown (G4)**: Cancellation token propagation and clean worker pool draining on shutdown.
- **Durable State Persistence & Crash Recovery (G5)**: SQLite DaemonStateStore with idempotency checks and RECOVERY_REQUIRED state on reboot.
- **Autonomy Governance & Adversarial Hardening (G6)**: Parameter-bound HMAC authorization tokens for high-risk actions, prohibited capability blocks, and worker isolation.
- **Unified Regression Baseline**: **183 / 183** passing tests across 12 test modules.

---

## [0.26.0-multimodal-hardening] - 2026-08-18

### Added
- **M22 — Multimodal Voice & Vision Subsystems Hardening (COMPLETE)**: Full live-path integration of existing VoiceManager and VisionManager into MasterOrchestrator under 6-gate DoD.
- **Live Multimodal Orchestration (G1)**: Typed voice and vision commands route through DecisionEngine and TaskDecomposer to VoiceEngineBackend and VisionEngineBackend.
- **Vision Grounding & Coordinate Frame Invariant (G2)**: Target UI elements bind to concrete screen/window coordinates with bounding boxes and confidence scores.
- **Voice Reliability & Degradation (G3)**: Robust multi-engine STT/TTS fallback hierarchy with deterministic degradation and offline failure isolation.
- **Device Privacy & Sensitive Window Blocking (G4)**: DevicePrivacyEngine pre-acquisition gating (denied permission $\implies$ zero capture attempt) with default-BLOCK on credential dialogs (KeePass, BitLocker, Windows Security).
- **Multimodal Memory Provenance (G5)**: Visual and voice perception records persist to CognitiveMemory with structured metadata (`modality`, `device_id`, `capture_time`, `window_title`, `coordinates`).
- **Unified Regression Suite (G6)**: 167 / 167 passing tests across 11 test suites with zero regressions.

---

## [0.25.0-research-hardening] - 2026-08-18

### Added
- **M21 — Research & Knowledge Engine Hardening (COMPLETE)**: Full end-to-end live research pipeline integration with 8-gate acceptance model verified.
- **Live Pipeline & Evidence Grounding (G1 & G2)**: User queries route seamlessly to `ResearchEngineBackend` and `ResearchEngine`, producing strict factual claim $\leftrightarrow$ citation key $\leftrightarrow$ URL bindings.
- **Citation Preservation Invariant (G3)**: Preservation of citation identity and provenance through `ResultMerger` into final user responses.
- **Semantic Memory Provenance (G4)**: Research findings promote into SQLite cognitive memory (`MemoryType.SEMANTIC`) with complete provenance metadata (`citations`, `claims`, `source_urls`, `research_event_id`).
- **Zero-Refetch Memory Direct Fulfillment (G5)**: Stage 2.8 direct fulfillment serves follow-up queries directly from cognitive memory with zero external provider calls.
- **Per-Provider Resilience (G6)**: Isolated provider failure handling ensuring valid results from healthy providers are preserved.
- **Network Egress & SSRF Protection (G7)**: Prohibited destinations (cloud metadata `169.254.169.254`, RFC1918 private LANs, loopback) filtered via `NetworkPolicyEngine`.
- **Deep Research Multi-Round Loop (G8)**: Multi-round iterative reasoning (`research.deep_query`) producing structured findings with verifiable citations and claims.
- **Unified Regression Suite**: 157 / 157 automated tests passing across 10 test modules.

---

## [0.24.0-security-hardening] - 2026-08-18

### Added
- **Phase 4 Security Hardening (COMPLETE)**: Dedicated `AuditWriterService` worker, cross-process authenticated Windows Named Pipe IPC (SDDL DACL + Windows Client SID validation + HMAC challenge-response), fail-closed production policy, and Windows Event Log OS-managed historical sink.
- **DPAPI Master Key Management & HKDF Derivation**: Windows DPAPI encryption at rest with RFC 5869 HKDF-SHA256 purpose-separated process signing key derivation and key envelope rotation metadata.
- **Canonical 11-Field Audit Schema**: Mathematical hash-chain linking (`payload_hash`, `previous_hash`, `current_hash`, `writer_instance_id`) with cross-sink continuity verification.
- **Security Hardening Track (Phases 1–4 Complete)**: 150 / 150 unified regression tests passing across all 9 test modules.

### Changed
- Synced all documentation to truth: README, roadmap, SYSTEM_CLASSIFICATION, CHANGELOG, RELEASE, RUNTIME.
- Fixed stale progress bars and priority queues across all tracking documents.

---

## [0.23.0-coding-intelligence] - 2026-08-18

### Added
- **M20 — Coding Intelligence 2.0**: `AntigravityCodingBridge` (agy CLI, `WorkspacePolicy` gate), `EditorTracker` (live IDE document perception), `TestEngine` + `BugRepair` automated repair loop, cross-project workspace matching.

---

## [0.22.0-capability-foundation] - 2026-08-15

### Added
- **M19 — Universal Capability & Tool Runtime**: `CapabilityRegistry`, typed `Capability` contracts, `ActionRisk` taxonomy, DAG plan graph with topological cycle detection, 5 capability providers (Desktop, Coding, Browser, Memory, Research).

---

## [0.21.0-world-model] - 2026-08-12

### Added
- **M18 — World Model**: Multi-provider `WorldModel` (workspace, repo, memory, desktop). `WorldModel.query()` unified entity queries, `WorldModel.snapshot()` serializable state, incremental updates.

---

## [0.20.0-cognitive-memory] - 2026-08-10

### Added
- **M17 — Cognitive Memory**: 8 typed stores (Working, Episodic, Semantic, Procedural, Preference, Project, Short-Term, Long-Term). `CognitiveMemoryEngine`, `RecallEngine`, `ConsolidationEngine`, `DecayEngine`, `ProjectMemoryFilter`.

---

## Foundation History (v0.0.1 – v0.19.0) — 2026-06-01 to 2026-08-08

> Consolidated summary. Full history available in git log.

| Version | Date | Milestone / Change |
|:---|:---|:---|
| `v0.19.0-foundation-truth-pass` | 2026-08-08 | `RUNTIME.md` + `SYSTEM_CLASSIFICATION.md` established as ground truth. M13 corrected to IN PROGRESS (coding backend was a mock). Coding backend routed to real `EngineeringManager`. |
| `v0.18.0-runtime-stabilization` | 2026-08-06 | Manual Runtime Acceptance doc, `SafetyPolicy` engine, zero-LLM control interception for lifecycle commands. |
| `v0.17.0-runtime-architecture` | 2026-08-06 | `RuntimeSession` base, `WorkerManager` for multi-domain session tracking, `ReferenceResolver` for pronoun resolution. |
| `v0.16.0-cognitive-orchestration` | 2026-08-06 | Executive Cognitive Coordinator, `SoftwareEngineeringSupervisor`. |
| `v0.15.0-core-platform` | 2026-08-05 | Canonical launcher (`aura.py`), `AuraDoctor` (22 diagnostics), `AuraInspector`, `AuraVerifier`, `BackendRegistry` with capability negotiation, GitHub Actions CI. |
| `v0.14.0` | 2026-08-01 | Research Engine (`ResearchPlanner`, `ResearchReasoner`, `CitationFormatter`), multi-provider search (Tavily, GitHub, Wikipedia, arXiv). |
| `v0.13.0` | 2026-07-15 | 17 Win32 Native Desktop Managers, pipeline safety layer with post-execution verification and rollback. |
| `v0.1.0` | 2026-06-01 | Initial foundation: Aura Brain core intelligence, event bus, provider interfaces. |
| `v0.0.1` | 2026-06-01 | Project initialization, directory structure, core Python modules. |

---

*Last Updated: August 20, 2026*
