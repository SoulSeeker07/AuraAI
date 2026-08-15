import argparse
import asyncio
import io
import os
import sys
from pathlib import Path

# Silence harmless third-party library warnings in CLI
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Configure sys.path FIRST before any core imports
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

while "" in sys.path:
    sys.path.remove("")
while str(PROJECT_ROOT) in sys.path: 
    sys.path.remove(str(PROJECT_ROOT))
while str(SRC_DIR) in sys.path:
    sys.path.remove(str(SRC_DIR))

sys.path.insert(0, str(SRC_DIR))
sys.path.insert(1, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(2, str(PROJECT_ROOT / "scripts"))


# Configure stdout and stderr to UTF-8 before any logging or core imports
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from clients.cli_client import CLIClient
from clients.gui_client import GUIClient

# Import logger from core module
from core import logger
from core.aura_core import AuraCore
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

        # Try to load configuration from config.json (only if not already set)
        try:
            import json
            from pathlib import Path

            config_path = Path(__file__).resolve().parent / "config" / "config.json"
            if config_path.exists() and "voice_enabled" not in config:
                with open(config_path, 'r') as f:
                    file_config = json.load(f)
                # Only use file config if voice_enabled not in runtime config
                if "voice_enabled" in file_config:
                    config["voice_enabled"] = file_config["voice_enabled"]
                logger.info(f"Loaded voice_enabled={config['voice_enabled']} from {config_path}")
        except Exception as e:
            logger.debug(f"Could not load configuration: {e}")

        if "data_path" not in config:
            config["data_path"] = str(
                Path(__file__).resolve().parent / "Data" / "ChatLog.json"
            )

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

    monitor_thread = threading.Thread(target=monitor.monitor, daemon=True)
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
    """Run AuraAI in PySide6 GUI mode."""
    print("Starting AuraAI in GUI mode...")
    print("-" * 60)

    # Get Aura Core (singleton pattern)
    aura_core = get_aura_core()

    # Create GUI client
    gui_client = GUIClient(aura_core)

    print("\n✓ Aura Core initialized")
    print("✓ GUI Client created")
    print("✓ Launching AuraAI PySide6 Control Center & Spotlight HUD...")

    from src.gui.app import AuraGUI

    gui = AuraGUI()
    return gui.run()


def main():
    """Main entry point for AuraAI."""
    parser = argparse.ArgumentParser(
        description="AuraAI - Multi-Agent AI Assistant",
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
        """,
    )

    parser.add_argument(
        "--doctor", action="store_true", help="Run Aura Doctor diagnostics"
    )

    parser.add_argument(
        "--inspect", action="store_true", help="Run Aura Inspector debugging dashboard"
    )

    parser.add_argument(
        "--verify", action="store_true", help="Run CI quality pipeline verification"
    )

    parser.add_argument("--cli", action="store_true", help="Run in CLI mode (default)")

    parser.add_argument("--gui", action="store_true", help="Run in GUI mode")

    parser.add_argument("--workspace", type=str, help="Override workspace path")

    args = parser.parse_args()

    if args.doctor:
        from src.engineering.doctor import AuraDoctor

        doctor = AuraDoctor(project_root=PROJECT_ROOT)
        doctor.diagnose()
        sys.exit(0)
    elif args.inspect:
        from src.engineering.inspector import AuraInspector

        inspector = AuraInspector(project_root=PROJECT_ROOT)
        inspector.inspect()
        sys.exit(0)
    elif args.verify:
        from src.engineering.doctor import AuraVerifier

        verifier = AuraVerifier(project_root=PROJECT_ROOT)
        success = verifier.run_verify()
        sys.exit(0 if success else 1)
    elif args.gui:
        # GUI mode
        gui_client = main_gui()
        return gui_client
    else:
        # CLI mode (default)
        asyncio.run(main_cli())
        return None


if __name__ == "__main__":
    app = main()
