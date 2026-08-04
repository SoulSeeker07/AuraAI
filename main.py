import sys
import argparse
import asyncio
import io
from pathlib import Path

# Configure stdout to UTF-8 BEFORE any other imports
# This fixes Unicode encoding issues on Windows (cp1252 vs UTF-8)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass  # If reconfiguration fails, keep the default

# Import logger from core module
from core import logger


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))  # project root first to find core/
sys.path.insert(1, str(SRC_DIR))  # src second to find logger
sys.path.insert(2, str(PROJECT_ROOT / "scripts"))  # scripts third to find utilities

from core.aura_core import AuraCore
from clients.cli_client import CLIClient
from clients.gui_client import GUIClient
from scripts.aura_monitor import AuraMonitor


# Singleton instance of AuraCore
_aura_core_instance = None

def get_aura_core(config: dict = None) -> AuraCore:
    """
    Get or create Aura Core instance (Singleton pattern).

    Args:
        config: Configuration dictionary

    Returns:
        AuraCore instance (singleton)
    """
    global _aura_core_instance

    if _aura_core_instance is None:
        # Ensure data_path is set for conversation history persistence
        if config is None:
            config = {}

        if 'data_path' not in config:
            from pathlib import Path
            config['data_path'] = str(Path(__file__).resolve().parent / "Data" / "ChatLog.json")

        _aura_core_instance = AuraCore(config=config)

    return _aura_core_instance


async def main_cli():
    """Run AuraAI in CLI mode."""
    print("Starting AuraAI in CLI mode...")
    print("-" * 60)

    # Get Aura Core (singleton pattern)
    aura_core = get_aura_core()

    # Create Aura Monitor
    monitor = AuraMonitor(aura_core, refresh_interval=2)

    # Create CLI client
    cli_client = CLIClient(aura_core)

    # Start monitor in a separate thread
    import threading
    monitor_thread = threading.Thread(
        target=monitor.monitor,
        daemon=True
    )
    monitor_thread.start()

    # Run CLI (now properly awaited)
    try:
        await cli_client.run()
    except KeyboardInterrupt:
        print("\n\n✓ Shutting down...")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        logger.error(f"CLI error: {e}", exc_info=True)
    finally:
        # Stop monitor
        monitor.running = False
        monitor_thread.join(timeout=2)
        # Note: aura_core.shutdown() is called by cli_client.py
        # We don't call it here to avoid double shutdown
        sys.exit(0)


def main_gui():
    """Run AuraAI in GUI mode."""
    print("Starting AuraAI in GUI mode...")
    print("-" * 60)

    # Get Aura Core (singleton pattern)
    aura_core = get_aura_core()

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
        asyncio.run(main_cli())
        return None


if __name__ == "__main__":
    app = main()
