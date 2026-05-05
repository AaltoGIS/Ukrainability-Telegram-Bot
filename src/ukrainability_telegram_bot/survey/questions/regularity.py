"""Regularity question handlers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import telebot
from telebot import types

from ...app import AppContext
from ...messages import messages
from ...telegram_io import (
    callback_index,
    escape_html,
    hide_keyboard,
    safe_answer_callback,
    safe_send_message,
)
from .base import register


SKIP_TO_WISHLIST_INDICES = frozenset({4, 5, 6})


@dataclass(frozen=True)
class RegularityCallbacks:
    ask_noticed_changes: Callable[[int, int, str], Any]
    ask_wishlist: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]
    clear_dependent_fields: Callable[[int, str, Any, Any], list[str]]
    get_anonymous_id: Callable[[int], str]


@register("regularity")
class RegularityQuestion:
    name = "regularity"
    callback_prefix = "regularity_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_regularity(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_regularity_selection(ctx, call)


def ask_regularity(ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
    try:
        ctx.sessions.set_data(user_id, "regularity", "")
        ctx.sessions.set_data(user_id, "current_question", "regularity")

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"regularity_{idx}")
            for idx, option in enumerate(messages[language]["options"]["regularity"])
        ]
        inline_kb.add(*buttons)

        safe_send_message(
            ctx,
            chat_id,
            messages[language]["regularity_question"],
            reply_markup=inline_kb,
        )
    except Exception as exc:
        logging.exception(f"Error in ask_regularity: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def handle_regularity_selection(ctx: AppContext, call: Any) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        options = messages[language]["options"]["regularity"]

        try:
            selected_idx = callback_index(call.data, "regularity", options)
        except (ValueError, IndexError):
            safe_answer_callback(ctx, call, messages[language]["invalid_selection"])
            return

        selected_regularity = options[selected_idx]
        ctx.sessions.set_data(user_id, "temp_regularity", selected_regularity)
        ctx.sessions.set_data(user_id, "temp_regularity_idx", selected_idx)

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        for idx, option in enumerate(options):
            text = f"✅ {option}" if idx == selected_idx else option
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=text,
                    callback_data=f"regularity_{idx}",
                )
            )
        inline_kb.add(
            types.InlineKeyboardButton(
                text=messages[language]["done_button"],
                callback_data="confirm_regularity",
            )
        )

        try:
            ctx.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=inline_kb,
            )
        except telebot.apihelper.ApiTelegramException as exc:
            if "message is not modified" not in str(exc):
                logging.exception(f"Error in handle_regularity_selection: {exc}")

        safe_answer_callback(
            ctx,
            call,
            f"{messages[language]['selected']} {selected_regularity}",
        )
    except Exception as exc:
        logging.exception(f"Error in handle_regularity_selection: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def confirm_regularity(
    ctx: AppContext,
    call: Any,
    callbacks: RegularityCallbacks,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        anon_id = callbacks.get_anonymous_id(user_id)
        selected_regularity = ctx.sessions.get_data(user_id, "temp_regularity")

        if selected_regularity:
            selected_idx = ctx.sessions.get_data(user_id, "temp_regularity_idx")
            if selected_idx is None:
                try:
                    selected_idx = messages[language]["options"]["regularity"].index(
                        selected_regularity
                    )
                except ValueError:
                    selected_idx = -1
            previous_regularity = ctx.sessions.get_data(user_id, "regularity", "")
            if previous_regularity != selected_regularity:
                ctx.flow_logger.info(
                    "User %s: Changed regularity from '%s' to '%s'",
                    anon_id,
                    previous_regularity,
                    selected_regularity,
                )

            ctx.sessions.set_data(user_id, "regularity", selected_regularity)
            ctx.sessions.set_profile(user_id, "regularity", selected_regularity)
            ctx.sessions.remove_data(user_id, "temp_regularity")
            ctx.sessions.remove_data(user_id, "temp_regularity_idx")
            ctx.sessions.remove_data(user_id, "current_question")

            if previous_regularity != selected_regularity:
                cleared_fields = callbacks.clear_dependent_fields(
                    user_id,
                    "regularity",
                    previous_regularity,
                    selected_regularity,
                )
                if cleared_fields:
                    ctx.flow_logger.info(
                        "User %s: Cleared fields due to regularity change: %s",
                        anon_id,
                        cleared_fields,
                    )

            safe_answer_callback(ctx, call, messages[language]["response_confirmed"])
            ctx.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None,
            )
            safe_send_message(
                ctx,
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_regularity)}</i>",
                parse_mode="HTML",
            )
            hide_keyboard(ctx, chat_id)

            should_skip = selected_idx in SKIP_TO_WISHLIST_INDICES
            if ctx.sessions.get_data(user_id, "modifying"):
                if not should_skip:
                    ctx.flow_logger.info(
                        "User %s: In modification flow, proceeding to noticed_changes",
                        anon_id,
                    )
                    callbacks.ask_noticed_changes(chat_id, user_id, language)
                else:
                    ctx.flow_logger.info(
                        "User %s: In modification flow, skipping follow-ups, going to final confirmation",
                        anon_id,
                    )
                    ctx.sessions.remove_data(user_id, "modifying")
                    ctx.sessions.remove_data(user_id, "modifying_field")
                    callbacks.ask_final_confirmation(chat_id, user_id, language)
            elif should_skip:
                ctx.flow_logger.info("User %s: Skipping directly to wishlist", anon_id)
                callbacks.ask_wishlist(chat_id, user_id, language)
            else:
                ctx.flow_logger.info(
                    "User %s: Regular visitor, proceeding to noticed_changes",
                    anon_id,
                )
                callbacks.ask_noticed_changes(chat_id, user_id, language)
        else:
            safe_answer_callback(ctx, call, messages[language]["select_option_first"])
    except Exception as exc:
        logging.exception(f"Error in confirm_regularity: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])
