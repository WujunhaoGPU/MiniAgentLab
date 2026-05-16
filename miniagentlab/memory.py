from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

MEMORY_REFERENCE_PREFIX = "$memory."


class MemoryReferenceError(ValueError):
    """Raised when a tool argument references missing short-term memory."""


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryItem:
    key: str
    value: Any
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ShortTermMemory:
    """Stores step outputs for a single agent run."""

    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}

    def set(self, key: str, value: Any, source: str, **metadata: Any) -> None:
        self._items[key] = MemoryItem(
            key=key,
            value=value,
            source=source,
            metadata=metadata,
        )

    def get(self, key: str, default: Any = None) -> Any:
        item = self._items.get(key)
        if item is None:
            return default
        return item.value

    def clear(self) -> None:
        self._items.clear()

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {key: item.to_dict() for key, item in self._items.items()}

    def resolve_references(self, value: Any) -> Any:
        if isinstance(value, str) and value.startswith(MEMORY_REFERENCE_PREFIX):
            key = value.removeprefix(MEMORY_REFERENCE_PREFIX)
            if not key:
                raise MemoryReferenceError("Memory reference is missing a key")
            if key not in self._items:
                raise MemoryReferenceError(f"Memory reference not found: {value}")
            return self._items[key].value

        if isinstance(value, dict):
            return {key: self.resolve_references(item) for key, item in value.items()}

        if isinstance(value, list):
            return [self.resolve_references(item) for item in value]

        return value


class ConversationMemory:
    """Stores user/assistant turns across agent runs."""

    allowed_roles = {"user", "assistant", "system"}

    def __init__(self, max_turns: int = 20) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")

        self.max_turns = max_turns
        self._turns: list[ConversationTurn] = []

    def add(self, role: str, content: str, **metadata: Any) -> None:
        if role not in self.allowed_roles:
            raise ValueError(f"Unsupported conversation role: {role}")
        self._turns.append(
            ConversationTurn(
                role=role,
                content=content,
                metadata=metadata,
            )
        )
        self._turns = self._turns[-self.max_turns :]

    def recent(self, limit: int | None = None) -> list[ConversationTurn]:
        if limit is None:
            return list(self._turns)
        if limit < 1:
            return []
        return self._turns[-limit:]

    def clear(self) -> None:
        self._turns.clear()

    def to_dict(self) -> list[dict[str, Any]]:
        return [turn.to_dict() for turn in self._turns]
