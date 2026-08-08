# Agent Execution & Safety Guidelines

## Tool Execution & Autonomy
- **Autonomous Editing & Execution**: You are expected to plan, write, edit files, and execute terminal commands autonomously without stopping to ask for user approval.
- **Proactive Implementation**: Perform code changes, bug fixes, refactoring, formatting, linting, and tests automatically.
- **Virtual Environment (.venv)**: Always run Python scripts, tools, formatting, linting, and tests using the project's virtual environment (e.g. `.\.venv\Scripts\python.exe` or `.\.venv\Scripts\pytest`). Never use global `python` or global `pip`.


## Deletion & Destructive Action Guardrail
- **STOP & CONFIRM FOR DELETION**: You MUST obtain explicit user confirmation before running any command or tool that results in irreversible data loss or file deletion (e.g., `rm`, `Remove-Item`, `git clean -fd`, `DROP TABLE`, or deleting project files/folders).
