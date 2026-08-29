import json
from pathlib import Path

target_file = Path(r"C:\Users\yrsre\.gemini\config\plugins\googlecloudtools.datacloud_telemetry\hooks.json")
config = {
    "googlecloudtools.datacloud_telemetry": {
        "enabled": True,
        "PreToolUse": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "node telemetry_hook_bundle.js --agent_name gemini --install_source \"Antigravity IDE\"",
                        "timeout": 30
                    }
                ]
            }
        ]
    }
}

target_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
print(f"Updated {target_file}")
print("Content:\n" + target_file.read_text(encoding="utf-8"))
