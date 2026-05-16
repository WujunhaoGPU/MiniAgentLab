from __future__ import annotations

import re
from abc import ABC, abstractmethod

from .schemas import Plan, Step
from .tool_registry import ToolRegistry


class Planner(ABC):
    @abstractmethod
    def plan(self, task: str, tools: ToolRegistry) -> Plan:
        raise NotImplementedError


class RuleBasedPlanner(Planner):
    """A deterministic planner for the first runnable loop."""

    _expression_pattern = re.compile(r"[-+*/().%\d\s]+")

    def plan(self, task: str, tools: ToolRegistry) -> Plan:
        if tools.has("calculator"):
            expression = self._extract_expression(task)
            if expression:
                return Plan(
                    goal=task,
                    steps=[
                        Step(
                            id="step_1",
                            description="Evaluate the arithmetic expression.",
                            tool="calculator",
                            args={"expression": expression},
                        )
                    ],
                )

        available = ", ".join(tools.names()) or "no tools"
        raise ValueError(f"RuleBasedPlanner could not plan this task. Available tools: {available}")

    def _extract_expression(self, task: str) -> str | None:
        candidates = [match.group(0).strip() for match in self._expression_pattern.finditer(task)]
        candidates = [item for item in candidates if any(char.isdigit() for char in item)]
        if not candidates:
            return None
        return max(candidates, key=len)
