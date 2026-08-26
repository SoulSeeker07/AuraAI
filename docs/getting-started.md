# Getting Started Guide

Welcome to Aura AI Platform (`v0.32.0-autonomous-desktop-os`). This guide will help you set up your local environment, run diagnostics, launch client interfaces, and use the unified CLI and HUD overlay launchers.

---

## 1. Prerequisites

- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python Runtime**: Python 3.11.x (Python 3.12+ compatible)
- **Git**: Git 2.30+
- **Virtual Environment**: `.venv` (strictly recommended)

---

## 2. Environment Setup

### Step 1: Clone Repository
```bash
git clone https://github.com/SoulSeeker07/AuraAI.git
cd AuraAI
```

### Step 2: Create & Activate Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### Step 3: Install Required Dependencies
```powershell
pip install -r requirements.txt
pip install -e .[dev]
```

### Step 4: Environment Variables
Copy `.env.example` to `.env` or set environment variables:
```powershell
set GROQ_API_KEY=your_groq_api_key_here
set GEMINI_API_KEY=your_gemini_api_key_here
```

---

## 3. Launchers & Operating Modes

### Unified Batch Launchers
- **`aura.bat` / `aura.cmd`**: One-click launcher for the unified Aura platform.
- **`run_chat.bat`**: Launches the conversational chat window interface.

### Interactive CLI Client
```powershell
.\.venv\Scripts\python.exe main.py
# Or via canonical launcher
.\.venv\Scripts\python.exe aura.py --cli
```

### Desktop HUD Overlays
Aura provides PySide6 ambient desktop overlays for system monitoring, task tracking, and personal OS workflows:

```powershell
# Launch System Monitor HUD (CPU, RAM, Network, GPU)
.\.venv\Scripts\python.exe run_status_hud.py

# Launch Agent Task Status HUD (Live DAG subtasks)
.\.venv\Scripts\python.exe run_task_status_hud.py

# Launch Personal OS Dashboard (Daily briefing, priorities, triggers)
.\.venv\Scripts\python.exe run_personal_os_hud.py

# Launch Glassmorphic Chat Window
.\.venv\Scripts\python.exe run_chat_window.py
```

---

## 4. Diagnostics & Verification

### Run System Health Check
```powershell
.\.venv\Scripts\python.exe aura.py --doctor
```
Runs 22 comprehensive checks covering Python version, venv, manifests, API keys, import hygiene, circular dependencies, loaded planners, and desktop managers.

### Inspect Telemetry Dashboard
```powershell
.\.venv\Scripts\python.exe aura.py --inspect
```
Displays live state telemetry, including registered planners, backends, capabilities, memory footprint, and event throughput.

### Execute Automated Test Suites
```powershell
# Run full deterministic test suite
.\.venv\Scripts\python.exe -m pytest tests/ -v
```
