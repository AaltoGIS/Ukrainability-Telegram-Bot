"""Question-module registry primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from ...app import AppContext


class Question(Protocol):
    name: str
    callback_prefix: str

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> Any: ...

    def handle(self, ctx: AppContext, call: Any) -> Any: ...


QUESTIONS: dict[str, Question] = {}


def register(name: str) -> Callable[[type[Question]], type[Question]]:
    def decorator(question_cls: type[Question]) -> type[Question]:
        QUESTIONS[name] = question_cls()
        return question_cls

    return decorator


def resolve_actions(ctx: AppContext, actions: Any | None = None) -> Any:
    if actions is not None:
        return actions

    from ..actions import SurveyActions

    return SurveyActions(ctx)


@dataclass(frozen=True)
class ConsentCallbacks:
    location_handler: Callable[..., Any]


@dataclass(frozen=True)
class PurposeCallbacks:
    ask_enjoyment: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]
    clear_callback_state: Callable[[int], Any] | None = None


@dataclass(frozen=True)
class DescriptionCallbacks:
    ask_final_confirmation: Callable[[int, int, str], Any]
    description_handler: Callable[..., Any]
