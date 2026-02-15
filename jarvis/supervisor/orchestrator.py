"""Top-level orchestrator for Jarvis Super Mode."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .auth_vault import AuthVault
from .channel_gateway import ChannelGateway
from .directory import DirectoryManager
from .onboarding import OnboardingManager
from .plugin_runtime import PluginRuntime
from .policy import PolicyEngine
from .schemas import ChannelMessage
from .worker_pool import WorkerPool

logger = logging.getLogger(__name__)


class SuperOrchestrator:
    def __init__(
        self,
        config,
        emit: Callable[[str, Any], None],
        agent_callback: Callable[[str, Optional[str]], Any],
    ):
        self.config = config
        self.emit = emit
        self.agent_callback = agent_callback

        self.onboarding = OnboardingManager(Path(config.SUPER_STATE_PATH))
        self.policy = PolicyEngine(Path(config.SUPER_POLICY_PATH))
        self.vault = AuthVault(Path(config.SUPER_VAULT_PATH), Path(config.SUPER_VAULT_KEY_PATH))
        self.gateway = ChannelGateway(Path(config.SUPER_CHANNELS_PATH))
        self.directory = DirectoryManager(Path(config.SUPER_DIRECTORY_PATH))
        self.plugins = PluginRuntime(Path(config.SUPER_PLUGINS_DIR))
        self.workers = WorkerPool(max_workers=config.MAX_AGENT_WORKERS, low_ram_mode=config.LOW_RAM_MODE)

        self.gateway.set_listener(self._on_channel_message)
        loaded, errors = self.plugins.reload()
        logger.info("Super plugins loaded: %s", loaded)
        if errors:
            logger.warning("Super plugin errors: %s", errors)

    def _current_policy_context(self):
        state = self.onboarding.state()
        return state.get("permission_profile", "power"), state.get("allowlist_users", [])

    def _authorize(self, action: str, user_id: str, text: str = "", metadata: Optional[Dict[str, Any]] = None):
        profile, allowlist = self._current_policy_context()
        decision = self.policy.evaluate(profile, action, user_id=user_id, allowlist=allowlist, text=text)
        if not decision.allowed:
            return {"ok": False, "error": decision.reason}
        if decision.step_up_required and not (metadata or {}).get("confirmed", False):
            return {"ok": False, "error": "Step-up confirmation required.", "step_up_required": True}
        return {"ok": True}

    def _on_channel_message(self, message: ChannelMessage):
        meta = dict(message.metadata or {})
        meta["channel"] = message.channel
        outcome = self.handle_text(message.text, source=message.channel, user_id=message.user_id, metadata=meta)
        self.emit("super_event", {"type": "channel_inbound", "channel": message.channel, "user_id": message.user_id, "outcome": outcome})

    def status(self):
        return {
            "onboarding": self.onboarding.state(),
            "channels": self.gateway.list_channels(),
            "plugins": self.plugins.list_plugins(),
            "providers": self.vault.list_providers(),
            "workers": self.workers.list_jobs(limit=15),
            "low_ram_mode": self.config.LOW_RAM_MODE,
            "max_workers": self.config.MAX_AGENT_WORKERS,
        }

    def onboard(self, payload: Dict[str, Any]):
        data = self.onboarding.run(payload)
        for channel in data.get("connected_channels", []):
            self.gateway.connect_channel(channel, persist=True)
        self.emit("super_event", {"type": "onboarding_completed", "state": data})
        return {"ok": True, "state": data}

    def connect_channel(self, name: str, settings: Optional[Dict[str, Any]] = None, token: Optional[str] = None):
        if token:
            self.vault.set_token(name.lower(), token, metadata={"channel": name.lower()})
        result = self.gateway.connect_channel(name, settings=settings or {}, persist=True)
        self.emit("super_event", {"type": "channel_connected", "channel": name.lower()})
        return result

    def disconnect_channel(self, name: str):
        result = self.gateway.disconnect_channel(name)
        self.emit("super_event", {"type": "channel_disconnected", "channel": name.lower()})
        return result

    def send_channel_message(self, channel: str, target: str, text: str, user_id: str, metadata: Optional[Dict[str, Any]] = None):
        auth = self._authorize("channel.send", user_id=user_id, text=text, metadata=metadata)
        if not auth.get("ok"):
            return auth
        result = self.gateway.send(channel, target, text)
        self.emit("super_event", {"type": "channel_outbound", "channel": channel.lower(), "target": target, "ok": result.get("ok", False)})
        return result

    def ingest_channel_message(self, channel: str, user_id: str, text: str, metadata: Optional[Dict[str, Any]] = None):
        auth = self._authorize("channel.receive", user_id=user_id, text=text, metadata=metadata)
        if not auth.get("ok"):
            return auth
        return self.gateway.ingest(channel, user_id, text, metadata)

    def _dispatch_agent(self, text: str, source: str, metadata: Optional[Dict[str, Any]] = None):
        try:
            return self.agent_callback(text, None)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "source": source}

    def _queue_agent_task(self, text: str, source: str, user_id: str, metadata: Optional[Dict[str, Any]] = None):
        auth = self._authorize("agent.chat", user_id=user_id, text=text, metadata=metadata)
        if not auth.get("ok"):
            return auth
        job_id = self.workers.submit(
            name=f"agent:{source}",
            fn=self._dispatch_agent,
            text=text,
            source=source,
            metadata=metadata,
            retries=1,
        )
        return {"ok": True, "job_id": job_id}

    def _handle_super_command(self, text: str, user_id: str, metadata: Optional[Dict[str, Any]] = None):
        raw = text.strip()
        if raw == "/super status":
            return {"ok": True, "handled": True, "message": "Super status ready.", "data": self.status()}
        if raw == "/super plugins":
            return {"ok": True, "handled": True, "data": self.plugins.list_plugins()}
        if raw == "/super jobs":
            return {"ok": True, "handled": True, "data": self.workers.list_jobs(limit=30)}
        if raw == "/super channels":
            return {"ok": True, "handled": True, "data": self.gateway.list_channels()}
        if raw.startswith("/channel connect "):
            channel = raw.split(" ", 2)[2].strip()
            data = self.connect_channel(channel)
            return {"ok": True, "handled": True, "data": data, "message": f"Channel '{channel}' connected."}
        if raw.startswith("/channel disconnect "):
            channel = raw.split(" ", 2)[2].strip()
            data = self.disconnect_channel(channel)
            return {"ok": True, "handled": True, "data": data, "message": f"Channel '{channel}' disconnected."}
        if raw.startswith("/channel send "):
            # /channel send <channel> <target> <message>
            parts = raw.split(" ", 4)
            if len(parts) < 5:
                return {"ok": False, "handled": True, "error": "Usage: /channel send <channel> <target> <message>"}
            _, _, channel, target, msg = parts
            data = self.send_channel_message(channel, target, msg, user_id=user_id, metadata=metadata)
            return {"ok": data.get("ok", False), "handled": True, "data": data}
        if raw.startswith("/plugin reload"):
            loaded, errors = self.plugins.reload()
            return {"ok": True, "handled": True, "data": {"loaded": loaded, "errors": errors}}
        if raw.startswith("/plugin run "):
            # /plugin run <action> <json_payload>
            parts = raw.split(" ", 3)
            if len(parts) < 4:
                return {"ok": False, "handled": True, "error": "Usage: /plugin run <action> <json_payload>"}
            action = parts[2].strip()
            try:
                payload = json.loads(parts[3])
            except json.JSONDecodeError:
                return {"ok": False, "handled": True, "error": "Invalid JSON payload for plugin action."}

            auth = self._authorize("plugin.execute", user_id=user_id, text=raw, metadata=metadata)
            if not auth.get("ok"):
                return {"ok": False, "handled": True, "error": auth.get("error"), "step_up_required": auth.get("step_up_required", False)}

            data = self.plugins.execute(action, payload)
            return {"ok": data.get("ok", False), "handled": True, "data": data}
        if raw.startswith("/directory set "):
            # /directory set <alias> <channel> <id>
            parts = raw.split(" ")
            if len(parts) < 6:
                return {"ok": False, "handled": True, "error": "Usage: /directory set <alias> <channel> <id>"}
            alias, channel, target_id = parts[2], parts[3], " ".join(parts[4:])
            existing = self.directory.list_contacts().get(alias, {})
            routes = dict(existing.get("routes", {}))
            routes[channel] = target_id
            rec = self.directory.upsert_contact(alias, routes, meta=existing.get("meta", {}))
            return {"ok": True, "handled": True, "data": rec}
        if raw == "/directory list":
            return {"ok": True, "handled": True, "data": self.directory.list_contacts()}
        if raw.startswith("/task async "):
            task_text = raw.removeprefix("/task async ").strip()
            data = self._queue_agent_task(task_text, source="cli", user_id=user_id, metadata=metadata)
            return {"ok": data.get("ok", False), "handled": True, "data": data}
        return {"handled": False}

    def handle_text(self, text: str, source: str, user_id: str = "local-admin", metadata: Optional[Dict[str, Any]] = None):
        metadata = metadata or {}
        if not text or not text.strip():
            return {"ok": False, "handled": True, "error": "Empty input."}

        if text.strip().startswith("/"):
            cmd = self._handle_super_command(text, user_id=user_id, metadata=metadata)
            if cmd.get("handled"):
                return cmd

        auth = self._authorize("agent.chat", user_id=user_id, text=text, metadata=metadata)
        if not auth.get("ok"):
            return {"ok": False, "handled": True, "error": auth.get("error"), "step_up_required": auth.get("step_up_required", False)}

        # Default path: dispatch to normal Jarvis agent.
        self._dispatch_agent(text, source=source, metadata=metadata)
        return {"ok": True, "handled": True, "routed_to": "agent"}
