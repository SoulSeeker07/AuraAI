# 🏛️ AuraAI System & Cognitive Architecture Documentation

> **CORE PRINCIPLE:** *"The architecture is largely complete. The runtime is not."*
> Every user request flows through a single cognitive runtime pipeline.

---

## 📊 High-Level Layer Breakdown

| Layer Level | Architecture Layer | Description | Modules | Classes | Functions | Complexity |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: |
| **1** | 🚀 **Applications & Clients** | CLI, GUI, REST/WS API servers, main entry points | 17 | 11 | 118 | 243 |
| **2** | 👑 **OS Kernel & Executive Brain** | AuraCore, ExecutiveBrain, RuntimeSession, MasterOrchestrator | 69 | 117 | 493 | 1599 |
| **3** | 🧠 **Cognitive Architecture (ACA)** | Cognitive Pipeline: Perception, DMM, Strategy, Policy, Planner, Coordinator, Reflection, Learning | 46 | 109 | 328 | 1136 |
| **4** | 🎯 **Domain Subsystems & Engines** | Desktop, Browser, Research, Engineering, Vision, Voice engines and adapters | 192 | 439 | 2572 | 5754 |
| **5** | 📚 **Memory & Knowledge Base** | Fact store, vector store, long-term memory, knowledge graphs, SQLite | 35 | 49 | 422 | 861 |
| **6** | 🏛️ **Infrastructure & Event Bus** | EventBus, Logger, Base Contracts, Configuration, Shared Schemas | 173 | 176 | 1336 | 3535 |
| **7** | 🔌 **Tool Execution & Plugins** | Plugins, Tool Registry, Extension Kits | 11 | 22 | 101 | 255 |

---

## 🔁 Continuous Agent Decision & Cognitive Pipeline Flow

```mermaid
graph TD
  subgraph USER_LAYER ["🚀 1. USER & APPLICATION INTERFACES"]
    USER(("👤 User Input"))
    CLI["💻 CLI Client (cli.py)"]
    GUI["🎨 Desktop GUI Client"]
    VOICE["🎙️ Voice Interface"]
  end

  subgraph CORE_LAYER ["👑 2. AURA OS KERNEL & RUNTIME CORE"]
    CORE["⚙️ AuraCore (aura_core.py)"]
    SESSION["📋 RuntimeSession"]
    EVENTBUS["⚡ EventBus (Broadcaster)"]
  end

  subgraph ACA_LAYER ["🧠 3. AURA COGNITIVE ARCHITECTURE (ACA)"]
    BLACKBOARD["📝 Blackboard (CognitiveState)"]
    DMM["🔍 Decision Manager (DMM)"]
    STRATEGY["🎯 StrategyEngine (Stage 1.5)"]
    POLICY["🛡️ PolicyEngine (Governance)"]
    PLANNER["📐 ACAPlanner (ExecutionGraph)"]
    COORDINATOR["⚡ ExecutionCoordinator (Stage 3)"]
    REFLECTION["🔄 ReflectionEngine (Stage 4)"]
    LEARNING["💡 LearningEngine (Stage 4)"]
  end

  subgraph SUBSYSTEMS_LAYER ["🎯 4. DOMAIN ENGINE ADAPTERS & SUBSYSTEMS"]
    REGISTRY["🏥 Backend & Capability Registry"]
    DESKTOP_ENG["🖥️ DesktopEngineAdapter → 17 Win32 Managers"]
    CODEACT_ENG["⚡ CodeAct Executor → Python Sandbox"]
    SMARTHOME_ENG["🏠 SmartHome Adapter → HA & Tapo KLAP"]
    BROWSER_ENG["🌐 BrowserEngineAdapter → Playwright"]
    RESEARCH_ENG["🔬 ResearchEngineAdapter → Deep Search"]
    ENGINEERING_ENG["🛠️ EngineeringManager → AST & Refactor"]
    VISION_ENG["👁️ VisionManager → OCR & Element Detect"]
    VOICE_ENG["🔊 VoiceManager → STT / TTS"]
    HUD_LAYER["📊 Desktop HUD Overlays → PySide6 Translucent"]
  end

  subgraph MEMORY_LAYER ["📚 5. KNOWLEDGE & PERSISTENCE"]
    MEMORY["💾 Memory 2.0 (Fact & Vector Store)"]
    GOALS["🎯 GoalManager (Long-term Goals)"]
    ARTIFACTS["📦 ArtifactManager"]
  end

  %% Flow Connections
  USER --> CLI & GUI & VOICE
  CLI & GUI & VOICE --> CORE
  CORE --> SESSION & BLACKBOARD
  BLACKBOARD --> DMM
  DMM --> STRATEGY
  STRATEGY --> POLICY
  POLICY --> PLANNER
  PLANNER --> COORDINATOR
  COORDINATOR --> REGISTRY
  REGISTRY --> DESKTOP_ENG & BROWSER_ENG & RESEARCH_ENG & ENGINEERING_ENG & VISION_ENG & VOICE_ENG
  DESKTOP_ENG & BROWSER_ENG & RESEARCH_ENG & ENGINEERING_ENG --> REFLECTION
  REFLECTION --> LEARNING
  LEARNING --> MEMORY
  COORDINATOR --> ARTIFACTS
  EVENTBUS -.-> BLACKBOARD & REFLECTION

  %% Styling
  style USER_LAYER fill:#FEF08A33,stroke:#CA8A04,stroke-width:2px
  style CORE_LAYER fill:#E9D5FF33,stroke:#9333EA,stroke-width:2px
  style ACA_LAYER fill:#FFEDD533,stroke:#EA580C,stroke-width:2px
  style SUBSYSTEMS_LAYER fill:#CCFBF133,stroke:#0D9488,stroke-width:2px
  style MEMORY_LAYER fill:#FED7AA33,stroke:#D97706,stroke-width:2px
```

---

## 🛡️ Guardrail Rules & Component Layer Contracts

1. **Single Entry Point**: All user requests enter through `AuraCore.process_request()`.
2. **Guardrail 1 Decoupling**: No domain backend (`src/desktop`, `src/browser`, `src/research`, `src/engineering`, `src/vision`) may import from `src.brain.aca`.
3. **Single Coordinator**: Only `ExecutionCoordinator` invokes execution engines via `EngineRegistry` & `EngineAdapters`.
4. **Shared Blackboard**: All stages read from and write to `Blackboard` (`CognitiveState`).

*Generated automatically on 2026-08-08 03:06:53 by `generate_architecture.py`.*