# Changelog

All notable changes to Aura AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **M20 — Coding Intelligence 2.0**: Complete engineering agent with AST analysis, code editor with backup/rollback, Antigravity bridge for code generation, World Model integration, and automated repair loop.
- `AntigravityCodingBridge` (`src/engineering/antigravity_bridge.py`) — routes code generation through `agy` CLI with `WorkspacePolicy.authorize_write()` gate.
- `EditorTracker` (`src/workspace/editor_tracker.py`) — live IDE document perception with fail-closed Win32 window matching.
- M20.6 Automated Repair Loop — `TestEngine` + `BugRepair` with exit code parsing and exhaustion-based rollback.
- M20.7 Active IDE Document Context — cross-project workspace matching and ground-truth filesystem validation.

---

## [0.22.0-capability-foundation] - 2026-08-15

### Added
- **M19 — Universal Capability & Tool Runtime**: `CapabilityRegistry`, `Capability` contract with typed schemas, `ActionRisk` taxonomy, DAG plan graph validation with topological cycle detection.
- 5 capability providers: `DesktopCapabilityProvider`, `CodingCapabilityProvider`, `BrowserCapabilityProvider`, `MemoryCapabilityProvider`, `ResearchCapabilityProvider`.
- Plan graph prerequisite validation with fail-closed liveness gating.

---

## [0.21.0-world-model] - 2026-08-12

### Added
- **M18 — Adaptive Computer Interaction Runtime & World Model**: Multi-provider world model with workspace, repository, memory, and desktop provider integration.
- `WorldModel.query()` — unified entity queries across all providers.
- `WorldModel.snapshot()` — serializable state representation.
- Incremental state updates without full rebuild.

---

## [0.20.0-cognitive-memory] - 2026-08-10

### Added
- **M17 — Cognitive Memory**: 8 typed memory stores (Working, Episodic, Semantic, Procedural, Preference, Project + Short-Term + Long-Term).
- `CognitiveMemoryEngine` (`src/memory/cognitive_memory.py`) — central memory engine.
- `RecallEngine` — multi-factor candidate scoring and ranking.
- `ConsolidationEngine` — post-execution memory merging.
- `DecayEngine` — retention decay evaluation.
- `ProjectMemoryFilter` — per-project memory isolation.

---

## [0.19.0-foundation-truth-pass] - 2026-08-08

### Added
- **Foundation Wiring & Truth Pass**: Stabilization gate between Phase 0 and Phase 1.
- `RUNTIME.md` — canonical live-path wiring map.
- `SYSTEM_CLASSIFICATION.md` — module lifecycle classification index.
- Corrected M13 status from COMPLETE to IN PROGRESS (coding backend was a mock).
- Corrected M09 status to COMPLETE — LEGACY (not on live path).
- Corrected M03 status to COMPLETE — FOUNDATION ONLY.

### Fixed
- Coding backend (`CodingBackendAdapter`) no longer returns hardcoded `success=True` — routes to `EngineeringManager` for real analysis.

---

## [0.18.0-runtime-stabilization] - 2026-08-06

### Added
- Manual Runtime Acceptance Manual (`docs/RUNTIME_ACCEPTANCE.md`).
- Configurable `SafetyPolicy` Engine (`config/safety_policy.yaml`).
- Zero-LLM Control Interception for worker status and lifecycle commands.

---

## [0.17.0-runtime-architecture] - 2026-08-06

### Added
- Unified `RuntimeSession` dataclass base for domain task sessions.
- System-wide `WorkerManager` for multi-domain session tracking.
- `ReferenceResolver` for conversational pronoun resolution.

---

## [0.16.0-cognitive-orchestration] - 2026-08-06

### Added
- Executive Cognitive Coordinator Architecture.
- `SoftwareEngineeringSupervisor` for long-running engineering sessions.

---

## [0.15.0-core-platform] - 2026-08-05

### Added
- Canonical umbrella launcher (`aura.py`) with `--doctor`, `--inspect`, `--verify`, `--cli`, `--gui`.
- `AuraDoctor` — 22 automated system diagnostic checks.
- `AuraInspector` — real-time CLI state debugging dashboard.
- `AuraVerifier` — one-command CI runner.
- Adaptive `BackendRegistry` with capability negotiation and latency metrics.
- Architecture & capability manifests (`config/`).
- GitHub Actions CI workflow.

### Changed
- Repository reorganization into structured subdirectories.
- Import hygiene standardization across `src/`.

---

## [0.14.0] - 2026-08-01

### Added
- Autonomous Research Engine (`ResearchPlanner`, `ResearchReasoner`, `CitationFormatter`).
- Multi-provider search integration (Tavily, GitHub, Wikipedia, arXiv).

---

## [0.13.0] - 2026-07-15

### Added
- Native Windows Desktop Managers (17 Win32 managers).
- Pipeline safety layer with automated post-execution verification and rollback.

---

## [0.1.0] - 2026-06-01

### Added
- Initial foundation launch, Aura Brain core intelligence, basic event bus, and provider interfaces.

---

## [0.0.1] - 2026-07-15

### Added
- Project initialization, basic directory structure, core Python modules.

---

*Last Updated: August 18, 2026*
