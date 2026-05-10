# jarvis/enhanced_planner.py - Advanced Task Planning with Multi-turn Support

import json
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class TaskPlanner:
    """Enhanced task planner with multi-turn support and progress tracking."""
    
    def __init__(self, llm, vision=None):
        self.llm = llm
        self.vision = vision
        self.active_tasks = {}  # Track ongoing tasks
        logger.info("Enhanced Task Planner initialized")

    def plan_complex_task(self, task_description: str, context: str = "") -> Dict:
        """Plan a complex task with multiple steps."""
        
        prompt = f"""You are JARVIS, a task planning expert. 
        
User wants to: {task_description}

Context: {context if context else 'None provided'}

Create a detailed step-by-step plan in JSON format.
Respond ONLY in this format:
{{
    "task_title": "Task Name",
    "difficulty": "easy|medium|hard",
    "estimated_duration": "minutes",
    "phases": [
        {{
            "phase": "Phase Name",
            "steps": ["Step 1", "Step 2"],
            "tools_needed": ["tool1", "tool2"],
            "success_criteria": "How to verify completion"
        }}
    ],
    "potential_issues": ["Issue 1", "Issue 2"],
    "fallback_plans": ["Plan B if Phase 1 fails"]
}}"""

        try:
            response = self.llm.generate(prompt)
            plan = self._parse_json(response)
            logger.info(f"Task planned: {plan.get('task_title', 'Unknown')}")
            return plan
        except Exception as e:
            logger.error(f"Error planning task: {e}")
            return {"error": str(e)}

    def build_local_tool_plan(self, text: str) -> Dict:
        """Deterministic planner for common local workflows.

        This keeps Jarvis useful when the LLM is offline or underperforming.
        """
        raw = (text or "").strip()
        lowered = raw.lower()
        plan = []
        response = ""

        match = re.search(
            r"(?:open|go to|visit)\s+(.+?)\s+and\s+search\s+(.+)",
            raw,
            re.IGNORECASE,
        )
        if match:
            target = match.group(1).strip()
            query = match.group(2).strip()
            response = f"Ji Boss, {target} open karke '{query}' search karta hoon."
            plan = [
                {"action": "open_website", "args": {"url": target}},
                {"action": "browser_task", "args": {"goal": f"search {query} and summarize"}},
            ]
            return {"response": response, "plan": plan, "continue_with_llm": False}

        if "browser" in lowered and ("summarize" in lowered or "summary" in lowered):
            response = "Ji Boss, browser operator se page summary nikalta hoon."
            plan = [{"action": "browser_task", "args": {"goal": raw}}]
            return {"response": response, "plan": plan, "continue_with_llm": False}

        if "phone" in lowered and any(word in lowered for word in ("message", "call", "search", "open")):
            response = "Ji Boss, phone workflow run karta hoon."
            plan = [{"action": "phone_control", "args": {"action": "voice_command", "text": raw.replace("phone", "", 1).strip()}}]
            return {"response": response, "plan": plan, "continue_with_llm": False}

        if any(token in lowered for token in ("desktop", "windows search", "start menu")):
            response = "Ji Boss, desktop workflow run karta hoon."
            plan = [{"action": "desktop_task", "args": {"goal": raw.replace("desktop", "", 1).strip() or raw}}]
            return {"response": response, "plan": plan, "continue_with_llm": False}

        if ("open " in lowered and " type " in lowered) or ("launch " in lowered and " type " in lowered):
            response = "Ji Boss, desktop par multi-step workflow run karta hoon."
            plan = [{"action": "desktop_task", "args": {"goal": raw}}]
            return {"response": response, "plan": plan, "continue_with_llm": False}

        return {"response": "", "plan": []}

    def create_roadmap(self, goal: str) -> Dict:
        """Generate a learning/achievement roadmap."""
        
        prompt = f"""Create a professional roadmap for: {goal}

Respond in Roman Urdu, structured JSON format:
{{
    "goal": "{goal}",
    "timeline": "weeks",
    "phases": [
        {{
            "phase": "Phase Name",
            "duration": "duration",
            "objectives": ["Objective 1"],
            "resources": ["Resource 1"],
            "milestones": ["Milestone 1"]
        }}
    ]
}}"""

        try:
            response = self.llm.generate(prompt)
            roadmap = self._parse_json(response)
            logger.info(f"Roadmap created: {goal}")
            return roadmap
        except Exception as e:
            logger.error(f"Error creating roadmap: {e}")
            return {"error": str(e)}

    def break_down_task(self, task: str, depth: int = 3) -> Dict:
        """Break down a task into sub-tasks recursively."""
        
        prompt = f"""Break down this task into smaller, actionable sub-tasks (max {depth} levels):

Task: {task}

Response format:
{{
    "task": "{task}",
    "subtasks": [
        {{
            "name": "Sub-task name",
            "description": "What needs to be done",
            "time_estimate": "minutes",
            "subtasks": [...]  // If applicable
        }}
    ]
}}"""

        try:
            response = self.llm.generate(prompt)
            breakdown = self._parse_json(response)
            logger.info(f"Task broken down: {task}")
            return breakdown
        except Exception as e:
            logger.error(f"Error breaking down task: {e}")
            return {"error": str(e)}

    def generate_code_solution(self, problem: str, language: str = "python") -> Dict:
        """Generate code solution for a programming problem."""
        
        prompt = f"""Solve this programming problem in {language}:

Problem: {problem}

Response format:
{{
    "problem": "{problem}",
    "language": "{language}",
    "explanation": "How the solution works",
    "code": "Complete working code",
    "test_cases": [
        {{"input": "test input", "expected_output": "expected output"}}
    ]
}}"""

        try:
            response = self.llm.generate(prompt)
            solution = self._parse_json(response)
            logger.info(f"Code solution generated")
            return solution
        except Exception as e:
            logger.error(f"Error generating solution: {e}")
            return {"error": str(e)}

    def start_task(self, task_id: str, plan: Dict):
        """Start tracking a task."""
        self.active_tasks[task_id] = {
            "plan": plan,
            "started_at": datetime.now().isoformat(),
            "completed_steps": [],
            "status": "in_progress"
        }
        logger.info(f"Task started: {task_id}")

    def update_task_progress(self, task_id: str, step_completed: str):
        """Update progress on a task."""
        if task_id in self.active_tasks:
            steps = self.active_tasks[task_id].get("completed_steps")
            if isinstance(steps, list):
                steps.append(step_completed)
            logger.info(f"Task {task_id} progress: {step_completed}")

    def complete_task(self, task_id: str):
        """Mark a task as complete."""
        if task_id in self.active_tasks:
            self.active_tasks[task_id]["status"] = "completed"
            self.active_tasks[task_id]["completed_at"] = datetime.now().isoformat()
            logger.info(f"Task completed: {task_id}")

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get current status of a task."""
        return self.active_tasks.get(task_id)

    def _parse_json(self, text: str) -> Dict:
        """Parse JSON from LLM response."""
        import re
        
        # Try direct JSON parse
        try:
            return json.loads(text)
        except:
            pass
        
        # Try extracting JSON block
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                # Clean up nested code blocks inside JSON if LLM made a mistake
                cleaned = match.group()
                return json.loads(cleaned)
            except:
                pass
        
        # Fallback to extremely simple extraction if needed
        logger.warning(f"JSON parsing failed for: {text[:100]}...")
        return {"raw": text, "error": "JSON parse failed"}

    def autonomous_step(self, goal: str, history: List[Dict], visual_context: Optional[Dict] = None) -> Dict:
        """Determine the next autonomous step based on goal, history, and vision."""
        
        vision_info = f"Visual Context: {json.dumps(visual_context)}" if visual_context else "No visual data."
        
        prompt = f"""You are the BRAIN of JARVIS. 
Your goal: {goal}

Current History: {json.dumps(history[-5:])}
{vision_info}

What is the single most logical NEXT step to achieve the goal?
If the goal is ALREADY reached, return 'task_completed'.
If you are stuck and need help, return 'stuck'.

Respond ONLY in JSON format:
{{
    "action": "tap|type|scroll|open_app|wait|think|stuck|task_completed",
    "params": {{ ... }},
    "reasoning": "Brief explanation",
    "next_check": "What to look for after this action"
}}"""

        try:
            response = self.llm.generate(prompt)
            return self._parse_json(response)
        except Exception as e:
            logger.error(f"Autonomous step error: {e}")
            return {"action": "stuck", "error": str(e)}

    def handle_error(self, failed_action: Dict, error_msg: str) -> Dict:
        """Propose a recovery plan when an action fails."""
        prompt = f"""An action failed in JARVIS.
Failed Action: {json.dumps(failed_action)}
Error: {error_msg}

Propose an alternative way to reach the same objective.
Respond in JSON:
{{
    "retry": bool,
    "alternative_action": {{ "action": "...", "params": {{}} }},
    "reasoning": "..."
}}"""
        try:
            response = self.llm.generate(prompt)
            return self._parse_json(response)
        except Exception as e:
            logger.error(f"Error recovery planning failed: {e}")
            return {"retry": False, "error": str(e)}

    def fallback_recovery(self, failed_action: Dict, error_msg: str) -> Dict:
        """Non-LLM recovery path for common tool failures."""
        action = str((failed_action or {}).get("action", "")).strip()
        params = failed_action.get("args", failed_action.get("params", {})) if isinstance(failed_action, dict) else {}
        message = (error_msg or "").lower()

        if action == "browser_task":
            query = params.get("goal", "")
            return {
                "retry": False,
                "alternative_action": {"action": "search_google", "args": {"query": query}},
                "reasoning": "Browser operator fail hua, Google search fallback use karo.",
            }

        if action == "open_app" and ("could not find" in message or "missing" in message):
            app = params.get("name") or params.get("app_name") or ""
            return {
                "retry": False,
                "alternative_action": {"action": "search_google", "args": {"query": f"download {app} windows"}},
                "reasoning": "App local system me nahi mila, search fallback use karo.",
            }

        if action == "read_file":
            path = params.get("path", "")
            parent = str(re.sub(r"[\\/][^\\/]+$", "", path)) if path else "."
            return {
                "retry": False,
                "alternative_action": {"action": "list_dir", "args": {"path": parent}},
                "reasoning": "File read fail hua, parent folder listing dikhao.",
            }

        if action == "phone_control":
            return {
                "retry": False,
                "alternative_action": {"action": "phone_control", "args": {"action": "status"}},
                "reasoning": "Phone command fail hua, pehle device status verify karo.",
            }

        return {"retry": False, "reasoning": "No safe deterministic recovery available."}

    def evaluate_result(self, goal: str, result: object) -> Dict:
        text = str(result or "")
        lowered = text.lower()
        success = not any(token in lowered for token in ("error", "failed", "denied", "missing", "unavailable"))
        return {
            "goal": goal,
            "success": success,
            "score": 1.0 if success else 0.0,
            "summary": text[:300],
        }


class DependencyGraph:
    """Tracks task dependencies and execution order."""
    
    def __init__(self):
        self.tasks = {}
        self.dependencies = {}
        logger.info("Dependency Graph initialized")
    
    def add_task(self, task_id: str, task_info: Dict):
        """Add a task to the graph."""
        self.tasks[task_id] = task_info
        self.dependencies[task_id] = []
    
    def add_dependency(self, task_id: str, depends_on: str):
        """Add a dependency relationship."""
        if task_id not in self.dependencies:
            self.dependencies[task_id] = []
        self.dependencies[task_id].append(depends_on)
    
    def get_execution_order(self) -> List[str]:
        """Get topologically sorted execution order."""
        # Simple topological sort
        visited = set()
        order = []
        
        def visit(task_id):
            if task_id in visited:
                return
            visited.add(task_id)
            for dep in self.dependencies.get(task_id, []):
                visit(dep)
            order.append(task_id)
        
        for task_id in self.tasks:
            visit(task_id)
        
        return order
    
    def get_blocking_tasks(self, task_id: str) -> List[str]:
        """Get tasks that must complete before this task."""
        return self.dependencies.get(task_id, [])
