# Engineering Diagnostics & Quality Tooling

The engineering module (`src/engineering/`) provides diagnostic, telemetry, and automated verification tools to maintain repository health and code quality.

---

## 1. Diagnostic Suite (`AuraDoctor`)

Invoked via `python aura.py --doctor`, `AuraDoctor` executes 22 automated system health checks:

- Python Version & Virtual Environment active status
- `architecture.json` and `capabilities.json` manifest loading
- Groq and Gemini API key availability
- Import hygiene and circular dependency check (AST import parsing)
- Health status of all 6 native desktop managers
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
