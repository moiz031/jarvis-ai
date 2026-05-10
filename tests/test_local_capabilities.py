from unittest.mock import MagicMock

from jarvis.config import Config
from jarvis.agent import Agent
from jarvis import runtime_support
from jarvis.tts_local import TextToSpeech
from jarvis.tools import automation
from jarvis.tools import multimedia


def _make_agent(monkeypatch):
    fake_llm = MagicMock()
    monkeypatch.setattr("jarvis.agent.OllamaLLM", lambda config: fake_llm)
    return Agent(Config(), MagicMock(), MagicMock())


def test_open_google_supports_query(monkeypatch):
    opened = []
    monkeypatch.setattr(multimedia.webbrowser, "open", lambda url: opened.append(url))

    result = multimedia.open_google("jarvis ai")

    assert opened
    assert "google.com/search?q=jarvis+ai" in opened[0]
    assert "jarvis ai" in result.lower()


def test_local_intent_open_app(monkeypatch):
    agent = _make_agent(monkeypatch)

    response, plan_data = agent._maybe_handle_local_intent("open notepad")

    assert "notepad" in response.lower()
    assert plan_data["continue_with_llm"] is False
    assert plan_data["plan"][0]["action"] == "open_app"
    assert plan_data["plan"][0]["args"]["name"] == "notepad"


def test_local_intent_phone_command(monkeypatch):
    agent = _make_agent(monkeypatch)

    response, plan_data = agent._maybe_handle_local_intent("phone open whatsapp")

    assert "phone" in response.lower()
    assert plan_data["plan"][0]["action"] == "phone_control"
    assert plan_data["plan"][0]["args"]["action"] == "open_app"
    assert plan_data["plan"][0]["args"]["app"] == "whatsapp"


def test_agent_reports_diagnostics_for_failed_tool_results(monkeypatch):
    agent = _make_agent(monkeypatch)
    agent.active = True
    agent.tts.speak = MagicMock()
    agent.gui = MagicMock()
    agent._execute_step = lambda step, task_id=None: "Tool Error: browser timeout"
    events = []
    agent.set_diagnostic_reporter(lambda payload: events.append(payload))

    agent._handle_plan(
        {
            "plan": [{"action": "browser_task", "args": {"goal": "open youtube"}}],
            "continue_with_llm": False,
            "goal": "open youtube",
        }
    )

    assert events
    assert events[0]["kind"] == "tool_error_result"
    assert events[0]["context"] == "browser_task"
    assert "timeout" in events[0]["message"].lower()


def test_windows_sapi_fallback_invokes_powershell(monkeypatch):
    tts = TextToSpeech(Config())
    calls = {}

    class Result:
        returncode = 0
        stderr = ""

    def fake_run(cmd, input=None, text=None, capture_output=None, check=None, creationflags=None):
        calls["cmd"] = cmd
        calls["input"] = input
        return Result()

    monkeypatch.setattr("jarvis.tts_local.os.name", "nt")
    monkeypatch.setattr("jarvis.tts_local.subprocess.run", fake_run)

    assert tts._speak_windows_sapi("hello boss") is True
    assert calls["cmd"][0].lower() == "powershell"
    assert calls["input"] == "hello boss"


def test_sendkeys_fallback_types_without_pyautogui(monkeypatch):
    calls = {}

    class Result:
        returncode = 0
        stderr = ""

    def fake_run(cmd, capture_output=None, text=None, check=None, env=None, creationflags=None):
        calls["cmd"] = cmd
        calls["env"] = env
        return Result()

    monkeypatch.setattr("jarvis.tools.automation.pyautogui", None)
    monkeypatch.setattr("jarvis.tools.automation.subprocess.run", fake_run)

    result = automation.type_text("hello boss")

    assert result == "Typed: hello boss"
    assert calls["cmd"][0].lower() == "powershell"
    assert calls["env"]["JARVIS_SENDKEYS"] == "hello boss"


def test_find_ollama_exe_prefers_existing_candidate(monkeypatch):
    monkeypatch.setattr(runtime_support.shutil, "which", lambda _: None)
    monkeypatch.setattr(runtime_support, "_candidate_ollama_paths", lambda: [r"C:\fake\ollama.exe", r"C:\missing.exe"])
    monkeypatch.setattr("jarvis.runtime_support.Path.exists", lambda self: str(self) == r"C:\fake\ollama.exe")

    assert runtime_support.find_ollama_exe() == r"C:\fake\ollama.exe"
