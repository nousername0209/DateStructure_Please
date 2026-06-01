from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")
K = TypeVar("K")


def merge_sort(items: list[T], key: Callable[[T], K], reverse: bool = False) -> list[T]:
    if len(items) <= 1:
        return items[:]

    middle = len(items) // 2
    left = merge_sort(items[:middle], key, reverse)
    right = merge_sort(items[middle:], key, reverse)
    return _merge(left, right, key, reverse)


def _merge(
    left: list[T],
    right: list[T],
    key: Callable[[T], K],
    reverse: bool,
) -> list[T]:
    result = []
    i = 0
    j = 0

    while i < len(left) and j < len(right):
        left_key = key(left[i])
        right_key = key(right[j])
        take_left = left_key >= right_key if reverse else left_key <= right_key
        if take_left:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result


def binary_search_by_id(profiles: list[dict], profile_id: str) -> dict | None:
    low = 0
    high = len(profiles) - 1

    while low <= high:
        mid = (low + high) // 2
        current_id = profiles[mid]["id"]
        if current_id == profile_id:
            return profiles[mid]
        if current_id < profile_id:
            low = mid + 1
        else:
            high = mid - 1
    return None
