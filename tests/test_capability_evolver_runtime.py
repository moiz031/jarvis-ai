from threading import Lock
from types import SimpleNamespace

from jarvis.core_engine import CoreEngine


class StubPlugins:
    def __init__(self):
        self.calls = []

    def execute(self, action, payload):
        self.calls.append((action, payload))
        if action == "capability_evolver.analyze":
            return {
                "ok": True,
                "result": {
                    "health_score": 45,
                    "patterns": [
                        {
                            "type": "regression",
                            "severity": "high",
                            "description": "browser timeout",
                            "occurrences": 2,
                            "affected_files": ["browser_task"],
                        }
                    ],
                    "recommendations": ["Add retries", "Improve monitoring"],
                    "summary": {"unique_patterns": 1},
                },
            }
        if action == "capability_evolver.evolve":
            return {
                "ok": True,
                "result": {
                    "strategy": "harden",
                    "recommendations": [{"priority": "high", "description": "Add monitoring"}],
                },
            }
        return {"ok": False, "error": "unexpected action"}


def _make_engine_for_runtime_tests():
    engine = CoreEngine.__new__(CoreEngine)
    engine.auto_capability_evolver = True
    engine.capability_evolver_cooldown_s = 30
    engine.capability_evolver_buffer_limit = 25
    engine._capability_lock = Lock()
    engine._capability_logs = []
    engine._capability_last_run = 0.0
    engine._capability_last_fingerprint = ""
    engine._capability_last_issue_fingerprint = ""
    engine.super_orchestrator = SimpleNamespace(plugins=StubPlugins())
    engine_events = []
    engine._emit = lambda kind, data: engine_events.append((kind, data))
    return engine, engine_events


def test_core_engine_runs_capability_evolver_on_agent_diagnostic():
    engine, events = _make_engine_for_runtime_tests()

    engine._handle_agent_diagnostic(
        {
            "kind": "tool_error_result",
            "message": "Tool Error: browser timeout",
            "context": "browser_task",
            "level": "error",
            "timestamp": "2026-04-25T10:00:00Z",
        }
    )

    calls = engine.super_orchestrator.plugins.calls
    assert calls[0][0] == "capability_evolver.analyze"
    assert calls[1][0] == "capability_evolver.evolve"
    assert events
    assert events[0][0] == "super_event"
    assert events[0][1]["type"] == "capability_analysis"
    assert events[0][1]["data"]["summary"]["health_score"] == 45


def test_core_engine_dedupes_repeated_runtime_analysis_within_cooldown():
    engine, events = _make_engine_for_runtime_tests()
    payload = {
        "kind": "tool_error_result",
        "message": "Tool Error: browser timeout",
        "context": "browser_task",
        "level": "error",
        "timestamp": "2026-04-25T10:00:00Z",
    }

    engine._handle_agent_diagnostic(payload)
    engine._handle_agent_diagnostic(payload)

    calls = engine.super_orchestrator.plugins.calls
    assert len(calls) == 2
    assert len(events) == 1
