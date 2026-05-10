from typing import Optional, List, Dict, Any, Tuple, Union
import ast
import json
import os
from pathlib import Path
import re
import threading
import time
import traceback


def _noop(*_args, **_kwargs):
    return None


try:
    from llm_ollama import OllamaLLM
except ImportError:
    try:
        from .llm_ollama import OllamaLLM
    except ImportError:
        OllamaLLM = None

try:
    from tts_local import TextToSpeech
except ImportError:
    try:
        from .tts_local import TextToSpeech
    except ImportError:
        TextToSpeech = None

try:
    from tools.safety import confirm_action, ensure_system_access, ensure_scope_access
except ImportError:
    try:
        from .tools.safety import confirm_action, ensure_system_access, ensure_scope_access
    except ImportError:
        confirm_action = lambda *a, **k: True
        ensure_system_access = lambda *a, **k: True
        ensure_scope_access = lambda *a, **k: True

try:
    from tools.apps import close_app, open_app, save_app_path
except ImportError:
    try:
        from .tools.apps import close_app, open_app, save_app_path
    except ImportError:
        close_app = open_app = save_app_path = _noop

try:
    from tools.files import list_dir, read_file, search_files, write_file
except ImportError:
    try:
        from .tools.files import list_dir, read_file, search_files, write_file
    except ImportError:
        list_dir = read_file = search_files = write_file = _noop

try:
    from tools.commands import run_command
except ImportError:
    try:
        from .tools.commands import run_command
    except ImportError:
        run_command = _noop

try:
    from tools.browser import browser_task
except ImportError:
    try:
        from .tools.browser import browser_task
    except ImportError:
        browser_task = lambda *a, **k: ""

try:
    from tools.desktop_operator import desktop_task
except ImportError:
    try:
        from .tools.desktop_operator import desktop_task
    except ImportError:
        desktop_task = lambda *a, **k: ""

try:
    from tools.vision import capture_and_analyze, analyze_image, extract_video_frame
except ImportError:
    try:
        from .tools.vision import capture_and_analyze, analyze_image, extract_video_frame
    except ImportError:
        capture_and_analyze = analyze_image = extract_video_frame = lambda *a, **k: ""

try:
    from tools.automation import type_text, press_key, scroll, mouse_click, move_mouse, hotkey
except ImportError:
    try:
        from .tools.automation import type_text, press_key, scroll, mouse_click, move_mouse, hotkey
    except ImportError:
        type_text = press_key = scroll = mouse_click = move_mouse = hotkey = _noop

try:
    from tools.system_ops import (
        get_system_status,
        get_clipboard_text,
        set_clipboard_text,
        get_active_window_title,
        optimize_system,
    )
except ImportError:
    try:
        from .tools.system_ops import (
            get_system_status,
            get_clipboard_text,
            set_clipboard_text,
            get_active_window_title,
            optimize_system,
        )
    except ImportError:
        get_system_status = lambda *a, **k: {"cpu_percent": 0, "ram_percent": 0}
        get_clipboard_text = lambda *a, **k: ""
        set_clipboard_text = lambda *a, **k: None
        get_active_window_title = lambda *a, **k: ""
        optimize_system = lambda *a, **k: ""

try:
    from tools.coach_rules import detect_issue
except ImportError:
    try:
        from .tools.coach_rules import detect_issue
    except ImportError:
        detect_issue = lambda *a, **k: None

try:
    from tools.multimedia import play_on_youtube, open_google, open_website
except ImportError:
    try:
        from .tools.multimedia import play_on_youtube, open_google, open_website
    except ImportError:
        play_on_youtube = open_google = open_website = lambda *a, **k: None

try:
    from plugins.home_automation import IoT
except ImportError:
    IoT = None

try:
    from memory.db import MemoryDB
except ImportError:
    try:
        from .memory.db import MemoryDB
    except ImportError:
        class MemoryDB:
            def __init__(self):
                pass
            def start_session(self, *a, **k):
                pass
            def add_turn(self, *a, **k):
                pass
            def get_context(self, *a, **k):
                return []
            def create_task(self, *a, **k):
                return ""
            def update_task(self, *a, **k):
                return None
            def add_task_step(self, *a, **k):
                return None
            def log_tool_event(self, *a, **k):
                return None
            def record_evaluation(self, *a, **k):
                return None
            def list_tasks(self, *a, **k):
                return []
            def search_conversation(self, *a, **k):
                return []
            def add_knowledge(self, *a, **k):
                return None
            def search_knowledge(self, *a, **k):
                return []
            def save_routine(self, *a, **k):
                return None
            def get_routine(self, *a, **k):
                return None
            def list_routines(self, *a, **k):
                return []

try:
    from planner import TaskPlanner
except ImportError:
    try:
        from .planner import TaskPlanner
    except ImportError:
        class TaskPlanner:
            def __init__(self, *a, **k):
                pass
            def create_roadmap(self, *a, **k):
                return {"phases": []}
            def build_local_tool_plan(self, *a, **k):
                return {"plan": []}
            def fallback_recovery(self, *a, **k):
                return {"retry": False}
            def evaluate_result(self, goal: str, result: Any):
                return {"goal": goal, "success": True, "score": 1.0, "summary": str(result)}
try:
    from rag_system import HybridRAGSystem
except ImportError:
    try:
        from .rag_system import HybridRAGSystem
    except ImportError:
        HybridRAGSystem = None
try:
    import cv2
except ImportError:
    cv2 = None
    print("Warning: opencv-python not found. Vision features will be disabled.")

class Agent:
    def __init__(self, config, tts: "TextToSpeech", gui: Any = None):
        self.config = config
        self.tts = tts
        self.gui = gui
        if OllamaLLM is not None:
            self.llm = OllamaLLM(config)
        else:
            raise ImportError("OllamaLLM could not be imported. Please ensure llm_ollama.py is available.")
        self.memory = MemoryDB()
        self.session_id = f"session_{int(time.time())}"
        self.memory.start_session(self.session_id)
        
        self.planner = TaskPlanner(self.llm)
        self.active = False
        self.active_lock = threading.Lock()  # Fix: Add thread-safe lock for active flag
        self.last_interaction: Optional[float] = None
        self.timeout = 300  # 5 minutes
        
        self.monitor_thread = threading.Thread(target=self.monitor_timeout, daemon=True)
        self.monitor_thread.start()
        self.max_plan_steps = int(os.getenv("AGENT_MAX_PLAN_STEPS", "8"))
        self.execution_retry_limit = max(1, int(os.getenv("AGENT_TOOL_RETRIES", "2")))
        self._last_spoken_text = ""
        self._last_spoken_at = 0.0
        self.phone = None
        self.phone_autonomous_runner = None
        self.current_task_id = None
        self.rag = HybridRAGSystem(self.memory) if HybridRAGSystem is not None else None
        self.diagnostic_reporter = None
        
        self.system_prompt = (
            "Tum JARVIS ho. User ko hamesha 'Boss' kaho. "
            "Zabaan: sirf natural Roman Urdu. "
            "Agar user English me bole tab bhi by-default Roman Urdu me short jawab do, "
            "jab tak user explicitly English na mange.\n\n"
            "Agar kisi tool/action ki zarurat ho to yeh format use karo:\n"
            "[[roman urdu response]]\n"
            "###PLAN###\n"
            '{"plan":[{"action":"tool_name","args":{}}]}\n\n'
            "Agar tool ki zarurat na ho to seedha response do, plan dena lazmi nahi.\n\n"
            "Rules:\n"
            "1) Response me English long sentences avoid karo.\n"
            "2) Agar plan do to JSON valid ho aur key 'plan' required ho.\n"
            "3) Agar task complete ho gaya ho to {'plan':[]} do.\n"
            "4) Tool output milne ke baad next step decide karo.\n"
            "5) In available actions ko prefer karo: open_app, close_app, save_app_path, "
            "read_file, write_file, list_dir, search_files, list_tasks, search_memory, add_knowledge, search_knowledge, "
            "save_routine, list_routines, run_routine, run_command, get_system_status, desktop_task, "
            "search_google, browser_task, open_website, play_on_youtube, get_clipboard_text, "
            "set_clipboard_text, get_active_window_title, optimize_system, type_text, press_key, "
            "scroll, mouse_click, move_mouse, hotkey, capture_and_analyze, analyze_image, "
            "phone_control, phone_autonomous, turn_on_lights, turn_off_lights, set_temperature, "
            "lock_doors, unlock_doors.\n"
            "6) Agar simple command seedha kisi ek tool se solve hoti ho to sirf ek step ka plan do."
        )

    def set_gui(self, gui):
        self.gui = gui

    def set_diagnostic_reporter(self, reporter):
        self.diagnostic_reporter = reporter

    def _report_runtime_diagnostic(
        self,
        kind: str,
        message: Any,
        *,
        context: str = "",
        level: str = "error",
        traceback_text: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not callable(self.diagnostic_reporter):
            return
        payload = {
            "kind": str(kind or "runtime_issue"),
            "level": str(level or "error").lower(),
            "message": str(message or ""),
            "context": str(context or ""),
            "traceback": str(traceback_text or ""),
            "extra": extra or {},
            "session_id": self.session_id,
            "task_id": self.current_task_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        try:
            self.diagnostic_reporter(payload)
        except Exception:
            pass

    def monitor_timeout(self):
        """Return the agent to idle mode after long inactivity."""
        while True:
            time.sleep(5)
            with self.active_lock:
                if not self.active or self.last_interaction is None:
                    continue
                if (time.time() - self.last_interaction) < self.timeout:
                    continue
                self.active = False
            timeout_msg = "Boss, kaafi dair se koi naya input nahi aya, main idle mode me chala gaya hoon."
            if self.gui:
                self.gui.update_status("Idle")
                self.gui.update_transcript("Jarvis", timeout_msg)
            if self._should_speak(timeout_msg):
                self.tts.speak(timeout_msg)

    def _fallback_for_plan(self, plan_data: Optional[dict] = None) -> str:
        plan = []
        if isinstance(plan_data, dict):
            maybe_plan = plan_data.get("plan", [])
            if isinstance(maybe_plan, list):
                plan = maybe_plan
        if not plan:
            return "Ji Boss, samajh gaya. Abhi karta hoon."

        action = str((plan[0] or {}).get("action", "")).strip().replace("_", " ")
        if action:
            return f"Ji Boss, pehle '{action}' run karta hoon."
        return "Ji Boss, abhi process karta hoon."

    def _prepare_spoken_response(self, text: str, plan_data: Optional[dict] = None) -> str:
        """Normalize model text while preserving useful content."""
        raw = str(text or "")
        raw = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).replace("```", "")
        raw = raw.replace("[[", "").replace("]]", "")
        raw = re.sub(r"\s+", " ", raw).strip()
        if "###PLAN###" in raw:
            raw = raw.split("###PLAN###", 1)[0].strip()

        low = raw.lower()
        bad_markers = (
            "i cannot",
            "i can't",
            "as an ai",
            "not in any language i can recognize",
            "there seems to be a mix-up",
            "llm service unavailable",
            "ollama start karein",
        )
        looks_like_json = raw.lstrip().startswith(("{", "["))
        if (not raw) or looks_like_json or any(marker in low for marker in bad_markers):
            return self._fallback_for_plan(plan_data)

        return raw

    def _should_speak(self, text: str) -> bool:
        now = time.time()
        normalized = re.sub(r"\s+", " ", str(text or "")).strip().lower()
        if not normalized:
            return False
        if normalized == self._last_spoken_text and (now - self._last_spoken_at) < 20:
            return False
        self._last_spoken_text = normalized
        self._last_spoken_at = now
        return True

    def _generate_llm_text(self, prompt: str, images: Optional[List[str]] = None) -> str:
        """Compatibility wrapper for LLM clients with generate or generate_stream."""
        # Primary path: direct generate()
        if hasattr(self.llm, "generate"):
            try:
                if images:
                    result = self.llm.generate(prompt, images=images)
                else:
                    result = self.llm.generate(prompt)
                if isinstance(result, str):
                    return result
            except TypeError:
                # Some clients don't accept images kwarg.
                result = self.llm.generate(prompt)
                if isinstance(result, str):
                    return result

        # Fallback path: stream chunks
        if hasattr(self.llm, "generate_stream"):
            chunks = []
            for chunk in self.llm.generate_stream(prompt):
                chunks.append(str(chunk))
            return "".join(chunks)

        return ""

    def _direct_plan(self, response: str, action: str, args: Optional[Dict[str, Any]] = None) -> Tuple[str, dict]:
        return response, {"plan": [{"action": action, "args": args or {}}], "continue_with_llm": False}

    def _memory_call(self, method: str, *args, **kwargs):
        fn = getattr(self.memory, method, None)
        if not callable(fn):
            return None
        try:
            return fn(*args, **kwargs)
        except Exception:
            return None

    def _is_error_result(self, result: Any) -> bool:
        if isinstance(result, dict):
            status = str(result.get("status", "")).lower()
            if status in {"error", "unknown", "denied"}:
                return True
        text = str(result or "").lower()
        return any(token in text for token in ("error", "failed", "denied", "missing", "unavailable"))

    def _should_retry_action(self, action: str, detail: Any) -> bool:
        retryable = {"browser_task", "desktop_task", "phone_control", "analyze_image", "capture_and_analyze", "run_command"}
        if action not in retryable:
            return False
        text = str(detail or "").lower()
        return any(
            token in text
            for token in ("timeout", "tempor", "connection", "network", "busy", "try again", "timed out")
        )

    def _record_task_evaluation(self, task_id: Optional[str], goal: str, result: Any):
        if not task_id:
            return
        evaluation = self.planner.evaluate_result(goal, result) if hasattr(self.planner, "evaluate_result") else {
            "success": not self._is_error_result(result),
            "score": 0.0 if self._is_error_result(result) else 1.0,
            "summary": str(result)[:300],
        }
        self._memory_call(
            "record_evaluation",
            self.session_id,
            "task",
            "completion",
            evaluation.get("score", 0.0),
            {
                "goal": goal,
                "success": evaluation.get("success", False),
                "summary": evaluation.get("summary", ""),
            },
            task_id=task_id,
        )

    def _folder_alias_path(self, text: str) -> Optional[Path]:
        lowered = (text or "").lower()
        home = Path.home()
        aliases = {
            "desktop": home / "Desktop",
            "documents": home / "Documents",
            "document": home / "Documents",
            "downloads": home / "Downloads",
            "download": home / "Downloads",
        }
        for alias, path in aliases.items():
            if alias in lowered:
                return path
        return None

    def _maybe_handle_local_intent(self, text: str, image_data: Optional[str] = None) -> Optional[Tuple[str, dict]]:
        raw = str(text or "").strip()
        lowered = re.sub(r"\s+", " ", raw.lower())
        if not lowered:
            return None

        if any(phrase in lowered for phrase in ("system status", "pc status", "computer status", "cpu ram", "ram status")):
            return self._direct_plan("Ji Boss, system status nikal raha hoon.", "get_system_status")

        if any(phrase in lowered for phrase in ("optimize system", "cleanup system", "clean memory", "optimize pc")):
            return self._direct_plan("Ji Boss, system cleanup report nikal raha hoon.", "optimize_system")

        if any(phrase in lowered for phrase in ("clipboard me kya hai", "what is in clipboard", "show clipboard", "read clipboard")):
            return self._direct_plan("Ji Boss, clipboard check karta hoon.", "get_clipboard_text")

        if any(phrase in lowered for phrase in ("recent tasks", "show tasks", "last tasks", "meri recent tasks")):
            return self._direct_plan("Ji Boss, recent tasks nikal raha hoon.", "list_tasks")

        if any(phrase in lowered for phrase in ("list routines", "show routines", "meri routines")):
            return self._direct_plan("Ji Boss, routines dikha raha hoon.", "list_routines")

        match = re.search(r"^(?:search memory for|remember about|find in memory)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan(
                "Ji Boss, memory me dhoond raha hoon.",
                "search_memory",
                {"query": match.group(1).strip()},
            )

        match = re.search(r"^(?:search knowledge for|find in knowledge)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan(
                "Ji Boss, knowledge base me dhoond raha hoon.",
                "search_knowledge",
                {"query": match.group(1).strip()},
            )

        match = re.search(r"^(?:remember that|save note|remember note)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            content = match.group(1).strip()
            title = content[:48]
            return self._direct_plan(
                "Ji Boss, yeh baat yaad rakh leta hoon.",
                "add_knowledge",
                {"title": title, "content": content},
            )

        match = re.search(r"^(?:save routine|create routine)\s+(.+?)\s+(?:as|for)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan(
                "Ji Boss, routine save karta hoon.",
                "save_routine",
                {"name": match.group(1).strip(), "goal": match.group(2).strip()},
            )

        match = re.search(r"^(?:run routine|start routine)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan(
                "Ji Boss, routine chala raha hoon.",
                "run_routine",
                {"name": match.group(1).strip()},
            )

        match = re.search(r"^(?:copy|clipboard par copy karo|copy to clipboard)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan(
                "Ji Boss, text clipboard me rakh diya jayega.",
                "set_clipboard_text",
                {"text": match.group(1).strip()},
            )

        if any(phrase in lowered for phrase in ("active window", "current window", "which window is open")):
            return self._direct_plan("Ji Boss, active window dekh raha hoon.", "get_active_window_title")

        if any(phrase in lowered for phrase in ("analyze screen", "screen analyze", "what is on screen", "screen par kya hai", "see my screen")):
            return self._direct_plan(
                "Ji Boss, screen dekh kar batata hoon.",
                "capture_and_analyze",
                {"prompt": "Screen par kya nazar aa raha hai? Short Roman Urdu me batao."},
            )

        match = re.search(r"^(?:open website|open site|visit)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            target = match.group(1).strip()
            return self._direct_plan(f"Ji Boss, {target} open karta hoon.", "open_website", {"url": target})

        match = re.search(r"^(?:search(?: google| web| browser)? for|google karo|web search karo)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            return self._direct_plan(f"Ji Boss, '{query}' search karta hoon.", "search_google", {"query": query})

        match = re.search(r"^(?:browse|browser task)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            goal = match.group(1).strip()
            return self._direct_plan(f"Ji Boss, browser me '{goal}' dekh raha hoon.", "browser_task", {"goal": goal})

        match = re.search(r"^(?:desktop do|on desktop|desktop task)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            goal = match.group(1).strip()
            return self._direct_plan("Ji Boss, desktop workflow run karta hoon.", "desktop_task", {"goal": goal})

        match = re.search(r"^(?:play|play on youtube|youtube par chalao)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            return self._direct_plan(f"Ji Boss, YouTube par '{query}' chala raha hoon.", "play_on_youtube", {"query": query})

        match = re.search(r"^(?:open|launch|start)\s+(.+?)(?:\s+app)?$", raw, re.IGNORECASE)
        if match and "." not in match.group(1):
            app = match.group(1).strip()
            if app.lower() not in {"website", "site"}:
                return self._direct_plan(f"Ji Boss, {app} open karta hoon.", "open_app", {"name": app})

        match = re.search(r"^(?:close|exit|band karo)\s+(.+?)(?:\s+app)?$", raw, re.IGNORECASE)
        if match:
            app = match.group(1).strip()
            return self._direct_plan(f"Ji Boss, {app} close karta hoon.", "close_app", {"name": app})

        match = re.search(r"^remember app\s+(.+?)\s+at\s+(.+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan(
                "Ji Boss, app path save karta hoon.",
                "save_app_path",
                {"name": match.group(1).strip(), "path": match.group(2).strip()},
            )

        folder = self._folder_alias_path(lowered)
        if folder and any(phrase in lowered for phrase in ("show", "list", "check", "open")) and "folder" in lowered:
            return self._direct_plan(
                "Ji Boss, folder ka content dikha raha hoon.",
                "list_dir",
                {"path": str(folder)},
            )

        match = re.search(r"^(?:search files for|find file|find files)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            root = self._folder_alias_path(lowered)
            query = re.sub(r"\s+in\s+(desktop|documents|downloads)\s*$", "", query, flags=re.IGNORECASE).strip()
            args = {"query": query}
            if root is not None:
                args["root"] = str(root)
            return self._direct_plan(f"Ji Boss, '{query}' files dhoond raha hoon.", "search_files", args)

        match = re.search(r"^read file\s+(.+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan("Ji Boss, file read karta hoon.", "read_file", {"path": match.group(1).strip()})

        match = re.search(
            r"^(?:create|write)\s+(?:a\s+)?file\s+named\s+(.+?)\s+on\s+(desktop|documents|downloads)\s+with\s+content\s+(.+)$",
            raw,
            re.IGNORECASE,
        )
        if match:
            file_name = match.group(1).strip()
            folder_name = match.group(2).strip().lower()
            content = match.group(3).strip()
            base = self._folder_alias_path(folder_name) or (Path.home() / folder_name.capitalize())
            return self._direct_plan(
                "Ji Boss, file create karta hoon.",
                "write_file",
                {"path": str(base / file_name), "content": content},
            )

        match = re.search(r"^(?:type|likho)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan("Ji Boss, text type karta hoon.", "type_text", {"text": match.group(1).strip()})

        match = re.search(r"^(?:press|key press)\s+([a-zA-Z_]+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan("Ji Boss, key press karta hoon.", "press_key", {"key": match.group(1).strip()})

        if "scroll down" in lowered:
            return self._direct_plan("Ji Boss, neeche scroll karta hoon.", "scroll", {"amount": -600})
        if "scroll up" in lowered:
            return self._direct_plan("Ji Boss, upar scroll karta hoon.", "scroll", {"amount": 600})

        match = re.search(r"^(?:click at|mouse click)\s+(\d+)\s*[,\s]\s*(\d+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan(
                "Ji Boss, mouse click karta hoon.",
                "mouse_click",
                {"x": int(match.group(1)), "y": int(match.group(2))},
            )

        match = re.search(r"^(?:move mouse to|mouse move)\s+(\d+)\s*[,\s]\s*(\d+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan(
                "Ji Boss, mouse move karta hoon.",
                "move_mouse",
                {"x": int(match.group(1)), "y": int(match.group(2))},
            )

        match = re.search(r"^(?:hotkey|shortcut)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            keys = [part.strip() for part in re.split(r"\s*\+\s*|\s+", match.group(1).strip()) if part.strip()]
            if keys:
                return self._direct_plan("Ji Boss, hotkey press karta hoon.", "hotkey", {"keys": keys})

        if lowered in {"phone status", "mobile status"}:
            return self._direct_plan("Ji Boss, phone status check karta hoon.", "phone_control", {"action": "status"})
        if lowered in {"phone screenshot", "mobile screenshot"}:
            return self._direct_plan("Ji Boss, phone screenshot leta hoon.", "phone_control", {"action": "screenshot"})
        if lowered in {"phone read screen", "read phone screen", "phone screen"}:
            return self._direct_plan("Ji Boss, phone screen read karta hoon.", "phone_control", {"action": "read_screen"})

        match = re.search(r"^phone open\s+(.+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan("Ji Boss, phone par app open karta hoon.", "phone_control", {"action": "open_app", "app": match.group(1).strip()})

        match = re.search(r"^phone search\s+(.+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan("Ji Boss, phone par search karta hoon.", "phone_control", {"action": "voice_command", "text": f"search {match.group(1).strip()}"})

        match = re.search(r"^phone type\s+(.+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan("Ji Boss, phone par type karta hoon.", "phone_control", {"action": "type_text", "text": match.group(1).strip()})

        match = re.search(r"^phone tap\s+(\d+)\s*[,\s]\s*(\d+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan(
                "Ji Boss, phone par tap karta hoon.",
                "phone_control",
                {"action": "tap", "x": int(match.group(1)), "y": int(match.group(2))},
            )

        match = re.search(r"^phone press\s+([a-zA-Z_]+)$", raw, re.IGNORECASE)
        if match:
            return self._direct_plan("Ji Boss, phone key press karta hoon.", "phone_control", {"action": "press_key", "key": match.group(1).strip()})

        match = re.search(r"^(?:phone do|phone command|on phone)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            goal = match.group(1).strip()
            if any(word in goal.lower() for word in ("open", "search", "message", "call", "scroll", "tap")):
                return self._direct_plan("Ji Boss, phone command run karta hoon.", "phone_control", {"action": "voice_command", "text": goal})
            return self._direct_plan("Ji Boss, phone task autonomous mode me shuru karta hoon.", "phone_autonomous", {"goal": goal})

        if hasattr(self.planner, "build_local_tool_plan"):
            built = self.planner.build_local_tool_plan(raw)
            if isinstance(built, dict) and built.get("plan"):
                return (
                    built.get("response") or "Ji Boss, local workflow plan bana diya hai.",
                    {
                        "plan": built.get("plan", []),
                        "continue_with_llm": bool(built.get("continue_with_llm", False)),
                    },
                )

        return None

    def handle_transcript(self, text: str, image_data: Optional[str] = None):
        """Handles user transcript, generates an initial plan, and starts execution."""
        with self.active_lock:
            if not self.active:
                self.active = True
                self.last_interaction = time.time()
                if self.gui: self.gui.update_status("Active")

        self.last_interaction = time.time()
        task_id = self._memory_call(
            "create_task",
            goal=text,
            session_id=self.session_id,
            status="planning",
            source="chat",
            metadata={"has_image": bool(image_data)},
        )
        self.current_task_id = task_id
        
        # Add user input to memory and GUI
        self.memory.add_turn("User", text, session_id=self.session_id)
        if self.gui: self.gui.update_transcript("User", text)

        try:
            if self.gui: self.gui.update_status("Thinking...")
            local_plan = self._maybe_handle_local_intent(text, image_data=image_data)
            if local_plan is not None:
                res_text, plan_data = local_plan
            else:
                history = self.memory.get_context(limit=5, session_id=self.session_id)
                context = "\n".join([f"{m['role']}: {m['content']}" for m in history])
                prompt = f"{self.system_prompt}\n\nRecent History:\n{context}\n\nUser Input: '{text}'"
                if image_data:
                    prompt += "\n[IMAGE DATA ATTACHED]"

                llm_response_text = self._generate_llm_text(
                    prompt, images=[image_data] if image_data else None
                )
                res_text, plan_data = self._parse_llm_response(llm_response_text)
                res_text = self._prepare_spoken_response(res_text, plan_data)
            
            if self.gui: self.gui.update_transcript("Jarvis", res_text)
            self.memory.add_turn("Jarvis", res_text, session_id=self.session_id)
            if res_text and self._should_speak(res_text):
                self.tts.speak(res_text)

            if isinstance(plan_data, dict):
                plan_data.setdefault("task_id", task_id)
                plan_data.setdefault("goal", text)
            if task_id:
                next_status = "running" if plan_data.get("plan") else "completed"
                self._memory_call("update_task", task_id, status=next_status, notes=res_text)
                if not plan_data.get("plan"):
                    self._record_task_evaluation(task_id, text, res_text)

            # Start the plan execution loop in a new thread
            if plan_data.get("plan"):
                threading.Thread(target=self._handle_plan, args=(plan_data,), daemon=True).start()

        except Exception as e:
            print(f"[Agent] Error in handle_transcript: {e}")
            tb_text = traceback.format_exc()
            print(tb_text, end="")
            error_msg = "Maafi Boss, kuch technical masla aa gaya."
            self.tts.speak(error_msg)
            if self.gui: self.gui.update_transcript("Jarvis", error_msg)
            if self.gui: self.gui.update_status("Idle")
            self._report_runtime_diagnostic(
                "chat_exception",
                e,
                context="agent.handle_transcript",
                traceback_text=tb_text,
                extra={"user_input": str(text or "")[:300], "has_image": bool(image_data)},
            )
            if task_id:
                self._memory_call("update_task", task_id, status="failed", notes=error_msg)
                self._record_task_evaluation(task_id, text, error_msg)
    
    def _handle_plan(self, plan_data: dict):
        """Executes a plan step-by-step, feeding back tool outputs to the LLM."""
        plan = plan_data.get("plan", [])
        continue_with_llm = bool(plan_data.get("continue_with_llm", True))
        task_id = plan_data.get("task_id")
        goal = str(plan_data.get("goal", "")).strip()
        step_index = 0  # Fix: Use index instead of pop to avoid losing state on error
        executed_steps = 0
        seen_steps: Dict[str, int] = {}
        last_result: Any = ""
        task_success = True
        
        while step_index < len(plan):
            with self.active_lock:
                if not self.active:
                    print("[Agent] Plan execution cancelled as agent is inactive.")
                    task_success = False
                    break

            executed_steps += 1
            if executed_steps > self.max_plan_steps:
                msg = "Boss, plan loop lamba ho gaya tha, maine yahin stop kiya. Aap next command dein."
                if self.gui: self.gui.update_transcript("Jarvis", msg)
                if self._should_speak(msg):
                    self.tts.speak(msg)
                break

            step = plan[step_index]
            action_name = step.get("action", "unknown")
            step_sig = json.dumps(step, ensure_ascii=False, sort_keys=True)
            seen_steps[step_sig] = seen_steps.get(step_sig, 0) + 1
            if seen_steps[step_sig] > 2:
                msg = f"Boss, '{action_name}' repeat ho raha tha, maine safe stop kar diya."
                if self.gui: self.gui.update_transcript("Jarvis", msg)
                if self._should_speak(msg):
                    self.tts.speak(msg)
                break
            
            try:
                if self.gui: self.gui.update_status(f"Executing: {action_name}")
                if task_id:
                    self._memory_call(
                        "add_task_step",
                        task_id,
                        step_index,
                        action_name,
                        step.get("args", step.get("params", {})),
                        status="executing",
                    )
                tool_output = self._execute_step(step, task_id=task_id)
                last_result = tool_output
                
                # Format tool output for the LLM
                tool_result_prompt = f"[TOOL_OUTPUT: {str(tool_output)}]"
                self.memory.add_turn("User", tool_result_prompt, session_id=self.session_id)
                if self.gui: self.gui.update_transcript("System", f"Tool Output: {str(tool_output)}")

                if task_id:
                    step_status = "failed" if self._is_error_result(tool_output) else "completed"
                    self._memory_call(
                        "add_task_step",
                        task_id,
                        step_index,
                        action_name,
                        step.get("args", step.get("params", {})),
                        status=step_status,
                        result_text=str(tool_output),
                    )

                if self._is_error_result(tool_output):
                    self._report_runtime_diagnostic(
                        "tool_error_result",
                        tool_output,
                        context=action_name,
                        extra={
                            "goal": goal,
                            "step_index": step_index,
                            "task_id": task_id,
                            "args": step.get("args", step.get("params", {})),
                        },
                    )
                    task_success = False
                    recovery = (
                        self.planner.fallback_recovery(step, str(tool_output))
                        if hasattr(self.planner, "fallback_recovery")
                        else {"retry": False}
                    )
                    reasoning = recovery.get("reasoning", "")
                    if task_id:
                        self._memory_call("update_task", task_id, status="recovering", notes=reasoning or str(tool_output))
                    if recovery.get("alternative_action"):
                        if self.gui and reasoning:
                            self.gui.update_transcript("Jarvis", f"Boss, recovery mode: {reasoning}")
                        plan = [recovery["alternative_action"]] + plan[step_index + 1:]
                        continue_with_llm = False
                        step_index = 0
                        task_success = True
                        continue

                if not continue_with_llm:
                    step_index += 1
                    continue

                # Get the next step from the LLM
                history = self.memory.get_context(limit=7, session_id=self.session_id)
                context = "\n".join([f"{m['role']}: {m['content']}" for m in history])
                prompt = f"{self.system_prompt}\n\nRecent History:\n{context}\n\nUser Input: '{tool_result_prompt}'"
                
                if self.gui: self.gui.update_status("Thinking...")
                llm_response_text = self._generate_llm_text(prompt)
                
                res_text, new_plan_data = self._parse_llm_response(llm_response_text)
                res_text = self._prepare_spoken_response(res_text, new_plan_data)
                
                if res_text:
                    if self.gui: self.gui.update_transcript("Jarvis", res_text)
                    self.memory.add_turn("Jarvis", res_text, session_id=self.session_id)
                    if self._should_speak(res_text):
                        self.tts.speak(res_text)

                plan = new_plan_data.get("plan", [])
                continue_with_llm = bool(new_plan_data.get("continue_with_llm", True))
                step_index = 0  # Reset index for new plan

            except Exception as e:
                print(f"[Agent] Step Execution Error ({action_name}): {e}")
                tb_text = traceback.format_exc()
                print(tb_text, end="")
                error_msg = f"Maafi Boss, '{action_name}' tool mein masla aa gaya."
                self.tts.speak(error_msg)
                if self.gui: self.gui.update_transcript("Jarvis", error_msg)
                self._report_runtime_diagnostic(
                    "tool_exception",
                    e,
                    context=action_name,
                    traceback_text=tb_text,
                    extra={
                        "goal": goal,
                        "step_index": step_index,
                        "task_id": task_id,
                        "args": step.get("args", step.get("params", {})),
                    },
                )
                task_success = False
                last_result = error_msg
                if task_id:
                    self._memory_call("update_task", task_id, status="failed", notes=error_msg)
                break # Stop plan execution on error
        
        if self.gui: self.gui.update_status("Idle")
        if task_id:
            final_status = "completed" if task_success else "failed"
            self._memory_call("update_task", task_id, status=final_status, notes=str(last_result)[:500])
            self._record_task_evaluation(task_id, goal or "task", last_result or final_status)
        print("[Agent] Plan execution complete.")

    def _execute_step(self, step: dict, task_id: Optional[str] = None):
        """Execute one step with retries, audit logging, and evaluation metadata."""
        action = step.get('action', '')
        args = step.get('args', step.get('params', {}))
        attempt = 0

        while attempt < self.execution_retry_limit:
            attempt += 1
            started = time.time()
            try:
                result = self._execute_action(action, args)
                duration_ms = int((time.time() - started) * 1000)
                self._memory_call(
                    "log_tool_event",
                    self.session_id,
                    action,
                    args=args,
                    result=result,
                    success=not self._is_error_result(result),
                    duration_ms=duration_ms,
                    task_id=task_id,
                    metadata={"attempt": attempt},
                )
                if self._is_error_result(result) and attempt < self.execution_retry_limit and self._should_retry_action(action, result):
                    time.sleep(min(1.5, 0.5 * attempt))
                    continue
                return result
            except Exception as exc:
                duration_ms = int((time.time() - started) * 1000)
                self._memory_call(
                    "log_tool_event",
                    self.session_id,
                    action,
                    args=args,
                    result="",
                    success=False,
                    duration_ms=duration_ms,
                    task_id=task_id,
                    error_text=str(exc),
                    metadata={"attempt": attempt},
                )
                if attempt < self.execution_retry_limit and self._should_retry_action(action, exc):
                    time.sleep(min(1.5, 0.5 * attempt))
                    continue
                raise

        return f"Tool Error: '{action}' exhausted retries"

    def _execute_action(self, action: str, args: dict):
        """Routes a single plan step to the appropriate tool function."""

        # Smart Home & IoT Automation
        if action == "turn_on_lights" and IoT:
            result = IoT.turn_on_lights()
            if self._should_speak(result): self.tts.speak(result)
            return result
        elif action == "turn_off_lights" and IoT:
            result = IoT.turn_off_lights()
            if self._should_speak(result): self.tts.speak(result)
            return result
        elif action == "set_temperature" and IoT:
            result = IoT.set_temperature(args.get("temp", 24))
            if self._should_speak(result): self.tts.speak(result)
            return result
        elif action == "lock_doors" and IoT:
            result = IoT.lock_doors()
            if self._should_speak(result): self.tts.speak(result)
            return result
        elif action == "unlock_doors" and IoT:
            result = IoT.unlock_doors()
            if self._should_speak(result): self.tts.speak(result)
            return result

        # Autonomous Self-Healing
        elif action == "diagnose_and_fix":
            return self._diagnose_and_fix(
                traceback_text=args.get("error", ""),
                file_path=args.get("file_path", ""),
                command=args.get("command", "")
            )

        # Standard System Tools
        elif action == "run_command":
            cmd = args.get('command')
            if cmd and confirm_action(f"Run command: {cmd}"):
                return run_command(cmd)
            return "Command denied or missing"

        elif action == "open_app":
            app = args.get('app_name', args.get('name'))
            if app:
                return open_app(app)
            return "Missing app name"

        elif action == "close_app":
            app = args.get('app_name', args.get('name'))
            if app:
                if confirm_action(f"Close app: {app}"):
                    return close_app(app)
                return "Close app denied"
            return "Missing app name"

        elif action == "save_app_path":
            app = args.get('app_name', args.get('name'))
            path = args.get('path')
            if app and path:
                return save_app_path(app, path)
            return "Missing app name or path"

        elif action == "read_file":
            path = args.get('path')
            return read_file(path) if path else "Missing path"

        elif action == "write_file":
            path = args.get('path')
            content = args.get('content')
            if path and content:
                if confirm_action(f"Write to file: {path}"):
                    return write_file(path, content)
            return "Denied or missing"

        elif action == "list_dir":
            path = args.get('path', '.')
            return list_dir(path)

        elif action == "search_files":
            query = args.get('query', '')
            root = args.get('root')
            if query:
                return search_files(query, root)
            return "Missing search query"

        elif action == "get_system_status":
            return get_system_status()

        elif action == "list_tasks":
            tasks = self._memory_call("list_tasks", self.session_id, 10) or []
            if not tasks:
                return "Recent tasks available nahi."
            return "\n".join(
                f"- {item.get('status', 'unknown')}: {item.get('goal', '')}"
                for item in tasks[:5]
            )

        elif action == "search_memory":
            query = args.get('query', '')
            if query:
                matches = self._memory_call("search_conversation", query, session_id=self.session_id, limit=5) or []
                knowledge = self._memory_call("search_knowledge", query, session_id=self.session_id, limit=5) or []
                rag_matches = self.rag.retrieve(query, session_id=self.session_id, limit=5) if self.rag is not None else []
                lines = []
                if matches:
                    lines.extend(
                        f"{item.get('role', 'Unknown')}: {item.get('content', '')}"
                        for item in matches
                    )
                if knowledge:
                    lines.extend(
                        f"Knowledge[{item.get('title', 'note')}]: {item.get('content', '')}"
                        for item in knowledge
                    )
                if rag_matches:
                    lines.extend(
                        f"RAG[{item.get('source', 'memory')}]: {item.get('content', '')}"
                        for item in rag_matches[:3]
                    )
                if not lines:
                    return f"'{query}' memory me nahi mila."
                return "\n".join(lines[:8])
            return "Missing memory query"

        elif action == "add_knowledge":
            title = args.get('title', '').strip() or "Note"
            content = args.get('content', '').strip()
            tags = args.get('tags', [])
            if content:
                self._memory_call("add_knowledge", title, content, session_id=self.session_id, tags=tags, source="user")
                if self.rag is not None:
                    self.rag.add_knowledge(title, content, session_id=self.session_id, tags=tags, source="user")
                return f"Knowledge save ho gayi: {title}"
            return "Missing knowledge content"

        elif action == "search_knowledge":
            query = args.get('query', '')
            if query:
                results = self._memory_call("search_knowledge", query, session_id=self.session_id, limit=5) or []
                if self.rag is not None:
                    results = results + self.rag.search_knowledge(query, session_id=self.session_id, limit=3)
                if not results:
                    return f"Knowledge base me '{query}' nahi mila."
                return "\n".join(
                    f"- {item.get('title', item.get('source', 'note'))}: {item.get('content', '')}"
                    for item in results[:6]
                )
            return "Missing knowledge query"

        elif action == "save_routine":
            name = args.get('name', '').strip()
            goal = args.get('goal', '').strip()
            steps = args.get('steps', [])
            if name and goal:
                self._memory_call("save_routine", name, goal, steps=steps, session_id=self.session_id)
                return f"Routine save ho gayi: {name}"
            return "Missing routine name or goal"

        elif action == "list_routines":
            routines = self._memory_call("list_routines", self.session_id, 10) or []
            if not routines:
                return "Routines available nahi."
            return "\n".join(
                f"- {item.get('routine_name', '')}: {item.get('goal', '')}"
                for item in routines[:10]
            )

        elif action == "run_routine":
            name = args.get('name', '').strip()
            routine = self._memory_call("get_routine", name)
            if not routine:
                return f"Routine '{name}' nahi mili."
            steps = routine.get("steps") or []
            if steps:
                outputs = []
                for routine_step in steps[:8]:
                    if isinstance(routine_step, dict) and routine_step.get("action"):
                        outputs.append(str(self._execute_step(routine_step, task_id=self.current_task_id)))
                return f"Routine '{name}' run ho gayi: " + " | ".join(outputs)
            goal = routine.get("goal", "")
            return self._execute_action("desktop_task", {"goal": goal}) if goal else f"Routine '{name}' me goal missing hai."

        elif action == "get_clipboard_text":
            text = get_clipboard_text()
            return text or "Clipboard khali hai."

        elif action == "set_clipboard_text":
            text = args.get('text', '')
            if text:
                return "Clipboard update ho gaya." if set_clipboard_text(text) else "Clipboard update nahi ho saka."
            return "Missing clipboard text"

        elif action == "get_active_window_title":
            title = get_active_window_title()
            return title or "Active window title available nahi."

        elif action == "optimize_system":
            if confirm_action("System cleanup report run karoon?"):
                return optimize_system()
            return "System optimization denied"

        elif action == "type_text":
            text_to_type = args.get('text', '')
            if text_to_type:
                if ensure_scope_access("automation", "keyboard automation"):
                    return type_text(text_to_type)
                return "Automation access denied"
        
        elif action == "press_key":
            key = args.get('key', '')
            if key:
                if ensure_scope_access("automation", "keyboard automation"):
                    return press_key(key)
                return "Automation access denied"

        elif action == "scroll":
            amount = int(args.get('amount', 0))
            if ensure_scope_access("automation", "mouse scroll"):
                return scroll(amount)
            return "Automation access denied"

        elif action == "mouse_click":
            x = args.get('x')
            y = args.get('y')
            if ensure_scope_access("automation", "mouse click"):
                return mouse_click(x, y)
            return "Automation access denied"

        elif action == "move_mouse":
            x = args.get('x')
            y = args.get('y')
            if x is not None and y is not None:
                if ensure_scope_access("automation", "mouse movement"):
                    return move_mouse(int(x), int(y))
                return "Automation access denied"
            return "Missing mouse coordinates"

        elif action == "hotkey":
            keys = args.get('keys', [])
            if keys:
                if ensure_scope_access("automation", "hotkey automation"):
                    return hotkey(*keys)
                return "Automation access denied"
            return "Missing hotkey keys"
                
        elif action == "play_on_youtube":
            query = args.get('query', '')
            if query:
                return play_on_youtube(query)

        elif action == "search_google":
            query = args.get('query', '')
            if query:
                return open_google(query)
            return open_google()

        elif action == "open_website":
            url = args.get('url', '')
            if url:
                return open_website(url)
            return "Missing website URL"

        elif action == "browser_task":
            goal = args.get('goal', '')
            if goal:
                if ensure_scope_access("browser", "browser automation"):
                    return browser_task(goal)
                return "Browser access denied"
            return "Missing browser task goal"

        elif action == "desktop_task":
            goal = args.get('goal', '')
            if goal:
                if ensure_scope_access("automation", "desktop operator"):
                    return desktop_task(goal)
                return "Automation access denied"
            return "Missing desktop goal"

        elif action == "capture_and_analyze":
            prompt = args.get('prompt', 'Screen par kya hai?')
            if ensure_scope_access("automation", "screen capture"):
                return capture_and_analyze(self.config, prompt)
            return "Screen capture access denied"

        elif action == "analyze_image":
            path = args.get('path', '')
            prompt = args.get('prompt', 'Is image me kya hai?')
            if path:
                return analyze_image(self.config, path, prompt)
            return "Missing image path"

        elif action == "phone_control":
            if self.phone is None:
                return "Phone control available nahi hai."
            return self.phone.handle_command(args)

        elif action == "phone_autonomous":
            goal = args.get('goal', '')
            if not goal:
                return "Missing phone goal"
            if callable(self.phone_autonomous_runner):
                self.phone_autonomous_runner(goal)
                return f"Phone autonomous task start kar diya: {goal}"
            return "Phone autonomous runner configured nahi."

        return f"Tool Error: Unsupported action '{action}'"

    def _diagnose_and_fix(self, traceback_text: str, file_path: str = "", command: str = ""):
        """Autonomous self-healing logic triggered by an error."""
        self.tts.speak("Boss, error detect hua hai. Main abhi fixing ki koshish kar raha hoon.")
        if self.gui: self.gui.update_status("Diagnosing...")
        
        file_content = ""
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
            except Exception as e:
                return f"Could not read file: {e}"
                
        prompt = f"Error Traceback:\n{traceback_text}\n\n"
        if file_content:
            prompt += f"Target File Content ({file_path}):\n{file_content}\n\n"
        prompt += f"System Command Being Run: {command}\n\n"
        prompt += "You are JARVIS's diagnostic system. Output ONLY the new code to replace the file content. Exclude ALL markdown backticks (no ```python). Just the exact new raw source code that fixes the problem. If no file context, describe the fix needed."

        new_code = self._generate_llm_text(prompt)
        new_code = new_code.replace("```python", "").replace("```", "").strip()
        
        if file_path and new_code:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_code)
                self.tts.speak("Code patch automatically apply kar diya gaya hai. Testing next phase.")
                if command:
                    return run_command(command)
                return "Patch applied successfully."
            except Exception as e:
                return f"Failed to apply patch: {e}"
                
        return f"Diagnostics output (No active file patched): {new_code}"

    def _parse_llm_response(self, response_text: str) -> Tuple[str, dict]:
        """Parses the LLM's raw text response to separate conversational text and a JSON plan."""
        response_text = str(response_text or "")
        res_text = response_text
        plan_data = {"plan": []}

        try:
            if "###PLAN###" in response_text:
                parts = response_text.split("###PLAN###", 1)
                res_text = parts[0].replace("[[", "").replace("]]", "").strip()
                potential_json = re.sub(r"```json\s*|\s*```", "", parts[1]).strip()
                parsed = self._parse_json_candidate(potential_json)

                if parsed is None:
                    obj_match = re.search(r"(\{[\s\S]*\})", potential_json)
                    arr_match = re.search(r"(\[[\s\S]*\])", potential_json)
                    candidate = obj_match.group(1) if obj_match else (arr_match.group(1) if arr_match else "")
                    if candidate:
                        parsed = self._parse_json_candidate(candidate)

                plan_data = self._normalize_plan_data(parsed)
            else:
                cleaned = re.sub(r"```(?:json)?", "", response_text, flags=re.IGNORECASE).replace("```", "").strip()
                parsed = self._parse_json_candidate(cleaned)

                if isinstance(parsed, dict):
                    if isinstance(parsed.get("plan"), list):
                        plan_data = {"plan": parsed.get("plan", [])}
                    for key in ("response", "text", "message", "reply"):
                        value = parsed.get(key)
                        if isinstance(value, str) and value.strip():
                            res_text = value.strip()
                            break
                    else:
                        if isinstance(parsed.get("plan"), list):
                            res_text = ""
                elif isinstance(parsed, list):
                    plan_data = {"plan": parsed}
                    res_text = ""
                else:
                    trailing_plan = re.search(r"(\{[\s\S]*\"plan\"\s*:\s*\[[\s\S]*\]\s*\})\s*$", cleaned)
                    if trailing_plan:
                        parsed = self._parse_json_candidate(trailing_plan.group(1))
                        normalized = self._normalize_plan_data(parsed)
                        if normalized["plan"]:
                            plan_data = normalized
                            prefix = cleaned[: trailing_plan.start()].strip()
                            if prefix:
                                res_text = prefix
                            else:
                                res_text = ""
        except Exception as e:
            print(f"[Agent] Error parsing LLM response: {e}. Using empty plan.")
            # Ensure res_text is the full response if parsing fails
            res_text = response_text.replace("[[", "").replace("]]", "").strip().split("###PLAN###")[0]
            plan_data = {"plan": []}

        if not str(res_text).strip():
            cleaned = re.sub(r"###PLAN###.*", "", response_text, flags=re.DOTALL)
            cleaned = cleaned.replace("[[", "").replace("]]", "").strip()
            if cleaned and not cleaned.lstrip().startswith(("{", "[")):
                res_text = cleaned

        return res_text, plan_data

    def _normalize_plan_data(self, parsed: Any) -> dict:
        if isinstance(parsed, dict):
            maybe_plan = parsed.get("plan", [])
            if isinstance(maybe_plan, list):
                return {"plan": [s for s in maybe_plan if isinstance(s, dict)]}
            return {"plan": []}
        if isinstance(parsed, list):
            return {"plan": [s for s in parsed if isinstance(s, dict)]}
        return {"plan": []}

    def _parse_json_candidate(self, raw_text: str) -> Optional[Union[dict, list]]:
        text = str(raw_text or "").strip()
        if not text:
            return None

        try:
            return json.loads(text)
        except Exception:
            pass

        repaired = self._repair_json(text)
        if repaired != text:
            try:
                parsed = json.loads(repaired)
                print("[Agent] JSON repaired successfully.")
                return parsed
            except Exception:
                pass

        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception:
            pass
        return None

    def _repair_json(self, faulty_json: str) -> str:
        """Attempts to fix common JSON errors from LLMs."""
        repaired = faulty_json
        repaired = re.sub(r"'(\w+)':", r'"\1":', repaired)
        repaired = re.sub(r":\s*'([^']*)'", r': "\1"', repaired)
        repaired = re.sub(r'(?<!")(\b\w+\b)(?=\s*:)', r'"\1"', repaired)
        repaired = re.sub(r',\s*([\]}])', r'\1', repaired)
        repaired = re.sub(r"([}\]\"0-9])\s+(\"[^\"]+\"\s*:)", r"\1, \2", repaired)
        repaired = re.sub(r"\bTrue\b", "true", repaired)
        repaired = re.sub(r"\bFalse\b", "false", repaired)
        repaired = re.sub(r"\bNone\b", "null", repaired)
        return repaired
    # --- File handling methods ---
    def handle_file(self, file_path: str):
        if not self.active:
            with self.active_lock:
                self.active = True
                if self.gui:
                    self.gui.update_status("Active")
        self.last_interaction = time.time()
        
        ext = file_path.lower().split('.')[-1]
        
        if ext in ['jpg', 'jpeg', 'png']:
            self.tts.speak("Ji boss, main is tasvir ko dekh raha hoon.")
            analysis = analyze_image(self.config, file_path)
            self.tts.speak(analysis)
            if self.gui: self.gui.update_transcript("Jarvis (Vision)", f"File: {os.path.basename(file_path)}\n\n{analysis}")
            
        elif ext in ['mp4', 'avi', 'mkv']:
            self.tts.speak("Ji boss, main video analyze kar raha hoon.")
            try:
                temp_image = extract_video_frame(file_path)

                frame_analysis = analyze_image(
                    self.config, temp_image, "Summarize this video frame briefly."
                )
                summary_prompt = (
                    "Summarize this video frame analysis in one concise response:\n"
                    f"{frame_analysis}"
                )
                summary = self._generate_llm_text(summary_prompt) or frame_analysis
                self.tts.speak(summary)
                if self.gui:
                    self.gui.update_transcript("Jarvis (Vision)", summary)

                try:
                    os.remove(temp_image)
                except Exception:
                    pass
            except Exception as e:
                self.tts.speak(f"Boss, video analysis mein masla aya: {e}")
        
        elif ext == 'pdf':
            self.tts.speak("Ji boss, main PDF file parh raha hoon.")
            try:
                try:
                    import PyPDF2 as pypdf2
                except ImportError:
                    import pypdf2

                text_content = ""
                with open(file_path, 'rb') as f:
                    reader = pypdf2.PdfReader(f)
                    for page in reader.pages:
                        text_content += page.extract_text() or ""
                if text_content.strip():
                    summary_prompt = f"Yeh PDF ka content hai:\n{text_content[:3000]}\n\nRoman Urdu mein short summary do."
                    self.handle_transcript(summary_prompt)
                else:
                    msg = "Boss, is PDF mein text nahi mila, shayad scanned image hai."
                    self.tts.speak(msg)
                    if self.gui:
                        self.gui.update_transcript("Jarvis", msg)
            except ImportError:
                try:
                    import pypdf

                    text_content = ""
                    with open(file_path, 'rb') as f:
                        reader = pypdf.PdfReader(f)
                        for page in reader.pages:
                            text_content += page.extract_text() or ""
                    if text_content.strip():
                        summary_prompt = f"Yeh PDF ka content hai:\n{text_content[:3000]}\n\nRoman Urdu mein short summary do."
                        self.handle_transcript(summary_prompt)
                    else:
                        msg = "Boss, is PDF mein text nahi mila."
                        self.tts.speak(msg)
                        if self.gui:
                            self.gui.update_transcript("Jarvis", msg)
                except Exception as e:
                    msg = f"Boss, PDF parh nahi saka: {e}"
                    self.tts.speak(msg)
                    if self.gui:
                        self.gui.update_transcript("Jarvis", msg)
            except Exception as e:
                msg = f"Boss, PDF mein masla: {e}"
                self.tts.speak(msg)
                if self.gui:
                    self.gui.update_transcript("Jarvis", msg)
        
        else:
            self.tts.speak(f"Boss, main abhi {ext} files analyze nahi kar sakta, magar future mein zaroor karunga!")
    
    def handle_stop(self):
        with self.active_lock:
            if self.active:
                self.active = False
                if self.gui: self.gui.update_status("Idle")
                self.tts.speak("Theek hai sir, offline ja raha hoon. Allah hafiz.")
