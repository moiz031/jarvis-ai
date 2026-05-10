"""Channel gateway abstraction for multi-source messaging."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import requests

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
    def connect(self):
        smtp_host = self.settings.get("smtp_host") or os.getenv("SMTP_HOST")
        smtp_port = int(self.settings.get("smtp_port") or os.getenv("SMTP_PORT", "587"))
        smtp_user = self.settings.get("smtp_user") or os.getenv("SMTP_USER")
        smtp_password = self.settings.get("smtp_password") or os.getenv("SMTP_PASSWORD")
        from_email = self.settings.get("from_email") or smtp_user

        if not smtp_host or not smtp_user or not smtp_password or not from_email:
            self.connected = False
            return {
                "ok": False,
                "channel": self.name,
                "error": "Missing SMTP settings (host/user/password/from_email).",
            }

        self.settings["smtp_port"] = smtp_port
        self.settings["from_email"] = from_email
        self.connected = True
        return {"ok": True, "channel": self.name}

    def send(self, target: str, text: str):
        if not self.connected:
            return {"ok": False, "error": f"{self.name} is not connected."}
        try:
            import smtplib
            from email.message import EmailMessage

            host = self.settings.get("smtp_host") or os.getenv("SMTP_HOST")
            port = int(self.settings.get("smtp_port") or os.getenv("SMTP_PORT", "587"))
            user = self.settings.get("smtp_user") or os.getenv("SMTP_USER")
            password = self.settings.get("smtp_password") or os.getenv("SMTP_PASSWORD")
            from_email = self.settings.get("from_email") or user
            subject = self.settings.get("subject") or "Jarvis Notification"

            msg = EmailMessage()
            msg["From"] = from_email
            msg["To"] = target
            msg["Subject"] = subject
            msg.set_content(text)

            with smtplib.SMTP(host, port, timeout=10) as server:
                server.starttls()
                server.login(user, password)
                server.send_message(msg)

            return {"ok": True, "channel": self.name, "target": target, "text": text}
        except Exception as exc:
            return {"ok": False, "channel": self.name, "error": str(exc)}


class TelegramAdapter(BaseChannelAdapter):
    def connect(self):
        token = self.settings.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            self.connected = False
            return {"ok": False, "channel": self.name, "error": "Missing Telegram bot token."}
        self.settings["bot_token"] = token
        self.connected = True
        return {"ok": True, "channel": self.name}

    def send(self, target: str, text: str):
        if not self.connected:
            return {"ok": False, "error": f"{self.name} is not connected."}
        token = self.settings.get("bot_token")
        chat_id = target or self.settings.get("default_chat_id")
        if not chat_id:
            return {"ok": False, "channel": self.name, "error": "Missing Telegram chat id target."}
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=10,
            )
            if not resp.ok:
                return {"ok": False, "channel": self.name, "error": f"Telegram API error: {resp.text}"}
            return {"ok": True, "channel": self.name, "target": str(chat_id), "text": text}
        except Exception as exc:
            return {"ok": False, "channel": self.name, "error": str(exc)}


class DiscordAdapter(BaseChannelAdapter):
    def connect(self):
        webhook_url = self.settings.get("webhook_url") or os.getenv("DISCORD_WEBHOOK_URL")
        if not webhook_url:
            self.connected = False
            return {"ok": False, "channel": self.name, "error": "Missing Discord webhook URL."}
        self.settings["webhook_url"] = webhook_url
        self.connected = True
        return {"ok": True, "channel": self.name}

    def send(self, target: str, text: str):
        if not self.connected:
            return {"ok": False, "error": f"{self.name} is not connected."}
        webhook_url = self.settings.get("webhook_url")
        payload = {"content": text}
        if target:
            payload["content"] = f"[{target}] {text}"
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code not in (200, 204):
                return {"ok": False, "channel": self.name, "error": f"Discord API error: {resp.text}"}
            return {"ok": True, "channel": self.name, "target": target, "text": text}
        except Exception as exc:
            return {"ok": False, "channel": self.name, "error": str(exc)}


class SlackAdapter(BaseChannelAdapter):
    def connect(self):
        bot_token = self.settings.get("bot_token") or os.getenv("SLACK_BOT_TOKEN")
        if not bot_token:
            self.connected = False
            return {"ok": False, "channel": self.name, "error": "Missing Slack bot token."}
        self.settings["bot_token"] = bot_token
        self.connected = True
        return {"ok": True, "channel": self.name}

    def send(self, target: str, text: str):
        if not self.connected:
            return {"ok": False, "error": f"{self.name} is not connected."}
        bot_token = self.settings.get("bot_token")
        channel = target or self.settings.get("default_channel")
        if not channel:
            return {"ok": False, "channel": self.name, "error": "Missing Slack channel target."}

        try:
            resp = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json; charset=utf-8"},
                json={"channel": channel, "text": text},
                timeout=10,
            )
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            if not resp.ok or not body.get("ok", False):
                return {"ok": False, "channel": self.name, "error": f"Slack API error: {body or resp.text}"}
            return {"ok": True, "channel": self.name, "target": channel, "text": text}
        except Exception as exc:
            return {"ok": False, "channel": self.name, "error": str(exc)}


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
