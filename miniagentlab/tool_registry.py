from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .schemas import ToolResult


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, str]
    func: Callable[..., Any]


class ToolRegistry:
    """Registers Python functions and calls them through a uniform result shape."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def tool(self, name: str | None = None, description: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.register(func, name=name, description=description)
            return func

        return decorator

    def register(
        self,
        func: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
    ) -> ToolSpec:
        tool_name = name or func.__name__
        if tool_name in self._tools:
            raise ValueError(f"Tool already registered: {tool_name}")

        spec = ToolSpec(
            name=tool_name,
            description=description or inspect.getdoc(func) or "",
            parameters=self._parameters_for(func),
            func=func,
        )
        self._tools[tool_name] = spec
        return spec

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            return ToolResult(success=False, error=f"Unknown tool: {name}")

        try:
            output = spec.func(**kwargs)
            return ToolResult(success=True, output=output)
        except Exception as exc:  # noqa: BLE001 - tools should not crash the agent loop
            return ToolResult(success=False, error=f"{type(exc).__name__}: {exc}")

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self) -> list[ToolSpec]:
        return [self._tools[name] for name in self.names()]

    def _parameters_for(self, func: Callable[..., Any]) -> dict[str, str]:
        signature = inspect.signature(func)
        return {
            name: str(parameter.annotation)
            for name, parameter in signature.parameters.items()
        }
