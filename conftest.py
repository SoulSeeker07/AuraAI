"""
Global pytest configuration for AuraAI test suite.
Ensures both workspace root and src/ are always on sys.path during test runs.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"

for p in [str(_SRC), str(_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)
