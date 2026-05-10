"""Permission and risk policy for Super Mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Set, Tuple

from .state_store import load_json


@dataclass(slots=True)
class PolicyDecision:
    allowed: bool
    reason: str
    step_up_required: bool = False


class PolicyEngine:
    def __init__(self, policy_path):
        self.policy_path = policy_path
        self._profiles = {
            "basic": {
                "allowed_actions": {
                    "agent.chat",
                    "system.status",
                    "channel.receive",
                    "plugin.list",
                    "plugin.reload",
                    "worker.status",
                },
                "require_step_up": {"browser.task", "files.write", "plugin.reload", "plugin.execute"},
            },
            "power": {
                "allowed_actions": {
                    "agent.chat",
                    "system.status",
                    "browser.task",
                    "files.read",
                    "files.write",
                    "automation.type",
                    "channel.send",
                    "channel.receive",
                    "plugin.list",
                    "plugin.reload",
                    "plugin.execute",
                    "worker.schedule",
                    "worker.status",
                },
                "require_step_up": {"automation.type", "files.write", "plugin.reload", "plugin.execute"},
            },
            "admin": {
                "allowed_actions": {"*"},
                "require_step_up": {"system.shutdown", "system.optimize"},
            },
        }
        self._danger_terms = {
            "shutdown",
            "format",
            "delete all",
            "drop database",
            "kill process",
            "rm -rf",
            "disable security",
            "credential",
            "password",
            "plugin reload",
            "plugin run",
        }
        self.custom_policy = {}
        self.reload()

    def reload(self):
        self.custom_policy = load_json(self.policy_path, default={})

    def _allowed_actions_for(self, profile_name: str) -> Set[str]:
        profile = self._profiles.get(profile_name, self._profiles["power"])
        actions = set(profile.get("allowed_actions", set()))
        custom = self.custom_policy.get("profiles", {}).get(profile_name, {})
        actions.update(custom.get("allow", []))
        for denied in custom.get("deny", []):
            actions.discard(denied)
        return actions

    def _step_up_actions_for(self, profile_name: str) -> Set[str]:
        profile = self._profiles.get(profile_name, self._profiles["power"])
        actions = set(profile.get("require_step_up", set()))
        custom = self.custom_policy.get("profiles", {}).get(profile_name, {})
        actions.update(custom.get("step_up", []))
        return actions

    def evaluate(
        self,
        profile_name: str,
        action: str,
        user_id: str,
        allowlist: Optional[Iterable[str]] = None,
        text: str = "",
    ) -> PolicyDecision:
        allowlist_set = set(allowlist or [])
        if allowlist_set and user_id not in allowlist_set:
            return PolicyDecision(False, f"User '{user_id}' is not allowlisted.")

        allowed_actions = self._allowed_actions_for(profile_name)
        if "*" not in allowed_actions and action not in allowed_actions:
            return PolicyDecision(False, f"Action '{action}' blocked for profile '{profile_name}'.")

        step_up = action in self._step_up_actions_for(profile_name)
        lowered = text.lower()
        if any(term in lowered for term in self._danger_terms):
            step_up = True

        return PolicyDecision(True, "Allowed", step_up_required=step_up)
