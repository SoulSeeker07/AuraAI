#!/usr/bin/env python
"""
AuraAI Architecture Diagram Generator (CLI Wrapper)
==================================================

Scans Python files in the repository using Python's built-in AST module,
groups modules into architecture layers, detects dependencies, and generates
architecture visualization files (DOT, Mermaid MMD, JSON, and text reports).

Usage:
    python generate_architecture.py --root . --output docs/architecture
    python generate_architecture.py --root . --layers-only
    python generate_architecture.py --root . --visuals
"""

import sys
from pathlib import Path

# Add tools/architecture-generator to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOL_DIR = PROJECT_ROOT / "tools" / "architecture-generator"
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

from generate_architecture import main

if __name__ == "__main__":
    sys.exit(main())
