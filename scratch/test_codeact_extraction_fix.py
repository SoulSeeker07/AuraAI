import re
import ast

def extract_code_block(text: str) -> str:
    text_clean = text.strip()

    # 1. Whole-response wrapped in code fence
    if text_clean.startswith("```"):
        first_nl = text_clean.find("\n")
        last_fence = text_clean.rfind("```")
        if first_nl != -1 and last_fence > first_nl and last_fence == len(text_clean) - 3:
            first_line = text_clean[:first_nl].strip().lower()
            if first_line == "```" or first_line.startswith("```python") or first_line.startswith("```py"):
                return text_clean[first_nl + 1:last_fence].strip()

    # 2. Find explicit standalone markdown python code blocks (multiline match)
    # Opening fence on its own line: ^\s*```(?:python|py)\s*$
    # Closing fence on its own line: ^\s*```\s*$
    pattern = r"(?m)^\s*```(?:python|py)\s*\n(.*?)(?:\n\s*```\s*$|\Z)"
    matches = re.findall(pattern, text_clean, re.DOTALL | re.IGNORECASE)
    if matches:
        return max(matches, key=len).strip()

    # 3. Fallback: match any standalone code block
    pattern_generic = r"(?m)^\s*```(?:[a-zA-Z0-9_-]+)?\s*\n(.*?)(?:\n\s*```\s*$|\Z)"
    matches_generic = re.findall(pattern_generic, text_clean, re.DOTALL | re.IGNORECASE)
    if matches_generic:
        return max(matches_generic, key=len).strip()

    # 4. Final fallback: standard non-greedy regex
    pattern_any = r"```(?:python)?\s*\n(.*?)```"
    matches_any = re.findall(pattern_any, text_clean, re.DOTALL | re.IGNORECASE)
    if matches_any:
        return max(matches_any, key=len).strip()

    return text_clean

def test_sibling_blocks():
    text = (
        "Here is the setup step:\n"
        "```bash\n"
        "pip install markdown\n"
        "```\n\n"
        "Here is the main python script:\n"
        "```python\n"
        "import json\n"
        "print('hello from python')\n"
        "```\n"
    )
    extracted = extract_code_block(text)
    assert "pip install" not in extracted, f"Sibling bash block leaked: {extracted}"
    assert "import json" in extracted
    assert "print('hello from python')" in extracted
    ast.parse(extracted)

def test_nested_code_fences_in_python_block():
    text = (
        "```python\n"
        "import json\n"
        "from pathlib import Path\n"
        "payload = {'code': 'def greet():\\n    print(\"hi\")'}\n"
        "lines = [\n"
        "    '# Title',\n"
        "    '```python',\n"
        "    payload['code'],\n"
        "    '```'\n"
        "]\n"
        "Path('out.md').write_text('\\n'.join(lines))\n"
        "```"
    )
    extracted = extract_code_block(text)
    assert extracted.startswith("import json")
    assert extracted.endswith("Path('out.md').write_text('\\n'.join(lines))")
    ast.parse(extracted)

def test_prose_with_nested_code_fences():
    text = (
        "Here is the requested script:\n\n"
        "```python\n"
        "import json\n"
        "lines = ['# Title', '```python', 'x = 1', '```']\n"
        "print('\\n'.join(lines))\n"
        "```\n\n"
        "Let me know if you need changes!"
    )
    extracted = extract_code_block(text)
    assert "Here is the requested script" not in extracted
    assert "Let me know" not in extracted
    assert "import json" in extracted
    assert "print('\\n'.join(lines))" in extracted
    ast.parse(extracted)

if __name__ == "__main__":
    test_sibling_blocks()
    print("test_sibling_blocks PASSED")
    test_nested_code_fences_in_python_block()
    print("test_nested_code_fences_in_python_block PASSED")
    test_prose_with_nested_code_fences()
    print("test_prose_with_nested_code_fences PASSED")
