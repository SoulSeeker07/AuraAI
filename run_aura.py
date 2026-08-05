"""
AuraAI Launcher

Simple launcher to switch between CLI and GUI modes.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from main import main


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AuraAI - Multi-Agent AI Assistant Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage:
  python run_aura.py              # Run CLI (default)
  python run_aura.py --cli        # Run CLI
  python run_aura.py --gui        # Run GUI
  python run_aura.py --help       # Show help
        """,
    )

    parser.add_argument("--cli", action="store_true", help="Run in CLI mode (default)")

    parser.add_argument("--gui", action="store_true", help="Run in GUI mode")

    parser.add_argument("--workspace", type=str, help="Override workspace path")

    args = parser.parse_args()

    if args.gui:
        print("Launching AuraAI in GUI mode...")
    elif args.cli:
        print("Launching AuraAI in CLI mode...")
    else:
        print("Launching AuraAI in CLI mode (default)...")

    # Run AuraAI
    app = main()


if __name__ == "__main__":
    main()
