from collections import deque
from dataclasses import dataclass, field
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass
class EventQueue(Generic[T]):
    """FIFO queue for staged effects, sounds, and animation events."""

    _items: deque[T] = field(default_factory=deque)

    def enqueue(self, item: T) -> None:
        self._items.append(item)

    def dequeue(self) -> T:
        if not self._items:
            raise IndexError("Cannot dequeue from an empty event queue.")
        return self._items.popleft()

    def peek(self) -> T | None:
        return self._items[0] if self._items else None

    def is_empty(self) -> bool:
        return not self._items

    def __len__(self) -> int:
        return len(self._items)
