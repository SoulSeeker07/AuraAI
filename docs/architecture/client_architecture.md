# AuraAI CLI/GUI Architecture

## Overview

AuraAI now uses a modular client architecture that separates the core intelligence from the presentation layer. This allows you to switch between CLI and GUI modes without modifying core code.

```
AuraAI/
├── core/
│   ├── aura_core.py          # The main Aura brain (Brain, Memory, Knowledge, Plugins)
│   ├── app.py                # Multi-agent system integration
│   └── ...
├── clients/
│   ├── __init__.py
│   ├── cli_client.py         # CLI client (interactive command-line)
│   └── gui_client.py         # GUI client (for QML interface)
├── main.py                    # Entry point with CLI/GUI switch
├── run_aura.py                # Simple launcher script
└── frontend/                  # QML GUI files
    └── Main.qml
```

## Architecture Principles

### 1. Separation of Concerns
- **Aura Core**: Pure business logic, no UI code
- **CLI Client**: Handles command-line input/output
- **GUI Client**: Handles QML interface communication

### 2. Single Source of Truth
All clients communicate with the same `AuraCore` instance. This ensures:
- Consistent behavior across all interfaces
- Easy testing (CLI is integration test environment)
- No duplicate code

### 3. Plug-and-Play
Add new clients (Voice, API, Web) without touching core code.

## Using AuraAI

### CLI Mode (Default)

Run AuraAI in the command-line interface:

```bash
# Using run_aura.py (recommended)
python run_aura.py

# Or using main.py
python main.py --cli

# Or no flag (default to CLI)
python main.py
```

The CLI provides:

#### General Commands
- `status` - Show system status
- `chat` - Start interactive chat
- `doctor` - Run health check
- `graph` - Show architecture graph
- `help` - Show help
- `quit` - Exit CLI

#### Memory Commands
- `memory` - Show memory statistics
- `memory:clear` - Clear working memory
- `memory:export` - Export memories

#### Knowledge Commands
- `knowledge` - Show knowledge statistics
- `knowledge:search <query>` - Search knowledge
- `knowledge:add` - Add to knowledge base
- `knowledge:clear` - Clear knowledge

#### Workspace Commands
- `workspace` - Show workspace info
- `workspace:scan <path>` - Scan workspace
- `workspace:analyze <file>` - Analyze file
- `workspace:fix <file>` - Fix file issues

#### Plugin Commands
- `plugins` - Show plugin status
- `plugins:load <name>` - Load plugin
- `plugins:unload <name>` - Unload plugin

#### Task Commands
- `tasks` - Show task status
- `tasks:list` - List all tasks
- `tasks:cancel <id>` - Cancel task

#### History Commands
- `history` - Show conversation history
- `history:clear` - Clear history

#### Workflow Commands
- `workflow` - Show workflow status
- `workflow:run <name>` - Run workflow
- `workflow:list` - List workflows

#### Agent Commands
- `agents` - Show agent information
- `agents:list` - List all agents
- `agents:info <name>` - Get agent details

#### Engineering Commands
- `engineering` - Show engineering tools
- `engineering:fix <file>` - Fix code issues
- `engineering:test <file>` - Run tests
- `engineering:docs <file>` - Generate documentation

### GUI Mode

Run AuraAI in GUI mode:

```bash
python run_aura.py --gui
```

The GUI mode will:
1. Initialize Aura Core
2. Create GUI Client
3. Launch QML interface

**Note**: GUI mode is not fully implemented yet. The GUI client is available and ready for integration with QML.

## Creating New Clients

To add a new client (e.g., Voice, API, Web):

1. Create new client class in `clients/` directory:

```python
# clients/voice_client.py
from core.aura_core import AuraCore

class VoiceClient:
    def __init__(self, aura_core: AuraCore):
        self.aura_core = aura_core

    def listen(self):
        # Voice recognition
        pass

    def speak(self, text):
        # Text-to-speech
        pass

    def process_command(self, command):
        # Process voice command
        return self.aura_core.run_task(...)
```

2. Add to `clients/__init__.py`:

```python
from .voice_client import VoiceClient

__all__ = ['CLIClient', 'GUIClient', 'VoiceClient']
```

3. Update `main.py` to include the new client:

```python
from clients.voice_client import VoiceClient

def main_voice():
    aura_core = create_aura_core()
    voice_client = VoiceClient(aura_core)
    # Run voice interface
    voice_client.run()
```

4. Add voice mode to `run_aura.py`:

```bash
python run_aura.py --voice
```

## Testing

The CLI is your best integration test environment:

1. Every bug becomes obvious in CLI
2. Easy to debug and reproduce
3. Full control over all features
4. Can test before GUI development

Once CLI reaches 100%, GUI is guaranteed to work.

## Switching Between CLI and GUI

No files need to be changed. Just use different commands:

```bash
# CLI mode
python run_aura.py --cli

# GUI mode
python run_aura.py --gui
```

## Implementation Notes

### Aura Core (`core/aura_core.py`)
- Contains all business logic
- No UI or presentation code
- Handles:
  - Memory management
  - Knowledge indexing
  - Plugin system
  - Workspace awareness
  - Task execution
  - Event handling

### CLI Client (`clients/cli_client.py`)
- Interactive command-line interface
- All CLI commands implemented
- User-friendly output formatting
- Error handling and validation

### GUI Client (`clients/gui_client.py`)
- API for QML interface
- Provides methods for QML to call Aura Core
- Can be extended for other GUI frameworks

### Main Entry Point (`main.py`)
- Handles command-line arguments
- Creates appropriate client based on mode
- Manages application lifecycle

## Future Enhancements

1. **Full GUI Implementation**
   - Complete QML interface using GUIClient
   - Real-time status updates
   - Interactive chat UI
   - Plugin management UI

2. **Voice Interface**
   - Voice recognition using Whisper or similar
   - Text-to-speech for responses
   - Voice commands

3. **API Client**
   - REST API endpoints
   - WebSocket support
   - SDK for other applications

4. **Web Interface**
   - Web-based GUI using web framework
   - Same API as GUIClient
   - Real-time updates

5. **Advanced Features**
   - Task scheduling
   - Workflow visualization
   - Real-time monitoring
   - Analytics dashboard

## Migration Guide

If you were using the old architecture:

1. **No changes needed for core logic**
   - All existing code still works
   - Aura Core uses existing services

2. **CLI mode works immediately**
   - Try `python run_aura.py --cli`
   - All commands should work

3. **GUI mode requires QML integration**
   - GUI client is ready
   - Need to create QML interface to use it

4. **Old code can be refactored**
   - Move specific logic to Aura Core
   - Use clients for input/output
   - Keep presentation separate

## Troubleshooting

### CLI doesn't start
- Check Python version (3.7+ required)
- Verify all dependencies are installed
- Check workspace path

### GUI mode doesn't work
- GUI client requires QML environment
- Make sure Qt is installed
- Check QML files are in frontend/

### Plugins not loading
- Check plugin paths
- Verify plugin dependencies
- Check plugin initialization

## Summary

The new CLI/GUI architecture provides:
- ✓ Clean separation of concerns
- ✓ Easy switching between modes
- ✓ Better maintainability
- ✓ Easy to add new clients
- ✓ CLI as integration test environment
- ✓ Full GUI support ready

Once CLI is 100%, GUI is guaranteed to work!
