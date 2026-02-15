"""Safety confirmations and system access gating."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    from config import Config
    from supervisor.onboarding import OnboardingManager
    from supervisor.state_store import load_json, save_json
except Exception:
    from ..config import Config
    from ..supervisor.onboarding import OnboardingManager
    from ..supervisor.state_store import load_json, save_json


_confirm_handler: Optional[Callable[..., bool]] = None


def set_confirm_handler(handler: Callable[..., bool]) -> None:
    global _confirm_handler
    _confirm_handler = handler


def _auto_confirm_enabled() -> bool:
    return os.getenv("JARVIS_AUTO_CONFIRM", "").strip().lower() in {"1", "true", "yes", "on"}


def _load_state(path: Path) -> Dict[str, Any]:
    default_state = {
        "onboarded": False,
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
    }
    state = load_json(path, default_state)
    for key, value in default_state.items():
        state.setdefault(key, value)
    profile = str(state.get("permission_profile") or "basic").lower()
    if "system_access_granted" not in state or state.get("system_access_granted") is None:
        state["system_access_granted"] = bool(state.get("onboarded")) and profile in {"power", "admin"}
    if "system_access_prompted" not in state or state.get("system_access_prompted") is None:
        state["system_access_prompted"] = bool(state.get("onboarded")) or bool(state.get("system_access_granted"))
    if "access_scopes" not in state or not isinstance(state.get("access_scopes"), dict):
        state["access_scopes"] = {
            "files": bool(state.get("system_access_granted")),
            "browser": bool(state.get("system_access_granted")),
            "automation": bool(state.get("system_access_granted")),
        }
    else:
        scopes = state.get("access_scopes") or {}
        for key in ("files", "browser", "automation"):
            scopes.setdefault(key, bool(state.get("system_access_granted")))
        state["access_scopes"] = scopes
    return state


def _has_full_access(state: Dict[str, Any]) -> bool:
    if "system_access_granted" in state:
        return bool(state.get("system_access_granted"))
    profile = str(state.get("permission_profile") or "basic").lower()
    return bool(state.get("onboarded")) and profile in {"power", "admin"}


def confirm_action(prompt: str, kind: str = "action", timeout: int = 35, default: bool = False) -> bool:
    """Ask user for confirmation before proceeding with a risky action.
    Returns True if confirmed, False otherwise.
    """
    if _auto_confirm_enabled():
        print(f"\n[SAFETY] AUTO-CONFIRM ENABLED: {prompt}")
        return True

    if _confirm_handler is not None:
        try:
            return bool(_confirm_handler(prompt=prompt, kind=kind, timeout=timeout, default=default))
        except TypeError:
            # Backward-compatible handler signature.
            return bool(_confirm_handler(prompt, timeout=timeout, default=default))

    print(f"\n[SAFETY] Confirmation handler missing. Defaulting to {default} for: {prompt}")
    return default


def ensure_system_access(reason: str = "system access", timeout: int = 45) -> bool:
    """Ensure the user has granted full system access once.

    Returns True if access is granted, otherwise False.
    """
    cfg = Config()
    state = _load_state(cfg.SUPER_STATE_PATH)
    if _has_full_access(state):
        return True

    if state.get("system_access_prompted"):
        return False

    prompt = f"Boss, kya main full system access le loon? ({reason})"
    approved = confirm_action(prompt, kind="system_access", timeout=timeout, default=False)

    payload = {
        "permission_profile": "power" if approved else "basic",
        "allowlist_users": state.get("allowlist_users") or ["local-admin"],
        "connect_channels": state.get("connected_channels") or [],
        "grant_system_access": bool(approved),
    }

    try:
        onboarding = OnboardingManager(Path(cfg.SUPER_STATE_PATH))
        onboarding.run(payload)
    except Exception:
        # Fallback to direct state write if onboarding fails.
        state.update(
            {
                "onboarded": True,
                "permission_profile": payload["permission_profile"],
                "system_access_granted": bool(approved),
                "system_access_prompted": True,
                "access_scopes": {
                    "files": bool(approved),
                    "browser": bool(approved),
                    "automation": bool(approved),
                },
            }
        )
        save_json(cfg.SUPER_STATE_PATH, state)

    return bool(approved)


def ensure_scope_access(scope: str, reason: str = "system access") -> bool:
    cfg = Config()
    state = _load_state(cfg.SUPER_STATE_PATH)
    if not _has_full_access(state):
        if not state.get("system_access_prompted"):
            if not ensure_system_access(reason):
                return False
            state = _load_state(cfg.SUPER_STATE_PATH)
        else:
            return False
    scopes = state.get("access_scopes") or {}
    return bool(scopes.get(scope))
