# Changelog

All notable changes to the Aura AI platform are documented in detail in [RELEASE.md](../RELEASE.md).

## [v1.1.0] - 2026-08-28 — Milestone 31: VoiceOS Holographic Neural Notch HUD & Dedicated Live Log Console
- Next-Gen VoiceOS Dynamic Island Notch HUD (`VoiceNotchOverlay`) anchored flush to the top taskbar with 120Hz smooth state morphing (IDLE -> LISTENING -> PROCESSING -> SUCCESS -> EXPANDED).
- Hardware-linked multi-frequency rainbow waveform visualizer powered by real-time microphone level streaming.
- Context-aware Dynamic Action & Source chips with instant execution and clean-slate resets.
- Auto-collapsing 5-second expanded result card with hover recall and 30-second processing safety recovery.
- Dedicated sub-millisecond Live System & Engine Logs Console (`LiveLogViewerOverlay`) with zero-lag binary tailing.
- 6 dynamic filter categories (`ALL`, `CHAT`, `INFO`, `DEBUG`, `WARNING`, `ERROR`) with real-time entry count badges and conversation dialogue integration.
- Strict functional separation between System Logs and Agent Task / DAG Queue overlays.

## [v1.0.0] - 2026-08-27 — Milestone 30: Holographic AI Core GUI & Cognitive Memory Pipeline
- Holographic Command Center GUI with real-time HUD telemetry, reactive DAG visualizer, and token tracker.
- Cognitive memory import pipeline supporting Claude and ChatGPT exports with fuzzy deduplication and schema normalization.
- Non-blocking RealBackendBridge streaming telemetry, memory facts, task execution trees, and environmental status.
- Live weather & meteorological service with fallback caching.
- Fastpath intent matrix and precedence hardening for instant HUD toggling and system restart management.
- Codebase AST syntax integrity test suite protecting 600+ Python modules.

## [v0.33.0] - 2026-08-25 — Milestone 29: Smart Home & Ambient HUDs
- Home Assistant REST/WebSocket integration and TP-Link Tapo KLAP local encryption driver.
- 8 translucent PySide6 desktop HUD overlays (Jarvis Rings, Chat Window, Weather, System Monitor, Matrix, etc.).
- Single-owner screenshot lifecycle management with leak prevention.

## [v0.32.0] - 2026-08-24 — Milestone 28: Dynamic CodeAct Runtime & Integrated Aura OS
- Dynamic CodeAct execution engine replacing rigid tool-calling with code synthesis.
- Hermetic Windows Job Object sandbox with AST safety validators.
- Sandboxed pytest test runner with restricted user privilege isolation.

## [v0.31.0] - 2026-08-22 — Milestone 27: Autonomous Engineering Platform
- Closed-loop bug fixing, test-driven repair, and PR assembly.
- AST symbol localization with innermost enclosing scope resolution.
- Safety ceiling (`PROTECTED_SAFETY_CEILING`) and Test-File Immunity.
- Single-write gate policy (`WorkspacePolicy`) with containment and write-point re-authorization.
- Byte-exact baseline snapshotting (`read_bytes`/`write_bytes`) and fail-closed rollback.
- Human cryptographic merge gate (`authorize_git_operation`) with HMAC ticket redemption.

## [v0.30.0] - 2026-08-21 — Milestone 26: Personal Operating System
- `RequestSource` classification (`HUMAN_INTERACTIVE`, `TRIGGER_AUTONOMOUS`, `DAEMON_BACKGROUND`, `AGENT_DELEGATED`).
- `ContextVar`-scoped autonomy level isolation (`_autonomy_level_ctx`).
- `DailyContextEngine` for proactive context synthesis and calendar/task briefs.
- Sub-second `WorkspaceSearchEngine` with inverted index and `FileSystemWatcher` live sync.
- Autonomous `TriggerScheduler` with template interpolation and cryptographic audit logging.
- `PersonalOSStateStore` SQLite persistence with schema migration.

## [0.1.0] - Foundation bootstrap
- Project layout
- Basic service scaffolding (FastAPI)
- QML frontend skeleton
- Docs and configuration


