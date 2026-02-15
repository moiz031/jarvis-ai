"""One-time onboarding flow for Super Mode."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .state_store import load_json, save_json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OnboardingManager:
    def __init__(self, state_path: Path):
        self.state_path = state_path

    def _read(self):
        return load_json(
            self.state_path,
            default={
                "onboarded": False,
                "created_at": None,
                "updated_at": None,
                "permission_profile": "basic",
                "allowlist_users": ["local-admin"],
                "connected_channels": [],
                "system_access_granted": False,
                "system_access_prompted": False,
                "access_scopes": {
                    "files": False,
                    "browser": False,
                    "automation": False,
                },
            },
        )

    def _write(self, data):
        data["updated_at"] = _now()
        save_json(self.state_path, data)

    def state(self):
        return self._read()

    def is_onboarded(self) -> bool:
        return bool(self._read().get("onboarded"))

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read()
        if not data.get("created_at"):
            data["created_at"] = _now()

        profile = str(payload.get("permission_profile") or data.get("permission_profile") or "basic").lower()
        if profile not in {"basic", "power", "admin"}:
            profile = "basic"

        users = payload.get("allowlist_users")
        if not isinstance(users, list) or not users:
            users = data.get("allowlist_users") or ["local-admin"]
        users = [str(x).strip() for x in users if str(x).strip()]

        channels: List[str] = payload.get("connect_channels") or []
        channels = [str(c).strip().lower() for c in channels if str(c).strip()]

        grant_system_access = payload.get("grant_system_access")
        if grant_system_access is None:
            grant_system_access = profile in {"power", "admin"}

        access_scopes = payload.get("access_scopes")
        default_scopes = {
            "files": bool(grant_system_access),
            "browser": bool(grant_system_access),
            "automation": bool(grant_system_access),
        }
        if isinstance(access_scopes, dict):
            for key in default_scopes:
                if key in access_scopes:
                    default_scopes[key] = bool(access_scopes[key])

        data.update(
            {
                "onboarded": True,
                "permission_profile": profile,
                "allowlist_users": users,
                "connected_channels": sorted(set(channels)),
                "one_time_access_granted": bool(grant_system_access),
                "system_access_granted": bool(grant_system_access),
                "system_access_prompted": True,
                "access_scopes": default_scopes,
            }
        )
        self._write(data)
        return data
