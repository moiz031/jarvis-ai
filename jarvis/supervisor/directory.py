"""Cross-channel contact directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .state_store import load_json, save_json


class DirectoryManager:
    def __init__(self, path: Path):
        self.path = path

    def _read(self):
        return load_json(self.path, default={"contacts": {}})

    def _write(self, data):
        save_json(self.path, data)

    def upsert_contact(self, alias: str, routes: Dict[str, str], meta: Optional[Dict[str, Any]] = None):
        data = self._read()
        contacts = data.setdefault("contacts", {})
        contacts[alias] = {
            "routes": routes,
            "meta": meta or {},
        }
        self._write(data)
        return contacts[alias]

    def resolve(self, alias: str, channel: str) -> Optional[str]:
        data = self._read()
        contact = data.get("contacts", {}).get(alias)
        if not contact:
            return None
        return contact.get("routes", {}).get(channel)

    def list_contacts(self) -> Dict[str, Any]:
        data = self._read()
        return data.get("contacts", {})
