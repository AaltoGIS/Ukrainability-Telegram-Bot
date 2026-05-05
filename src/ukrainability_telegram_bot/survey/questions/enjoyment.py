"""Enjoyment question handlers."""

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


@dataclass(frozen=True)
class EnjoymentCallbacks:
    ask_visitor_type: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]


@register("enjoyment")
class EnjoymentQuestion:
    name = "enjoyment"
    callback_prefix = "enjoyment_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_enjoyment(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_enjoyment_selection(ctx, call)


def ask_enjoyment(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
    remove_keyboard: bool = False,
) -> None:
    try:
        predefined_purposes = ctx.sessions.get_data(user_id, "purpose_visit", [])
        custom_purposes = ctx.sessions.get_data(user_id, "custom_purposes", [])
        all_purposes = predefined_purposes + custom_purposes

        if all_purposes:
            joined_purposes = ", ".join(all_purposes)
            enjoyment_text = messages[language][
                "enjoyment_question_with_purposes"
            ].format(purposes=joined_purposes)
        else:
            enjoyment_text = messages[language]["enjoyment_question"]

        ctx.sessions.set_data(user_id, "current_question", "enjoyment")

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"enjoyment_{idx}")
            for idx, option in enumerate(messages[language]["enjoyment_options"])
        ]
        inline_kb.add(*buttons)
        safe_send_message(ctx, chat_id, enjoyment_text, reply_markup=inline_kb)
    except Exception as exc:
        logging.exception(f"Error in ask_enjoyment: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def handle_enjoyment_selection(
    ctx: AppContext,
    call: Any,
    callbacks: EnjoymentCallbacks | None = None,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        language = ctx.sessions.get_data(user_id, "language")
        if not language:
            profile_language = ctx.sessions.get_profile(user_id, "language")
            if profile_language:
                language = profile_language
                ctx.sessions.set_data(user_id, "language", language)
            else:
                safe_send_message(ctx, chat_id, messages["en"]["please_use_start"])
                return

        options = messages[language]["enjoyment_options"]
        try:
            idx = callback_index(call.data, "enjoyment", options)
        except (ValueError, IndexError):
            safe_answer_callback(ctx, call, messages[language]["invalid_rating"])
            return

        enjoyment = options[idx]
        ctx.sessions.set_data(user_id, "temp_enjoyment", enjoyment)

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        for option_idx, option in enumerate(options):
            text = f"✅ {option}" if option_idx == idx else option
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=text,
                    callback_data=f"enjoyment_{option_idx}",
                )
            )
        inline_kb.add(
            types.InlineKeyboardButton(
                text=messages[language]["done_button"],
                callback_data="confirm_enjoyment",
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
                logging.exception(f"Telegram API error in handle_enjoyment_selection: {exc}")

        safe_answer_callback(ctx, call, f"{messages[language]['selected']} {enjoyment}")
    except Exception as exc:
        logging.exception(f"Error in handle_enjoyment_selection: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def confirm_enjoyment(
    ctx: AppContext,
    call: Any,
    callbacks: EnjoymentCallbacks,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        temp_enjoyment = ctx.sessions.get_data(user_id, "temp_enjoyment")

        if temp_enjoyment:
            ctx.sessions.set_data(user_id, "enjoyment", temp_enjoyment)
            ctx.sessions.remove_data(user_id, "temp_enjoyment")
            ctx.sessions.remove_data(user_id, "current_question")

            safe_answer_callback(ctx, call, messages[language]["response_confirmed"])
            ctx.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None,
            )

            safe_send_message(
                ctx,
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(temp_enjoyment)}</i>",
                parse_mode="HTML",
            )
            hide_keyboard(ctx, chat_id)

            if ctx.sessions.get_data(user_id, "modifying"):
                ctx.sessions.remove_data(user_id, "modifying")
                ctx.sessions.remove_data(user_id, "modifying_field")
                callbacks.ask_final_confirmation(chat_id, user_id, language)
            else:
                callbacks.ask_visitor_type(chat_id, user_id, language)
        else:
            safe_answer_callback(ctx, call, messages[language]["select_option_first"])
    except Exception as exc:
        logging.exception(f"Error in confirm_enjoyment: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])
