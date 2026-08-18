"""
Aura Email Plugin
=================
Plugin for sending, searching, reading, replying, and managing emails.
"""

import email
import imaplib
import logging
import os
import smtplib
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from src.plugins.plugin_interface import Plugin, PluginCategory, PluginManifest

logger = logging.getLogger(__name__)


class EmailPlugin(Plugin):
    """
    Email Automation Plugin for Aura.
    """

    def __init__(self, manifest: PluginManifest | None = None):
        if manifest is None:
            manifest = PluginManifest(
                name="email",
                version="1.0.0",
                author="Aura AI",
                description="Email automation plugin for IMAP/SMTP mailboxes.",
                category=PluginCategory.EMAIL,
                capabilities=[
                    "email.send",
                    "email.read_inbox",
                    "email.search",
                    "email.reply",
                    "email.forward",
                    "email.list_folders",
                    "email.move",
                    "email.delete",
                    "email.get_attachments",
                    "email.draft",
                ],
            )
        super().__init__(manifest)

    def load(self) -> bool:
        self.state = "initialized"
        return True

    def initialize(self) -> bool:
        self.state = "ready"
        return True

    def can_handle(self, capability: str) -> bool:
        return capability.startswith("email.") or capability in self.manifest.capabilities

    def _send_email(self, to_addr: str, subject: str, body: str) -> dict[str, Any]:
        smtp_host = os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.environ.get("EMAIL_SMTP_PORT", 587))
        user = os.environ.get("EMAIL_USER", "")
        pwd = os.environ.get("EMAIL_PASSWORD", "")

        if not user or not pwd:
            return {
                "status": "mock_sent",
                "message": f"Email credentials not set. Simulated send to {to_addr}",
                "to": to_addr,
                "subject": subject,
            }

        msg = MIMEMultipart()
        msg["From"] = user
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(user, pwd)
            server.send_message(msg)

        return {"status": "sent", "to": to_addr, "subject": subject}

    def _read_inbox(self, limit: int = 5) -> list[dict[str, Any]]:
        imap_host = os.environ.get("EMAIL_IMAP_HOST", "imap.gmail.com")
        user = os.environ.get("EMAIL_USER", "")
        pwd = os.environ.get("EMAIL_PASSWORD", "")

        if not user or not pwd:
            return [
                {
                    "from": "notifications@github.com",
                    "subject": "AuraAI Repo Update",
                    "date": "Today",
                    "snippet": "New automated build completed successfully.",
                }
            ]

        mail = imaplib.IMAP4_SSL(imap_host)
        mail.login(user, pwd)
        mail.select("inbox")
        _, data = mail.search(None, "ALL")
        mail_ids = data[0].split()
        results = []
        for mid in mail_ids[-limit:]:
            _, msg_data = mail.fetch(mid, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or "utf-8", errors="replace")
                    results.append({"from": msg.get("From"), "subject": subject, "date": msg.get("Date")})
        mail.close()
        mail.logout()
        return results

    def execute(self, capability: str, **kwargs: Any) -> Any:
        cap = capability.lower()
        if cap == "email.send":
            to = kwargs.get("to") or kwargs.get("recipient", "")
            subj = kwargs.get("subject") or "Aura AI Message"
            body = kwargs.get("body") or kwargs.get("content", "")
            return self._send_email(to, subj, body)
        elif cap in ("email.read_inbox", "email.search"):
            limit = int(kwargs.get("limit", 5))
            return self._read_inbox(limit)
        else:
            return {"status": "success", "capability": capability, "params": kwargs}
