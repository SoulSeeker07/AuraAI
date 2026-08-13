# Phase 6 — Hardening & Real-World Validation (AuraAI)

> Live tracker for Phase 6 of the Aura Personal AI OS hardening campaign.
> Invariant: **Normalize wording, never invent intent.**
> Architecture: **FROZEN** — no new brains, routers, planners, or execution layers
> are introduced; adversarial robustness is achieved by stressing the existing
> perception → governance → execution pipeline.

---

## H-Gate Status

| Gate | Name | Status | Evidence |
|---|---|---|---|
| **H1** | Full-System Regression | 🟢 PASS | `pytest tests/unit -q` → **138 passed, 3 warnings** (9 Aug 2026; 112 baseline + 26 H4 deterministic pins) |
| **H2** | Windows Endurance | 🟡 PASS (functional) / resource observation | 30m04s, 403 cycles, G1–G10 & G13–G15 PASS, **0 exceptions / 0 stuck / 0 false successes**; G11 (handles +6,493 / limit 250) & G12 (2 orphan chromium) FAIL — see §Post-retrofit re-validation below |
| **H3** | Cross-Domain E2E | 🟢 PASS | `scratch/test_phase6_cross_domain.py` → **8/8 gates, 13.88s** (re-run post-retrofit, 9 Aug 2026) |
| **H4** | Adversarial NL + STT Robustness | 🟢 PASS | `scratch/test_phase6_adversarial.py` → **10/10 gates** (re-run #4 post-retrofit, 9 Aug 2026) |

---

## Post-Retrofit Re-validation (bare-import conversion, 9 Aug 2026)

After the H2/H3 gate scripts were converted from `src.*` to canonical bare imports
(singleton-identity invariant), all three H-gates were re-run **on the real Windows
machine**:

| Gate | Re-run result | Evidence |
|---|---|---|
| H3 | 🟢 **8/8 PASS** | 13.88s; all 8 cross-domain gates PASS |
| H4 | 🟢 **10/10 PASS** | run #4; G1–G10 all PASS |
| H2 | 🟡 functional PASS / resource FAIL | 30m04s, 403 cycles (see below) |

### H2 re-run detail (duration 1804s, 403 cycles)
- Functional lifecycle: **G1–G10 PASS**, **G13 Event Queue Drain PASS**, **G14 Graceful
  Shutdown PASS**, **G15 Clean Restart PASS**.
- Integrity: **0 unhandled exceptions, 0 stuck executions, 0 false successes**.
- Resource stability (H2-G11): RSS +54.1 MB (limit 150 ✓), threads −6 (limit 10 ✓),
  **handles +6,493 (limit 250 ✗)** → FAIL.
- Browser/process cleanup (H2-G12): 2 orphan chromium processes above baseline → FAIL.
- **Classification:** the import-convention retrofit is a pure module-prefix change and
  cannot produce OS handles or processes. The G11/G12 observation is a runtime-level
  characteristic of the current working-tree baseline (which carries pre-existing WIP
  changes in `desktop_backend.py` / `execution_coordinator.py` / `desktop/native/verification.py`).
  It is tracked as an open hardening item — **not silently resolved**; the gate is
  reported honestly at 🟡.

---

## H4 — Adversarial NL + STT Robustness

### Scope
Stress the **existing** pipeline only:

```text
NLUEngine → ReferenceResolver → DecisionEngine (DMM) → ExecutionPolicy → PersonalOSRuntime → ExecutionCoordinator → GoalVerifier
```

No new NLU/brain/router/engine was added. One defect found & fixed **inside the
existing policy layer** (see below).

### Acceptance Facts (real Windows machine, 2026-08-09)

| Gate | Scenario | Result |
|---|---|---|
| H4-G1 | Corrupted STT / noise words | 🟢 PASS |
| H4-G2 | Typos & phonetic misspellings | 🟢 PASS |
| H4-G3 | Incomplete / truncated commands | 🟢 PASS |
| H4-G4 | Ambiguous pronoun referents | 🟢 PASS |
| H4-G5 | Multi-intent utterances | 🟢 PASS |
| H4-G6 | Contradictory follow-up | 🟢 PASS |
| H4-G7 | Non-English filler / code-mixing | 🟢 PASS |
| H4-G8 | High-risk phrasing must block | 🟢 PASS |
| H4-G9 | Empty / whitespace / punctuation input | 🟢 PASS |
| H4-G10 | Repeated identical goals (idempotency) | 🟢 PASS |

### H4 Defect Found & Fixed (G8)
- **Symptom:** `"format drive C"` and `"kill all running processes"` were
  classified as chat, collapsed to a generic `provider.open_app` action, and
  executed (returned SUCCESS).
- **Root cause:** `classify_action_risk()` matched high-risk keywords against the
  **action name** only; provider/chat steps keep the original user wording in the
  **params** (`{"task": "chat", "message": "format drive C"}`), so the intent was
  invisible to the risk classifier.
- **Fix (existing component, no new architecture):**
  `src/core/orchestration/autonomy_mode.py` — added **phrase-gated** high-risk
  matching over the execution parameters (`format drive|disk|volume|…`,
  `kill all|every|process…`, `wipe/erase/purge … all`,
  `delete/remove/drop/destroy … all`, `shutdown/reboot/halt …`,
  `logout/sign out … all|now`, `rm -rf`).
- **False-positive control:** benign chat is preserved —
  `"what is format in excel?"`, `"explain the kill command in linux"`,
  `"search for the movie kill bill"` remain LOW/MEDIUM risk.
- **Outcome:** all four G8 high-risk inputs now BLOCK (ASK_USER → BLOCKED under
  ASSISTED autonomy when not user-authorized); H4: **10/10 PASS**.

### Deterministic CI Coverage
`tests/unit/test_phase6_adversarial_nl.py` — 26 OS-agnostic unit pins:
- Normalization invariance (G1/G2)
- "Never invent intent" ambiguity outcomes (G4/G6)
- High-risk phrasing → HIGH risk + ASK_USER; benign chat → not blocked (G8)
- Autonomy/risk confirmation matrix
- Degenerate-input safety (G9)

---

## Permanent Architectural Invariants (sealed with Phase 6)

### 1. Import Convention (split-singleton protection)
- `pythonpath = ["src"]` in `pyproject.toml` ⇒ `brain.X` and `src.brain.X` are
  two different module keys for the same file.
- Rule: no `src.` prefix for `brain|core|experts|autonomy|voice|vision` in
  `src/`, `tests/`, or active `scratch/` code.
- Enforcement:
  - `scripts/check_import_convention.py` (scans 673 files; 12 frozen M18–M23
    historical artifacts allowlisted with documented reasons).
  - `tests/architecture/test_import_convention.py` (pytest guard).
  - CI step `Import Convention Check (split-singleton guard)` in
    `.github/workflows/ci.yml`.
- Singleton identity regression test:
  `tests/unit/test_personal_os_runtime.py::test_00_singleton_identity_invariant`
  asserts `EngineRegistry.get_instance() is runtime.engine_registry`,
  `DomainExpertRegistry.get_instance() is runtime.expert_registry`, and
  `ExecutionPolicy.get_instance() is runtime.policy`.

### 2. Frozen Artifact Policy
- Historical M18–M23 gate scripts remain **byte-for-byte/functionally untouched**.
- Active Phase 6 gates (H2/H3/H4) use canonical bare imports only.

---

## Required Run-Order Before Any Future H-Gate
```powershell
.\.venv\Scripts\python.exe scripts/check_import_convention.py
.\.venv\Scripts\pytest tests/architecture -q
.\.venv\Scripts\pytest tests/unit -q
```
All three must be green before running the next Windows acceptance gate.