import json
from ai.key_pool import KeyPool

kp = KeyPool.get_instance()

tools_14 = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file"},
                    "start_line": {"type": "integer", "description": "Optional start line"},
                    "end_line": {"type": "integer", "description": "Optional end line"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace exact existing text with new replacement text in a workspace file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file"},
                    "target_content": {"type": "string", "description": "Exact existing code snippet to replace"},
                    "replacement_content": {"type": "string", "description": "New code snippet to insert"}
                },
                "required": ["path", "target_content", "replacement_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run targeted pytest verification suite on a test file or module.",
            "parameters": {
                "type": "object",
                "properties": {
                    "test_target": {"type": "string", "description": "Path to test file or specific test function"}
                },
                "required": ["test_target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terminal_run_command",
            "description": "Execute a shell or PowerShell command on the system. Safe read-only inspection commands execute immediately; mutating commands generate an approval ticket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The exact shell command line string to execute."},
                    "cwd": {"type": "string", "description": "Optional working directory path."},
                    "ticket_id": {"type": "string", "description": "Cryptographic approval ticket ID for mutating commands."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_get_telemetry",
            "description": "Get real-time hardware telemetry: CPU, RAM, battery level, and active OS metrics.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vision_inspect_screen",
            "description": "Capture current screen and inspect visible text, active window content, and open applications via OCR/vision.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Specific element, application, or text to look for on screen."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_navigate_and_read",
            "description": "Navigate to a web URL using headless browser engine and extract page text or markdown content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The web URL to navigate to."},
                    "extract_mode": {"type": "string", "enum": ["markdown", "text", "title", "links"], "description": "Extraction mode"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_interact",
            "description": "Perform an interactive action in the active browser page (click, type, scroll, wait).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["click", "type", "scroll", "press_key"]},
                    "selector": {"type": "string", "description": "CSS or XPath selector"},
                    "value": {"type": "string", "description": "Text value to type or key to press"}
                },
                "required": ["action", "selector"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_launch_app",
            "description": "Launch a Windows application (e.g. notepad, spotify, chrome, calc, vscode).",
            "parameters": {
                "type": "object",
                "properties": {
                    "application": {"type": "string", "description": "Name of the application to launch"}
                },
                "required": ["application"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_control_window",
            "description": "Control an application window (focus, minimize, maximize, restore, or close).",
            "parameters": {
                "type": "object",
                "properties": {
                    "window_title": {"type": "string", "description": "Window title or app name"},
                    "action": {"type": "string", "enum": ["focus", "minimize", "maximize", "restore", "close"]}
                },
                "required": ["window_title", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_save_fact",
            "description": "Save a user preference, profile detail, or persistent note to memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["profile", "preference", "skill", "project", "goal"]},
                    "key": {"type": "string", "description": "Fact key"},
                    "value": {"type": "string", "description": "Information to remember"}
                },
                "required": ["category", "key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_query_facts",
            "description": "Query persistent memory to recall user preferences or facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "key": {"type": "string"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "personal_os_agenda",
            "description": "Get today agenda, deadlines, and prioritized tasks from Personal OS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD date"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_plan_update",
            "description": "Update the active task plan and subtasks progress checklist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_id": {"type": "string"},
                                "title": {"type": "string"},
                                "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "failed"]}
                            },
                            "required": ["task_id", "title", "status"]
                        }
                    }
                },
                "required": ["tasks"]
            }
        }
    }
]

prompts = [
    ("Prompt 1 (Code Edit)", "In file src/calc.py, change x = 1 to x = 2"),
    ("Prompt 2 (Run Tests vs Terminal)", "Run the pytest test suite for tests/test_calc.py"),
    ("Prompt 3 (Screen Inspection vs Telemetry)", "Check what is currently on my screen and tell me if Notepad is open"),
    ("Prompt 4 (Browser Navigate)", "Open https://news.ycombinator.com and extract the headlines in markdown"),
    ("Prompt 5 (Memory Query)", "Do you remember what my favorite editor is?")
]

def run_suite(api_key):
    client = kp.get_groq_client(api_key)
    for model_name in ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]:
        print("==================================================")
        print(f"EVALUATING MODEL: {model_name} with 14 tools in context")
        print("==================================================")
        for label, p in prompts:
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are Aura, an AI desktop assistant. Use the provided tools when appropriate."},
                        {"role": "user", "content": p}
                    ],
                    tools=tools_14,
                    tool_choice="auto"
                )
                choice = resp.choices[0]
                if choice.message.tool_calls:
                    tc_strs = [f"{tc.function.name}({tc.function.arguments})" for tc in choice.message.tool_calls]
                    print(f"{label}: TOOL CALL -> {'; '.join(tc_strs)}")
                else:
                    print(f"{label}: NO TOOL CALL -> {choice.message.content.strip()[:100]}")
            except Exception as e:
                print(f"{label}: ERROR -> {e}")
        print()

if __name__ == "__main__":
    kp.execute_with_failover(run_suite, service="groq")
