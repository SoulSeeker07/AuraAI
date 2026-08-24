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
