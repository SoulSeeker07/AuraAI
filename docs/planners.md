# Domain Planner System Specification

Planners in Aura AI are specialized domain reasoning engines responsible for analyzing user intent, decomposing multi-step goals, and producing execution plans.

---

## 1. Registered Planners

Aura includes four domain-specific planners registered in `config/capabilities.json`:

| Planner Class | Domain | Core Capabilities |
| :--- | :--- | :--- |
| **`DesktopPlanner`** | Native OS Automation | `desktop.window.activate`, `desktop.clipboard.copy`, `desktop.display.info` |
| **`ResearchPlanner`** | Deep Research | `research.decompose`, `research.evidence.evaluate`, `research.citations` |
| **`CodingPlanner`** | Software Refactoring | `code.ast.parse`, `code.edit`, `code.test.run` |
| **`BrowserPlanner`** | Web Automation | `browser.navigate`, `browser.element.click`, `browser.screenshot` |

---

## 2. Dynamic Discovery Schema (`config/planner.schema.json`)

Planners register dynamically via JSON Schema contracts:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AuraPlannerDeclaration",
  "type": "object",
  "required": ["planner_id", "domain", "supported_capabilities", "version"],
  "properties": {
    "planner_id": { "type": "string" },
    "domain": { "type": "string" },
    "version": { "type": "string" },
    "supported_capabilities": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

---

## 3. Execution Lifecycle

1. **Intent Analysis**: Planner receives target intent and workspace context.
2. **Decomposition**: Task split into sub-steps with assigned capabilities.
3. **Capability Negotiation**: Capability key requested from `BackendRegistry`.
4. **Step Execution**: Handed to native manager or backend LLM adapter.
5. **Verification & Trace**: Recorded in `ExecutionTrace` and `ExecutionMemory`.
