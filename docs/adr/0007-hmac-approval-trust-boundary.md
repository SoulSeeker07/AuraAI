# ADR 0007: What the HMAC Approval Ticket Actually Protects

* **Status:** Accepted
* **Date:** 2026-08-24
* **Author:** Sreekanta YR

## Context & Problem Statement
`CryptographicApprovalAuthority` (`src/desktop/native/security/approval_authority.py`) issues
HMAC-SHA256 tickets: `generate_human_signature(ticket_id)` signs
`f"{ticket_id}:{ticket.action_hash}"`, and `verify_and_redeem(...)` checks replay
(`is_redeemed`), TTL (`expires_at`), action-hash substitution, and signature validity via
`hmac.compare_digest`, then marks the ticket redeemed.

The docstring on `generate_human_signature` reads *"Called strictly by the trusted Human UI /
CLI approval channel"*, which invites a reading that has now been explicitly rejected: that
signing from a GUI and redeeming in a manager establishes a trust boundary between the two.

It does not. Three verified facts:

1. `self._secret_key` is a single process-wide value on a `get_instance()` singleton
   (`approval_authority.py:57-67`) — DPAPI-derived when available, an ephemeral
   `secrets.token_bytes(32)` otherwise.
2. `generate_human_signature` is an ordinary instance method with no caller
   authentication, no OS-level gate, and no separate address space.
3. Therefore any in-process code — including a code path an LLM caused to run — that can
   reach the singleton can mint a valid signature for any ticket it can create.

Moving the call site from a manager into a GUI widget relocates the signing call. It does not
make the signature unforgeable by the code on the other side of it.

## Decision
Record the boundary as it is, and scope future work against that record rather than against
the docstring.

**What HMAC approval tickets do protect:**
* **LLM self-authorization.** A model cannot emit a `(ticket_id, signature)` pair as text.
  It must cause a call to `generate_human_signature`, which is a single auditable chokepoint
  that emits a `TICKET_SIGNED` audit event. Ticket-bearing execution is therefore
  attributable to one code path instead of diffused across every call site.
* **Ticket integrity in transit and over time.** Replay (single-use redemption), expiry
  (TTL), and parameter substitution (action-hash binding) are genuinely enforced, and are
  the properties the trigger scheduler depends on when it gates a recurring autonomous
  action on a pre-issued ticket.

**What they do not do:**
* They do **not** distinguish a GUI process from a manager, an adapter, or an agent loop.
  All share one key in one process.
* They do **not** prove a human was present. They prove the signing chokepoint was invoked.
* They are **not** a defense against in-process compromise, plugin code, or arbitrary
  `exec` reached through a tool.

**Deferred (not implemented, not scheduled by this ADR):** real human-channel isolation —
signing in a separate process holding the key, with an OS-level presence check (UAC
elevation prompt or Windows Hello) gating each signature. Only that closes the boundary the
current docstring implies.

## Alternatives Considered
* **Describe it as a trust boundary and move on.** Rejected. An incorrect security claim in
  a comment is worse than no claim: the next reader inherits the wrong threat model and
  builds on it. This is the failure mode the M25 hardening pass exists to catch.
* **Block the GUI approval widget until separate-process signing exists.** Rejected as
  disproportionate. The chokepoint plus audit trail is a real improvement over unlogged
  ambient authority, and the widget does not weaken any property listed above.
* **Delete the "trusted Human UI / CLI approval channel" docstring instead of writing an
  ADR.** Rejected as insufficient — the reasoning needs a durable home, not just the
  removal of a misleading line.

## Consequences
* **Positive:** The security model is written down at the strength it actually holds.
  Ticket-gated autonomous triggers keep their replay/TTL/substitution guarantees. Any future
  claim of human-presence enforcement has to point at new mechanism, not at this one.
* **Negative:** In-process code can still mint signatures, so a compromised or LLM-steered
  in-process path remains inside the trust envelope. Anything requiring proof of human
  presence must wait for separate-process signing.
* **Operational note:** `generate_human_signature` has **zero production callers today** —
  only tests exercise it (`test_phase1_manager_hardening`, `test_phase2_network_egress`,
  `test_phase3_security_hardening`, `test_all_new_capabilities`,
  `test_engineering_g5_git_governance`, `test_autonomous_hardening_and_state_injection`).
  The first production caller makes a test-only path load-bearing. A standalone,
  Qt-free integration test of the `generate_human_signature` → `verify_and_redeem` round
  trip through real orchestrator plumbing is a prerequisite for that caller, so integration
  bugs surface in pytest rather than live in an event loop.
