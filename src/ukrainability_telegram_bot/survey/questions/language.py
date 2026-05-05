"""Language-selection handlers."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ...app import AppContext
from ...messages import messages
from ...telegram_io import (
    callback_suffix,
    safe_answer_callback,
    safe_send_message,
    send_next_step_prompt,
)
from . import consent as consent_question
from .base import register, resolve_actions


@dataclass(frozen=True)
class LanguageCallbacks:
    location_handler: Callable[..., Any]


def callbacks_from_context(ctx: AppContext, actions: Any | None = None) -> LanguageCallbacks:
    actions = resolve_actions(ctx, actions)
    return LanguageCallbacks(
        location_handler=actions.handle_location_step,
    )


@register("language")
class LanguageQuestion:
    name = "language"
    callback_prefix = "language_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        raise NotImplementedError("language prompt is sent by the welcome question")

    def handle(self, ctx: AppContext, call: Any) -> None:
        raise NotImplementedError("language handlers need explicit callbacks")


def handle_language_selection(
    ctx: AppContext,
    call: Any,
    callbacks: LanguageCallbacks,
) -> None:
    chat_id = call.message.chat.id
    try:
        user_id = call.from_user.id
        data = callback_suffix(call.data, "language")

        if data not in {"en", "uk"}:
            safe_answer_callback(ctx, call, messages["en"]["invalid_selection"])
            return

        language = data
        ctx.sessions.set_data(user_id, "language", language)
        ctx.sessions.set_profile(user_id, "language", language)

        safe_answer_callback(
            ctx,
            call,
            messages[language]["language_callback_ack"].format(language=language.upper()),
        )
        ctx.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
        safe_send_message(ctx, chat_id, messages[language]["language_selected"])

        consent = ctx.sessions.get_profile(user_id, "consent")
        if consent is True:
            time.sleep(0.5)
            send_next_step_prompt(
                ctx,
                chat_id,
                messages[language]["send_location"],
                callbacks.location_handler,
            )
            return

        consent_question.ConsentQuestion().ask(ctx, chat_id, user_id, language)
    except Exception as exc:
        logging.exception(f"Error in handle_language_selection: {exc}")
        safe_send_message(ctx, chat_id, messages["en"]["error_occurred"])
