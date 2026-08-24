import re
import pathlib

pattern = re.compile(r'patch\(\s*(["\'])src\.([a-zA-Z0-9_\.]+)\1')

files = [
    "tests/test_continuous_loop_level3.py",
    "tests/test_deep_research.py",
    "tests/memory/test_auracore_brain_init_wiring.py",
    "tests/memory/test_integration_voice_memory.py",
    "tests/unit/test_auracore_autonomy.py",
    "tests/unit/test_native_managers_audit.py",
]

modified = 0
for rel in files:
    p = pathlib.Path(rel)
    if not p.exists():
        continue
    content = p.read_text(encoding="utf-8")
    new_content = pattern.sub(r'patch(\1\2\1', content)
    if new_content != content:
        p.write_text(new_content, encoding="utf-8")
        modified += 1
        print(f"Updated patch targets in {rel}")

print(f"Done. Modified {modified} files.")
