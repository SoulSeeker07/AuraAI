"""
One-Time Administrator Setup Utility for Aura AI Sandbox Account (Path B)
Location: scripts/setup_sandbox_account.py

Run this script once as Administrator to provision 'AuraSandboxUser', configure
kernel-enforced NTFS DACLs, and set Windows Outbound Firewall egress block rules.

Usage:
    python scripts/setup_sandbox_account.py --setup --workspace "D:\\Sreekanta\\VS Code Project\\Desktop AI\\AuraAI"
"""

import argparse
import ctypes
import os
import secrets
import sys
from pathlib import Path

# Add project root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.desktop.native.sandbox.account_provisioner import AccountProvisioner, SANDBOX_USER_NAME


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Aura AI Sandbox Account Provisioner")
    parser.add_argument("--setup", action="store_true", help="Provision AuraSandboxUser, set DACLs, and configure Firewall")
    parser.add_argument("--workspace", type=str, default=str(REPO_ROOT), help="Active workspace path")
    parser.add_argument("--password", type=str, default=None, help="Custom password (optional)")

    args = parser.parse_args()

    print("================================================================")
    print(" [*] Aura AI Sandbox Account & NTFS DACL Provisioner")
    print("================================================================")

    if not is_admin():
        print("\n[!] ERROR: This script must be run from an elevated Administrator PowerShell/Terminal prompt.")
        print("    Please right-click PowerShell -> 'Run as Administrator' and re-run this command.\n")
        sys.exit(1)

    provisioner = AccountProvisioner(SANDBOX_USER_NAME)
    password = args.password or os.environ.get("AURA_SANDBOX_PASSWORD", "AuraSandboxPass123!")

    if not provisioner.account_exists():
        print(f"\n[*] Creating local standard user '{SANDBOX_USER_NAME}'...")
        ok, msg = provisioner.create_account(password)
        if not ok:
            print(f"[!] Failed to create user: {msg}")
            sys.exit(1)
        print(f"[+] User '{SANDBOX_USER_NAME}' created successfully.")
    else:
        print(f"\n[*] User '{SANDBOX_USER_NAME}' already exists. Updating password...")
        ok, msg = provisioner.set_account_password(password)
        if not ok:
            print(f"[!] Warning: Could not update password: {msg}")
        else:
            print(f"[+] Password for '{SANDBOX_USER_NAME}' updated successfully.")

    print(f"\n[*] Applying kernel-enforced NTFS DACLs for workspace: {args.workspace}")
    ok, msg = provisioner.configure_ntfs_dacls(workspace_root=args.workspace)
    if not ok:
        print(f"[!] Failed to configure DACLs: {msg}")
        sys.exit(1)

    print(f"[+] NTFS DACL boundaries configured successfully:")
    print(f"    - DENY (Full Control): %USERPROFILE% (~/.ssh, ~/.aws, browser vaults)")
    print(f"    - DENY (Full Control): Workspace secrets (.env, config/secrets.json)")
    print(f"    - GRANT (Modify):      {args.workspace}")

    print(f"\n[*] Configuring Windows Advanced Firewall Outbound Block Rule for '{SANDBOX_USER_NAME}'...")
    ok_fw, msg_fw = provisioner.configure_firewall_rules()
    if not ok_fw:
        print(f"[!] Warning: Could not configure Firewall: {msg_fw}")
    else:
        print(f"[+] Windows Outbound Firewall block rule 'BlockAuraSandboxEgress' active.")

    print("\n================================================================")
    print(" [+] One-Time Sandbox Provisioning Complete!")
    print("================================================================\n")


if __name__ == "__main__":
    main()
