# Aura AI Release History & Changelog

All notable changes to the Aura AI Platform are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [`v0.32.0-dynamic-codeact`] - 2026-08-22

### Added
- **Milestone 28 — Dynamic CodeAct & Hybrid Capability Architecture (COMPLETE)**: General-purpose sandboxed code execution architecture (`DynamicCodeActExecutor`) for artifact synthesis (PowerPoint, Word documents, Excel spreadsheets, format conversions, CSV aggregations, JSON configs) with closed-loop diagnostic repair state machine (27 dedicated automated tests).
- **AST-Based Static Import Checker**: Pre-execution AST safety verification (`check_imports`) blocking network egress (`socket`, `requests`, `urllib`), process escapes (`subprocess`, `ctypes`, `win32api`), and dynamic eval (`eval`, `exec`, `__import__`).
- **Hermetic Staging Sandbox**: Ephemeral staging directory jail with isolated minimal Windows environment (`SYSTEMROOT`, `SYSTEMDRIVE`, `PATH`, `TEMP`, `TMP`) bounded under Windows kernel Job Objects (`Win32JobSandbox`).
- **Post-Execution Binary Format Validators**: Multi-format structural verification using real format parsers (`python-pptx`, `python-docx`, `openpyxl`, PDF headers, images, CSV, JSON).
- **15-Goal Convergence Evaluation**: 93.3% convergence rate ($\le 2$ repair attempts) across 15 real-world synthesis tasks (80.0% on shot 1, average latency 12.8s).
- **Track 1 Acceptance Test Suite (T1–T6)**: 100% passed end-to-end through `MasterOrchestrator.process_request_async()` with physical file-on-disk verification.
- **T1 Known-Folder Resolution & Routing**: Enhanced `FileManager` to cleanly resolve `$known_folder:desktop\filename.txt` subpaths with default permission for known user folders.

---

## [`v0.31.0-autonomous-engineering`] - 2026-08-22

### Added
- **Milestone 27 — Autonomous Engineering Platform (COMPLETE)**: Full closed-loop bug fixing, test-driven repair, and pull request assembly with fail-closed security and self-modification governance across 5 verified gates (35 dedicated automated tests, 225 total platform tests).
- **G1 Workspace Staging & Protected Ceiling**: Recursive globbing blocks autonomous tampering with security files, governance engines, and write gates (`PROTECTED_SAFETY_CEILING`); atomic Win32 OS-level repo locks (`msvcrt.locking`); `RequestSource.AGENT_DELEGATED` context-floor inheritance in `MasterOrchestrator`.
- **G2 Fault Localization & AST Slicing**: Structured traceback frame parser mapping pytest failure frames to source coordinates; AST symbol resolution selecting innermost enclosing scopes (functions, methods, classes); strict containment filtering of test files, stdlib, and `.venv/site-packages`.
- **G3 Patch Synthesis & Single-Write Gate Enforcement**: AST syntax validation before diff generation; blunt Test-File Immunity (`RewardHackingViolation` on modifying existing tests/fixtures); `ADD_TEST` mode permitting net-new tests; authoritative write-gate re-verification directly at the `apply_patch()` disk-write point.
- **G4 Self-Healing Loop & Rollback Safety**: Iterative repair loop bounded by `max_retries=3`; immediate hard-stop on ceiling/immunity violations; binary byte-exact snapshot & rollback (`read_bytes`/`write_bytes`); loud `RuntimeError` failure on unreadable files; failed untracked-deletion tracking.
- **G5 Human Merge Gate & PR Assembly**: Structured `PRSummary` markdown generator with evidence citations and diffs; fail-closed `authorize_git_operation()` requiring human cryptographic ticket redemption via `CryptographicApprovalAuthority.verify_and_redeem()`.
- **Technical Debt Registry**: Registered `TD-008` (HIGH — Out-of-process pytest execution without sandbox privilege dropping) and `TD-009` (MEDIUM — Human ticket-issuance UI/CLI flow for Git-operation approvals not yet wired end-to-end).

---

## [`v0.30.0-personal-os`] - 2026-08-21

### Added
- **Milestone 26 — Personal Operating System (COMPLETE)**: Proactive daily context synthesis, sub-second workspace search, autonomous background event triggers, and persistent OS state management across 5 verified gates (21 dedicated automated tests).
- **G1 Request Source Classification & Governance**: `RequestSource` enum (`HUMAN_INTERACTIVE`, `TRIGGER_AUTONOMOUS`, `DAEMON_BACKGROUND`, `AGENT_DELEGATED`) with `ContextVar`-scoped autonomy level isolation (`_autonomy_level_ctx`) and strict domain ceiling enforcement (`trigger_allowed_domains`).
- **G2 Proactive Daily Context Synthesis**: `DailyContextEngine` assembling calendar events, priority tasks, stale files, and recent research into structured daily briefings with caching.
- **G3 Sub-Second Workspace Search**: In-memory inverted index and SQLite document cache (`WorkspaceSearchEngine`) providing sub-100ms workspace search with live incremental updates via `FileSystemWatcher`.
- **G4 Autonomous Trigger Engine**: `TriggerScheduler` executing cron/interval/event triggers with template parameter interpolation and cryptographic audit logging.
- **G5 OS State Persistence & Schema Migration**: SQLite-backed `PersonalOSStateStore` managing state transitions, schema versions, and reboot recovery.

---

## [`v0.27.0-autonomous-daemon`] - 2026-08-18

### Added
- **Milestone 23 — Autonomous Daemon & Background Operations (COMPLETE)**: Complete transformation of AuraAI into a persistent, autonomous agent daemon runtime under the hardened 6-Gate Definition of Done.
- **G1 Live Orchestration Path**: Background task dispatch (`daemon.spawn`, `daemon.status`, `daemon.list`, `daemon.cancel`) and scheduler requests route through `MasterOrchestrator` $\rightarrow$ `DecisionEngine` $\rightarrow$ `TaskDecomposer` $\rightarrow$ `DaemonEngineBackend` / `SchedulerBackendAdapter`.
- **G2 Asynchronous Background Execution**: Bounded worker thread pool with cooperative lifecycle isolation and explicit state machine (`SCHEDULED` $\rightarrow$ `CLAIMED` $\rightarrow$ `RUNNING` $\rightarrow$ `COMPLETED` / `FAILED` / `CANCELLED` / `PAUSED` / `RECOVERY_REQUIRED`).
- **G3 Deterministic Scheduling & Triggers**: One-shot timers, interval recurring jobs, and cron routines with durable timezone awareness (`UTC`) and explicit offline catch-up policies (`SKIP_STALE`, `EXECUTE_ONCE_ON_RECOVERY`).
- **G4 Cooperative Interruption & Safe Shutdown**: `CancellationToken` cooperative aborts, pause/resume job lifecycle controls, and clean daemon shutdown draining active workers within timeout boundaries.
- **G5 Durable Persistence & Crash Recovery Invariant**: SQLite-backed `DaemonStateStore` with atomic idempotency key claims (`{job_id}_{timestamp}`). Hard crashes during `RUNNING` state transition to `RECOVERY_REQUIRED` on reboot with zero ambiguous silent replay.
- **G6 Autonomy Governance & Cryptographic Tokens**: `AutonomyGovernanceEngine` enforces parameter-bound, time-bound HMAC-SHA256 authorization tokens for elevated `ActionRisk`, unconditionally blocks `PROHIBITED` capabilities, and handles worker exceptions cleanly.
- **12-Module Unified Platform Regression Green**: **183 / 183** automated tests passing across DACL isolation, sandbox, containment, manager hardening, network egress, security phases 1–4, research, multimodal, and autonomous daemon.

---

## [`v0.26.0-multimodal-hardening`] - 2026-08-18

### Added
- **Milestone 22 — Multimodal Voice & Vision Subsystems Hardening (COMPLETE)**: Complete integration of existing voice and vision engines into the canonical `MasterOrchestrator` execution pipeline under a verified 6-Gate Definition of Done.
- **G1 Live Pipeline Orchestration**: Speech audio and screen perception queries route seamlessly through `DecisionEngine` and `TaskDecomposer` to `VoiceEngineBackend` and `VisionEngineBackend`.
- **G2 Vision Grounding Invariant**: Screen capture $\rightarrow$ OCR/UI element detection $\rightarrow$ concrete coordinate space grounding with bounding boxes, screen indices, and active window anchors.
- **G3 Voice Reliability & Degradation**: End-to-end speech flow (Google STT / FasterWhisper / Vosk $\rightarrow$ Orchestrator $\rightarrow$ Piper / Edge-TTS) with graceful degradation and deterministic offline/unavailable error reporting.
- **G4 Device Privacy & Containment Invariant**: Independent permission gating for microphone, screen capture, and camera via `DevicePrivacyEngine` (denied permission $\implies$ zero hardware capture attempt).
- **Sensitive-Window Default-BLOCK Protection**: Pre-capture detection of credential dialogs (KeePass, 1Password, BitLocker, Windows Security) with immediate capture BLOCK before frame acquisition.
- **G5 Multimodal Memory Provenance**: Screen and voice observations persist into `CognitiveMemoryEngine` (`MemoryType.SEMANTIC`) with complete provenance metadata (`modality`, `device_id`, `capture_time`, `window_title`, `coordinates`).
- **G6 Unified Platform Regression**: 167 / 167 automated tests passing across 11 test modules with 0 regressions.

---

## [`v0.25.0-research-hardening`] - 2026-08-18

### Added
- **Milestone 21 — Research & Knowledge Engine Hardening (COMPLETE)**: Complete end-to-end live research capability path integrated into `MasterOrchestrator` with 8-gate acceptance model verified.
- **G1 & G2 Live Pipeline & Evidence Grounding**: Real user queries route from NLU / `DecisionEngine` to `ResearchEngineBackend` and `ResearchEngine`, binding every factual claim to a resolvable citation key, domain, snippet, and target source URL (`claim_id` $\leftrightarrow$ `citation_key` $\leftrightarrow$ `source_url` $\leftrightarrow$ evidence).
- **G3 Citation Preservation Invariant**: Citation identity survives the entire pipeline (`research.search` $\rightarrow$ `research.synthesize` $\rightarrow$ `ResultMerger` $\rightarrow$ `final_response`), preventing stripped or orphaned sources in user responses.
- **G4 Semantic Memory Provenance**: Verified research results consolidate into SQLite cognitive memory (`MemoryType.SEMANTIC`) with complete provenance metadata (`citations`, `claims`, `source_urls`, `research_event_id`, `topic`).
- **G5 Zero-Refetch Memory Direct Fulfillment**: Stage 2.8 direct fulfillment serves follow-up queries directly from cognitive memory with zero external provider calls (`call_count == 0`).
- **G6 Per-Provider Resilience**: Graceful per-provider degradation where rate-limited or timing-out providers do not collapse overall multi-provider research.
- **G7 Network Egress & SSRF Protection**: Filtered all retrieved URLs through `NetworkPolicyEngine` before synthesis, blocking cloud metadata (`169.254.169.254`), RFC1918 private subnets, and loopback endpoints.
- **G8 Deep Research Multi-Round Loop**: Verified multi-round iterative deep research capability (`research.deep_query`) producing structured findings with comprehensive citations and claims.
- **10-Module Unified Regression Green**: 157 / 157 automated tests passing across DACL isolation, sandbox, containment, manager hardening, network egress, security phases 1–4, and milestone 21 research.

---

## [`v0.24.0-security-hardening`] - 2026-08-18

### Added
- **Security Hardening Track Complete (Phases 1–4)**: Complete 4-tier security architecture with 150/150 unified regression tests passing.
- **Phase 4 — Isolated Audit Writer Service**: Dedicated out-of-process `AuditWriterService` maintaining monotonic sequences and hash-chain authority, communicating across authenticated Named Pipe IPC (SDDL DACL, client Windows identity checks, and HMAC challenge-response).
- **DPAPI Master Key & HKDF-SHA256 Derivation**: Key storage protected at rest via Windows DPAPI (`win32crypt.CryptProtectData`) with purpose-separated process signing keys derived via RFC 5869 HKDF-SHA256.
- **Canonical 11-Field Schema & OS Event Log Sink**: Structured, mathematically verifiable security events broadcast to the OS-managed Windows Event Log (`Application` log).
- **Fail-Closed Security Policy**: Production mode fails closed on audit service disconnection, barring silent downgrades to unverified same-principal logs.

---

## [`v0.23.0-coding-intelligence`] - 2026-08-18

### Added
- **M20 — Coding Intelligence 2.0 (COMPLETE)**: Full engineering agent pipeline with AST analysis, code editor with physical byte-for-byte backup/rollback, Antigravity CLI bridge for code generation, World Model integration, and automated repair loop.
- **M20.3 — Antigravity Agent Delegation**: `AntigravityCodingBridge` routing code generation through `agy --mode plan` with `WorkspacePolicy.authorize_write()` as sole write gate.
- **M20.5 — World Model Integration**: Multi-domain `query_multi()` async dispatch with thread pool isolation and graceful decay.
- **M20.6 — Automated Repair Loop**: `TestEngine` + `BugRepair` with exit code parsing (0: pass, 1: fail, 2/5: collection error), scoped test execution, and exhaustion-based rollback.
- **M20.7 — Active IDE Document Context**: `EditorTracker` with fail-closed Win32 window perception, cross-project workspace matching, and ground-truth filesystem validation.

---

## [`v0.22.0-capability-foundation`] - 2026-08-15

### Added
- **M19 — Universal Capability & Tool Runtime (COMPLETE)**: Dynamic `CapabilityRegistry` with `ICapabilityProvider` contract, `ActionRisk` 5-tier governance taxonomy, typed `input_schema`/`output_schema`, and first-class DAG attributes.
- **5 Capability Providers**: `DesktopCapabilityProvider` (100+ native capabilities), `CodingCapabilityProvider`, `BrowserCapabilityProvider`, `MemoryCapabilityProvider`, `ResearchCapabilityProvider`.
- **Plan Graph Validation**: `validate_plan_graph()` with topological DFS cycle detection and fail-closed liveness gating.
- **Master Orchestrator Wiring**: Stage 3.2 plan validation and `resolve_domain()` canonical domain authority.

---

## [`v0.21.0-world-model`] - 2026-08-12

### Added
- **M18 — World Model (COMPLETE)**: Unified multi-provider environment representation serving as single source of truth for all subsystems.
- **10 Provider Slots**: DesktopProvider, RepositoryProvider, KnowledgeGraphProvider, DependencyProvider, SymbolGraphProvider, MemoryProvider, ResearchProvider, BrowserProvider, NetworkProvider, CalendarProvider.
- `WorldModel.query(entity)` returning cross-provider facts, `WorldModel.snapshot()` for serializable state.

---

## [`v0.20.0-cognitive-memory`] - 2026-08-10

### Added
- **M17 — Cognitive Memory (COMPLETE)**: 8 typed memory stores with recall, decay, consolidation, and project-scoped isolation.
- `CognitiveMemoryEngine`, `WorkingMemoryManager`, `EpisodicMemoryRecorder`, `SemanticMemoryStore`, `ProceduralMemoryStore`, `RecallEngine`, `ConsolidationEngine`, `DecayEngine`, `ProjectMemoryFilter`.

---

## [`v0.19.0-foundation-truth-pass`] - 2026-08-08

### Added
- **Foundation Wiring & Truth Pass**: Stabilization gate ensuring all Phase 0 items marked operational actually work through the real runtime.
- `RUNTIME.md` — canonical live-path wiring map.
- `SYSTEM_CLASSIFICATION.md` — full module lifecycle classification index.

### Fixed
- Coding backend no longer returns hardcoded `success=True` — routes to `EngineeringManager`.
- Corrected milestone status inflation (M03, M09, M10, M13).

---

## [`v0.18.0-runtime-stabilization`] - 2026-08-06

### Added
- **Manual Runtime Acceptance Manual (`docs/RUNTIME_ACCEPTANCE.md`)**: Formalized regression testing checklist covering Desktop, Browser, Engineering, Runtime, and Memory subsystems.
- **Configurable `SafetyPolicy` Engine (`config/safety_policy.yaml`)**: Hardened protection preventing termination of protected applications (`Code.exe`, `vscode`, `explorer.exe`, `System`).
- **Zero-LLM Control Interception**: Deterministic worker status lookup (`"status?"`, `"Show active workers"`) and domain lifecycle controls (`pause`, `resume`, `cancel`).

---

## [`v0.17.0-runtime-architecture`] - 2026-08-06

### Added
- **Unified `RuntimeSession` Dataclass Base**: Standardized abstract base for domain task sessions (`EngineeringSession`, `BrowserSession`, `DesktopSession`, `ResearchSession`).
- **System-Wide `WorkerManager`**: Multi-domain session tracking and lifecycle management across all execution workers.
- **Reference Pronoun Resolver (`ReferenceResolver`)**: Conversational pronoun resolution ("it", "that window") bound to live `WorldSnapshot` and `WorldTimeline`.

---

## [`v0.16.0-cognitive-orchestration`] - 2026-08-06

### Added
- **Executive Cognitive Coordinator Architecture**: Re-architected Groq as the Project Manager supervising domain execution streams without emitting raw code snippets into chat.
- **Software Engineering Supervisor (`SoftwareEngineeringSupervisor`)**: Long-running engineering session engine delegating code synthesis strictly to `Antigravity CLI` with asynchronous validation workers (`PytestWorker`, `RuffWorker`, `GitDiffWorker`).

---

## [`v0.15.0-core-platform`] - 2026-08-05

### Added
- **Canonical Umbrella Launcher (`aura.py`)**: Unified entry point for `--doctor`, `--inspect`, `--verify`, `--cli`, and `--gui`.
- **System Diagnostic Suite (`AuraDoctor`)**: 22 automated system diagnostic checks covering environment, manifests, keys, imports, memory footprint, startup time, and native managers.
- **Telemetry Dashboard (`AuraInspector`)**: Real-time CLI state debugging dashboard (`python aura.py --inspect`).
- **Pipeline Verification Runner (`AuraVerifier`)**: One-command CI runner (`python aura.py --verify`) enforcing Ruff, Black, Isort, Mypy, and Pytest architecture tests.
- **Adaptive Backend Router (`BackendRegistry`)**: Dynamic capability negotiation (`negotiate_capabilities()`) with moving-average latency, success rate, and call count metrics tracking.
- **Architecture & Capability Manifests (`config/`)**: Single-source-of-truth JSON/YAML manifests (`architecture.json`, `capabilities.json`, `plugin.schema.json`, `planner.schema.json`).
- **AST Dependency Graph Generator (`scripts/generate_dep_graph.py`)**: AST import parser enforcing zero architectural layer violations.
- **GitHub Actions CI Workflow (`.github/workflows/ci.yml`)**: Automated pipeline workflow.

### Changed
- **Repository Reorganization**: Relocated misplaced root files into structured subdirectories (`tests/desktop/`, `scripts/`, `logs/`, `docs/milestones/`).
- **Import Hygiene**: Standardized imports across `src/` to eliminate `from src.` import prefixes.

---

## [`v0.14.0`] - 2026-08-01

### Added
- Autonomous Research Engine (`ResearchPlanner`, `ResearchReasoner`, `CitationFormatter`).
- Multi-provider search integration (Tavily, GitHub, Wikipedia, arXiv).

---

## [`v0.13.0`] - 2026-07-15

### Added
- Native Windows Desktop Managers (`WindowManager`, `ClipboardManager`, `DisplayManager`, `AudioManager`, `PowerManager`, `NetworkManager`).
- Pipeline safety layer with automated post-execution verification and rollback.

---

## [`v0.1.0`] - 2026-06-01

### Added
- Initial foundation launch, Aura Brain core intelligence, basic event bus, and provider interfaces.

---

*Last Updated: August 18, 2026*
