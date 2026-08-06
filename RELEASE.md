# Aura AI Release History & Changelog

All notable changes to the Aura AI Platform are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
