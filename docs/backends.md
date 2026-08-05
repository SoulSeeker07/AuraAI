# Backend Registry & Capability Router

The `BackendRegistry` (`src/core/backends/backend_registry.py`) dynamically routes execution requests to available LLM providers, CLI tools, and native engines.

---

## 1. Supported Backend Adapters

Aura supports 4 provider backends:

- **Groq Adapter**: Ultra-low latency inference (`llama-3.3-70b-versatile`, `mixtral-8x7b-32768`).
- **Gemini Adapter**: Deep reasoning and multimodal understanding (`gemini-2.0-flash`).
- **Antigravity CLI Adapter**: CLI integration adapter for local coding tasks.
- **Desktop Engine Adapter**: Direct C++/Win32 execution adapter.

---

## 2. Adaptive Negotiation Protocol

Backends are negotiated dynamically via `negotiate_capabilities()`:

```python
from core.backends.backend_registry import BackendRegistry

registry = BackendRegistry.get_instance()
selected_backend = registry.negotiate_capabilities(
    required_capabilities=["reason.deep@3", "code.edit@1"],
    preferred_backend="gemini"
)
```

---

## 3. Metrics Tracking

`BackendRegistry` tracks moving-average statistics per backend:
- `latency_ms`: Response time window
- `success_rate`: Execution success percentage
- `total_calls`: Call volume counter

Telemetry is inspected via `python aura.py --inspect`.
