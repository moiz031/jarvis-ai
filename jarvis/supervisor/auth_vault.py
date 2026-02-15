"""Encrypted token vault for channel and provider credentials."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .state_store import load_json, save_json

try:
    import win32crypt  # type: ignore
except Exception:
    win32crypt = None

try:
    from cryptography.fernet import Fernet
except Exception:
    Fernet = None


class AuthVault:
    def __init__(self, vault_path: Path, key_path: Path):
        self.vault_path = vault_path
        self.key_path = key_path
        self._cipher = self._build_cipher()

    def _build_cipher(self):
        if Fernet is None:
            return None

        if self.key_path.exists():
            key = self.key_path.read_bytes()
            return Fernet(key)

        seed = f"{os.getenv('USERNAME', 'jarvis')}::{os.getenv('COMPUTERNAME', 'host')}"
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_path.write_bytes(key)
        return Fernet(key)

    def _encrypt_text(self, text: str) -> str:
        raw = text.encode("utf-8")

        if win32crypt is not None:
            blob = win32crypt.CryptProtectData(raw, "jarvis-super-vault", None, None, None, 0)[1]
            return "dpapi:" + base64.b64encode(blob).decode("ascii")

        if self._cipher is not None:
            return "fernet:" + self._cipher.encrypt(raw).decode("ascii")

        return "plain:" + base64.b64encode(raw).decode("ascii")

    def _decrypt_text(self, encrypted: str) -> str:
        if encrypted.startswith("dpapi:") and win32crypt is not None:
            raw = base64.b64decode(encrypted.removeprefix("dpapi:"))
            return win32crypt.CryptUnprotectData(raw, None, None, None, 0)[1].decode("utf-8")

        if encrypted.startswith("fernet:") and self._cipher is not None:
            token = encrypted.removeprefix("fernet:").encode("ascii")
            return self._cipher.decrypt(token).decode("utf-8")

        if encrypted.startswith("plain:"):
            raw = base64.b64decode(encrypted.removeprefix("plain:"))
            return raw.decode("utf-8")

        return ""

    def _read(self) -> Dict[str, Any]:
        return load_json(self.vault_path, default={"providers": {}})

    def _write(self, data: Dict[str, Any]) -> None:
        save_json(self.vault_path, data)

    def set_token(self, provider: str, token: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        data = self._read()
        providers = data.setdefault("providers", {})
        providers[provider] = {
            "token": self._encrypt_text(token),
            "metadata": metadata or {},
        }
        self._write(data)

    def get_token(self, provider: str) -> Optional[str]:
        data = self._read()
        provider_data = data.get("providers", {}).get(provider)
        if not provider_data:
            return None
        encrypted = provider_data.get("token", "")
        if not encrypted:
            return None
        return self._decrypt_text(encrypted)

    def get_metadata(self, provider: str) -> Dict[str, Any]:
        data = self._read()
        return data.get("providers", {}).get(provider, {}).get("metadata", {})

    def delete_token(self, provider: str) -> bool:
        data = self._read()
        providers = data.get("providers", {})
        if provider not in providers:
            return False
        del providers[provider]
        self._write(data)
        return True

    def list_providers(self):
        data = self._read()
        return sorted(data.get("providers", {}).keys())
