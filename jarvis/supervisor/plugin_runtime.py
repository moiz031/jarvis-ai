"""Plugin loader and action dispatcher."""

from __future__ import annotations

import ast
import importlib.util
import logging
import os
import hashlib
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)


class PluginRuntime:
    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.actions: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self.plugins: Dict[str, Dict[str, Any]] = {}
        self.policy_path = self.plugins_dir / "plugin_policy.json"
        self.plugin_policy = {
            "enabled_plugins": [],
            "blocked_imports": [
                "ctypes",
                "multiprocessing",
                "os",
                "socket",
                "subprocess",
                "sys",
            ],
            "blocked_builtins": ["eval", "exec", "compile", "__import__", "open", "input", "breakpoint"],
        }

    def register_action(self, plugin_name: str, action_name: str, handler: Callable[[Dict[str, Any]], Any], description: str = ""):
        key = action_name.strip()
        if not key:
            raise ValueError("action_name is required")
        if "." not in key:
            raise ValueError(f"Action '{key}' must be namespaced (for example '{plugin_name}.action').")
        self.actions[key] = handler
        self.plugins.setdefault(plugin_name, {"actions": {}, "description": ""})
        self.plugins[plugin_name]["actions"][key] = description

    def register_plugin(self, plugin_name: str, description: str = ""):
        self.plugins.setdefault(plugin_name, {"actions": {}, "description": description or ""})
        if description:
            self.plugins[plugin_name]["description"] = description

    def _load_policy(self):
        import json

        if not self.policy_path.exists():
            return
        try:
            with self.policy_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self.plugin_policy.update({k: v for k, v in data.items() if isinstance(v, list)})
        except Exception as exc:
            logger.warning("Plugin policy load failed: %s", exc)

    def _is_plugin_enabled(self, plugin_name: str) -> bool:
        enabled = self.plugin_policy.get("enabled_plugins", [])
        env_value = os.getenv("JARVIS_PLUGIN_ENFORCE_ALLOWLIST", "").strip().lower()
        enforce = env_value in {"1", "true", "yes", "on"} if env_value else bool(enabled)
        if not enforce:
            return True
        return plugin_name in enabled

    def _validate_plugin_source(self, path: Path):
        blocked_imports = set(self.plugin_policy.get("blocked_imports", []))
        blocked_builtins = set(self.plugin_policy.get("blocked_builtins", []))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_name = alias.name.split(".", 1)[0]
                    if root_name in blocked_imports:
                        raise RuntimeError(f"blocked import '{root_name}'")
            elif isinstance(node, ast.ImportFrom):
                root_name = (node.module or "").split(".", 1)[0]
                if root_name in blocked_imports:
                    raise RuntimeError(f"blocked import '{root_name}'")
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in blocked_builtins:
                    raise RuntimeError(f"blocked builtin '{func.id}'")

    def _digest(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

    def reload(self) -> Tuple[List[str], List[str]]:
        loaded: List[str] = []
        errors: List[str] = []
        self.actions.clear()
        self.plugins.clear()
        self._load_policy()

        for path in sorted(self.plugins_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            mod_name = f"jarvis_plugin_{path.stem}"
            try:
                if not self._is_plugin_enabled(path.stem):
                    raise RuntimeError("plugin is not allowlisted")
                self._validate_plugin_source(path)
                spec = importlib.util.spec_from_file_location(mod_name, str(path))
                if spec is None or spec.loader is None:
                    raise RuntimeError("spec/loader not found")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "register"):
                    module.register(self)
                else:
                    raise RuntimeError("register(runtime) not found")
                self.plugins.setdefault(path.stem, {"actions": {}, "description": ""})
                self.plugins[path.stem]["digest"] = self._digest(path)
                loaded.append(path.stem)
            except Exception as exc:
                if str(exc) == "plugin is not allowlisted":
                    logger.info("Plugin skipped by policy (%s)", path.name)
                    continue
                logger.warning("Plugin load failed (%s): %s", path.name, exc)
                errors.append(f"{path.stem}: {exc}")
        return loaded, errors

    def list_plugins(self):
        out = []
        for name, info in self.plugins.items():
            out.append(
                {
                    "name": name,
                    "description": info.get("description", ""),
                    "actions": sorted(info.get("actions", {}).keys()),
                    "digest": info.get("digest", ""),
                }
            )
        out.sort(key=lambda x: x["name"])
        return out

    def execute(self, action_name: str, payload: Dict[str, Any]):
        handler = self.actions.get(action_name)
        if handler is None:
            return {"ok": False, "error": f"Plugin action '{action_name}' not found."}
        try:
            result = handler(payload)
            return {"ok": True, "action": action_name, "result": result}
        except Exception as exc:
            return {"ok": False, "action": action_name, "error": str(exc)}
