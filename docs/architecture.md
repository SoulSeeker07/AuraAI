# Architecture Overview

This document outlines the architecture for Aura, a modular AI agent system with separation between core intelligence and presentation layers.

## System Components

### Core Components

**Aura Core** (`core/`)
- Pure business logic without UI code
- Handles: Memory management, Knowledge indexing, Plugin system, Workspace awareness, Task execution, Event handling
- Single source of truth for all clients

**Clients** (`clients/`)
- CLI Client (`cli_client.py`) - Interactive command-line interface
- GUI Client (`gui_client.py`) - QML interface communication API

**Plugins** (`plugins/`)
- Modular plugin ecosystem
- Categories: Browser, Calendar, Desktop, Docker, Email, Engineering, Filesystem, Git, Knowledge, MCP, Networking, Office, Shared, Terminal, Vision, Voice

### Presentation Layer

**Desktop** (`apps/desktop/`)
- QML-based control center using PySide6
- Main application interface

**Overlay** (`apps/overlay/`)
- QML frameless overlay invoked by hotkey
- Context-aware display layer

## Communication

- **WebSocket** - Local real-time communication (AI/messaging, status updates)
- **HTTP** - Config and control interface
- **Event Bus** - Asynchronous event handling across components

## Architecture Principles

1. **Separation of Concerns** - Core logic separated from presentation
2. **Single Source of Truth** - All clients use same AuraCore instance
3. **Plug-and-Play** - Add new clients/plugins without modifying core code

## Usage

### CLI Mode
```bash
python run_aura.py --cli
python main.py --cli
python main.py  # defaults to CLI
```

### GUI Mode
```bash
python run_aura.py --gui
```

### Services
Aura runs FastAPI + WebSocket services in background for AI/messaging operations.

## Key Directories

- `core/` - Core business logic (Brain, Memory, Plugins)
- `clients/` - Input/output interfaces (CLI, GUI, Voice, API, Web)
- `backend/` - Backend services (AI, Automation, Vision, Voice)
- `plugins/` - Plugin ecosystem
- `apps/` - Desktop and overlay applications
- `frontend/` - QML GUI files
- `shared/` - Shared utilities and models
- `docs/` - Documentation
- `tests/` - Test suites

See [roadmap.md](roadmap.md) for milestone breakdown and delivery plan.
