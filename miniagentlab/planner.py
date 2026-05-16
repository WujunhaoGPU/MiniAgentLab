from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from .llm import LLMClient
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


class LLMPlanner(Planner):
    """Uses an LLM to produce a structured Plan JSON object."""

    def __init__(self, llm: LLMClient, max_retries: int = 1) -> None:
        self.llm = llm
        self.max_retries = max_retries

    def plan(self, task: str, tools: ToolRegistry) -> Plan:
        prompt = self._build_prompt(task, tools)
        last_error: str | None = None

        for attempt in range(self.max_retries + 1):
            response = self.llm.complete(prompt)
            try:
                return self._parse_plan(response, tools)
            except ValueError as exc:
                last_error = str(exc)
                prompt = self._build_repair_prompt(task, response, last_error, tools)

        raise ValueError(f"LLMPlanner failed to produce a valid plan: {last_error}")

    def _build_prompt(self, task: str, tools: ToolRegistry) -> str:
        tool_specs = [
            {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            }
            for spec in tools.specs()
        ]
        return (
            "Create a JSON execution plan for the user task.\n"
            "Return only one JSON object, without markdown fences or commentary.\n"
            "The JSON schema is:\n"
            "{\n"
            '  "goal": "string",\n'
            '  "steps": [\n'
            "    {\n"
            '      "id": "step_1",\n'
            '      "description": "string",\n'
            '      "tool": "registered_tool_name",\n'
            '      "args": {"argument_name": "argument_value"}\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"Registered tools:\n{json.dumps(tool_specs, ensure_ascii=False, indent=2)}\n\n"
            f"User task:\n{task}"
        )

    def _build_repair_prompt(
        self,
        task: str,
        previous_response: str,
        error: str,
        tools: ToolRegistry,
    ) -> str:
        return (
            f"{self._build_prompt(task, tools)}\n\n"
            "Your previous response could not be parsed or validated.\n"
            f"Validation error: {error}\n"
            f"Previous response:\n{previous_response}\n\n"
            "Return a corrected JSON object only."
        )

    def _parse_plan(self, response: str, tools: ToolRegistry) -> Plan:
        raw = self._extract_json(response)
        goal = raw.get("goal")
        steps_raw = raw.get("steps")

        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("Plan goal must be a non-empty string")
        if not isinstance(steps_raw, list) or not steps_raw:
            raise ValueError("Plan steps must be a non-empty list")

        steps: list[Step] = []
        for index, item in enumerate(steps_raw, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"Step {index} must be an object")

            step_id = item.get("id")
            description = item.get("description")
            tool = item.get("tool")
            args = item.get("args", {})

            if not isinstance(step_id, str) or not step_id.strip():
                raise ValueError(f"Step {index} id must be a non-empty string")
            if not isinstance(description, str) or not description.strip():
                raise ValueError(f"Step {index} description must be a non-empty string")
            if not isinstance(tool, str) or not tool.strip():
                raise ValueError(f"Step {index} tool must be a non-empty string")
            if not tools.has(tool):
                raise ValueError(f"Step {index} references unknown tool: {tool}")
            if not isinstance(args, dict):
                raise ValueError(f"Step {index} args must be an object")

            steps.append(Step(id=step_id, description=description, tool=tool, args=args))

        return Plan(goal=goal, steps=steps)

    def _extract_json(self, response: str) -> dict[str, Any]:
        text = response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        decoder = json.JSONDecoder()
        candidates = [text]
        first_brace = text.find("{")
        if first_brace > 0:
            candidates.append(text[first_brace:])

        for candidate in candidates:
            try:
                parsed, _ = decoder.raw_decode(candidate)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                raise ValueError("Planner response JSON must be an object")
            return parsed

        raise ValueError("Planner response did not contain a valid JSON object")
