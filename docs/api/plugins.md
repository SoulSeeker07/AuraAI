# Aura Plugin SDK

The Aura Plugin SDK provides everything you need to create, develop, and deploy plugins for Aura AI.

## Overview

Plugins are modular extensions that add capabilities to Aura. They follow a consistent lifecycle:
- **Load**: Initialize the plugin
- **Initialize**: Set up the plugin's internal state
- **Execute**: Handle capabilities
- **Shutdown**: Clean up resources

## Plugin Structure

### Directory Layout

```
plugins/
├── desktop/
│   ├── my_plugin/
│   │   ├── __init__.py
│   │   ├── my_plugin.py
│   │   ├── _manifest.json
│   │   └── README.md
├── filesystem/
├── browser/
├── terminal/
├── git/
├── networking/
├── vision/
├── voice/
├── office/
├── email/
├── calendar/
├── knowledge/
├── docker/
├── database/
└── mcp/
    └── shared/
        └── plugin_sdk/
            ├── plugin_cli.py
            ├── manifest_generator.py
            └── README.md
```

## Plugin Categories

| Category | Description |
|----------|-------------|
| **desktop** | Desktop automation and UI control |
| **filesystem** | File operations, search, manipulation |
| **browser** | Browser automation, scraping, APIs |
| **terminal** | Terminal commands, shell operations |
| **git** | Git operations, repository management |
| **networking** | HTTP requests, web scraping, network tools |
| **vision** | Image analysis, OCR, computer vision |
| **voice** | Voice recognition, synthesis, audio processing |
| **office** | Office document manipulation (Word, Excel, PDF) |
| **email** | Email sending, reading, automation |
| **calendar** | Calendar events, reminders, scheduling |
| **knowledge** | Knowledge base management, search |
| **docker** | Docker container management |
| **database** | Database queries, CRUD operations |
| **mcp** | Model Context Protocol servers |

## Creating a Plugin

### Method 1: Using the CLI

```bash
aura-plugin-cli create-plugin my_plugin desktop
```

This creates:
- A plugin directory structure
- A template plugin file
- An empty manifest file
- A README with documentation template

### Method 2: Using the Manifest Generator

```python
from plugins.shared.plugin_sdk.manifest_generator import PluginManifestGenerator

generator = (
    PluginManifestGenerator(
        name="my_plugin",
        category="filesystem"
    )
    .set_author("Your Name")
    .set_description("My plugin does cool things")
    .add_capability("read_file")
    .add_capability("write_file")
    .add_permission("read_file")
    .add_permission("write_file")
)

manifest = generator.generate()
generator.save()
```

### Method 3: Manual Creation

1. Create a directory for your plugin in the appropriate category folder
2. Create `my_plugin.py` implementing the `Plugin` class
3. Create `_manifest.json` with plugin metadata
4. Create `__init__.py` (can be empty)
5. Create `README.md` with usage documentation

## Plugin Implementation

### Basic Plugin Structure

```python
import logging
from typing import Any, Dict, Optional
from src.plugins.plugin_interface import Plugin, PluginManifest, PluginCategory


class MyPlugin(Plugin):
    """Your plugin description."""

    def __init__(self, manifest: PluginManifest):
        """Initialize the plugin."""
        super().__init__(manifest)

    def load(self) -> bool:
        """Load the plugin."""
        try:
            logger.info(f"Loading plugin: {self.manifest.name}")

            # Register capabilities
            for capability in self.manifest.capabilities:
                self.register_capability(capability, self._handle_capability)

            return True

        except Exception as e:
            logger.error(f"Failed to load plugin: {e}")
            return False

    def initialize(self) -> bool:
        """Initialize the plugin."""
        try:
            logger.info(f"Initializing plugin: {self.manifest.name}")

            self.state = "ready"
            return True

        except Exception as e:
            logger.error(f"Failed to initialize plugin: {e}")
            return False

    def execute(self, capability: str, **kwargs) -> Any:
        """Execute a capability."""
        try:
            handler = self.get_capability_handler(capability)
            if not handler:
                raise Exception(f"Capability '{capability}' not found")

            return handler(**kwargs)

        except Exception as e:
            logger.error(f"Error executing capability '{capability}': {e}")
            self.set_error(e)
            raise

    def _handle_capability(self, **kwargs) -> Any:
        """Handle capability execution."""
        # Implement your logic here
        return {"status": "success", "result": "done"}

    def shutdown(self) -> bool:
        """Shutdown the plugin."""
        try:
            logger.info(f"Shutting down plugin: {self.manifest.name}")
            return True
        except Exception as e:
            logger.error(f"Error shutting down plugin: {e}")
            return False
```

### PluginManifest Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | str | Yes | Plugin name (no spaces) |
| `version` | str | Yes | Semantic version (e.g., 1.0.0) |
| `author` | str | No | Plugin author |
| `description` | str | Yes | Plugin description |
| `category` | PluginCategory | Yes | Category of the plugin |
| `capabilities` | List[str] | Yes | List of capabilities provided |
| `permissions` | List[str] | No | Required permissions |
| `dependencies` | List[str] | No | Plugin dependencies |
| `min_aura_version` | str | Yes | Minimum Aura version |
| `max_aura_version` | str | No | Maximum Aura version |
| `is_optional` | bool | Yes | Whether plugin is optional |
| `is_system` | bool | Yes | Whether plugin is system-level |

## Capabilities

Capabilities are the building blocks of plugin functionality. Each capability:
- Has a name (e.g., `read_file`, `search`, `export`)
- Is exposed to the Brain for execution
- Must be implemented by the plugin

### Capability Naming Convention

Use lowercase with underscores:
- ✅ `read_file`, `write_file`, `search_files`
- ❌ `ReadFile`, `read file`, `read-file`

### Implementing Capabilities

```python
def _handle_read_file(self, **kwargs) -> Dict:
    """Read a file."""
    file_path = kwargs.get('file_path')

    if not file_path:
        raise Exception("file_path is required")

    with open(file_path, 'r') as f:
        content = f.read()

    return {
        "success": True,
        "content": content,
        "size": len(content)
    }
```

## Permissions

Plugins declare permissions they need to operate. The PermissionManager will validate these before allowing execution.

### Permission Levels

| Level | Description |
|-------|-------------|
| SAFE | Low-risk operations |
| MEDIUM | Moderate-risk operations |
| HIGH | High-risk operations (require user confirmation) |
| CRITICAL | Critical operations (require admin privileges) |

### Common Permissions

- `read_file`, `write_file`, `delete_file`
- `read_directory`, `list_directory`
- `execute_command`, `execute_shell`
- `access_network`, `make_http_request`
- `access_database`, `query_database`

## Dependencies

Plugins can declare dependencies on other plugins:

```json
{
  "name": "database_tool",
  "dependencies": ["file_reader", "search"]
}
```

Aura will ensure dependencies are loaded before your plugin.

## Plugin Lifecycle Events

Plugins can publish events that the Brain can listen to:

```python
def _some_operation(self):
    # Perform operation
    result = self._do_something()

    # Publish event
    self.registry.trigger_event(
        "operation_complete",
        plugin_name=self.manifest.name,
        result=result
    )
```

## Debugging

### Enable Plugin Logging

```python
# In your plugin
logger = logging.getLogger(f"plugin.{self.manifest.name}")
logger.setLevel(logging.DEBUG)

# Add handler
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)
```

### View Plugin Status

```python
from plugins import PluginManager

manager = PluginManager(registry)

# Get status of all plugins
statuses = manager.get_all_plugin_statuses()
for name, status in statuses.items():
    print(f"{name}: {status['state']}")

# Get specific plugin status
status = manager.get_plugin_status("my_plugin")
print(f"Enabled: {status['enabled']}")
print(f"Capabilities: {status['capabilities']}")
```

### Enable Plugin Debug Mode

Add this to your plugin's `__init__.py`:

```python
import logging

# Enable debug logging
logging.getLogger("plugin_system").setLevel(logging.DEBUG)
```

## Testing Your Plugin

Create a test script:

```python
# test_my_plugin.py
import sys
import os
sys.path.insert(0, 'src')

from plugins import PluginRegistry, PluginManager

# Initialize registry
registry = PluginRegistry(plugins_dir="plugins")
manager = PluginManager(registry, enable_auto_discovery=False)
manager.initialize()

# Get your plugin
plugin = manager.get_plugin("my_plugin")

if plugin:
    # Execute capability
    result = plugin.execute("read_file", file_path="test.txt")
    print(f"Result: {result}")
else:
    print("Plugin not found")
```

## Common Patterns

### Async Capability Execution

```python
import asyncio

async def _async_operation(self, **kwargs):
    await asyncio.sleep(1)
    return {"status": "completed"}
```

### Batch Operations

```python
def _batch_read_files(self, **kwargs):
    """Read multiple files."""
    file_paths = kwargs.get('file_paths', [])

    results = []
    for path in file_paths:
        try:
            content = self._read_file(path)
            results.append({"file": path, "content": content})
        except Exception as e:
            results.append({"file": path, "error": str(e)})

    return {"results": results}
```

### File Watching

```python
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class MyPlugin(Plugin):
    def __init__(self, manifest):
        super().__init__(manifest)
        self.observer = Observer()

    def load(self):
        super().load()
        self.observer.schedule(MyHandler(self), path="/path/to/watch")
        self.observer.start()

    def shutdown(self):
        self.observer.stop()
        self.observer.join()
        super().shutdown()

class MyHandler(FileSystemEventHandler):
    def __init__(self, plugin):
        self.plugin = plugin

    def on_modified(self, event):
        if event.is_directory:
            return
        self.plugin.execute("file_modified", file_path=event.src_path)
```

## Best Practices

1. **Keep plugins focused**: Each plugin should do one thing well
2. **Handle errors gracefully**: Always use try-except blocks
3. **Validate inputs**: Check that all required parameters are provided
4. **Log everything**: Use the logger for all important events
5. **Document capabilities**: Clearly document what your plugin does
6. **Test thoroughly**: Test with various inputs and edge cases
7. **Use async when possible**: For I/O operations, use async/await
8. **Clean up resources**: Always release resources in shutdown()

## Next Steps

- Read the [Plugin Architecture](architecture.md) document
- See [plugin_interface.py](src/plugins/plugin_interface.py) for the interface definition
- Run [tests/test_plugin_integration.py](tests/test_plugin_integration.py) to understand how plugins work
- Create your first plugin using `aura-plugin-cli create-plugin`
