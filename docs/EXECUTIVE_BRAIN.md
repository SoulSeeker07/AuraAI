# Aura Executive Brain (v0.19)

## Vision

Aura is **not** a chatbot.

Aura is **not** an intent classifier.

Aura is an **AI Operating System**.

An operating system does not immediately execute every request. It first understands the user's goal, reasons about the current system state, creates an execution strategy, delegates work to specialized engines, verifies the outcome, reflects on failures, and finally learns from the interaction.

The Executive Brain is the cognitive center of Aura.

---

## Architecture

```text
User
   │
   ▼
AuraCore
   │
   ▼
ExecutiveBrain
   │
   ├── Layer 1 : DMM (Decision Making Module)
   ├── Layer 2 : Planner
   ├── Layer 3 : Executor
   ├── Layer 4 : Reflection
   └── Layer 5 : Learning
   │
   ▼
MasterOrchestrator
   │
   ▼
Execution Engines
```

The Executive Brain is the only intelligent component.
Every other module is deterministic.

---

## The Golden Rule

> **The Executive Brain thinks. The Planner organizes. The Engines execute. Reflection validates. Learning improves.**

---

## Layer 1 — Decision Making Module (DMM)

**File:** `src/brain/executive/dmm.py`

The DMM is the executive. It understands the user's intention, not classifies keywords.

For every request it answers:

```text
What is the user's goal?
↓
What information do I already know?
↓
Do I have enough information?
↓
Can I infer the missing details?
↓
Should I ask a clarification?
↓
Which capabilities are required?
↓
Build an execution map.
```

The DMM never executes anything. It only thinks.

### Output: ExecutionMap

The DMM produces a **structured, machine-readable execution plan** using a fixed schema:

```yaml
Goal: str
RequiredCapabilities: list[Capability]
ExecutionPlan: list[ExecutionStep]
ExpectedResult: str
Verification: SuccessCriteria
Fallbacks: list[FallbackOption]
```

This makes plans deterministic, easy to validate, and safe for Aura to execute automatically.

### Example: "Open YouTube in Chrome"

```yaml
Goal: Open youtube in chrome
RequiredCapabilities: [desktop, browser]
ExecutionPlan:
  - Check if chrome is already running
  - Launch chrome if not already running
  - Wait for chrome window to appear
  - Navigate to https://www.youtube.com
  - Verify page loaded: youtube
ExpectedResult: chrome displays the youtube homepage
Verification:
  - chrome window exists
  - Navigation to youtube succeeded
```

---

## Layer 2 — Planner

**File:** `src/brain/executive/planner.py`

Converts an ExecutionMap into concrete runtime actions.

The Planner determines:
- execution order
- dependencies
- retries
- parallel tasks
- runtime sessions

The planner never decides the goal.

---

## Layer 3 — Executor

**File:** `src/brain/executive/executor.py`

Uses existing engines:
- Desktop Engine
- Browser Engine
- Research Engine
- Engineering Engine (Antigravity)
- Memory Engine
- Voice Engine

These engines never think. They simply execute assigned tasks.

---

## Layer 4 — Reflection

**File:** `src/brain/executive/reflection.py`

Reflection begins after execution.

Questions include:
- Did execution succeed?
- Did verification pass?
- Did an error occur?
- Can the problem be recovered automatically?
- Should another capability be used?
- Should the user be informed?

Example:
```
paint.exe not found
```

Reflection:
```
Try mspaint.exe.
↓
Success.
↓
Update verification.
```

---

## Layer 5 — Learning

**File:** `src/brain/executive/learning.py`

Learning occurs only after the task is complete.

The Learning Engine captures:
- new facts
- user preferences
- behavior corrections
- workflow patterns

Example:
```
User: "When I ask 'Summarize today's session',
       summarize everything we worked on."
```

Learning stores:
```yaml
Type: BehaviorRule
Trigger: Summarize today's session
Action: Summarize RuntimeSession
Priority: High
```

Next time, the DMM consults learned behavior before planning.

---

## Executive Thinking Loop

```text
Observe
↓
Understand
↓
Reason
↓
Plan
↓
Execute
↓
Verify
↓
Reflect
↓
Learn
↓
Observe...
```

Execution is only one stage. Thinking comes first.

---

## The Role of the LLM

Groq is not the executor. Groq is the Executive Brain.

Responsibilities:
- Understand natural language
- Infer user goals
- Select capabilities
- Produce execution maps
- Supervise execution
- Interpret results
- Summarize outcomes

Groq should **not**:
- generate project code directly
- launch applications
- manipulate files
- automate browsers

Those responsibilities belong to specialized engines.

---

## File Structure

```
src/brain/executive/
├── __init__.py          # Public exports
├── execution_map.py     # ExecutionMap schema (fixed, machine-readable)
├── dmm.py               # Layer 1: Decision Making Module
├── planner.py           # Layer 2: Executive Planner
├── executor.py          # Layer 3: Executive Executor
├── reflection.py        # Layer 4: Reflection Engine
├── learning.py          # Layer 5: Learning Engine
└── executive_brain.py   # ExecutiveBrain orchestrator (5-layer pipeline)
```

---

## Integration

The Executive Brain is integrated into `AuraCore`:

```python
# core/aura_core.py
self.executive_brain = ExecutiveBrain(llm_client=self.groq_client)
self.executive_brain.executor = ExecutiveExecutor(orchestrator=orchestrator)
```

Requests can be processed via:

```python
response = await aura_core.process_via_executive_brain("Open YouTube in Chrome")
```

---

## Roadmap

```text
v0.18.5
Architecture Lock
✓

↓

v0.19.0
Executive Brain (DMM)
✓

• Goal Understanding ✓
• Context Awareness ✓
• Capability Selection ✓
• Execution Map Generation ✓
• Executive Supervision ✓

↓

v0.20.0
Adaptive Learning Runtime
• Fact Learning
• Behavior Learning
• Preference Learning
• Workflow Learning

↓

v0.21.0
Voice Runtime

↓

v0.22.0
Browser Intelligence

↓

v0.23.0
GUI Runtime

↓

v1.0
Aura OS