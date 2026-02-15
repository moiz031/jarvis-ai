"""Built-in lightweight plugin examples for Super Mode."""

from __future__ import annotations

from datetime import datetime

try:
    import psutil
except Exception:
    psutil = None


def register(runtime):
    runtime.register_plugin("system_plugin", description="Basic system utilities for Super Mode")

    def sys_ping(payload):
        return {"pong": True, "timestamp": datetime.utcnow().isoformat(), "payload": payload}

    def sys_metrics(_payload):
        if psutil is None:
            return {"cpu": None, "ram": None, "note": "psutil unavailable"}
        vm = psutil.virtual_memory()
        return {"cpu": psutil.cpu_percent(interval=0.2), "ram_percent": vm.percent, "ram_total_gb": round(vm.total / (1024**3), 2)}

    runtime.register_action("system_plugin", "sys.ping", sys_ping, description="Simple heartbeat check.")
    runtime.register_action("system_plugin", "sys.metrics", sys_metrics, description="Return CPU and RAM metrics.")
