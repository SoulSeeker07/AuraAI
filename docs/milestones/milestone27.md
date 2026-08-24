# Milestone 27 — Autonomous Engineering Platform (`v0.31.0`)

## Goal
Milestone 27 introduces the **Autonomous Engineering Platform** for AuraAI, providing closed-loop bug fixing, test-driven repair, and pull request assembly with fail-closed security, self-modification governance, and byte-exact rollback mechanisms.

---

## 1. Five Verified Acceptance Gates

| Gate | Focus Area | Deliverables & Verified Architectural Invariants | Test File |
| :--- | :--- | :--- | :--- |
| **G1** | **Workspace Staging & Protected Ceiling** | `StagingWorkspace` lifecycle; recursive path globbing blocking edits to security/governance/write-gate files (`PROTECTED_SAFETY_CEILING`); atomic Win32 OS-level repository lock (`msvcrt.locking`); `RequestSource.AGENT_DELEGATED` context-floor inheritance in `MasterOrchestrator`. | `tests/test_engineering_g1_isolation.py` (7 tests) |
| **G2** | **Fault Localization & AST Slicing** | Structured `TestFailureFrame` parser; `FaultLocalizer` with AST symbol resolution selecting innermost enclosing scopes (functions, methods, classes); strict containment filtering of test files, stdlib, and `.venv/site-packages`. | `tests/test_engineering_g2_localization.py` (7 tests) |
| **G3** | **Patch Synthesis & Single-Write Gate** | AST syntax validation before diff generation; blunt Test-File Immunity (`RewardHackingViolation` on modifying existing tests/fixtures); `ADD_TEST` mode permitting net-new tests; authoritative write-gate re-verification directly at the `apply_patch()` disk-write point. | `tests/test_engineering_g3_patch_synthesis.py` (7 tests) |
| **G4** | **Self-Healing Loop & Rollback Safety** | Iterative repair loop bounded by `max_retries=3`; immediate hard-stop on ceiling/immunity violations; binary byte-exact snapshot & rollback (`read_bytes`/`write_bytes`); loud `RuntimeError` failure on unreadable files; failed untracked-deletion tracking. | `tests/test_engineering_g4_repair_rollback.py` (8 tests) |
| **G5** | **Human Merge Gate & PR Assembly** | Structured `PRSummary` markdown generator with evidence citations and unified diffs; single-path cryptographic ticket redemption in `authorize_git_operation()` via `CryptographicApprovalAuthority.verify_and_redeem()`. | `tests/test_engineering_g5_git_governance.py` (6 tests) |

---

## 2. Core Architectural Components

1. **Safety Ceiling & Write Gate**:
   - Defined in [`src/engineering/safety_ceiling.py`](file:///D:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/engineering/safety_ceiling.py) and [`src/engineering/workspace_policy.py`](file:///D:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/engineering/workspace_policy.py).
   - Enforces workspace containment (`validate_containment`), protected ceiling blocks (`is_path_protected`), and test-file immunity (`is_test_file`).

2. **Fault Localizer & Test Runner Adapter**:
   - Defined in [`src/engineering/test_runner.py`](file:///D:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/engineering/test_runner.py) and [`src/engineering/fault_localizer.py`](file:///D:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/engineering/fault_localizer.py).
   - Resolves failing test stack traces to concrete, innermost AST symbols inside the repository.

3. **Autonomous Engineering Loop**:
   - Defined in [`src/engineering/autonomous_loop.py`](file:///D:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/engineering/autonomous_loop.py).
   - Manages baseline snapshotting, retry iteration, patch application, and clean rollback with zero residual artifacts.

4. **PR Assembler & Git Governance**:
   - Defined in [`src/engineering/pr_assembler.py`](file:///D:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/engineering/pr_assembler.py).
   - Blocks destructive git operations (`merge_to_main`, `git_push_force`, branch deletion) unless a valid human cryptographic ticket and signature are redeemed.

---

## 3. Technical Debt Items Logged
- **`TD-008` (HIGH)**: Pytest execution in autonomous loop runs out-of-process without privilege dropping (Sandbox Containment).
- **`TD-009` (MEDIUM)**: Human ticket-issuance UI/CLI flow for Git-operation approvals not yet wired end-to-end (fail-closed backstop fully verified).
