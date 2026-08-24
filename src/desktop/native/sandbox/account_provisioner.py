"""
Account Provisioner & NTFS DACL Manager
Location: src/desktop/native/sandbox/account_provisioner.py

Manages the local standard service account (AuraSandboxUser) and configures
OS-enforced NTFS DACLs (DENY on sensitive host paths, GRANT on workspace).
"""

import ctypes
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SANDBOX_USER_NAME = "AuraSandboxUser"


class AccountProvisioner:
    """
    Handles creation of the unprivileged sandbox account and NTFS DACL configuration.
    """

    def __init__(self, username: str = SANDBOX_USER_NAME):
        self.username = username

    @staticmethod
    def is_admin() -> bool:
        """Check if current process has administrative elevation."""
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def account_exists(self) -> bool:
        """Check if the sandbox user account exists on the local machine."""
        try:
            res = subprocess.run(
                ["net", "user", self.username],
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            return res.returncode == 0
        except Exception:
            return False

    def set_account_password(self, password: str) -> tuple[bool, str]:
        """Update password for existing sandbox account (Requires Admin)."""
        if not self.is_admin():
            return False, "Administrator privileges required."
        try:
            cmd = ["net", "user", self.username, password]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10.0)
            if res.returncode != 0:
                return False, f"Failed to set password: {res.stderr}"
            return True, "Password updated successfully."
        except Exception as exc:
            return False, f"Password update error: {exc}"

    def create_account(self, password: str) -> tuple[bool, str]:
        """
        Create local standard user account (Requires Admin Privileges).
        """
        if not self.is_admin():
            return False, "Administrator privileges are required to create local user accounts."

        try:
            # 1. Create local user
            cmd = [
                "net", "user", self.username, password,
                "/add",
                "/comment:Aura AI Isolated Sandbox Execution Account",
                "/passwordchg:no",
                "/expires:never",
                "/active:yes",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10.0)
            if res.returncode != 0:
                return False, f"Failed to create user: {res.stderr or res.stdout}"

            logger.info(f"Successfully provisioned local user '{self.username}'.")
            return True, f"User '{self.username}' provisioned successfully."
        except Exception as exc:
            return False, f"Account creation exception: {exc}"


    def configure_ntfs_dacls(
        self,
        workspace_root: str | Path,
        extra_deny_paths: list[str | Path] | None = None,
    ) -> tuple[bool, str]:
        """
        Configure kernel-enforced NTFS DACLs using icacls.exe (Requires Admin Privileges):
        - DENY on %USERPROFILE%, ~/.ssh, ~/.aws, and project secret files.
        - GRANT (Modify) on the active workspace root.
        """
        if not self.is_admin():
            return False, "Administrator privileges are required to modify NTFS DACLs."

        ws_path = Path(workspace_root).resolve()
        user_profile = Path(os.environ.get("USERPROFILE", "C:\\Users\\default")).resolve()

        deny_targets: list[Path] = [
            user_profile / ".ssh",
            user_profile / ".aws",
            user_profile / ".gnupg",
            user_profile / "AppData" / "Local" / "Google" / "Chrome" / "User Data",
            ws_path / ".env",
            ws_path / "config" / "secrets.json",
        ]

        if extra_deny_paths:
            for p in extra_deny_paths:
                deny_targets.append(Path(p).resolve())

        try:
            # 1. Apply DENY rules on specific sensitive directories & files
            for target in deny_targets:
                if target.exists():
                    cmd = ["icacls", str(target), "/deny", f"{self.username}:(OI)(CI)(F)", "/q", "/c"]
                    subprocess.run(cmd, capture_output=True, text=True, timeout=30.0)

            # 2. Apply GRANT (Read & Execute) on active workspace directory (with 60s timeout for large .venv trees)
            if ws_path.exists():
                cmd = ["icacls", str(ws_path), "/grant:r", f"{self.username}:(OI)(CI)(RX)", "/q", "/c"]
                subprocess.run(cmd, capture_output=True, text=True, timeout=60.0)

            return True, "NTFS DACL boundaries configured successfully."
        except Exception as exc:
            return False, f"DACL configuration error: {exc}"

    def configure_firewall_rules(self) -> tuple[bool, str]:
        """
        Configure Windows Advanced Firewall outbound block rule scoped to sandbox user SID (Requires Admin).
        """
        if not self.is_admin():
            return False, "Administrator privileges required to configure firewall rules."

        ps_cmd = (
            f"$account = New-Object System.Security.Principal.NTAccount('{self.username}'); "
            f"$sid = $account.Translate([System.Security.Principal.SecurityIdentifier]).Value; "
            f"Remove-NetFirewallRule -DisplayName 'BlockAuraSandboxEgress' -ErrorAction SilentlyContinue; "
            f"New-NetFirewallRule -DisplayName 'BlockAuraSandboxEgress' -Direction Outbound "
            f"-Action Block -Owner $sid -Profile Any -Description 'Block outbound network traffic for Aura AI sandbox user';"
        )

        try:
            res = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=15.0,
            )
            if res.returncode != 0:
                return False, f"Firewall rule creation failed: {res.stderr or res.stdout}"
            return True, "Outbound network egress rule configured successfully."
        except Exception as exc:
            return False, f"Firewall configuration error: {exc}"

    def grant_staging_access(self, staging_dir: str | Path) -> bool:
        """
        Grant AuraSandboxUser un-elevated Modify permissions on a user-owned ephemeral staging directory.
        """
        target = Path(staging_dir).resolve()
        if not target.exists():
            return False
        try:
            cmd = ["icacls", str(target), "/grant", f"{self.username}:(OI)(CI)(M)", "/q"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10.0)
            return res.returncode == 0
        except Exception as exc:
            logger.warning(f"Failed to grant staging access to {self.username}: {exc}")
            return False


def grant_staging_access(staging_dir: str | Path, username: str = SANDBOX_USER_NAME) -> bool:
    """Convenience helper to grant ephemeral staging permissions."""
    provisioner = AccountProvisioner(username=username)
    return provisioner.grant_staging_access(staging_dir)





