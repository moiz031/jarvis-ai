"""Channel gateway abstraction for multi-source messaging."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .schemas import ChannelMessage
from .state_store import load_json, save_json

logger = logging.getLogger(__name__)


class BaseChannelAdapter:
    def __init__(self, name: str, settings: Optional[Dict[str, Any]] = None):
        self.name = name
        self.settings = settings or {}
        self.connected = False

    def connect(self):
        self.connected = True
        return {"ok": True, "channel": self.name}

    def disconnect(self):
        self.connected = False
        return {"ok": True, "channel": self.name}

    def send(self, target: str, text: str):
        if not self.connected:
            return {"ok": False, "error": f"{self.name} is not connected."}
        return {"ok": True, "channel": self.name, "target": target, "text": text}


class EmailAdapter(BaseChannelAdapter):
    pass


class TelegramAdapter(BaseChannelAdapter):
    pass


class DiscordAdapter(BaseChannelAdapter):
    pass


class SlackAdapter(BaseChannelAdapter):
    pass


ADAPTERS = {
    "email": EmailAdapter,
    "telegram": TelegramAdapter,
    "discord": DiscordAdapter,
    "slack": SlackAdapter,
    "whatsapp": BaseChannelAdapter,
}


class ChannelGateway:
    def __init__(self, state_path: Path):
        self.state_path = state_path
        self.adapters: Dict[str, BaseChannelAdapter] = {}
        self._listener: Optional[Callable[[ChannelMessage], None]] = None
        self._load_from_state()

    def _read_state(self):
        return load_json(self.state_path, default={"channels": {}})

    def _write_state(self, data):
        save_json(self.state_path, data)

    def _load_from_state(self):
        data = self._read_state()
        channels = data.get("channels", {})
        for name, cfg in channels.items():
            if cfg.get("enabled"):
                self.connect_channel(name, cfg.get("settings", {}), persist=False)

    def set_listener(self, callback: Callable[[ChannelMessage], None]):
        self._listener = callback

    def connect_channel(self, name: str, settings: Optional[Dict[str, Any]] = None, persist: bool = True):
        key = name.lower()
        adapter_cls = ADAPTERS.get(key, BaseChannelAdapter)
        adapter = adapter_cls(key, settings or {})
        result = adapter.connect()
        self.adapters[key] = adapter
        if persist:
            data = self._read_state()
            data.setdefault("channels", {})[key] = {"enabled": True, "settings": settings or {}}
            self._write_state(data)
        return result

    def disconnect_channel(self, name: str):
        key = name.lower()
        adapter = self.adapters.get(key)
        if adapter:
            adapter.disconnect()
            del self.adapters[key]
        data = self._read_state()
        if key in data.get("channels", {}):
            data["channels"][key]["enabled"] = False
            self._write_state(data)
        return {"ok": True, "channel": key}

    def list_channels(self):
        data = self._read_state()
        channels = data.get("channels", {})
        out = []
        for name, cfg in channels.items():
            out.append(
                {
                    "name": name,
                    "enabled": bool(cfg.get("enabled")),
                    "connected": name in self.adapters and self.adapters[name].connected,
                    "settings": cfg.get("settings", {}),
                }
            )
        # Include runtime-only channels if any.
        known = {x["name"] for x in out}
        for name, adapter in self.adapters.items():
            if name not in known:
                out.append({"name": name, "enabled": True, "connected": adapter.connected, "settings": adapter.settings})
        return out

    def send(self, channel: str, target: str, text: str):
        key = channel.lower()
        adapter = self.adapters.get(key)
        if adapter is None:
            return {"ok": False, "error": f"Channel '{key}' not connected."}
        return adapter.send(target, text)

    def ingest(self, channel: str, user_id: str, text: str, metadata: Optional[Dict[str, Any]] = None):
        msg = ChannelMessage(channel=channel.lower(), user_id=user_id, text=text, metadata=metadata or {})
        logger.info("Inbound channel message: %s/%s", msg.channel, msg.user_id)
        if self._listener:
            self._listener(msg)
        return {"ok": True, "message": "Inbound message accepted."}
