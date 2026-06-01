from dataclasses import dataclass, field
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass
class UIStack(Generic[T]):
    """Stack for active screen and overlay management."""

    _items: list[T] = field(default_factory=list)

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        if not self._items:
            raise IndexError("Cannot pop from an empty UI stack.")
        return self._items.pop()

    def peek(self) -> T | None:
        return self._items[-1] if self._items else None

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)
