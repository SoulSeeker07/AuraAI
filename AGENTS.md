# Agent Execution & Safety Guidelines

## Tool Execution & Autonomy
- **Autonomous Editing & Execution**: You are expected to plan, write, edit files, and execute terminal commands autonomously without stopping to ask for user approval.
- **Proactive Implementation**: Perform code changes, bug fixes, refactoring, formatting, linting, and tests automatically.
- **Virtual Environment (.venv)**: Always run Python scripts, tools, formatting, linting, and tests using the project's virtual environment (e.g. `.\.venv\Scripts\python.exe` or `.\.venv\Scripts\pytest`). Never use global `python` or global `pip`.


## Deletion & Destructive Action Guardrail
- **STOP & CONFIRM FOR DELETION**: You MUST obtain explicit user confirmation before running any command or tool that results in irreversible data loss or file deletion (e.g., `rm`, `Remove-Item`, `git clean -fd`, `DROP TABLE`, or deleting project files/folders).


## Definition of Done — Non-Negotiable

A task is NOT complete until:
1. **Real Execution**: The actual change has been executed (not described) and you have observed its real output — a test run, a benchmark, a log line — not your prediction of what it would show.
2. **Falsifiable Verification**: If a claim can be falsified by a specific check (e.g. "this doesn't affect X" — check X; "the warning fires" — trigger it and show the log line), that check has actually been run, not reasoned about.
3. **Observation vs Expectation**: Before reporting success, ask yourself: "Am I describing what I did, or what I expect happened?" If it's the latter, run it first.
4. **Honest Reporting of Gaps**: If something fails, is unverified, or only partially works, say so explicitly in the summary — do not present partial success as completion. A false "done" costs more time than an honest "not yet."
5. **Regression Claims Require Baseline Proof**: Any claim about "no regression" or "unrelated to my changes" must be checked against a clean/prior state, not asserted from confidence.

### Verification Calibration
- **Scale to the Claim**: A one-line typo fix does not need a full regression suite; a claim like "this doesn't affect the GUI tests" or "the index is faster" must be proven with targeted tests or concrete numbers.
- **No Verification Theater**: Verification must directly test the specific claim being made. Running an unrelated command to produce output does not satisfy this rule.
