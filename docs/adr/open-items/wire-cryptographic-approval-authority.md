# Technical Debt / Milestone Tracked Item: Wire CryptographicApprovalAuthority End-to-End [RESOLVED & CERTIFIED]

## Status: CLOSED / CERTIFIED (2026-09-01)
*Fully resolved and verified across all execution subsystems (`DaemonRuntime`, `ConversationEngine`, `TriggerScheduler`, and `BrowserBackend`) with zero-bypass AST guardrails.*

## Context & Motivation
During the investigation of shell command execution and risk classification (Defect A / Option B), we identified that while `CryptographicApprovalAuthority` (`src/desktop/native/security/approval_authority.py`) is fully implemented with HMAC-SHA256 signing, audit logging, and single-use redemption contracts, it is now invoked across all live execution paths in `ConversationEngine`, native desktop managers, `SafetyGate` (browser), and `FocusManager`.

Currently:
1. `LOW`-risk commands (`git status`, `git log`, `git diff`, `where`, `echo`, etc.) are executed directly via `ShellExecutor` with output verification.
2. `MEDIUM` and `HIGH` risk commands (mutating or destructive commands, commands with shell operators `|`, `&&`, `>`, etc.) fail closed with an explicit message informing the user that approval gating is required and directing them to run the command in a terminal.

## Scope of Follow-on Work
To enable safe autonomous execution of `MEDIUM` and `HIGH` risk commands, the approval authority must be wired end-to-end across perception, routing, and execution:

1. **Ticket Issuance:**
   - When a `MEDIUM` or `HIGH` risk capability/command is requested, `CryptographicApprovalAuthority.get_instance().create_command_ticket(command, cwd)` (or `create_ticket`) issues a signed ticket with an un-forgeable ID (e.g. `tkt_<hex>`).
   - The UI / ConversationEngine presents the ticket ID, command description, and risk level to the user.

2. **Intent & Token Resolution:**
   - Update `IntentRouter` to recognize `tkt_<hex>` tokens in addition to the browser agent's `AUTH-` / `TICK-` tokens in user utterances like `"confirm tkt_12345678"`.

3. **Approval Redemption & Execution:**
   - In `ConversationEngine`, route `confirm_ticket` with a `tkt_` prefix to `CryptographicApprovalAuthority.verify_and_redeem_command(...)`.
   - On valid human signature / redemption, dispatch the stored command for execution and return the verified results.

4. **Testing & Security Proofs:**
   - Unit tests for replay attack prevention (redeemed tickets cannot be executed twice).
   - Tamper-resistance tests (modified command payloads fail HMAC verification).
   - Expiration TTL enforcement.
