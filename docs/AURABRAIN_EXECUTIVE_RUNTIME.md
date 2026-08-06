# AuraBrain — The Executive Runtime (v0.19)

## Vision

Aura is **not** a chatbot. Aura is **not** an intent classifier. Aura is an **AI Operating System**.

AuraBrain is the Executive Runtime that coordinates the full cognitive pipeline.

---

## Architecture

```text
User
  │
  ▼
AuraCore Runtime
  │
  ▼
AuraBrain (Executive Runtime)
  │
  ├── Layer 0   : Context Manager
  ├── Layer 0.5 : World Model
  ├── Layer 2   : Goal Analyzer
  ├── Layer 3   : Capability Selector
  ├── Layer 4   : Execution Map Generator (Groq)
  ├── Layer 5   : Execution Map Validator
  ├── Layer 7   : Execution Coordinator
  ├── Layer 8   : Verification
  ├── Layer 9   : Reflection
  └── Layer 10  : Learning (Conservative)
  │
  ▼
MasterOrchestrator
  │
  ▼
Desktop | Browser | Research | Engineering | Memory | Voice | Vision
```

---

## The Golden Rule

> **The Executive Brain thinks. The Planner organizes. The Engines execute. Reflection validates. Learning improves.**

---

## Layer 0 — Context Manager

**File:** `src/brain/context_manager.py`

Runs BEFORE Groq. Collects everything Aura already knows so Groq doesn't have to guess.

Collects: conversation, pending questions, developer mode, runtime session, current project, current apps, browser tabs, focused window, memory facts, learned behaviors.

Think of it as Aura's RAM.

---

## Layer 0.5 — World Model

**File:** `src/brain/world_model.py`

Context is conversation. World Model is the computer.

Tracks: applications (running, focused, PID), browser tabs, workspace (project, git branch), voice (mic), clipboard, focused window.

Updates continuously — not only when the user asks. This is how Aura understands "Open it" → "it" → Chrome without asking.

---

## Layer 2 — Goal Analyzer

**File:** `src/brain/goal_analyzer.py`

Decomposes user requests into goals and sub-goals.

Example:
```
User: "Open YouTube in Chrome"

Goal: Open YouTube
Sub Goals:
  - Ensure Chrome exists
  - Focus browser
  - Navigate
  - Verify page
```

No mention of Browser Intent. Only goals.

---

## Layer 3 — Capability Selector

**File:** `src/brain/capability_selector.py`

Converts goals into capabilities.

```
Desktop: Launch Chrome
Browser: Navigate
Verification: Confirm page
```

Now Groq knows exactly what tools exist.

---

## Layer 4 — Execution Map Generator (Groq)

**File:** `src/brain/execution_map_generator.py`

The heart of Aura. Instead of asking Groq "Answer this user", Aura asks:

> "You are AuraBrain. Below is the Context Manager output. Below is the World Model. Below are available capabilities. Create ONLY a JSON Execution Map. Do NOT answer the user. Do NOT explain. Return valid JSON."

Example output:
```json
{
  "goal": "Open YouTube",
  "capabilities": ["desktop", "browser"],
  "steps": [
    {"engine": "desktop", "action": "launch_application", "parameters": {"application": "chrome"}},
    {"engine": "browser", "action": "navigate", "parameters": {"url": "https://youtube.com"}}
  ],
  "verification": ["chrome_running", "youtube_loaded"]
}
```

Groq is thinking. Aura is executing.

---

## Layer 5 — Execution Map Validator

**File:** `src/brain/execution_map_validator.py`

Never trust the LLM blindly. Every Execution Map must be validated.

Checks: unknown engines, unknown actions, invalid URLs, dangerous commands, missing verification, invalid JSON.

If validation fails → Ask Groq again.

---

## Layer 7 — Execution Coordinator

**File:** `src/brain/execution_coordinator.py`

Aura doesn't execute. It coordinates.

Delegates to: Desktop Engine, Browser Engine, Research Engine, Engineering Engine, Voice Engine, Memory Engine.

Each engine never thinks. It simply executes assigned tasks.

---

## Layer 8 — Verification

**File:** `src/brain/verification.py`

Richer than a simple success check. Validates each verification criterion from the Execution Map.

```
Requested: Open YouTube
Observed:
  - Chrome launched
  - youtube.com loaded
  - Page title
  - Window focused
  - PASS
```

If any check fails → Reflection.

---

## Layer 9 — Reflection

**File:** `src/brain/reflection.py`

Reflection answers:
- Did every step succeed?
- Was recovery needed?
- Was another capability better?
- Should I retry?
- Should I ask user?
- Should this improve future plans?

Example:
```
paint.exe → Failed → Retry mspaint.exe → Success → Record Recovery
```

---

## Layer 10 — Learning (Conservative)

**File:** `src/brain/learning.py`

Never learn automatically.

| Type | When | Example |
|------|------|---------|
| Facts | Immediate | "My favorite editor is VS Code." → Store |
| Preferences | Immediate | "Always answer in markdown." → Store |
| Behaviors | Immediate | "When I ask 'Summarize today's session', summarize RuntimeSession." → Store |
| Workflows | Observed | Need repeated evidence (3+ times) → Ask user to confirm |

---

## File Structure

```
src/brain/
├── __init__.py                  # Public exports
├── aura_brain.py                # AuraBrain Executive Runtime (orchestrator)
├── context_manager.py           # Layer 0: Context Manager
├── world_model.py               # Layer 0.5: World Model
├── goal_analyzer.py             # Layer 2: Goal Analyzer
├── capability_selector.py       # Layer 3: Capability Selector
├── execution_map_generator.py   # Layer 4: Execution Map Generator (Groq)
├── execution_map_validator.py   # Layer 5: Execution Map Validator
├── execution_coordinator.py     # Layer 7: Execution Coordinator
├── verification.py              # Layer 8: Verification
├── reflection.py                # Layer 9: Reflection (re-export)
├── learning.py                  # Layer 10: Learning (Conservative)
└── executive/                   # Legacy executive modules
```

---

## Integration

```python
# core/aura_core.py
self.executive_brain = AuraBrain(
    context_manager=ContextManager(memory=self.memory),
    world_model=WorldModel(),
    goal_analyzer=GoalAnalyzer(),
    capability_selector=CapabilitySelector(),
    execution_map_generator=ExecutionMapGenerator(llm_client=self.groq_client),
    execution_map_validator=ExecutionMapValidator(),
    execution_coordinator=ExecutionCoordinator(orchestrator=orchestrator),
    verification_engine=VerificationEngine(),
    reflection_engine=ReflectionEngine(),
    learning_engine=LearningEngine(),
    llm_client=self.groq_client,
)
```

Process requests:
```python
response = await aura_core.process_via_executive_brain("Open YouTube in Chrome")
```

---

## Success Criteria for v0.19

- [x] Every user request first goes through **Context Manager** and **World Model**
- [x] **Groq** produces a validated **Execution Map**, not a direct answer
- [x] The **Execution Coordinator** delegates all work to specialized engines
- [x] **Reflection** verifies outcomes and suggests recovery when needed
- [x] **Learning** stores only explicit facts, preferences, behaviors, or confirmed workflow patterns