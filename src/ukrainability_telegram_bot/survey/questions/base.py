"""Question-module registry primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from ...app import AppContext


class Question(Protocol):
    name: str
    callback_prefix: str

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> Any:
        ...

    def handle(self, ctx: AppContext, call: Any) -> Any:
        ...


QUESTIONS: dict[str, Question] = {}


def register(name: str) -> Callable[[type[Question]], type[Question]]:
    def decorator(question_cls: type[Question]) -> type[Question]:
        QUESTIONS[name] = question_cls()
        return question_cls

    return decorator


@dataclass(frozen=True)
class ConsentCallbacks:
    location_handler: Callable[..., Any]


@dataclass(frozen=True)
class PurposeCallbacks:
    ask_enjoyment: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]
    clear_callback_state: Callable[[int], Any] | None = None


@dataclass(frozen=True)
class EnjoymentCallbacks:
    ask_visitor_type: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]


@dataclass(frozen=True)
class VisitorTypeCallbacks:
    ask_duration: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]


@dataclass(frozen=True)
class DurationCallbacks:
    ask_accessibility: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]


@dataclass(frozen=True)
class AccessibilityCallbacks:
    ask_regularity: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]


@dataclass(frozen=True)
class RegularityCallbacks:
    ask_noticed_changes: Callable[[int, int, str], Any]
    ask_wishlist: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]
    clear_dependent_fields: Callable[[int, str, Any, Any], list[str]]
    get_anonymous_id: Callable[[int], str]


@dataclass(frozen=True)
class DescriptionCallbacks:
    ask_final_confirmation: Callable[[int, int, str], Any]
    description_handler: Callable[..., Any]
