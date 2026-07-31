import sys
import argparse
import asyncio
from pathlib import Path

# Import logger from core module
from core import logger


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))  # project root first to find core/
sys.path.insert(1, str(SRC_DIR))  # src second to find logger

from core.aura_core import AuraCore
from clients.cli_client import CLIClient
from clients.gui_client import GUIClient


def create_aura_core(config: dict = None) -> AuraCore:
    """
    Create and initialize Aura Core.

    Args:
        config: Configuration dictionary

    Returns:
        AuraCore instance
    """
    # Ensure data_path is set for conversation history persistence
    if config is None:
        config = {}

    if 'data_path' not in config:
        from pathlib import Path
        config['data_path'] = str(Path(__file__).resolve().parent / "Data" / "ChatLog.json")

    return AuraCore(config=config)


def main_cli():
    """Run AuraAI in CLI mode."""
    print("Starting AuraAI in CLI mode...")
    print("-" * 60)

    # Create Aura Core
    aura_core = create_aura_core()

    # Create CLI client
    cli_client = CLIClient(aura_core)

    # Run CLI
    try:
        asyncio.run(cli_client.run())
    except KeyboardInterrupt:
        print("\n\n✓ Shutting down...")
        aura_core.shutdown()
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        logger.error(f"CLI error: {e}", exc_info=True)
        aura_core.shutdown()
        sys.exit(1)


def main_gui():
    """Run AuraAI in GUI mode."""
    print("Starting AuraAI in GUI mode...")
    print("-" * 60)

    # Create Aura Core
    aura_core = create_aura_core()

    # Create GUI client
    gui_client = GUIClient(aura_core)

    # Note: In real implementation, this would launch QML interface
    # For now, we'll create the GUI client and show its status
    print("\n✓ Aura Core initialized")
    print("✓ GUI Client created")
    print("\nGUI mode is not fully implemented yet.")
    print("Use CLI mode for now: python main.py --cli")
    print("\nTo enable GUI:")
    print("1. Make sure QML files are in frontend/")
    print("2. Create a GUI launcher that uses GUIClient")
    print("3. Set up Qt/QML environment")

    # Return GUI client for use with QML
    return gui_client


def main():
    """Main entry point for AuraAI."""
    parser = argparse.ArgumentParser(
        description='AuraAI - Multi-Agent AI Assistant',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py              # Run CLI mode (default)
  python main.py --cli        # Run CLI mode
  python main.py --gui        # Run GUI mode
  python main.py --help       # Show help

Modes:
  CLI    - Interactive command-line interface
  GUI    - Graphical user interface (QML)
        """
    )

    parser.add_argument(
        '--cli',
        action='store_true',
        help='Run in CLI mode (default)'
    )

    parser.add_argument(
        '--gui',
        action='store_true',
        help='Run in GUI mode'
    )

    parser.add_argument(
        '--workspace',
        type=str,
        help='Override workspace path'
    )

    args = parser.parse_args()

    # Determine mode
    if args.gui:
        # GUI mode
        gui_client = main_gui()
        # In real implementation, this would launch QML
        # For now, return the GUI client for reference
        return gui_client
    else:
        # CLI mode (default)
        main_cli()
        return None


if __name__ == "__main__":
    app = main()
