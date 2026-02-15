# config.py - Configuration settings for Jarvis

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    from profiles import get_profile
    from security.secrets import secrets_manager
except ImportError:
    from .profiles import get_profile
    from .security.secrets import secrets_manager

try:
    import psutil
except Exception:
    psutil = None

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
    CONFIG_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    CONFIG_DIR = BASE_DIR

ENV_PATH = CONFIG_DIR / ".env"
if not ENV_PATH.exists():
    ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)


def _auto_profile_name(profile_name: str) -> str:
    requested = (profile_name or "").strip().lower()
    if requested and requested != "auto":
        return requested

    if psutil is None:
        return "balanced"

    try:
        ram_gb = psutil.virtual_memory().total / (1024**3)
        return "low_ram" if ram_gb <= 8.5 else "balanced"
    except Exception:
        return "balanced"


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    WAKE_PHRASE = "Jarvis, let's start"
    STOP_PHRASE = "Jarvis stop"

    PROFILE_NAME = _auto_profile_name(os.getenv("JARVIS_PROFILE", "auto"))
    PROFILE = get_profile(PROFILE_NAME)

    TTS_VOICE = secrets_manager.decrypt(os.getenv("TTS_VOICE", "ur_urdu"))

    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", PROFILE.llm_model)
    FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gpt-4o-mini")
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", PROFILE.whisper_model)

    OPENAI_API_KEY = secrets_manager.decrypt(os.getenv("OPENAI_API_KEY"))
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    ELEVENLABS_API_KEY = secrets_manager.decrypt(os.getenv("ELEVENLABS_API_KEY"))
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")

    KILL_HOTKEY = "ctrl+shift+k"

    LOW_RAM_MODE = _get_bool("JARVIS_LOW_RAM_MODE", PROFILE_NAME == "low_ram")
    MAX_AGENT_WORKERS = int(os.getenv("MAX_AGENT_WORKERS", "2" if LOW_RAM_MODE else "4"))

    APPS_JSON = CONFIG_DIR / "data" / "apps.json"
    MEMORY_DB = CONFIG_DIR / "data" / "memory.db"

    SUPER_STATE_PATH = CONFIG_DIR / "data" / "super_state.json"
    SUPER_CHANNELS_PATH = CONFIG_DIR / "data" / "super_channels.json"
    SUPER_POLICY_PATH = CONFIG_DIR / "data" / "super_policy.json"
    SUPER_DIRECTORY_PATH = CONFIG_DIR / "data" / "super_directory.json"
    SUPER_VAULT_PATH = CONFIG_DIR / "data" / "super_vault.json"
    SUPER_VAULT_KEY_PATH = CONFIG_DIR / "data" / "super_vault.key"
    SUPER_PLUGINS_DIR = BASE_DIR / "jarvis" / "plugins"

    def __init__(self):
        self.APPS_JSON.parent.mkdir(parents=True, exist_ok=True)
        self.MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
        self.SUPER_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_super_defaults()
        self._validate_config()

    def _ensure_super_defaults(self):
        if not self.SUPER_STATE_PATH.exists():
            self.SUPER_STATE_PATH.write_text(
                (
                    '{\n'
                    '  "onboarded": false,\n'
                    '  "permission_profile": "basic",\n'
                    '  "allowlist_users": ["local-admin"],\n'
                    '  "connected_channels": [],\n'
                    '  "system_access_granted": false,\n'
                    '  "system_access_prompted": false,\n'
                    '  "access_scopes": {\n'
                    '    "files": false,\n'
                    '    "browser": false,\n'
                    '    "automation": false\n'
                    '  }\n'
                    '}\n'
                ),
                encoding="utf-8",
            )

        if not self.SUPER_CHANNELS_PATH.exists():
            self.SUPER_CHANNELS_PATH.write_text('{"channels": {}}\n', encoding="utf-8")

        if not self.SUPER_POLICY_PATH.exists():
            self.SUPER_POLICY_PATH.write_text('{"profiles": {}}\n', encoding="utf-8")

        if not self.SUPER_DIRECTORY_PATH.exists():
            self.SUPER_DIRECTORY_PATH.write_text('{"contacts": {}}\n', encoding="utf-8")

    def as_dict(self):
        return {
            "wake_phrase": self.WAKE_PHRASE,
            "stop_phrase": self.STOP_PHRASE,
            "whisper_model": self.WHISPER_MODEL,
            "ollama_host": self.OLLAMA_HOST,
            "ollama_model": self.OLLAMA_MODEL,
            "fallback_model": self.FALLBACK_MODEL,
            "openai_api": bool(self.OPENAI_API_KEY),
            "elevenlabs_api": bool(self.ELEVENLABS_API_KEY),
            "tts_voice": self.TTS_VOICE,
            "kill_hotkey": self.KILL_HOTKEY,
            "profile_name": self.PROFILE_NAME,
            "low_ram_mode": self.LOW_RAM_MODE,
            "max_agent_workers": self.MAX_AGENT_WORKERS,
        }

    def _validate_config(self):
        warnings = []

        if not self.OLLAMA_HOST:
            warnings.append("[WARNING] OLLAMA_HOST not set. Using default: http://localhost:11434")

        if not self.OPENAI_API_KEY:
            warnings.append("[WARNING] OPENAI_API_KEY not set. Vision and cloud features will be limited.")

        if not self.ELEVENLABS_API_KEY:
            warnings.append("[WARNING] ELEVENLABS_API_KEY not set. Cloud TTS will not be available.")

        if warnings:
            print("\n" + "=" * 60)
            print("Configuration Warnings:")
            for warning in warnings:
                print(f"  {warning}")
            print("=" * 60 + "\n")
