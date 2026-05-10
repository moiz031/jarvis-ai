from pathlib import Path
from types import SimpleNamespace

from jarvis.supervisor.orchestrator import SuperOrchestrator


def _mk_config(tmp_path: Path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / "plugin_policy.json").write_text(
        '{"enabled_plugins":["demo"],"blocked_imports":["subprocess","socket","ctypes","os","sys","multiprocessing"],"blocked_builtins":["eval","exec","compile","__import__","open","input","breakpoint"]}\n',
        encoding="utf-8",
    )
    (plugins_dir / "demo.py").write_text(
        """
def register(runtime):
    runtime.register_plugin("demo", "demo plugin")
    runtime.register_action("demo", "demo.echo", lambda payload: payload, "echo payload")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return SimpleNamespace(
        SUPER_STATE_PATH=tmp_path / "super_state.json",
        SUPER_CHANNELS_PATH=tmp_path / "super_channels.json",
        SUPER_POLICY_PATH=tmp_path / "super_policy.json",
        SUPER_DIRECTORY_PATH=tmp_path / "super_directory.json",
        SUPER_VAULT_PATH=tmp_path / "super_vault.json",
        SUPER_VAULT_KEY_PATH=tmp_path / "super_vault.key",
        SUPER_PLUGINS_DIR=plugins_dir,
        MAX_AGENT_WORKERS=1,
        LOW_RAM_MODE=True,
    )


def test_super_orchestrator_onboarding_and_commands(tmp_path):
    cfg = _mk_config(tmp_path)
    emitted = []
    dispatched = []

    def emit(msg_type, data):
        emitted.append((msg_type, data))

    def agent_callback(text, _image):
        dispatched.append(text)
        return {"ok": True}

    sup = SuperOrchestrator(cfg, emit=emit, agent_callback=agent_callback)

    onboard = sup.onboard(
        {
            "permission_profile": "power",
            "allowlist_users": ["tester"],
            "connect_channels": ["telegram"],
        }
    )
    assert onboard["ok"] is True

    blocked = sup.handle_text("hello", source="ui", user_id="not-allowed", metadata={})
    assert blocked["ok"] is False

    allowed = sup.handle_text("hello boss", source="ui", user_id="tester", metadata={})
    assert allowed["ok"] is True
    assert dispatched[-1] == "hello boss"

    plugins = sup.handle_text("/super plugins", source="ui", user_id="tester", metadata={})
    assert plugins["ok"] is True

    plugin_run = sup.handle_text('/plugin run demo.echo {"x":1}', source="ui", user_id="tester", metadata={"confirmed": True})
    assert plugin_run["ok"] is True
    assert plugin_run["data"]["result"]["x"] == 1


def test_plugin_runtime_blocks_dangerous_imports(tmp_path):
    cfg = _mk_config(tmp_path)
    (cfg.SUPER_PLUGINS_DIR / "plugin_policy.json").write_text(
        '{"enabled_plugins":["demo","evil"],"blocked_imports":["subprocess","socket","ctypes","os","sys","multiprocessing"],"blocked_builtins":["eval","exec","compile","__import__","open","input","breakpoint"]}\n',
        encoding="utf-8",
    )
    (cfg.SUPER_PLUGINS_DIR / "evil.py").write_text(
        """
import subprocess

def register(runtime):
    runtime.register_plugin("evil", "bad plugin")
    runtime.register_action("evil", "evil.run", lambda payload: payload, "danger")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    sup = SuperOrchestrator(cfg, emit=lambda *_: None, agent_callback=lambda *_: {"ok": True})
    loaded, errors = sup.plugins.reload()
    assert "demo" in loaded
    assert any(err.startswith("evil: blocked import 'subprocess'") for err in errors)


def test_capability_evolver_plugin_runs_analysis_and_evolution(tmp_path):
    cfg = _mk_config(tmp_path)
    repo_root = Path(__file__).resolve().parents[1]
    source_plugin = repo_root / "jarvis" / "plugins" / "capability_evolver.py"
    target_plugin = cfg.SUPER_PLUGINS_DIR / "capability_evolver.py"
    target_plugin.write_text(source_plugin.read_text(encoding="utf-8"), encoding="utf-8")
    (cfg.SUPER_PLUGINS_DIR / "plugin_policy.json").write_text(
        '{"enabled_plugins":["demo","capability_evolver"],"blocked_imports":["subprocess","socket","ctypes","os","sys","multiprocessing"],"blocked_builtins":["eval","exec","compile","__import__","open","input","breakpoint"]}\n',
        encoding="utf-8",
    )

    sup = SuperOrchestrator(cfg, emit=lambda *_: None, agent_callback=lambda *_: {"ok": True})
    loaded, errors = sup.plugins.reload()
    assert "capability_evolver" in loaded
    assert errors == []

    status = sup.plugins.execute("capability_evolver.status", {})
    assert status["ok"] is True
    assert status["result"]["skill"] == "capability-evolver"
    assert "analyze" in status["result"]["supported_actions"]

    logs = [
        {"timestamp": "2026-04-25T10:00:00Z", "level": "error", "message": "ETIMEDOUT", "context": "jarvis/tools/browser.py"},
        {"timestamp": "2026-04-25T10:01:00Z", "level": "error", "message": "ETIMEDOUT", "context": "jarvis/tools/browser.py"},
        {"timestamp": "2026-04-25T10:02:00Z", "level": "error", "message": "ETIMEDOUT", "context": "jarvis/tools/browser.py"},
        {"timestamp": "2026-04-25T10:03:00Z", "level": "warn", "message": "Retry queue backing up", "context": "jarvis/core_engine.py"},
        {"timestamp": "2026-04-25T10:04:00Z", "level": "info", "message": "Speech pipeline slow: 2500ms", "context": "jarvis/tts_local.py"},
        {"timestamp": "2026-04-25T10:05:00Z", "level": "info", "message": "Intent routing timeout after 3000ms", "context": "jarvis/planner.py"},
    ]

    analysis = sup.plugins.execute("capability_evolver.analyze", {"logs": logs})
    assert analysis["ok"] is True
    assert analysis["result"]["health_score"] < 60
    assert analysis["result"]["summary"]["unique_patterns"] >= 2
    assert any(pattern["type"] == "regression" for pattern in analysis["result"]["patterns"])
    assert any("Hot files" in item for item in analysis["result"]["recommendations"])

    evolution = sup.plugins.execute(
        "capability_evolver.run",
        {"action": "evolve", "logs": logs, "strategy": "auto"},
    )
    assert evolution["ok"] is True
    assert evolution["result"]["strategy"] == "harden"
    assert evolution["result"]["recommendations"]
    assert evolution["result"]["risk_assessment"]["level"] == "low"
