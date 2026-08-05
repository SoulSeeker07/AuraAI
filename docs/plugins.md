# Plugin Ecosystem Architecture

The plugin architecture enables extending Aura AI capabilities dynamically without modifying core source code.

---

## 1. Declarative Schema (`config/plugin.schema.json`)

All plugins declare capabilities and dependencies via `plugin.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AuraPluginDeclaration",
  "type": "object",
  "required": ["plugin_id", "name", "version", "entry_point", "capabilities"],
  "properties": {
    "plugin_id": { "type": "string" },
    "name": { "type": "string" },
    "version": { "type": "string" },
    "entry_point": { "type": "string" },
    "capabilities": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

---

## 2. Plugin Lifecycle

1. **Auto-Discovery**: Scans `plugins/` directory for `plugin.json` manifests.
2. **Schema Validation**: Validates manifest against `plugin.schema.json`.
3. **Registration**: Registers capability keys into `BackendRegistry`.
4. **Activation**: Instantiates entry point and subscribes to `EventBus`.
