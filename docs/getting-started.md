# Getting Started Guide

Welcome to Aura AI Platform (`v0.15.0-core-platform`). This guide will help you set up your local environment, run diagnostics, launch client interfaces, and use the unified CLI launcher.

---

## 1. Prerequisites

- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python Runtime**: Python 3.11.x (Python 3.12+ features compatible)
- **Git**: Git 2.30+
- **Virtual Environment**: `.venv` recommended

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
.venv\Scripts\activate
```

### Step 3: Install Required Dependencies
```powershell
pip install -r requirements.txt
pip install -e .[dev]
```

### Step 4: Environment Variables (Optional)
Copy `.env.example` to `.env` or export environment variables:
```powershell
set GROQ_API_KEY=your_groq_api_key_here
set GEMINI_API_KEY=your_gemini_api_key_here
```

---

## 3. Canonical Launcher (`aura.py`)

Aura provides a single umbrella entry point script `aura.py` supporting diagnostic, telemetry, verification, CLI, and GUI modes.

### Run System Health Check
```powershell
python aura.py --doctor
```
Runs 22 comprehensive checks covering Python version, venv, manifests, API keys, import hygiene, circular dependencies, loaded planners, and desktop managers.

### Inspect Telemetry Dashboard
```powershell
python aura.py --inspect
```
Displays live state telemetry, including registered planners, backends, capabilities, memory footprint, and event throughput.

### Execute Verification Pipeline
```powershell
python aura.py --verify
```
Runs Ruff, Black, Isort, Mypy, and Pytest architecture tests in one command.

### Launch Interactive CLI Client
```powershell
python aura.py --cli
```

### Launch GUI Interface
```powershell
python aura.py --gui
```
