# Backend Registry & Capability Adapters

The `BackendRegistry` (`src/core/backends/backend_registry.py`) and `CapabilityRegistry` (`src/core/capabilities/capability_registry.py`) dynamically route execution requests to available LLM providers, CLI bridges, persistent daemons, and native Win32 engines.

---

## 1. Registered Backend Adapters (23 Live Adapters)

Aura supports 23 unified backend adapters across native OS, intelligence, and integration domains:

| Category | Backend Adapter | Key Managed Capabilities |
| :--- | :--- | :--- |
| **Native OS & Input** | `DesktopEngineBackend` | Direct Win32 window, display, and application lifecycle control |
| | `InputBackendAdapter` | Win32 ctypes `SendInput` mouse movement, clicks, drag, keys, hotkeys |
| | `TerminalBackendAdapter` | PowerShell and CMD synchronous/asynchronous execution & CWD tracking |
| | `ScreenActionBackendAdapter` | Full screen capture, coordinate grounding, closed-loop UI actions |
| | `NotificationBackendAdapter` | Native Windows toast notifications, message boxes, and audio cues |
| | `SettingsBackendAdapter` | Windows Registry (`winreg`) toggles, dark mode, startup app management |
| | `SoftwareBackendAdapter` | Installed application enumeration, `winget`, `pip`, and `npm` package management |
| | `SecurityBackendAdapter` | Windows Firewall profile inspection, Defender status, UAC elevation, workstation locking |
| **Multimodal & Media** | `VoiceEngineBackend` | Multi-engine STT (Google, Whisper, Vosk) & TTS (Piper, Edge-TTS) with offline fallback |
| | `VisionEngineBackend` | Screen capture, OCR, UI grounding coordinates, sensitive window protection |
| **Intelligence & Memory** | `CodingBackendAdapter` | AST analysis, `CodeEditor` rollback, Antigravity bridge, automated repair loop |
| | `ResearchEngineBackend` | Evidence grounding, citation preservation, deep research, SSRF egress filter |
| | `MemoryBackend` | SQLite cognitive fact store & memory retrieval |
| **Autonomy & Scheduling** | `DaemonEngineBackend` | Persistent daemon background tasks, bounded worker pool, crash recovery |
| | `SchedulerBackendAdapter` | One-shot timers, interval schedules, cron patterns, and cancellation |
| **Productivity & Cloud** | `CalendarBackendAdapter` | SQLite-backed calendar events and task management |
| | `EmailBackendAdapter` | IMAP/SMTP email parsing and dispatch |
| | `OfficeBackendAdapter` | DOCX/XLSX generation and document automation |
| | `DockerBackendAdapter` | Container lifecycle management via Docker CLI |
| | `MCPBackendAdapter` | Model Context Protocol server registration and tool invocation |
| | `PlaywrightBrowserAdapter` | Headless/headed Playwright DOM automation and navigation |

---

## 2. Adaptive Negotiation Protocol

Backends are negotiated dynamically via `negotiate_capabilities()`:

```python
from core.backends.backend_registry import BackendRegistry

registry = BackendRegistry.get_instance()
selected_backend = registry.negotiate_capabilities(
    required_capabilities=["code.edit@1", "system.info@1"],
    preferred_backend="antigravity"
)
```

---

## 3. Metrics Tracking & Telemetry

`BackendRegistry` tracks moving-average statistics per backend:
- `latency_ms`: Response time window
- `success_rate`: Execution success percentage
- `total_calls`: Call volume counter

Telemetry can be inspected in real time via:
```bash
python aura.py --inspect
```

---

*Last Updated: August 18, 2026 — v0.27.0-autonomous-daemon*
