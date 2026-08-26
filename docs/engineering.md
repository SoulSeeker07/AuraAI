# Engineering Diagnostics, Quality Tooling & Autonomous Platform

The engineering subsystem (`src/engineering/`) provides diagnostic telemetry, verification pipelines, and the **Autonomous Engineering Platform** for closed-loop bug fixing and test-driven repair.

---

## 1. Diagnostic Suite (`AuraDoctor`)

Invoked via `python aura.py --doctor`, `AuraDoctor` executes 22 automated system health checks:

- Python Version & Virtual Environment active status
- `architecture.json` and `capabilities.json` manifest loading
- Groq and Gemini API key availability
- Import hygiene and circular dependency check (AST import parsing)
- Health status of native desktop managers
- Multi-agent runtime and plugin ecosystem status
- Memory footprint (< 250 MB) and startup latency (< 5.0 s)

---

## 2. Telemetry Dashboard (`AuraInspector`)

Invoked via `python aura.py --inspect`, `AuraInspector` renders a real-time terminal state dashboard showing:
- Registered planners and backends
- Total and healthy capability counts
- Event bus throughput (events/sec)
- Process memory usage

---

## 3. Verification Pipeline (`AuraVerifier`)

Invoked via `python aura.py --verify`, `AuraVerifier` executes the mandatory CI pipeline:
1. **Ruff Linting**: `ruff check`
2. **Black Formatting**: `black --check`
3. **Isort Order**: `isort --check`
4. **Mypy Type Check**: `mypy`
5. **Architecture Tests**: `pytest tests/architecture/`

---

## 4. Autonomous Engineering Platform (Milestone 27 & 28)

The Autonomous Engineering Platform enables closed-loop, self-healing code repair bounded by strict security guardrails:

- **`FaultLocalizer`**: Parses test failure stack frames and slices AST structures to identify the innermost enclosing function/method/class scopes.
- **`SandboxedPytestRunnerAdapter`**: Executes test suites under `AuraSandboxUser` isolated by Windows Job Objects (512MB memory cap, CPU limit, sanitized environment).
- **`WorkspacePolicy` & Single-Write Gate**: Enforces directory containment, blocks edits to the protected safety ceiling (`PROTECTED_SAFETY_CEILING`), and ensures test-file immunity.
- **`AutonomousEngineeringLoop`**: Orchestrates snapshotting, retry bounds (`max_retries=3`), diff generation, patch application, and byte-exact rollbacks.
- **`PatchBundleAssembler`**: Compiles structured PR markdown summaries with unified diffs, requiring cryptographic HMAC approval tokens before git merge/push actions.
