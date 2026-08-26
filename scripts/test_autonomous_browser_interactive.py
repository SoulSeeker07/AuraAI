"""
Interactive Test Suite for Aura Autonomous Browser Engine
Location: scripts/test_autonomous_browser_interactive.py

Run via:
    .\.venv\Scripts\python.exe scripts/test_autonomous_browser_interactive.py
"""

import sys
import os
import time
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(1, str(PROJECT_ROOT / "src"))

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


def run_aura_cli(query: str) -> None:
    print(f"\n{BOLD}{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{YELLOW}▶ Executing:{RESET} {BOLD}aura {query}{RESET}")
    print(f"{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}\n")

    cmd = [
        str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"),
        "main.py",
        "--cli",
        f"aura {query}",
    ]
    subprocess.run(cmd, cwd=str(PROJECT_ROOT))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(f"\n{BOLD}{MAGENTA}╔══════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{MAGENTA}║      🌐 AURA AUTONOMOUS BROWSER ENGINE TEST SUITE            ║{RESET}")
    print(f"{BOLD}{MAGENTA}╚══════════════════════════════════════════════════════════════╝{RESET}\n")

    test_scenarios = [
        (
            "1. DOM Fast-Path (Structured Wikipedia Search)",
            "browse to wikipedia and search artificial intelligence",
            "Tests URL launching and search query typing via the sandboxed DOM path."
        ),
        (
            "2. Vision-Native On-Screen Path (Grounded OCR & Native Click)",
            "click on screen search box and type AI automation",
            "Forces VISION_NATIVE mode, coordinate grounding (>=0.75 conf), and Win32 input."
        ),
        (
            "3. High-Risk Safety Interceptor (Checkout / Payment Block)",
            "browse to store and checkout cart now",
            "Verifies fail-closed safety block and persistent authorization ticket generation."
        ),
        (
            "4. Web Video Search & Navigation",
            "browse to youtube and search lo-fi beats",
            "Tests media search and browser navigation."
        ),
    ]

    while True:
        print(f"\n{BOLD}Select an autonomous browser test to run:{RESET}")
        for i, (title, _, desc) in enumerate(test_scenarios, 1):
            print(f"  {GREEN}[{i}]{RESET} {BOLD}{title}{RESET}\n      {YELLOW}→ {desc}{RESET}")
        print(f"  {GREEN}[5]{RESET} {BOLD}Run High-Risk Block + Live Confirmation Flow (End-to-End){RESET}")
        print(f"  {GREEN}[6]{RESET} {BOLD}Custom Command (Type your own browser prompt){RESET}")
        print(f"  {RED}[0] Exit{RESET}\n")

        choice = input(f"{BOLD}Enter choice [0-6]: {RESET}").strip()

        if choice == "0":
            print(f"\n{GREEN}👋 Done testing Autonomous Browser Engine!{RESET}\n")
            break
        elif choice in ("1", "2", "3", "4"):
            idx = int(choice) - 1
            _, query, _ = test_scenarios[idx]
            run_aura_cli(query)
        elif choice == "5":
            print(f"\n{BOLD}{YELLOW}--- Step 1: Triggering High-Risk Block ---{RESET}")
            run_aura_cli("browse to store and checkout cart now")
            ticket = input(f"\n{BOLD}{CYAN}Enter the issued ticket ID (e.g. AUTH-XXXXXX): {RESET}").strip()
            if ticket:
                print(f"\n{BOLD}{YELLOW}--- Step 2: Confirming Authorization Ticket ---{RESET}")
                run_aura_cli(f"confirm {ticket}")
        elif choice == "6":
            custom = input(f"{BOLD}Enter custom browser goal for Aura: {RESET}").strip()
            if custom:
                run_aura_cli(custom)
        else:
            print(f"{RED}Invalid option. Please enter 0-6.{RESET}")


if __name__ == "__main__":
    main()
