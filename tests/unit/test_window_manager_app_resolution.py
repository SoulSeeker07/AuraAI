"""
Unit test for WindowManager application executable resolution.
"""

import os

from desktop.native.managers.window_manager import WindowManager


def test_resolve_app_executable_chrome():
    wm = WindowManager()
    resolved = wm._resolve_app_executable("chrome")
    assert resolved is not None
    res_path = resolved[1] if isinstance(resolved, tuple) else resolved
    # On Windows systems with Chrome installed, it should return an absolute path ending in chrome.exe
    if os.name == "nt":
        assert res_path.lower().endswith("chrome.exe") or res_path == "chrome.exe"
        if os.path.exists(res_path):
            assert os.path.isabs(res_path)


def test_resolve_app_executable_aliases():
    wm = WindowManager()
    resolved_gchrome = wm._resolve_app_executable("google chrome")
    resolved_notepad = wm._resolve_app_executable("notepad")
    resolved_calc = wm._resolve_app_executable("calc")

    assert resolved_gchrome is not None
    p_notepad = resolved_notepad[1] if isinstance(resolved_notepad, tuple) else resolved_notepad
    p_calc = resolved_calc[1] if isinstance(resolved_calc, tuple) else resolved_calc
    assert p_notepad.lower().endswith("notepad.exe")
    assert p_calc.lower().endswith("calc.exe")
