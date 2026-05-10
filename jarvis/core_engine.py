# jarvis/core_engine.py - Main runtime engine with Super Mode integration

import logging
import os
import queue
import threading
import time
import traceback
import uuid
import re
from typing import Any, Dict

import requests

try:
    from agent import Agent
    from config import Config
    from stt_whisper_fixed import SpeechRecognizer
    from tts_local import TextToSpeech
    from tools import safety as safety_tools
    from tools.phone_tool import PhoneTool
    from planner import TaskPlanner
except ImportError:
    from .agent import Agent
    from .config import Config
    from .stt_whisper_fixed import SpeechRecognizer
    from .tts_local import TextToSpeech
    from .tools import safety as safety_tools
    from .tools.phone_tool import PhoneTool
    from .planner import TaskPlanner

try:
    from supervisor import SuperOrchestrator
except Exception:
    try:
        from .supervisor import SuperOrchestrator
    except Exception:
        SuperOrchestrator = None

try:
    from background_monitor import BackgroundMonitor
    from vision_monitor import VisionMonitor
except ImportError:
    BackgroundMonitor = VisionMonitor = None


try:
    from hotkey_listener import HotkeyListener
except Exception:
    try:
        from .hotkey_listener import HotkeyListener
    except Exception:
        HotkeyListener = None

try:
    from sound_fx import SoundFX
except Exception:
    try:
        from .sound_fx import SoundFX
    except Exception:
        class SoundFX:
            @staticmethod
            def play_wake():
                return None

            @staticmethod
            def play_processing():
                return None

logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class ConfirmationBroker:
    def __init__(self, emit, tts):
        self.emit = emit
        self.tts = tts
        self._pending = {}
        self._order = []
        self._lock = threading.Lock()

    def request(self, prompt: str, kind: str = "action", timeout: int = 35, default: bool = False) -> bool:
        request_id = str(uuid.uuid4())
        event = threading.Event()
        holder = {"approved": default}
        with self._lock:
            self._pending[request_id] = (event, holder)
            self._order.append(request_id)

        payload = {"id": request_id, "prompt": prompt, "kind": kind, "timeout": timeout}
        self.emit("confirm_request", payload)

        try:
            if self.tts:
                self.tts.speak(prompt)
        except Exception:
            pass

        approved = default
        if event.wait(timeout):
            approved = bool(holder.get("approved"))

        with self._lock:
            self._pending.pop(request_id, None)
        return approved

    def resolve(self, request_id: str, approved: bool) -> None:
        with self._lock:
            pending = self._pending.get(request_id)
            if request_id in self._order:
                self._order.remove(request_id)
        if not pending:
            return
        event, holder = pending
        holder["approved"] = bool(approved)
        event.set()

    def has_pending(self) -> bool:
        with self._lock:
            return bool(self._order)

    def resolve_latest(self, approved: bool) -> str | None:
        with self._lock:
            if not self._order:
                return None
            request_id = self._order[-1]
        self.resolve(request_id, approved)
        return request_id

    @staticmethod
    def parse_voice(text: str) -> bool | None:
        lowered = text.lower()
        tokens = re.findall(r"[a-zA-Z]+", lowered)
        yes = {"yes", "yeah", "yep", "ok", "okay", "allow", "confirm", "haan", "han", "ha", "ji", "theek", "sahi", "bilkul"}
        no = {"no", "nope", "nah", "nahi", "nahin", "deny", "cancel", "mat", "band", "ruko", "stop"}
        if any(tok in yes for tok in tokens):
            return True
        if any(tok in no for tok in tokens):
            return False
        return None


class CoreEngine(threading.Thread):
    def __init__(self, input_queue, output_queue):
        super().__init__(daemon=True)
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.running = True
        self.is_processing = False

        self.config = Config()
        self.mic_active = False
        self.auto_start_stt = _bool_env("JARVIS_AUTO_START_STT", False)
        self.enable_background_monitor = _bool_env("JARVIS_ENABLE_BACKGROUND_MONITOR", False)
        self.enable_vision_monitor = _bool_env("JARVIS_ENABLE_VISION_MONITOR", False)
        self.tts = TextToSpeech(self.config, self.output_queue)
        try:
            logger.info("TTS backend: %s", self.tts.describe_backend())
        except Exception:
            pass
        self.stt: SpeechRecognizer | None = None
        self.stt_thread: threading.Thread | None = None
        self.confirmations = ConfirmationBroker(self._emit, self.tts)
        safety_tools.set_confirm_handler(self.confirmations.request)

        self.agent = Agent(self.config, self.tts, gui=self._create_mock_gui())
        if hasattr(self.agent, "set_diagnostic_reporter"):
            self.agent.set_diagnostic_reporter(self._handle_agent_diagnostic)
        self.super_orchestrator = None
        self.auto_capability_evolver = _bool_env("JARVIS_AUTO_CAPABILITY_EVOLVER", True)
        self.capability_evolver_cooldown_s = max(0, int(os.getenv("JARVIS_CAPABILITY_EVOLVER_COOLDOWN_S", "20")))
        self.capability_evolver_buffer_limit = max(5, int(os.getenv("JARVIS_CAPABILITY_EVOLVER_BUFFER", "25")))
        self._capability_lock = threading.Lock()
        self._capability_logs = []
        self._capability_last_run = 0.0
        self._capability_last_fingerprint = ""
        self._capability_last_issue_fingerprint = ""
        if SuperOrchestrator is not None:
            try:
                self.super_orchestrator = SuperOrchestrator(
                    config=self.config,
                    emit=self._emit,
                    agent_callback=self._dispatch_agent_from_super,
                )
                logger.info("Super Orchestrator initialized")
            except Exception as exc:
                logger.warning("Super Orchestrator disabled: %s", exc)
        else:
            logger.warning("Super Orchestrator module unavailable")

        self.hotkey = None
        if HotkeyListener is not None:
            try:
                self.hotkey = HotkeyListener(self)
                self.hotkey.start()
            except Exception as exc:
                logger.warning("Hotkey listener disabled: %s", exc)
        else:
            logger.warning("Hotkey listener module unavailable; kill hotkey disabled.")

        self.phone = PhoneTool(self._emit, llm=self.agent.llm)
        self.planner = TaskPlanner(self.agent.llm, vision=self.phone.vision)
        self.agent.phone = self.phone
        self.agent.phone_autonomous_runner = self._handle_phone_autonomous
        self.autonomous_history = []
        
        # Start proactive monitors
        self.background_monitor = None
        self.vision_monitor = None
        if BackgroundMonitor and self.enable_background_monitor:
            self.background_monitor = BackgroundMonitor(self._emit)
            self.background_monitor.start()
        if VisionMonitor and self.enable_vision_monitor:
            self.vision_monitor = VisionMonitor(self.config, self._emit)
            self.vision_monitor.start()

        logger.info("Core Engine initializing...")

    def _create_mock_gui(self):
        class MockGUI:
            def __init__(self, parent):
                self.parent = parent

            def update_status(self, status):
                self.parent._emit("status", status)

            def update_transcript(self, role, text):
                self.parent._emit("transcript", {"role": role, "text": text})

            def update_partial(self, role, text):
                self.parent._emit("partial_transcript", {"role": role, "text": text})

            def add_sys_log(self, text):
                self.parent.log(text)

        return MockGUI(self)

    def log(self, text):
        logger.info("[Engine] %s", text)
        self._emit("log", text)

    def _emit(self, msg_type, data):
        try:
            self.output_queue.put({"type": msg_type, "data": data})
        except Exception as exc:
            logger.error("Error emitting message: %s", exc)

    def _normalize_runtime_issue(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(payload or {})
        return {
            "timestamp": str(data.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
            "level": str(data.get("level") or "error").lower(),
            "message": str(data.get("message") or data.get("error") or "runtime issue"),
            "context": str(data.get("context") or data.get("kind") or "jarvis.runtime"),
            "stack": str(data.get("traceback") or data.get("traceback_text") or ""),
            "kind": str(data.get("kind") or "runtime_issue"),
            "extra": data.get("extra") or {},
        }

    def _record_runtime_issue(
        self,
        kind: str,
        message: Any,
        *,
        context: str = "",
        level: str = "error",
        traceback_text: str = "",
        extra: Dict[str, Any] | None = None,
    ) -> None:
        issue = self._normalize_runtime_issue(
            {
                "kind": kind,
                "message": message,
                "context": context,
                "level": level,
                "traceback": traceback_text,
                "extra": extra or {},
            }
        )
        self._run_capability_evolver(issue)

    def _handle_agent_diagnostic(self, payload: Dict[str, Any]) -> None:
        issue = self._normalize_runtime_issue(payload)
        self._run_capability_evolver(issue)

    def _run_capability_evolver(self, issue: Dict[str, Any]) -> None:
        if not getattr(self, "auto_capability_evolver", True):
            return

        plugin_runtime = getattr(getattr(self, "super_orchestrator", None), "plugins", None)
        if plugin_runtime is None:
            return

        now = time.time()
        with self._capability_lock:
            self._capability_logs.append(issue)
            if len(self._capability_logs) > self.capability_evolver_buffer_limit:
                self._capability_logs = self._capability_logs[-self.capability_evolver_buffer_limit :]

            issue_fingerprint = (
                f"{issue.get('level')}:{issue.get('context')}:{str(issue.get('message', ''))[:120]}"
            )
            fingerprint = "|".join(
                f"{item.get('level')}:{item.get('context')}:{str(item.get('message', ''))[:80]}"
                for item in self._capability_logs[-3:]
            )
            if (
                self.capability_evolver_cooldown_s > 0
                and (now - self._capability_last_run) < self.capability_evolver_cooldown_s
                and issue_fingerprint == self._capability_last_issue_fingerprint
            ):
                return

            logs = list(self._capability_logs)
            self._capability_last_run = now
            self._capability_last_fingerprint = fingerprint
            self._capability_last_issue_fingerprint = issue_fingerprint

        analysis = plugin_runtime.execute("capability_evolver.analyze", {"logs": logs})
        if not analysis.get("ok"):
            logger.warning("Capability evolver analyze failed: %s", analysis.get("error"))
            return

        analysis_result = analysis.get("result", {})
        patterns = analysis_result.get("patterns", [])
        should_evolve = analysis_result.get("health_score", 100) < 70 or any(
            pattern.get("type") == "regression" or pattern.get("severity") in {"high", "critical"}
            for pattern in patterns
        )
        evolution_result = None
        if should_evolve:
            evolution = plugin_runtime.execute(
                "capability_evolver.evolve",
                {"logs": logs, "strategy": "auto", "target_file": issue.get("context", "")},
            )
            if evolution.get("ok"):
                evolution_result = evolution.get("result")
            else:
                logger.warning("Capability evolver evolve failed: %s", evolution.get("error"))

        self._emit(
            "super_event",
            {
                "type": "capability_analysis",
                "data": {
                    "trigger": issue.get("kind", "runtime_issue"),
                    "issue": issue,
                    "analysis": analysis_result,
                    "evolution": evolution_result,
                    "summary": {
                        "health_score": analysis_result.get("health_score"),
                        "pattern_count": analysis_result.get("summary", {}).get("unique_patterns", len(patterns)),
                        "recommendations": analysis_result.get("recommendations", [])[:3],
                    },
                },
            },
        )

    def check_ollama(self):
        try:
            logger.info("Checking Ollama connection at %s...", self.config.OLLAMA_HOST)
            # Use longer timeout and handle more connection issues
            res = requests.get(f"{self.config.OLLAMA_HOST}/api/tags", timeout=10)
            if res.status_code == 200:
                logger.info("Ollama connected")
                return True
            logger.warning("Ollama returned status code: %s", res.status_code)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            logger.error("Ollama Connection Failed or Timed out: %s", exc)
        except Exception as exc:
            logger.error("Ollama connection error: %s", exc)

        self._emit("error", "Ollama Connection Lost - Please ensure Ollama is running.")
        return False

    def _start_stt_listener(self):
        if self.stt_thread and self.stt_thread.is_alive():
            return

        def init_stt():
            try:
                logger.info("Initializing STT (Whisper)...")
                self.stt = SpeechRecognizer(self.config)

                def on_wake():
                    logger.info("Wake word detected")
                    SoundFX.play_wake()
                    self._emit("status", "Listening...")

                def on_transcript(text):
                    if not text:
                        return
                    if text == "__stt_no_match__":
                        msg = "Boss, awaz clear nahi aayi. Zara dobara bolen."
                        self._emit("transcript", {"role": "Jarvis", "text": msg})
                        try:
                            self.tts.speak(msg)
                        except Exception:
                            pass
                        self._emit("status", "Listening...")
                        return
                    logger.info("User said: %s", text)
                    SoundFX.play_processing()
                    self._emit("status", "Thinking...")
                    if self.confirmations.has_pending():
                        decision = self.confirmations.parse_voice(text)
                        if decision is not None:
                            request_id = self.confirmations.resolve_latest(decision)
                            msg = "Confirmation approved." if decision else "Confirmation denied."
                            self._emit("transcript", {"role": "Jarvis", "text": msg})
                            if request_id:
                                self._emit("confirm_resolved", {"id": request_id, "approved": decision})
                            try:
                                self.tts.speak(msg)
                            except Exception:
                                pass
                            return
                    self._handle_chat(text)

                def on_stop():
                    logger.info("Stop command received")
                    self._emit("status", "Idle")

                self.stt.listen_for_wake(on_wake, on_transcript, on_stop)
            except Exception as exc:
                logger.error("STT initialization error: %s", exc)
                traceback.print_exc()
                self._emit("error", "STT initialization failed")

        self.stt_thread = threading.Thread(target=init_stt, daemon=True, name="jarvis-stt")
        self.stt_thread.start()

    def run(self):
        logger.info("Starting Core Engine...")
        self._emit("status", "Idle")
        if self.super_orchestrator:
            try:
                if not self.super_orchestrator.onboarding.is_onboarded():
                    notice = "Boss, pehli dafa system access ke liye approval chahiye. UI par allow ya limited choose karein."
                    self._emit("transcript", {"role": "Jarvis", "text": notice})
                    self._emit("super_event", {"type": "onboarding_required", "state": self.super_orchestrator.onboarding.state()})
                    try:
                        self.tts.speak(notice)
                    except Exception:
                        pass
            except Exception as exc:
                logger.warning("Super onboarding check failed: %s", exc)

        if self.auto_start_stt:
            self._start_stt_listener()
        else:
            logger.info("STT auto-start disabled; listener will initialize on first mic enable.")

        logger.info("Core Engine ready. Waiting for commands...")
        while self.running:
            try:
                msg = self.input_queue.get(timeout=1)
                cmd_type = msg.get("type")
                data = msg.get("data")

                if cmd_type == "chat":
                    self._handle_chat(data, msg.get("image"))
                elif cmd_type == "mic_toggle":
                    self._handle_mic(data)
                elif cmd_type == "mute_toggle":
                    self.tts.set_mute(data)
                elif cmd_type == "vision_response":
                    self._handle_vision_data(data)
                elif cmd_type == "file_analyze":
                    self._handle_file_analyze(data)
                elif cmd_type == "stop_action":
                    self._handle_stop_action()
                elif cmd_type == "shutdown":
                    logger.info("Shutdown requested")
                    self.running = False
                    if self.stt:
                        self.stt.shutdown()
                    if self.hotkey and hasattr(self.hotkey, "stop"):
                        self.hotkey.stop()
                    if hasattr(self, 'background_monitor') and self.background_monitor:
                        self.background_monitor.stop()
                    if hasattr(self, 'vision_monitor') and self.vision_monitor:
                        self.vision_monitor.stop()
                elif cmd_type == "super_onboard":
                    self._handle_super_onboard(data or {})
                elif cmd_type == "super_connect_channel":
                    self._handle_super_connect(data or {})
                elif cmd_type == "super_disconnect_channel":
                    self._handle_super_disconnect(data or {})
                elif cmd_type == "super_channel_inbound":
                    self._handle_super_channel_inbound(data or {})
                elif cmd_type == "super_channel_send":
                    self._handle_super_channel_send(data or {})
                elif cmd_type == "super_status":
                    self._handle_super_status()
                elif cmd_type == "super_plugin_reload":
                    self._handle_super_plugin_reload()
                elif cmd_type == "super_task":
                    self._handle_super_task(data or {})
                elif cmd_type == "confirm_response":
                    payload = data or {}
                    request_id = str(payload.get("id", ""))
                    approved = bool(payload.get("approved", False))
                    self.confirmations.resolve(request_id, approved)
                    if request_id:
                        self._emit("confirm_resolved", {"id": request_id, "approved": approved})
                elif cmd_type == "phone_control":
                    self.phone.handle_command(data)

            except queue.Empty:
                continue
            except Exception as exc:
                logger.error("Engine error: %s", exc)
                tb_text = traceback.format_exc()
                print(tb_text, end="")
                self._record_runtime_issue(
                    "engine_exception",
                    exc,
                    context="core_engine.run",
                    traceback_text=tb_text,
                )
                self._emit("error", f"Engine error: {str(exc)}")

    def _handle_file_analyze(self, data):
        path = data.get("path")
        self._emit("status", "Analyzing File...")

        def run_analyze():
            try:
                self.agent.handle_file(path)
                self._emit("status", "Idle")
            except Exception as exc:
                logger.error("File analysis error: %s", exc)
                tb_text = traceback.format_exc()
                print(tb_text, end="")
                self._record_runtime_issue(
                    "file_analysis_exception",
                    exc,
                    context="core_engine.file_analysis",
                    traceback_text=tb_text,
                )
                self._emit("transcript", {"role": "Jarvis", "text": "Maafi boss, file analyze karne mein masla ho raha hai."})
                self._emit("status", "Idle")

        threading.Thread(target=run_analyze, daemon=True).start()

    def _dispatch_agent_from_super(self, text, image_data=None):
        self.agent.handle_transcript(text, image_data)
        return {"ok": True}

    def _handle_chat(self, text, image_data=None):
        self._emit("status", "Thinking...")

        def run_chat():
            try:
                if self.super_orchestrator is not None:
                    outcome = self.super_orchestrator.handle_text(
                        text=text,
                        source="ui",
                        user_id="local-admin",
                        metadata={"confirmed": False},
                    )
                    if not outcome.get("ok", True):
                        error = outcome.get("error", "Task blocked by policy")
                        self._emit("transcript", {"role": "Jarvis", "text": error})
                        self.tts.speak(error)
                    if outcome.get("data") is not None:
                        self._emit("super_event", {"type": "chat_outcome", "data": outcome.get("data")})
                else:
                    self.agent.handle_transcript(text, image_data)
                self._emit("status", "Idle")
            except Exception as exc:
                logger.error("Agent error: %s", exc)
                tb_text = traceback.format_exc()
                print(tb_text, end="")
                self._record_runtime_issue(
                    "chat_exception",
                    exc,
                    context="core_engine._handle_chat",
                    traceback_text=tb_text,
                    extra={"user_input": str(text or "")[:300]},
                )
                self._emit("transcript", {"role": "Jarvis", "text": "Maafi boss, kuch technical masla aa gaya. Dobara bolein?"})
                self._emit("status", "Idle")

        threading.Thread(target=run_chat, daemon=True).start()

    def _handle_mic(self, active: bool):
        self.mic_active = active
        if active and (self.stt_thread is None or not self.stt_thread.is_alive()):
            self._start_stt_listener()
        if self.stt:
            self.stt.active = active
            if active:
                self.stt.last_active_time = time.time()
                self._emit("status", "Listening...")
            else:
                self._emit("status", "Idle")

    def _handle_phone_autonomous(self, goal: str):
        """Start an autonomous loop to achieve a phone-based goal."""
        self._emit("status", "Autonomous Mode")
        self.autonomous_history = []
        
        def run_loop():
            max_steps = 10
            for i in range(max_steps):
                if not self.running: break
                
                # 1. Get Visual Context
                visual = self.phone.vision.get_visual_context() if self.phone.vision else None
                
                # 2. Ask Brain for next step
                decision = self.planner.autonomous_step(goal, self.autonomous_history, visual)
                self._emit("log", f"Brain Decision: {decision.get('reasoning')}")
                
                action = decision.get("action")
                if action == "task_completed":
                    self._emit("transcript", {"role": "Jarvis", "text": f"Boss, kaam ho gaya: {goal}"})
                    break
                elif action == "stuck":
                    self._emit("transcript", {"role": "Jarvis", "text": "Maafi boss, main stuck hoon. Thodi help chahiye."})
                    break
                
                # 3. Execute Action
                self._emit("status", f"Acting: {action}")
                res = self.phone.handle_command({"action": action, **decision.get("params", {})})
                
                # 4. Record history
                self.autonomous_history.append({
                    "step": i,
                    "goal": goal,
                    "decision": decision,
                    "result": res
                })
                
                # Error Recovery
                if res.get("status") == "error":
                    recovery = self.planner.handle_error(decision, res.get("message", "Unknown error"))
                    if not recovery.get("retry"):
                        self._emit("transcript", {"role": "Jarvis", "text": "Error recovery failed. Stopping."})
                        break
                    self._emit("log", f"Recovery: {recovery.get('reasoning')}")
                
                time.sleep(2) # Wait for UI to react
            
            self._emit("status", "Idle")

        threading.Thread(target=run_loop, daemon=True).start()

    def _handle_vision_data(self, _data):
        return None

    def _handle_stop_action(self):
        self.tts.stop()
        if self.agent:
            self.agent.active = False
        self._emit("status", "System Stopped")
        self._emit("log", "System stopped by user.")

    def _handle_super_onboard(self, data):
        if self.super_orchestrator is None:
            self._emit("error", "Super mode is unavailable.")
            return
        result = self.super_orchestrator.onboard(data)
        self._emit("super_event", {"type": "onboard_result", "data": result})

    def _handle_super_connect(self, data):
        if self.super_orchestrator is None:
            self._emit("error", "Super mode is unavailable.")
            return
        channel = (data.get("channel") or "").strip()
        if not channel:
            self._emit("error", "Missing channel name.")
            return
        result = self.super_orchestrator.connect_channel(
            channel,
            settings=data.get("settings") or {},
            token=data.get("token"),
        )
        self._emit("super_event", {"type": "connect_result", "data": result})

    def _handle_super_disconnect(self, data):
        if self.super_orchestrator is None:
            self._emit("error", "Super mode is unavailable.")
            return
        channel = (data.get("channel") or "").strip()
        if not channel:
            self._emit("error", "Missing channel name.")
            return
        result = self.super_orchestrator.disconnect_channel(channel)
        self._emit("super_event", {"type": "disconnect_result", "data": result})

    def _handle_super_channel_inbound(self, data):
        if self.super_orchestrator is None:
            self._emit("error", "Super mode is unavailable.")
            return
        result = self.super_orchestrator.ingest_channel_message(
            channel=str(data.get("channel", "unknown")),
            user_id=str(data.get("user_id", "unknown")),
            text=str(data.get("text", "")),
            metadata=data.get("metadata") or {},
        )
        self._emit("super_event", {"type": "inbound_result", "data": result})

    def _handle_super_channel_send(self, data):
        if self.super_orchestrator is None:
            self._emit("error", "Super mode is unavailable.")
            return
        result = self.super_orchestrator.send_channel_message(
            channel=str(data.get("channel", "")),
            target=str(data.get("target", "")),
            text=str(data.get("text", "")),
            user_id=str(data.get("user_id", "local-admin")),
            metadata=data.get("metadata") or {},
        )
        self._emit("super_event", {"type": "send_result", "data": result})

    def _handle_super_status(self):
        if self.super_orchestrator is None:
            self._emit("error", "Super mode is unavailable.")
            return
        self._emit("super_event", {"type": "status", "data": self.super_orchestrator.status()})

    def _handle_super_plugin_reload(self):
        if self.super_orchestrator is None:
            self._emit("error", "Super mode is unavailable.")
            return
        loaded, errors = self.super_orchestrator.plugins.reload()
        self._emit("super_event", {"type": "plugin_reload", "data": {"loaded": loaded, "errors": errors}})

    def _handle_super_task(self, data):
        if self.super_orchestrator is None:
            self._emit("error", "Super mode is unavailable.")
            return
        text = str(data.get("text", "")).strip()
        if not text:
            self._emit("error", "Task text is required.")
            return
        outcome = self.super_orchestrator.handle_text(
            text=text,
            source=str(data.get("source", "api")),
            user_id=str(data.get("user_id", "local-admin")),
            metadata=data.get("metadata") or {},
        )
        self._emit("super_event", {"type": "task_result", "data": outcome})
