# Runtime Acceptance Checklist & Verification Manual
Location: `docs/RUNTIME_ACCEPTANCE.md`

This document defines the official manual acceptance checklist and regression manual for the Aura AI Platform runtime. Every release must pass these acceptance gates in the live CLI (`python aura.py --cli`) prior to tagging a new platform version.

---

## 📋 Runtime Acceptance Matrix

### 🖥️ 1. Desktop Subsystem Acceptance
- [ ] **Launch Application**: `"Open Notepad"` → Native OS window opens and is verified via `WorldSnapshot`.
- [ ] **Minimize Window**: `"Minimize it"` → Target window minimizes to taskbar without ambiguity.
- [ ] **Restore Window**: `"Restore it"` → Minimized window restores to foreground.
- [ ] **Close Window**: `"Close it"` → Non-protected application closes cleanly.
- [ ] **Focus Existing Window**: `"Focus Notepad"` → Reuses running window handle (`hwnd`) instead of launching duplicate instances.
- [ ] **Reuse Existing Application**: `"Open Notepad"` when already open → ExecutionPolicy triggers `REUSE_EXISTING` and focuses window.
- [ ] **Respect SafetyPolicy**: `"Close VS Code"` → Blocked by `SafetyPolicy` with exception message `Safety constraint: AuraAI is prohibited from closing protected application 'Visual Studio Code'.`

---

### 🌐 2. Browser Subsystem Acceptance
- [ ] **Launch Browser**: `"Open Chrome"` → Playwright Browser Engine opens persistent browser context.
- [ ] **Reuse Browser**: `"Open Chrome"` when open → Reuses active browser session without spawning duplicate processes.
- [ ] **Navigate Web Target**: `"Open YouTube"` → Opens YouTube in active browser context.
- [ ] **Social Media Navigation**: `"Open Instagram"` → Opens Instagram tab in active context.
- [ ] **Search Engine**: `"Search Google for Python docs"` → Performs search and displays results.
- [ ] **Close Tab**: `"Close Instagram tab"` → Closes specific tab by title/URL match.
- [ ] **Close Filtered Tabs**: `"Close documentation tabs"` → Closes matching domain tabs while preserving main context.
- [ ] **Reuse Existing Tab**: `"Switch to YouTube"` → Focuses existing open tab.
- [ ] **Resource Ownership Tracking**: `ResourceOwnershipTracker` records Aura-owned browser tabs.

---

### 🛠️ 3. Software Engineering Subsystem Acceptance
- [ ] **Delegated Execution**: `"Create hello.py"` → Request delegates directly to `SoftwareEngineeringSupervisor`.
- [ ] **Antigravity Worker**: `Antigravity CLI` worker session launches asynchronously.
- [ ] **IDE Integration**: VS Code opens target file in active workspace (`D:\AuraAI`).
- [ ] **Physical File Creation**: File is created on disk with project conventions.
- [ ] **Validation Worker Execution**: `PytestWorker`, `RuffWorker`, and `GitDiffWorker` run validation checks.
- [ ] **Worker Telemetry**: Worker progress percentages stream to `EngineeringSession`.
- [ ] **No Chat Code Generation**: Groq **never** emits raw python markdown blocks into chat CLI.

---

### ⚡ 4. Runtime & WorkerManager Acceptance
- [ ] **Active Worker Summary**: `"Show active workers"` → Displays clean multi-domain session listing (`Engineering`, `Browser`, `Desktop`, `Research`).
- [ ] **Pause Domain**: `"Pause engineering"` → `WorkerManager` pauses active engineering worker session.
- [ ] **Resume Domain**: `"Resume engineering"` → `WorkerManager` resumes paused engineering session.
- [ ] **Cancel Worker**: `"Cancel worker 1"` → Cancels specified worker by ID or index.
- [ ] **Zero-LLM Status Queries**: `"status?"` / `"How's it going?"` → Deterministically returns session progress without LLM inference.
- [ ] **Session Replay**: `SessionReplayEngine` recreates timeline trace.
- [ ] **Timeline Audit**: `WorldTimeline` stores ordered event sequence.

---

### 🧠 5. Conversational Reference & Memory Acceptance
- [ ] **Pronoun Resolution**: `"it"`, `"that"`, `"this window"` resolve correctly to current focused or active OS window.
- [ ] **Previous Action Context**: Follow-up commands (`"Close it"`) operate on previous action target.
- [ ] **Ownership Recall**: System distinguishes user-opened vs. Aura-opened windows/tabs.
- [ ] **Session History Integrity**: Conversation history maintains turn context across domain switches.
