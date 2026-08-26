"""
Unit Tests for AST Static Checker
Location: tests/test_codeact/test_static_checker.py
"""

import pytest
from src.codeact.static_checker import check_imports


def test_allowed_standard_library_imports():
    code = """
import math
import datetime
import json
from pathlib import Path
from collections import defaultdict

x = math.sqrt(16)
now = datetime.datetime.now()
"""
    result = check_imports(code)
    assert result.passed is True
    assert len(result.blocked_imports) == 0
    assert len(result.disallowed_imports) == 0


def test_allowed_explicit_libraries():
    code = """
from pptx import Presentation
from docx import Document
import openpyxl

prs = Presentation()
"""
    result = check_imports(code, allowed_libraries=["python-pptx", "python-docx", "openpyxl"])
    assert result.passed is True


def test_blocked_network_imports():
    code = """
import socket
import requests
import urllib.request
"""
    result = check_imports(code)
    assert result.passed is False
    assert "socket" in result.blocked_imports
    assert "requests" in result.blocked_imports
    assert "urllib.request" in result.blocked_imports


def test_blocked_subprocess_and_ctypes():
    code = """
import subprocess
import ctypes
subprocess.run(["cmd.exe", "/c", "dir"])
"""
    result = check_imports(code)
    assert result.passed is False
    assert "subprocess" in result.blocked_imports
    assert "ctypes" in result.blocked_imports


def test_blocked_eval_and_exec_calls():
    code = """
cmd = "print(1)"
eval(cmd)
"""
    result = check_imports(code)
    assert result.passed is False
    assert any("eval" in v for v in result.violations)


def test_blocked_os_system_call():
    code = """
import os
os.system("calc.exe")
"""
    result = check_imports(code)
    assert result.passed is False
    assert any("os.system" in v for v in result.violations)


def test_disallowed_unlisted_library():
    code = """
import pandas as pd
import numpy as np
"""
    # Without pandas and numpy in allowed_libraries
    result = check_imports(code, allowed_libraries=["python-pptx"])
    assert result.passed is False
    assert "pandas" in result.disallowed_imports or "numpy" in result.disallowed_imports


def test_syntax_error_handling():
    code = "def broken_syntax(:"
    result = check_imports(code)
    assert result.passed is False
    assert "SyntaxError" in result.violations[0]


def test_adversarial_import_from_os_system_blocked():
    """Adversarial bypass: from os import system -> direct call."""
    code = """
from os import system
system("calc.exe")
"""
    result = check_imports(code)
    assert result.passed is False
    assert any("os.system" in v or "system" in v for v in result.violations)


def test_adversarial_import_from_aliased_symbol_blocked():
    """Adversarial bypass: from os import system as s -> s('cmd')."""
    code = """
from os import system as s
s("calc.exe")
"""
    result = check_imports(code)
    assert result.passed is False
    assert any("os.system" in v or "s" in v for v in result.violations)


def test_adversarial_import_from_shutil_rmtree_blocked():
    """Adversarial bypass: from shutil import rmtree -> rmtree('.')."""
    code = """
from shutil import rmtree
rmtree("./")
"""
    result = check_imports(code)
    assert result.passed is False
    assert any("shutil.rmtree" in v or "rmtree" in v for v in result.violations)


def test_adversarial_getattr_dynamic_call_blocked():
    """Adversarial bypass: getattr(os, 'system')('calc.exe')."""
    code = """
import os
getattr(os, "system")("calc.exe")
"""
    result = check_imports(code)
    assert result.passed is False
    assert any("getattr" in v for v in result.violations)


def test_adversarial_two_level_getattr_binding_blocked():
    """Two-level indirection: f = getattr; f(os, 'system')('calc.exe')."""
    code = """
import os
f = getattr
f(os, "system")("calc.exe")
"""
    result = check_imports(code)
    assert result.passed is False
    assert any("getattr" in v for v in result.violations)


def test_adversarial_attribute_binding_blocked():
    """Two-level indirection: s = os.system; s('calc.exe')."""
    code = """
import os
s = os.system
s("calc.exe")
"""
    result = check_imports(code)
    assert result.passed is False
    assert any("system" in v for v in result.violations)


def test_adversarial_eval_binding_blocked():
    """Two-level indirection: ev = eval; ev('print(1)')."""
    code = """
ev = eval
ev("print(1)")
"""
    result = check_imports(code)
    assert result.passed is False
    assert any("eval" in v for v in result.violations)


def test_adversarial_pathlib_direct_unlink_blocked():
    """Adversarial bypass: Path('target.txt').unlink()."""
    code = """
from pathlib import Path
Path("target.txt").unlink()
"""
    result = check_imports(code)
    assert result.passed is False
    assert any("unlink" in v for v in result.violations)


def test_adversarial_pathlib_variable_unlink_blocked():
    """Adversarial bypass: p = Path('target.txt'); p.unlink()."""
    code = """
from pathlib import Path
p = Path("target.txt")
p.unlink()
"""
    result = check_imports(code)
    assert result.passed is False
    assert any("unlink" in v for v in result.violations)


def test_legitimate_list_remove_permitted():
    """Legitimate code: my_list.remove('item') should NOT be blocked."""
    code = """
items = ["apple", "banana", "cherry"]
items.remove("banana")
"""
    result = check_imports(code)
    assert result.passed is True
    assert len(result.violations) == 0


def test_adversarial_aliased_os_remove_blocked():
    """Adversarial bypass: import os as o; o.remove('file.txt')."""
    code = """
import os as o
o.remove("file.txt")
"""
    result = check_imports(code)
    assert result.passed is False
    assert any("remove" in v for v in result.violations)


def test_extract_code_block_sibling_languages():
    """Verify that extract_code_block extracts the python block and ignores sibling bash blocks."""
    from src.codeact.drafters import extract_code_block
    text = (
        "Setup instructions:\n"
        "```bash\n"
        "pip install markdown\n"
        "```\n\n"
        "Python script:\n"
        "```python\n"
        "import json\n"
        "print('hello from python')\n"
        "```\n"
    )
    extracted = extract_code_block(text)
    assert "pip install" not in extracted
    assert "import json" in extracted
    assert "print('hello from python')" in extracted
    assert check_imports(extracted).passed is True


def test_extract_code_block_nested_fences_in_python_script():
    """Verify that extract_code_block does not prematurely truncate scripts that output markdown codeblocks."""
    from src.codeact.drafters import extract_code_block
    text = (
        "```python\n"
        "import json\n"
        "from pathlib import Path\n"
        "payload = {'title': 'Guide', 'code': 'def greet():\\n    return \"hi\"'}\n"
        "lines = [\n"
        "    f'# {payload[\"title\"]}',\n"
        "    '```python',\n"
        "    payload['code'],\n"
        "    '```',\n"
        "    'Finished.'\n"
        "]\n"
        "Path('out.md').write_text('\\n'.join(lines), encoding='utf-8')\n"
        "```"
    )
    extracted = extract_code_block(text)
    assert extracted.startswith("import json")
    assert "Path('out.md')" in extracted
    assert check_imports(extracted).passed is True


def test_extract_code_block_prose_envelope():
    """Verify conversational text before and after code fences is stripped cleanly."""
    from src.codeact.drafters import extract_code_block
    text = (
        "Here is the complete script to generate the document:\n\n"
        "```python\n"
        "import json\n"
        "print('clean execution')\n"
        "```\n\n"
        "I hope this helps! Let me know if you want modifications."
    )
    extracted = extract_code_block(text)
    assert "Here is the complete" not in extracted
    assert "I hope this helps" not in extracted
    assert extracted.strip() == "import json\nprint('clean execution')"


def test_extract_code_block_sibling_with_trailing_prose():
    """Verify sibling bash + python blocks followed by trailing prose are extracted cleanly without leaking prose or bash code."""
    from src.codeact.drafters import extract_code_block
    text = (
        "Step 1: Install prerequisites:\n"
        "```bash\n"
        "pip install requests\n"
        "```\n\n"
        "Step 2: Run the script:\n"
        "```python\n"
        "import json\n"
        "from pathlib import Path\n"
        "Path('result.txt').write_text('done', encoding='utf-8')\n"
        "```\n\n"
        "Make sure to check the output file afterwards!"
    )
    extracted = extract_code_block(text)
    assert "pip install" not in extracted
    assert "Step 1" not in extracted
    assert "Step 2" not in extracted
    assert "Make sure to check" not in extracted
    assert extracted.startswith("import json")
    assert extracted.endswith("Path('result.txt').write_text('done', encoding='utf-8')")
    assert check_imports(extracted).passed is True


