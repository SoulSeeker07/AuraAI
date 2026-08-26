# Milestone 29 — Smart Home / IoT Integration & Ambient Desktop HUD Interaction (`v0.33.0`)

## Goal
Milestone 29 expands AuraAI beyond local desktop OS automation into **Physical Ambient Intelligence & Multi-Device Control**, providing bidirectional Home Assistant WebSocket integration, direct local Tapo/Kasa device encryption protocols (KLAP AES-CBC-128), a verified Smart Home capability domain, and an enhanced glassmorphic HUD overlay suite for real-time ambient awareness.

---

## 1. Core Architectural Pillars

| Pillar | Focus Area | Deliverables & Verified Architectural Invariants | Key Components |
| :--- | :--- | :--- | :--- |
| **P1** | **Home Assistant WebSocket & REST Integration** | Bidirectional state synchronization via HA WebSocket; resilient event listener; dynamic entity registry; state-aware command verification with optimistic dispatch and automatic state rollback on failure. | [`src/integrations/smarthome/ha_client.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/integrations/smarthome/ha_client.py), [`src/integrations/smarthome/ha_ws.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/integrations/smarthome/ha_ws.py) |
| **P2** | **Direct Tapo / Kasa IoT Protocol (KLAP)** | Zero-cloud local device control; KLAP (Kasa Local Access Protocol) handshake; SHA-256 seed negotiation; AES-CBC-128 cryptographic payload encryption; direct color/brightness/effect control on TP-Link Tapo L530 and smart plugs. | [`src/integrations/smarthome/tapo_client.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/integrations/smarthome/tapo_client.py) |
| **P3** | **Unified Smart Home Backend & Capability Domain** | Dedicated `SmartHomeBackendAdapter` and `SmartHomeCapabilityProvider` exposing 12 structured capabilities (`light.*`, `switch.*`, `climate.*`, `camera.*`, `scene.*`, `smarthome.state`); 4-tier risk classification; async loop bridging; graceful offline degradation. | [`src/core/backends/adapters/smarthome_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/backends/adapters/smarthome_backend.py), [`src/core/capabilities/providers/smarthome_provider.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/core/capabilities/providers/smarthome_provider.py) |
| **P4** | **Ambient Desktop HUD Suite** | Frameless translucent PySide6 HUDs: `JarvisRingsOverlay` (dynamic pulsing orbital arcs), `ChatWindowOverlay` (floating conversational UI with voice controls), `WeatherOverlay`, `SystemMonitorOverlay`, `PersonalOSDashboardOverlay`, `AgentTaskStatusOverlay`, `MatrixOverlay`, `SystemStatusOverlay`. | [`src/gui/widgets/`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/gui/widgets/), [`src/gui/real_backend_bridge.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/gui/real_backend_bridge.py) |
| **P5** | **Real-Time Telemetry & IPC Bridge** | Low-latency state bridge (`RealBackendBridge`) linking core runtime telemetry (CPU/RAM/GPU, active DAG subtasks, triggers, daily context, and smart home states) directly to Qt GUI signals without blocking the event loop. | [`src/gui/real_backend_bridge.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/gui/real_backend_bridge.py), [`src/gui/signals.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/src/gui/signals.py) |

---

## 2. Deep Dive: Smart Home Subsystem Architecture

```text
┌────────────────────────────────────────────────────────┐
│                   AuraCore Orchestration               │
│        (MasterOrchestrator · TaskDecomposer)           │
└────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│               SmartHomeCapabilityProvider              │
│       (12 Registered Capabilities · ActionRisk)         │
└────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│                SmartHomeBackendAdapter                 │
│         (Async Loop Bridging · State Rollback)         │
└────────────────────────────────────────────────────────┘
              │                             │
              ▼                             ▼
┌───────────────────────────┐ ┌───────────────────────────┐
│    HomeAssistantClient    │ │        TapoClient         │
│  (REST API + WebSocket)   │ │  (Local KLAP AES-CBC-128) │
└───────────────────────────┘ └───────────────────────────┘
              │                             │
              ▼                             ▼
      Home Assistant Core             TP-Link Tapo L530
     (Entities, Scenes, Fans)        (Smart Bulb / Plugs)
```

### Supported Smart Home Capabilities:
1. `light.turn_on` / `light.turn_off` / `light.toggle`: Brightness (0–255), RGB color, color temperature, transition time.
2. `switch.turn_on` / `switch.turn_off` / `switch.toggle`: Smart plugs, relays, and switches.
3. `climate.set_temperature` / `climate.set_hvac_mode`: Thermostat and HVAC target control.
4. `camera.get_stream_url` / `camera.snapshot`: Camera RTSP/HLS stream URL acquisition and snapshots (`ActionRisk.MEDIUM`).
5. `scene.apply`: Room-wide or house-wide scene activation.
6. `smarthome.state`: Entity state inspection and attribute discovery.

---

## 3. Deep Dive: Ambient HUD Overlays

The Ambient HUD layer renders hardware-accelerated translucent widgets directly above the Windows desktop with zero disruption to active applications:

1. **`JarvisRingsOverlay`**:
   - Multi-layered concentric orbital rings rendered using `QPainter` with sub-pixel antialiasing.
   - Dynamic rotation speeds, glowing gradients, and reactive pulsing based on AI thinking / speech state.
   - Draggable frameless window with click-through toggle and persistent screen geometry.

2. **`ChatWindowOverlay`**:
   - Floating conversation window with markdown rendering, streaming token display, and voice waveform visualizer.
   - Integrated microphone toggle, model switcher, and expandable tool execution drawer.

3. **`PersonalOSDashboardOverlay` & `SystemMonitorOverlay`**:
   - Live telemetry charts for CPU, memory, disk, network, and GPU.
   - Proactive daily briefings, pending triggers, and scheduled task notifications.

---

## 4. Verification & Test Coverage

- **SmartHome Backend & Provider Suite**: [`tests/test_smarthome_backend.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/test_smarthome_backend.py) (5/5 passing)
- **Home Assistant Client Suite**: [`tests/test_ha_client.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/test_ha_client.py) (passing)
- **Jarvis Rings & Overlay Suite**: [`tests/test_jarvis_rings.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/test_jarvis_rings.py) (passing)
- **Engineering Sandboxed Runner Suite**: [`tests/test_engineering_sandboxed_runner.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/test_engineering_sandboxed_runner.py) (5/5 passing)
- **CodeAct Test Suite**: [`tests/test_codeact/`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/test_codeact/) (43/43 passing)
- **RAG & File Services Suite**: [`tests/unit/test_rag_and_file_services.py`](file:///d:/Sreekanta/VS%20Code%20Project/Desktop%20AI/AuraAI/tests/unit/test_rag_and_file_services.py) (passing)
