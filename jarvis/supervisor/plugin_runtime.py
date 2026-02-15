"""Plugin loader and action dispatcher."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)


class PluginRuntime:
    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.actions: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self.plugins: Dict[str, Dict[str, Any]] = {}

    def register_action(self, plugin_name: str, action_name: str, handler: Callable[[Dict[str, Any]], Any], description: str = ""):
        key = action_name.strip()
        if not key:
            raise ValueError("action_name is required")
        self.actions[key] = handler
        self.plugins.setdefault(plugin_name, {"actions": {}, "description": ""})
        self.plugins[plugin_name]["actions"][key] = description

    def register_plugin(self, plugin_name: str, description: str = ""):
        self.plugins.setdefault(plugin_name, {"actions": {}, "description": description or ""})
        if description:
            self.plugins[plugin_name]["description"] = description

    def reload(self) -> Tuple[List[str], List[str]]:
        loaded: List[str] = []
        errors: List[str] = []
        self.actions.clear()
        self.plugins.clear()

        for path in sorted(self.plugins_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            mod_name = f"jarvis_plugin_{path.stem}"
            try:
                spec = importlib.util.spec_from_file_location(mod_name, str(path))
                if spec is None or spec.loader is None:
                    raise RuntimeError("spec/loader not found")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "register"):
                    module.register(self)
                else:
                    raise RuntimeError("register(runtime) not found")
                loaded.append(path.stem)
            except Exception as exc:
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
