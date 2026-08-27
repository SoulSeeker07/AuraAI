"""
AuraAI Windows Auto-Start Manager
=================================
Manages silent background auto-start of the Aura Voice Notch on Windows boot/logon.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_STARTUP_DIR = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))
_VBS_FILE = _STARTUP_DIR / "AuraVoiceNotch.vbs"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PYTHONW = _PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe"
_NOTCH_SCRIPT = _PROJECT_ROOT / "run_voice_notch.py"


def is_autostart_enabled() -> bool:
    """Check if the autostart VBS launcher exists in Windows Startup folder."""
    return _VBS_FILE.exists()


def enable_autostart() -> bool:
    """Create silent VBS launcher in Windows Startup directory."""
    try:
        _STARTUP_DIR.mkdir(parents=True, exist_ok=True)
        py_exe = str(_PYTHONW).replace("/", "\\")
        notch_py = str(_NOTCH_SCRIPT).replace("/", "\\")
        root_dir = str(_PROJECT_ROOT).replace("/", "\\")

        vbs_content = (
            'Set WshShell = CreateObject("WScript.Shell")\n'
            f'WshShell.CurrentDirectory = "{root_dir}"\n'
            f'WshShell.Run """{py_exe}"" ""{notch_py}""", 0, False\n'
        )
        _VBS_FILE.write_text(vbs_content, encoding="ascii")
        return True
    except Exception:
        return False


def disable_autostart() -> bool:
    """Remove VBS launcher from Windows Startup directory."""
    try:
        if _VBS_FILE.exists():
            _VBS_FILE.unlink()
        return True
    except Exception:
        return False
