# ADR 0006: Configurable SafetyPolicy Engine

* **Status:** Accepted  
* **Date:** 2026-08-06  
* **Author:** Sreekanta YR  

## Context & Problem Statement
Autonomous AI desktop agents risk accidentally closing critical user applications (e.g. VS Code while coding, Windows Explorer, active Python runners, or system processes) when fulfilling ambiguous "close it" or "clean up" requests. Hardcoded process name checks were brittle and non-configurable.

## Decision
Implement a central, configurable `SafetyPolicy` engine (`src/execution/safety_policy.py` & `config/safety_policy.yaml`):
- Protects critical IDE and OS applications (`Code.exe`, `vscode`, `explorer.exe`, `System`, `python.exe`, `cmd.exe`, `powershell.exe`).
- Integrated into native window management (`WindowManager._handle_close`) and desktop execution adapter (`DesktopEngineBackend.execute`).
- Raises `PermissionError` and returns a clean `DesktopResult(status=FAILED, error="Safety constraint...")` prior to calling Win32 APIs.

## Alternatives Considered
* **Hardcoded String Checks in WindowManager**: Rejected because users could not customize protected apps without modifying Python source files.
* **Post-Termination Rollback**: Rejected because closing VS Code or System Explorer cannot be cleanly undone post-facto.

## Consequences
* **Positive**: Guarantees IDE and OS stability; fully configurable via YAML; prevents accidental data or process loss.
* **Negative**: Attempts to close protected processes return explicit error responses rather than executing.
