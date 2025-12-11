"""
Task planner for LocalAgent.

Implements structured task planning similar to agentic workflows:
1. User provides a task
2. LLM outputs a structured plan (JSON)
3. Steps are executed sequentially
4. Progress is tracked and reported
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime


class StepStatus(Enum):
    """Status of a task step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskStep:
    """A single step in a task plan."""
    id: int
    description: str
    status: StepStatus = StepStatus.PENDING
    depends_on: List[int] = field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskStep":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            status=StepStatus(data.get("status", "pending")),
            depends_on=data.get("depends_on", []),
            result=data.get("result"),
            error=data.get("error"),
        )


@dataclass
class TaskPlan:
    """A complete task plan with multiple steps."""
    goal: str
    steps: List[TaskStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    current_step: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "current_step": self.current_step,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskPlan":
        """Create from dictionary."""
        plan = cls(
            goal=data["goal"],
            current_step=data.get("current_step", 0),
        )
        plan.steps = [TaskStep.from_dict(s) for s in data.get("steps", [])]
        return plan

    def get_progress(self) -> Dict[str, Any]:
        """Get progress summary."""
        total = len(self.steps)
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in self.steps if s.status == StepStatus.FAILED)
        pending = sum(1 for s in self.steps if s.status == StepStatus.PENDING)

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "progress_percent": (completed / total * 100) if total > 0 else 0,
        }

    def get_next_step(self) -> Optional[TaskStep]:
        """Get the next step to execute."""
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                # Check dependencies
                deps_met = all(
                    self.steps[dep_id - 1].status == StepStatus.COMPLETED
                    for dep_id in step.depends_on
                    if dep_id <= len(self.steps)
                )
                if deps_met:
                    return step
        return None

    def format_progress(self) -> str:
        """Format progress as a string."""
        lines = [f"## Plan: {self.goal}\n"]

        for step in self.steps:
            if step.status == StepStatus.COMPLETED:
                icon = "✅"
            elif step.status == StepStatus.IN_PROGRESS:
                icon = "🔄"
            elif step.status == StepStatus.FAILED:
                icon = "❌"
            elif step.status == StepStatus.SKIPPED:
                icon = "⏭️"
            else:
                icon = "⬜"

            lines.append(f"{icon} Step {step.id}: {step.description}")
            if step.error:
                lines.append(f"   Error: {step.error}")

        progress = self.get_progress()
        lines.append(f"\nProgress: {progress['completed']}/{progress['total']} ({progress['progress_percent']:.0f}%)")

        return "\n".join(lines)


class TaskPlanner:
    """
    Manages task planning and execution.

    Usage:
        planner = TaskPlanner(interpreter)
        planner.enable()

        # Now when user sends a complex task, LLM will:
        # 1. First output a structured plan
        # 2. Execute steps one by one
        # 3. Report progress

    Example plan from LLM:
        {
            "goal": "Add login feature to the app",
            "steps": [
                {"id": 1, "description": "Create user model", "depends_on": []},
                {"id": 2, "description": "Add authentication routes", "depends_on": [1]},
                {"id": 3, "description": "Create login form", "depends_on": [1]},
                {"id": 4, "description": "Add tests", "depends_on": [2, 3]}
            ]
        }
    """

    # Prompt to instruct LLM to output a plan
    PLANNING_PROMPT = """
## Task Planning Mode

When given a complex task, you MUST first output a structured plan before executing.

**Plan Format (JSON):**
```json
{
    "goal": "Brief description of the overall goal",
    "steps": [
        {"id": 1, "description": "First step description", "depends_on": []},
        {"id": 2, "description": "Second step", "depends_on": [1]},
        {"id": 3, "description": "Third step (can run after 1)", "depends_on": [1]}
    ]
}
```

**Rules:**
1. Output the plan JSON FIRST, before any code
2. Each step should be atomic and clear
3. Use depends_on to specify which steps must complete first
4. Keep plans to 3-7 steps for most tasks
5. After outputting the plan, wait for confirmation before proceeding

**When to Plan:**
- Multi-file changes
- New features
- Refactoring
- Bug fixes that require investigation

**When NOT to Plan:**
- Simple questions
- Single-file edits
- Quick fixes
"""

    def __init__(self, interpreter: Any):
        """
        Initialize task planner.

        Args:
            interpreter: OpenInterpreter instance
        """
        self.interpreter = interpreter
        self._enabled = False
        self._current_plan: Optional[TaskPlan] = None
        self._auto_execute = False  # Auto-execute steps without confirmation

    def enable(self, auto_execute: bool = False) -> "TaskPlanner":
        """
        Enable planning mode.

        Args:
            auto_execute: Automatically execute steps without confirmation
        """
        self._enabled = True
        self._auto_execute = auto_execute
        return self

    def disable(self) -> "TaskPlanner":
        """Disable planning mode."""
        self._enabled = False
        return self

    @property
    def enabled(self) -> bool:
        """Whether planning mode is enabled."""
        return self._enabled

    @property
    def current_plan(self) -> Optional[TaskPlan]:
        """Get the current plan."""
        return self._current_plan

    def get_planning_prompt(self) -> str:
        """Get the planning prompt to add to system message."""
        if not self._enabled:
            return ""
        return self.PLANNING_PROMPT

    def parse_plan(self, text: str) -> Optional[TaskPlan]:
        """
        Parse a plan from LLM output.

        Args:
            text: LLM response text

        Returns:
            TaskPlan if found, None otherwise
        """
        # Method 1: Try to find JSON in code blocks
        code_block_patterns = [
            r'```json\s*([\s\S]*?)\s*```',  # ```json {...} ```
            r'```\s*([\s\S]*?)\s*```',       # ``` {...} ```
        ]

        for pattern in code_block_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    data = json.loads(match.strip())
                    if "goal" in data and "steps" in data:
                        plan = TaskPlan.from_dict(data)
                        self._current_plan = plan
                        return plan
                except json.JSONDecodeError:
                    continue

        # Method 2: Try to find inline JSON with goal and steps
        try:
            # Find the start of JSON
            start_idx = text.find('{"goal"')
            if start_idx == -1:
                start_idx = text.find('{ "goal"')

            if start_idx != -1:
                # Find matching closing brace
                depth = 0
                end_idx = start_idx
                for i, char in enumerate(text[start_idx:], start_idx):
                    if char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0:
                            end_idx = i + 1
                            break

                if end_idx > start_idx:
                    json_str = text[start_idx:end_idx]
                    data = json.loads(json_str)
                    if "goal" in data and "steps" in data:
                        plan = TaskPlan.from_dict(data)
                        self._current_plan = plan
                        return plan
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    def start_step(self, step_id: int) -> bool:
        """
        Mark a step as in progress.

        Args:
            step_id: Step ID to start

        Returns:
            True if successful
        """
        if not self._current_plan:
            return False

        for step in self._current_plan.steps:
            if step.id == step_id:
                step.status = StepStatus.IN_PROGRESS
                step.started_at = datetime.now()
                return True
        return False

    def complete_step(self, step_id: int, result: str = None) -> bool:
        """
        Mark a step as completed.

        Args:
            step_id: Step ID to complete
            result: Optional result description

        Returns:
            True if successful
        """
        if not self._current_plan:
            return False

        for step in self._current_plan.steps:
            if step.id == step_id:
                step.status = StepStatus.COMPLETED
                step.result = result
                step.completed_at = datetime.now()
                return True
        return False

    def fail_step(self, step_id: int, error: str = None) -> bool:
        """
        Mark a step as failed.

        Args:
            step_id: Step ID that failed
            error: Error message

        Returns:
            True if successful
        """
        if not self._current_plan:
            return False

        for step in self._current_plan.steps:
            if step.id == step_id:
                step.status = StepStatus.FAILED
                step.error = error
                step.completed_at = datetime.now()
                return True
        return False

    def get_progress_message(self) -> str:
        """Get a progress message for the current plan."""
        if not self._current_plan:
            return "No active plan"
        return self._current_plan.format_progress()

    def get_next_step_prompt(self) -> Optional[str]:
        """
        Get a prompt for the next step.

        Returns:
            Prompt string or None if no more steps
        """
        if not self._current_plan:
            return None

        next_step = self._current_plan.get_next_step()
        if not next_step:
            return None

        return f"""
## Executing Step {next_step.id}: {next_step.description}

Please execute this step now. When done, indicate completion.

Current Progress:
{self._current_plan.format_progress()}
"""

    def reset(self) -> "TaskPlanner":
        """Reset the planner (clear current plan)."""
        self._current_plan = None
        return self

    def create_plan(self, goal: str, steps: List[Dict[str, Any]]) -> TaskPlan:
        """
        Create a plan programmatically.

        Args:
            goal: Plan goal
            steps: List of step dictionaries

        Returns:
            Created TaskPlan
        """
        plan = TaskPlan(goal=goal)
        for step_data in steps:
            step = TaskStep(
                id=step_data.get("id", len(plan.steps) + 1),
                description=step_data["description"],
                depends_on=step_data.get("depends_on", []),
            )
            plan.steps.append(step)

        self._current_plan = plan
        return plan

    def get_stats(self) -> Dict[str, Any]:
        """Get planner statistics."""
        return {
            "enabled": self._enabled,
            "auto_execute": self._auto_execute,
            "has_plan": self._current_plan is not None,
            "progress": self._current_plan.get_progress() if self._current_plan else None,
        }
