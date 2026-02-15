# jarvis/enhanced_planner.py - Advanced Task Planning with Multi-turn Support

import json
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class TaskPlanner:
    """Enhanced task planner with multi-turn support and progress tracking."""
    
    def __init__(self, llm):
        self.llm = llm
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
            self.active_tasks[task_id]["completed_steps"].append(step_completed)
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
                return json.loads(match.group())
            except:
                pass
        
        # Fallback
        return {"raw": text}


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
