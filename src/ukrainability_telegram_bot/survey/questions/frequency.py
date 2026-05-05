"""Visit-frequency change question handlers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from telebot import types

from ...app import AppContext
from ...messages import messages
from ...telegram_io import (
    callback_index,
    escape_html,
    safe_answer_callback,
    safe_send_message,
)
from .base import register


DID_NOT_VISIT_BEFORE_INDICES = frozenset({0})


@dataclass(frozen=True)
class FrequencyCallbacks:
    ask_noticed_changes: Callable[[int, int, str], Any]
    ask_wishlist: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]
    clear_dependent_fields: Callable[[int, str, Any, Any], list[str]]
    get_anonymous_id: Callable[[int], str]


@register("frequency_change")
class FrequencyQuestion:
    name = "frequency_change"
    callback_prefix = "frequency_change_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_frequency_change(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_frequency_change_selection(ctx, call)


def ask_frequency_change(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
) -> None:
    try:
        ctx.sessions.set_data(user_id, "frequency_change", "")
        ctx.sessions.set_data(user_id, "current_question", "frequency_change")
        options = messages[language]["options"]["frequency_change"]
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton(
                text=option,
                callback_data=f"frequency_change_{idx}",
            )
            for idx, option in enumerate(options)
        ]
        inline_kb.add(*buttons)
        safe_send_message(
            ctx,
            chat_id,
            messages[language]["frequency_change_question"],
            reply_markup=inline_kb,
        )
    except Exception as exc:
        logging.exception(f"Error in ask_frequency_change: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def handle_frequency_change_selection(
    ctx: AppContext,
    call: Any,
    callbacks: FrequencyCallbacks | None = None,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        anon_id = callbacks.get_anonymous_id(user_id) if callbacks else "unknown"
        options = messages[language]["options"]["frequency_change"]

        try:
            idx = callback_index(call.data, "frequency_change", options)
        except (ValueError, IndexError):
            safe_answer_callback(ctx, call, messages[language]["invalid_selection"])
            return

        selected_frequency_change = options[idx]
        previous_freq_change = ctx.sessions.get_data(user_id, "frequency_change", "")

        if (
            callbacks is not None
            and ctx.sessions.get_data(user_id, "modifying")
            and previous_freq_change != selected_frequency_change
        ):
            ctx.flow_logger.info(
                "User %s: Modified frequency_change from '%s' to '%s'",
                anon_id,
                previous_freq_change,
                selected_frequency_change,
            )

        ctx.sessions.set_data(user_id, "frequency_change", selected_frequency_change)
        ctx.sessions.remove_data(user_id, "current_question")

        safe_answer_callback(
            ctx,
            call,
            f"{messages[language]['selected']} {selected_frequency_change}",
        )
        ctx.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
        safe_send_message(
            ctx,
            chat_id,
            f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_frequency_change)}</i>",
            parse_mode="HTML",
        )

        if callbacks is not None and previous_freq_change != selected_frequency_change:
            callbacks.clear_dependent_fields(
                user_id,
                "frequency_change",
                previous_freq_change,
                selected_frequency_change,
            )

        did_not_visit_before = idx in DID_NOT_VISIT_BEFORE_INDICES
        if did_not_visit_before:
            ctx.sessions.set_data(user_id, "noticed_changes", selected_frequency_change)

        if callbacks is None:
            return

        if ctx.sessions.get_data(user_id, "modifying"):
            if did_not_visit_before:
                ctx.sessions.remove_data(user_id, "modifying")
                ctx.sessions.remove_data(user_id, "modifying_field")
                callbacks.ask_final_confirmation(chat_id, user_id, language)
            else:
                callbacks.ask_noticed_changes(chat_id, user_id, language)
        elif did_not_visit_before:
            callbacks.ask_wishlist(chat_id, user_id, language)
        else:
            callbacks.ask_noticed_changes(chat_id, user_id, language)
    except Exception as exc:
        logging.exception(f"Error in handle_frequency_change_selection: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])
