from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

MEMORY_REFERENCE_PREFIX = "$memory."


class MemoryReferenceError(ValueError):
    """Raised when a tool argument references missing short-term memory."""


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
