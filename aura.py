"""
AuraAI Umbrella CLI Launcher & Diagnostic System
=================================================
Usage:
  python aura.py --doctor     Run system diagnostic & health checks
  python aura.py --verify     Run CI quality & verification pipeline
  python aura.py --cli        Run interactive CLI assistant
  python aura.py --gui        Run GUI mode
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))


def main():
    parser = argparse.ArgumentParser(
        description="AuraAI - Desktop AI Platform & Engineering Tooling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python aura.py --doctor     # Run Aura Doctor system diagnostics
  python aura.py --verify     # Run complete CI quality verification pipeline
  python aura.py --cli        # Run interactive CLI assistant (default)
  python aura.py --gui        # Launch GUI application
        """,
    )

    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run comprehensive system diagnostics and health checks",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Run interactive system state inspector dashboard",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run CI pipeline (ruff, black, isort, mypy, pytest, architecture tests)",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in CLI mode (default)",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Run in GUI mode",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        help="Override workspace path",
    )

    args = parser.parse_args()

    if args.doctor:
        from engineering.doctor import AuraDoctor

        doctor = AuraDoctor(project_root=PROJECT_ROOT)
        doctor.diagnose()
        sys.exit(0)
    elif args.inspect:
        from engineering.inspector import AuraInspector

        inspector = AuraInspector(project_root=PROJECT_ROOT)
        inspector.inspect()
        sys.exit(0)
    elif args.verify:
        from engineering.doctor import AuraVerifier

        verifier = AuraVerifier(project_root=PROJECT_ROOT)
        success = verifier.run_verify()
        sys.exit(0 if success else 1)
    else:
        from main import main as main_entry

        main_entry()


if __name__ == "__main__":
    main()
