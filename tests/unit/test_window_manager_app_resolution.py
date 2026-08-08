"""
Unit test for WindowManager application executable resolution.
"""

import os

from desktop.native.managers.window_manager import WindowManager


def test_resolve_app_executable_chrome():
    wm = WindowManager()
    resolved = wm._resolve_app_executable("chrome")
    assert resolved is not None
    # On Windows systems with Chrome installed, it should return an absolute path ending in chrome.exe
    if os.name == "nt":
        assert resolved.lower().endswith("chrome.exe") or resolved == "chrome.exe"
        if os.path.exists(resolved):
            assert os.path.isabs(resolved)


def test_resolve_app_executable_aliases():
    wm = WindowManager()
    resolved_gchrome = wm._resolve_app_executable("google chrome")
    resolved_notepad = wm._resolve_app_executable("notepad")
    resolved_calc = wm._resolve_app_executable("calc")

    assert resolved_gchrome is not None
    assert resolved_notepad.lower().endswith("notepad.exe")
    assert resolved_calc.lower().endswith("calc.exe")
