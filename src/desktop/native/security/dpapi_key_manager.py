"""
DPAPI Master Key Manager & HKDF-SHA256 Key Derivation Engine
Location: src/desktop/native/security/dpapi_key_manager.py

Protects master cryptographic secrets at rest using Windows Data Protection API (DPAPI via win32crypt).
Provides deterministic, verifiable key derivation using HKDF-SHA256 with explicit key envelope metadata,
purpose-separated contexts, and rotation descriptors.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import logging
import os
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import win32crypt

logger = logging.getLogger(__name__)

DPAPI_ENTROPY_PURPOSE = b"AuraAI.Security.MasterKey.Entropy.v1"


@dataclass
class KeyEnvelopeMetadata:
    """Metadata envelope for a persisted or derived cryptographic key."""

    key_id: str
    created_at: str
    algorithm: str
    purpose: str
    version: int
    derivation_salt_hex: str
    master_key_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


class DPAPIKeyManager:
    """
    Manages DPAPI-protected master keys and HKDF-derived process keys.
    """

    def __init__(
        self,
        storage_dir: str | Path | None = None,
        entropy: bytes = DPAPI_ENTROPY_PURPOSE,
    ):
        if storage_dir is None:
            base_dir = Path(os.getenv("LOCALAPPDATA", str(Path.home() / ".aura"))) / "AuraAI" / "security" / "keys"
        else:
            base_dir = Path(storage_dir).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)
        self._storage_dir = base_dir
        self._entropy = entropy
        self._master_key_file = self._storage_dir / "master_key.dpapi"
        self._meta_file = self._storage_dir / "master_key_meta.json"

    @property
    def storage_dir(self) -> Path:
        return self._storage_dir

    def protect_bytes(self, plaintext: bytes, description: str = "AuraAI Master Key") -> bytes:
        """
        Encrypt plaintext using Windows DPAPI (CryptProtectData) bound to current user context.
        """
        try:
            encrypted_blob = win32crypt.CryptProtectData(
                plaintext,
                description,
                self._entropy,
                None,  # Reserved
                None,  # Prompt struct
                0,     # Flags
            )
            return encrypted_blob
        except Exception as exc:
            raise RuntimeError(f"DPAPI CryptProtectData failed: {exc}") from exc

    def unprotect_bytes(self, ciphertext: bytes) -> tuple[str, bytes]:
        """
        Decrypt ciphertext using Windows DPAPI (CryptUnprotectData).
        Returns: (description, plaintext_bytes)
        """
        try:
            desc, plaintext = win32crypt.CryptUnprotectData(
                ciphertext,
                self._entropy,
                None,
                None,
                0,
            )
            return desc, plaintext
        except Exception as exc:
            raise RuntimeError(f"DPAPI CryptUnprotectData failed: {exc}") from exc

    def get_or_create_master_key(self, force_rotate: bool = False) -> tuple[bytes, KeyEnvelopeMetadata]:
        """
        Retrieve existing DPAPI-protected master key or generate and persist a new 256-bit master key.
        """
        if self._master_key_file.exists() and self._meta_file.exists() and not force_rotate:
            try:
                encrypted_blob = self._master_key_file.read_bytes()
                _, master_key = self.unprotect_bytes(encrypted_blob)
                meta_json = json.loads(self._meta_file.read_text(encoding="utf-8"))
                metadata = KeyEnvelopeMetadata(**meta_json)
                if len(master_key) == 32:
                    return master_key, metadata
            except Exception as exc:
                logger.warning(f"[DPAPIKeyManager] Failed to load existing master key blob ({exc}). Rotating.")

        # Generate fresh 256-bit master secret
        new_master_key = secrets.token_bytes(32)
        new_salt = secrets.token_bytes(32)
        key_id = str(uuid.uuid4())
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        metadata = KeyEnvelopeMetadata(
            key_id=key_id,
            created_at=created_at,
            algorithm="AES-256/HMAC-SHA256",
            purpose="master_key_root",
            version=1,
            derivation_salt_hex=new_salt.hex(),
        )

        encrypted_blob = self.protect_bytes(new_master_key, description=f"AuraAI Master Key {key_id}")
        self._master_key_file.write_bytes(encrypted_blob)
        self._meta_file.write_text(json.dumps(asdict(metadata), indent=2), encoding="utf-8")

        return new_master_key, metadata

    def hkdf_extract_and_expand(
        self,
        ikm: bytes,
        salt: bytes,
        info: bytes,
        length: int = 32,
    ) -> bytes:
        """
        Standard RFC 5869 HKDF-SHA256 (Extract and Expand).
        """
        # Step 1: Extract
        if not salt:
            salt = b"\x00" * 32
        prk = hmac.new(salt, ikm, hashlib.sha256).digest()

        # Step 2: Expand
        n = (length + 31) // 32
        t = b""
        okm = b""
        for i in range(1, n + 1):
            t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
            okm += t
        return okm[:length]

    def derive_purpose_key(
        self,
        purpose: str,
        master_key: bytes | None = None,
        master_meta: KeyEnvelopeMetadata | None = None,
        version: int = 1,
    ) -> tuple[bytes, KeyEnvelopeMetadata]:
        """
        Derive a deterministic, purpose-specific key using HKDF-SHA256.
        Formula: HKDF-SHA256(IKM=master_key, salt=derivation_salt, info="AuraAI/{purpose}/{key_id}/v{version}")
        """
        if master_key is None or master_meta is None:
            master_key, master_meta = self.get_or_create_master_key()

        derived_key_id = str(uuid.uuid4())
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        salt = bytes.fromhex(master_meta.derivation_salt_hex)
        info_string = f"AuraAI/{purpose}/{derived_key_id}/v{version}".encode("utf-8")

        derived_bytes = self.hkdf_extract_and_expand(
            ikm=master_key,
            salt=salt,
            info=info_string,
            length=32,
        )

        derived_meta = KeyEnvelopeMetadata(
            key_id=derived_key_id,
            created_at=created_at,
            algorithm="HMAC-SHA256",
            purpose=purpose,
            version=version,
            derivation_salt_hex=salt.hex(),
            master_key_id=master_meta.key_id,
            extra={"info": info_string.decode("utf-8")},
        )

        return derived_bytes, derived_meta
