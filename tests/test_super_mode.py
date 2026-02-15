from pathlib import Path
from types import SimpleNamespace

from jarvis.supervisor.orchestrator import SuperOrchestrator


def _mk_config(tmp_path: Path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
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
