# Definition of Done (DoD)
Location: `docs/DEFINITION_OF_DONE.md`

This document defines the strict **Definition of Done (DoD)** for all milestones and feature releases in Aura AI. Every milestone must satisfy all criteria across the 6 categories before it is declared complete or merged into the primary platform branch.

---

## 📋 Milestone Completion Checklist

### 1. Architecture
- [ ] **Documented**: Comprehensive architectural specification updated in `docs/` and `docs/adr/`.
- [ ] **Contract Compliance**: All interfaces implement standard contracts (`RuntimeSession`, `BasePlanner`, `BaseBackendAdapter`).
- [ ] **No Core Redesign**: Extends existing abstractions without inventing duplicate core models or altering frozen APIs.

### 2. Code Quality
- [ ] **Ruff Linting**: Passes `ruff check .` with zero errors or warnings.
- [ ] **Black Formatting**: Passes `black --check .` with zero formatting violations.
- [ ] **Isort Import Order**: Passes `isort --check-only .` with standard import ordering.
- [ ] **Mypy Static Typing**: Passes `mypy src/` with zero type errors.

### 3. Testing & Verification
- [ ] **Unit Tests**: Domain unit tests pass 100%.
- [ ] **Architecture Tests**: Dependency graph and import boundary tests (`tests/architecture/`) pass with zero layer violations.
- [ ] **Runtime Acceptance**: Subsystem manual acceptance scenarios (`docs/RUNTIME_ACCEPTANCE.md`) pass in live runtime (`main.py` / `aura.py --cli`).

### 4. Documentation
- [ ] **`README.md`**: Updated with features, philosophy, and version badges.
- [ ] **`RELEASE.md`**: Detailed release notes added under semantic versioning.
- [ ] **`roadmap.md`**: Milestone status and completion percentage updated.
- [ ] **Architecture Docs**: Layer manifests and ADR records updated in `docs/adr/`.

### 5. Runtime & Safety
- [ ] **Manual Acceptance Passed**: All domain checklist items pass in live execution.
- [ ] **Zero Regression**: Desktop, Browser, Engineering, and Memory subsystems function without breaking existing workflows.
- [ ] **Automated Pipeline**: `python aura.py --verify` returns `ALL CHECKS PASSED`.

### 6. Platform Freeze
- [ ] **Architecture Frozen**: Core interfaces marked frozen in `docs/ARCHITECTURE_FREEZE.md`.
- [ ] **Public Interfaces Intact**: No breaking changes to public platform contracts.
