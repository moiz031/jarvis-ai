from pathlib import Path

from jarvis.planner import TaskPlanner
from jarvis.rag_system import HybridRAGSystem
from jarvis.tools import vision as vision_mod
from jarvis.tools.browser import BrowserOperator
from jarvis.tools.desktop_operator import DesktopOperator


class DummyLLM:
    def generate(self, prompt: str):
        return '{"ok": true}'


def test_browser_operator_builds_multistep_plan():
    operator = BrowserOperator(headless=True)

    plan = operator.plan_goal("open youtube.com and search lofi hip hop")

    actions = [step.action for step in plan]
    assert actions[:3] == ["goto", "type_search", "open_first_result"]
    assert actions[-1] == "summarize"


def test_planner_fallback_recovery_for_browser():
    planner = TaskPlanner(DummyLLM())

    recovery = planner.fallback_recovery(
        {"action": "browser_task", "args": {"goal": "search jarvis ai"}},
        "timeout while opening page",
    )

    assert recovery["alternative_action"]["action"] == "search_google"
    assert "jarvis ai" in recovery["alternative_action"]["args"]["query"]


def test_memory_db_task_and_search_roundtrip(tmp_path, monkeypatch):
    import jarvis.memory.db as db_mod

    if db_mod.MemoryDB._instance is not None:
        try:
            db_mod.MemoryDB._instance.conn.close()
        except Exception:
            pass
    db_mod.MemoryDB._instance = None
    db_mod.MemoryDB._initialized = False
    monkeypatch.setattr(db_mod, "DB_PATH", Path(tmp_path) / "memory.db")

    db = db_mod.MemoryDB()
    session_id = "workflow_test"
    db.start_session(session_id)
    db.add_turn("User", "remember budget plan", session_id=session_id)
    task_id = db.create_task("check budget", session_id=session_id, status="running")
    db.add_task_step(task_id, 0, "search_memory", {"query": "budget"}, status="completed", result_text="found")
    db.log_tool_event(session_id, "search_memory", args={"query": "budget"}, result="found", task_id=task_id)
    db.record_evaluation(session_id, "task", "completion", 1.0, {"goal": "check budget"}, task_id=task_id)

    tasks = db.list_tasks(session_id=session_id, limit=5)
    matches = db.search_conversation("budget", session_id=session_id, limit=5)

    assert tasks
    assert tasks[0]["goal"] == "check budget"
    assert matches
    assert matches[0]["content"] == "remember budget plan"


def test_memory_db_routine_and_knowledge_roundtrip(tmp_path, monkeypatch):
    import jarvis.memory.db as db_mod

    if db_mod.MemoryDB._instance is not None:
        try:
            db_mod.MemoryDB._instance.conn.close()
        except Exception:
            pass
    db_mod.MemoryDB._instance = None
    db_mod.MemoryDB._initialized = False
    monkeypatch.setattr(db_mod, "DB_PATH", Path(tmp_path) / "memory.db")

    db = db_mod.MemoryDB()
    session_id = "routine_test"
    db.start_session(session_id)
    db.add_knowledge("wifi note", "wifi password is hidden safely", session_id=session_id, tags=["wifi"])
    db.save_routine("morning", "open notepad and type hello", steps=[{"action": "desktop_task", "args": {"goal": "open notepad and type hello"}}], session_id=session_id)

    routine = db.get_routine("morning")
    knowledge = db.search_knowledge("wifi", session_id=session_id, limit=5)

    assert routine is not None
    assert routine["goal"] == "open notepad and type hello"
    assert knowledge
    assert knowledge[0]["title"] == "wifi note"
    snapshot = db.get_dashboard_snapshot(session_id=session_id)
    assert snapshot["knowledge_count"] >= 1
    assert snapshot["routines"]


def test_hybrid_rag_retrieves_from_memory(tmp_path, monkeypatch):
    import jarvis.memory.db as db_mod

    if db_mod.MemoryDB._instance is not None:
        try:
            db_mod.MemoryDB._instance.conn.close()
        except Exception:
            pass
    db_mod.MemoryDB._instance = None
    db_mod.MemoryDB._initialized = False
    monkeypatch.setattr(db_mod, "DB_PATH", Path(tmp_path) / "memory.db")

    db = db_mod.MemoryDB()
    session_id = "rag_test"
    db.start_session(session_id)
    db.add_turn("User", "my favorite editor is vscode", session_id=session_id)
    db.add_knowledge("editor pref", "user likes vscode for coding", session_id=session_id)
    rag = HybridRAGSystem(db)

    results = rag.retrieve("vscode coding", session_id=session_id, limit=5)

    assert results
    assert "vscode" in results[0]["content"].lower()


def test_desktop_operator_executes_split_workflow(monkeypatch):
    import jarvis.tools.desktop_operator as desktop_mod

    calls = []
    monkeypatch.setattr(desktop_mod, "open_app", lambda name: calls.append(("open", name)) or f"opened {name}")
    monkeypatch.setattr(desktop_mod, "type_text", lambda text: calls.append(("type", text)) or f"typed {text}")
    monkeypatch.setattr(desktop_mod, "press_key", lambda key: calls.append(("press", key)) or f"pressed {key}")

    result = DesktopOperator(sleeper=lambda *_: None).execute("open notepad and type hello then press enter")

    assert ("open", "notepad") in calls
    assert ("type", "hello") in calls
    assert ("press", "enter") in calls
    assert "Desktop workflow complete" in result


def test_extract_video_frame_uses_runtime_helper_when_cv2_missing(monkeypatch, tmp_path):
    target = tmp_path / "frame.jpg"
    monkeypatch.setattr(vision_mod, "cv2", None)
    monkeypatch.setattr(
        vision_mod,
        "_run_runtime_helper",
        lambda command, *args: {"ok": True, "path": str(target)},
    )

    result = vision_mod.extract_video_frame("sample.mp4", str(target))

    assert result == str(target)
