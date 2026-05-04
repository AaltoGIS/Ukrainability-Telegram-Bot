"""Small thread-safe state container and survey dependency helpers."""

from __future__ import annotations

import copy
import threading
import time
from typing import Any, Optional


class UserState:
    def __init__(self) -> None:
        self._data: dict[int, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def get(self, user_id: int, key: Optional[str] = None, default: Any = None) -> Any:
        with self._lock:
            if key is None:
                return copy.deepcopy(self._data.get(user_id, default))
            return self._data.get(user_id, {}).get(key, default)

    def set(self, user_id: int, key: str, value: Any) -> None:
        with self._lock:
            self._data.setdefault(user_id, {})[key] = value
            self._data[user_id]["last_activity_time"] = time.time()

    def remove(self, user_id: int, key: str) -> None:
        with self._lock:
            if user_id in self._data:
                self._data[user_id].pop(key, None)

    def clear_keys(self, user_id: int, keys: list[str]) -> None:
        with self._lock:
            if user_id not in self._data:
                return
            for key in keys:
                self._data[user_id].pop(key, None)


QUESTION_DEPENDENCIES = {
    "regularity": ["frequency_change", "noticed_changes", "changes_detail"],
    "frequency_change": ["noticed_changes", "changes_detail"],
    "noticed_changes": ["changes_detail"],
}


def dependent_fields(field: str) -> list[str]:
    return list(QUESTION_DEPENDENCIES.get(field, []))


def requires_follow_up(regularity_response: str) -> bool:
    return regularity_response in [
        "I visit this place regularly",
        "I visit this place occasionally",
        "Відвідую це місце регулярно",
        "Відвідую це місце час від часу",
    ]


def skips_changes_questions(frequency_response: str) -> bool:
    return frequency_response in [
        "This is my first time here",
        "Це мій перший раз тут",
    ]


def requires_changes_detail(changes_response: str) -> bool:
    return changes_response in [
        "Yes, changes for the better",
        "Yes, changes for the worse",
        "Так, зміни на краще",
        "Так, зміни на гірше",
    ]
