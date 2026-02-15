# jarvis/agent.py
from typing import Optional, List, Dict, Any, Tuple, Union
import json
import threading
import time
import re
import os
from pathlib import Path
import traceback

from llm_ollama import OllamaLLM
from tts_local import TextToSpeech
from tools.safety import confirm_action, ensure_system_access, ensure_scope_access
from tools.apps import open_app
from tools.files import list_dir, read_file, write_file
from tools.commands import run_command
from tools.browser import browser_task
from tools.vision import capture_and_analyze, analyze_image
from tools.automation import type_text, press_key, scroll, mouse_click, move_mouse, hotkey
try:
    import cv2
except ImportError:
    cv2 = None
    print("Warning: opencv-python not found. Vision features will be disabled.")

from tools.system_ops import get_system_status, get_clipboard_text, set_clipboard_text, get_active_window_title, optimize_system
from tools.coach_rules import detect_issue
from tools.multimedia import play_on_youtube, open_google, open_website

from memory.db import MemoryDB

from planner import TaskPlanner

class Agent:
    def __init__(self, config, tts: TextToSpeech, gui: Any = None):
        self.config = config
        self.tts = tts
        self.gui = gui
        self.llm = OllamaLLM(config)
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
        
        self.system_prompt = (
            "You are JARVIS, a highly intelligent and FRIENDLY personal AI assistant."
            "Primary Language: Conversational Roman Urdu (like people chat in Pakistan/India)."
            "Tone: Loyal, helpful, and very natural. Address the user as 'Boss'."
            "Rule 0: ALWAYS create a thought process and a plan. Your response MUST follow this format:"
            "[[YOUR NATURAL URDU RESPONSE]]\n"
            "###PLAN###\n"
            '{"plan": [{"phase": "Task", "action": "tool_name", "args": {...}}]}'
            "\n\n"
            "HOW THE LOOP WORKS:\n"
            "1. You get a User Input. You create a response and a plan.\n"
            "2. I execute ONE step of your plan.\n"
            "3. I will give you the result of that step as '[TOOL_OUTPUT: ...]'.\n"
            "4. You will use that output to continue to the next step or decide you are done.\n"
            "5. If you are done, your plan array will be empty `[]`, and you will give a final summary message in Roman Urdu.\n"
            "Example:\n"
            "User Input: 'Mera CPU status kya hai?'\n"
            "Your Response:\n"
            "[[Ji Boss, abhi check karta hoon.]]\n"
            "###PLAN###\n"
            '[{"action": "get_stats", "args": {}}]\n\n'
            "My next prompt to you will be:\n"
            "User Input: '[TOOL_OUTPUT: System Status: CPU 15%, RAM 60%]'\n"
            "Your next response would be:\n"
            "[[Boss, aapka CPU 15% aur RAM 60% use ho rahi hai.]]\n"
            "###PLAN###\n"
            '{"plan": []}'
        )

    def set_gui(self, gui):
        self.gui = gui

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

    def handle_transcript(self, text: str, image_data: Optional[str] = None):
        """Handles user transcript, generates an initial plan, and starts execution."""
        with self.active_lock:
            if not self.active:
                self.active = True
                self.last_interaction = time.time()
                if self.gui: self.gui.update_status("Active")

        self.last_interaction = time.time()
        
        # Add user input to memory and GUI
        self.memory.add_turn("User", text, session_id=self.session_id)
        if self.gui: self.gui.update_transcript("User", text)

        # Generate the initial plan
        history = self.memory.get_context(limit=5, session_id=self.session_id)
        context = "\n".join([f"{m['role']}: {m['content']}" for m in history])
        prompt = f"{self.system_prompt}\n\nRecent History:\n{context}\n\nUser Input: '{text}'"
        
        if image_data:
            prompt += "\n[IMAGE DATA ATTACHED]"

        try:
            if self.gui: self.gui.update_status("Thinking...")
            llm_response_text = self._generate_llm_text(
                prompt, images=[image_data] if image_data else None
            )
            
            res_text, plan_data = self._parse_llm_response(llm_response_text)
            
            if self.gui: self.gui.update_transcript("Jarvis", res_text)
            self.memory.add_turn("Jarvis", res_text, session_id=self.session_id)
            if res_text:
                self.tts.speak(res_text)

            # Start the plan execution loop in a new thread
            threading.Thread(target=self._handle_plan, args=(plan_data,), daemon=True).start()

        except Exception as e:
            print(f"[Agent] Error in handle_transcript: {e}")
            traceback.print_exc()
            error_msg = "Maafi Boss, kuch technical masla aa gaya."
            self.tts.speak(error_msg)
            if self.gui: self.gui.update_transcript("Jarvis", error_msg)
            if self.gui: self.gui.update_status("Idle")
    
    def _handle_plan(self, plan_data: dict):
        """Executes a plan step-by-step, feeding back tool outputs to the LLM."""
        plan = plan_data.get("plan", [])
        step_index = 0  # Fix: Use index instead of pop to avoid losing state on error
        
        while step_index < len(plan):
            with self.active_lock:
                if not self.active:
                    print("[Agent] Plan execution cancelled as agent is inactive.")
                    break

            step = plan[step_index]
            action_name = step.get("action", "unknown")
            
            try:
                if self.gui: self.gui.update_status(f"Executing: {action_name}")
                tool_output = self._execute_step(step)
                
                # Format tool output for the LLM
                tool_result_prompt = f"[TOOL_OUTPUT: {str(tool_output)}]"
                self.memory.add_turn("User", tool_result_prompt, session_id=self.session_id)
                if self.gui: self.gui.update_transcript("System", f"Tool Output: {str(tool_output)}")

                # Get the next step from the LLM
                history = self.memory.get_context(limit=7, session_id=self.session_id)
                context = "\n".join([f"{m['role']}: {m['content']}" for m in history])
                prompt = f"{self.system_prompt}\n\nRecent History:\n{context}\n\nUser Input: '{tool_result_prompt}'"
                
                if self.gui: self.gui.update_status("Thinking...")
                llm_response_text = self._generate_llm_text(prompt)
                
                res_text, new_plan_data = self._parse_llm_response(llm_response_text)
                
                if res_text:
                    if self.gui: self.gui.update_transcript("Jarvis", res_text)
                    self.memory.add_turn("Jarvis", res_text, session_id=self.session_id)
                    self.tts.speak(res_text)

                plan = new_plan_data.get("plan", [])
                step_index = 0  # Reset index for new plan

            except Exception as e:
                print(f"[Agent] Step Execution Error ({action_name}): {e}")
                traceback.print_exc()
                error_msg = f"Maafi Boss, '{action_name}' tool mein masla aa gaya."
                self.tts.speak(error_msg)
                if self.gui: self.gui.update_transcript("Jarvis", error_msg)
                break # Stop plan execution on error
        
        if self.gui: self.gui.update_status("Idle")
        print("[Agent] Plan execution complete.")

    def _parse_llm_response(self, response_text: str) -> Tuple[str, dict]:
        """Parses the LLM's raw text response to separate conversational text and a JSON plan."""
        res_text = response_text
        plan_data = {"plan": []}

        try:
            if "###PLAN###" in response_text:
                parts = response_text.split("###PLAN###", 1)
                res_text = parts[0].replace("[[", "").replace("]]", "").strip()
                potential_json = parts[1].strip()
                
                json_match = re.search(r'(\{.*\})', potential_json, re.DOTALL)
                if json_match:
                    plan_json_str = json_match.group(1)
                    plan_json_str = re.sub(r'```json\s*|\s*```', '', plan_json_str).strip()
                    
                    try:
                        plan_data = json.loads(plan_json_str)
                    except json.JSONDecodeError:
                        # Attempt to repair JSON
                        repaired_json = self._repair_json(plan_json_str)
                        plan_data = json.loads(repaired_json)
                        print(f"[Agent] JSON Repaired successfully.")
        except Exception as e:
            print(f"[Agent] Error parsing LLM response: {e}. Using empty plan.")
            # Ensure res_text is the full response if parsing fails
            res_text = response_text.replace("[[", "").replace("]]", "").strip().split("###PLAN###")[0]
            plan_data = {"plan": []}
            
        return res_text, plan_data

    def _repair_json(self, faulty_json: str) -> str:
        """Attempts to fix common JSON errors from LLMs."""
        repaired = faulty_json
        try:
            repaired = re.sub(r"'(\w+)':", r'"\1":', repaired)
            repaired = re.sub(r":\s*'([^']*)'", r': "\1"', repaired)
            repaired = re.sub(r'(?<!")(\b\w+\b)(?=\s*:)', r'"\1"', repaired)
            repaired = re.sub(r',\s*([\]}])', r'\1', repaired)
            return repaired
        except Exception:
            raise json.JSONDecodeError("JSON repair failed", faulty_json, 0)

    def _execute_step(self, step: dict) -> str:
        """Executes a single tool action and returns the output as a string."""
        action = step.get("action")
        args = step.get("args", {})
        
        # Default response if action is unknown or has no return
        output = f"Action '{action}' executed."

        if action == "open_app":
            app_name = args.get("name")
            if not ensure_scope_access("automation", "Open application"):
                output = "Automation access not granted."
            else:
                open_app(app_name)
                output = f"Application '{app_name}' started."
        
        elif action == "get_stats":
            stats = get_system_status()
            output = f"System Status: CPU {stats['cpu_percent']}%, RAM {stats['ram_percent']}%"
            if stats.get('battery') and stats['battery'].get('percent') is not None:
                output += f", Battery {stats['battery']['percent']}%"

        elif action == "read_clipboard":
            output = f"Clipboard content: '{get_clipboard_text()}'"

        elif action == "write_clipboard":
            if not ensure_scope_access("automation", "Write clipboard"):
                output = "Automation access not granted."
            elif confirm_action("Clipboard update karun?"):
                set_clipboard_text(args.get("text", ""))
                output = "Text written to clipboard."
            else:
                output = "Action cancelled by user."

        elif action == "check_window":
            title = get_active_window_title()
            output = f"Current active window is: '{title}'"

        elif action == "capture_vision":
            analysis = capture_and_analyze(self.config, args.get("prompt", "Analyze this."))
            issue = detect_issue(analysis)
            if issue:
                analysis += f"\nNote: Maine ek technical issue detect kiya hai ({issue['tag']})."
            output = analysis

        elif action == "type_text":
            text_to_type = args.get('text')
            if not ensure_scope_access("automation", "Type on screen"):
                output = "Automation access not granted."
            elif confirm_action(f"Type karun? '{text_to_type}'"):
                type_text(text_to_type)
                output = f"Typed text: '{text_to_type}'"
            else:
                output = "Action cancelled by user."

        elif action == "mouse_click":
            if not ensure_scope_access("automation", "Mouse click"):
                output = "Automation access not granted."
            elif confirm_action("Click karun?"):
                mouse_click(args.get("x"), args.get("y"))
                output = "Mouse clicked."
            else:
                output = "Action cancelled by user."

        elif action == "browser_task":
            goal = args.get("goal")
            if not ensure_scope_access("browser", "Browser automation"):
                output = "Browser access not granted."
            else:
                output = browser_task(goal) # Assume browser_task returns a summary string

        elif action == "play_youtube":
            query = args.get("query")
            if not ensure_scope_access("browser", "Open YouTube"):
                output = "Browser access not granted."
            else:
                play_on_youtube(query)
                output = f"Playing '{query}' on YouTube."

        elif action == "open_google":
            if not ensure_scope_access("browser", "Open browser"):
                output = "Browser access not granted."
            else:
                open_google()
                output = "Google opened."

        elif action == "open_website":
            url = args.get("url")
            if not ensure_scope_access("browser", "Open website"):
                output = "Browser access not granted."
            else:
                open_website(url)
                output = f"Website '{url}' opened."

        elif action == "create_roadmap":
            goal = args.get("goal")
            roadmap_data = self.planner.create_roadmap(goal)
            transcript_text = f"--- ROADMAP: {goal.upper()} ---\n"
            for item in roadmap_data.get("phases", []):
                transcript_text += f"* {item['phase']}: {item['objectives']}\n"
            if self.gui: self.gui.update_transcript("Jarvis (Planner)", transcript_text)
            output = f"Roadmap for '{goal}' has been created and displayed."
        
        elif action == "optimize_system":
            if not ensure_scope_access("automation", "System optimize"):
                output = "Automation access not granted."
            elif confirm_action("System optimize karun?"):
                report = optimize_system()
                if self.gui: self.gui.update_transcript("Jarvis (System)", report)
                output = f"System optimized. Report: {report}"
            else:
                output = "Action cancelled by user."
        
        else:
            output = f"Unknown action: {action}"
            
        return output

    def monitor_timeout(self):
        while True:
            li = self.last_interaction
            if self.active and li is not None and (time.time() - li > self.timeout):
                self.handle_stop()
            time.sleep(10)

    # --- File handling methods are unchanged for now ---
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
                if cv2 is None:
                    self.tts.speak("Boss, video analysis ke liye OpenCV required hai.")
                    return

                cap = cv2.VideoCapture(file_path)
                ok, frame = cap.read()
                cap.release()
                if not ok:
                    self.tts.speak("Boss, video ka frame read nahi ho saka.")
                    return

                temp_image = str(Path(file_path).with_suffix(".jarvis_frame.jpg"))
                cv2.imwrite(temp_image, frame)

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
            # This part also needs refactoring. It currently calls handle_transcript directly.
            # ... (original PDF analysis code) ...
        
        else:
            self.tts.speak(f"Boss, main abhi {ext} files analyze nahi kar sakta, magar future mein zaroor karunga!")
    
    def handle_stop(self):
        with self.active_lock:
            if self.active:
                self.active = False
                if self.gui: self.gui.update_status("Idle")
                self.tts.speak("Theek hai sir, offline ja raha hoon. Allah hafiz.")
