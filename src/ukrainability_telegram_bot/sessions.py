"""Thread-safe in-memory survey session storage."""

from __future__ import annotations

import copy
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


class SessionStore:
    """Own user session data, profile data, and tracked Telegram message IDs."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: dict[int, dict[str, Any]] = {}
        self._profiles: dict[int, dict[str, Any]] = {}
        self._message_ids: dict[int, dict[str, int]] = {}

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    @property
    def data(self) -> dict[int, dict[str, Any]]:
        return self._data

    @property
    def profiles(self) -> dict[int, dict[str, Any]]:
        return self._profiles

    @contextmanager
    def locked(self) -> Iterator[SessionStore]:
        with self._lock:
            yield self

    def get_data(self, user_id: int, key: str | None = None, default: Any = None) -> Any:
        with self._lock:
            session = self._data.setdefault(user_id, {})
            if key is None:
                return session
            return session.get(key, default)

    def set_data(self, user_id: int, key: str, value: Any) -> None:
        with self._lock:
            self._data.setdefault(user_id, {})[key] = value

    def remove_data(self, user_id: int, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(user_id, {}).pop(key, default)

    def get_profile(self, user_id: int, key: str | None = None, default: Any = None) -> Any:
        with self._lock:
            profile = self._profiles.setdefault(user_id, {})
            if key is None:
                return profile
            return profile.get(key, default)

    def set_profile(self, user_id: int, key: str, value: Any) -> None:
        with self._lock:
            self._profiles.setdefault(user_id, {})[key] = value

    def remove_profile(self, user_id: int, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._profiles.get(user_id, {}).pop(key, default)

    def snapshot(self, user_id: int) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._data.get(user_id, {}))

    def profile_snapshot(self, user_id: int) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._profiles.get(user_id, {}))

    def all_user_ids(self) -> list[int]:
        with self._lock:
            return list(self._data.keys())

    def update_activity(self, user_id: int) -> None:
        self.set_data(user_id, "last_activity_time", time.time())

    def evict_inactive(self, hours: int) -> list[int]:
        cutoff_time = time.time() - (hours * 60 * 60)
        removed: list[int] = []
        with self._lock:
            for user_id, data in list(self._data.items()):
                if data.get("last_activity_time", 0) < cutoff_time:
                    self._data.pop(user_id, None)
                    removed.append(user_id)
        return removed

    def register_message_id(self, user_id: int, message_type: str, message_id: int) -> None:
        with self._lock:
            self._message_ids.setdefault(user_id, {})[message_type] = message_id

    def get_message_id(self, user_id: int, message_type: str) -> int | None:
        with self._lock:
            return self._message_ids.get(user_id, {}).get(message_type)

    def clear_message_ids(self, user_id: int) -> None:
        with self._lock:
            self._message_ids.pop(user_id, None)

    def clear_transient_keys(
        self,
        user_id: int,
        *,
        prefixes: set[str] | frozenset[str] = frozenset(),
        exact_keys: set[str] | frozenset[str] = frozenset(),
    ) -> None:
        with self._lock:
            session = self._data.get(user_id)
            if not session:
                return
            for key in list(session):
                if key in exact_keys or any(key.startswith(prefix) for prefix in prefixes):
                    session.pop(key, None)
