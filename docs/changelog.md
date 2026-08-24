# Changelog

All notable changes to the Aura AI platform are documented in detail in [RELEASE.md](../RELEASE.md).

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


