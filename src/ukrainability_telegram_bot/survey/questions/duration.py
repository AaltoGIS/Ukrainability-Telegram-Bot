"""Duration question handlers."""

from __future__ import annotations

import logging
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
from .base import DurationCallbacks, register


@register("duration")
class DurationQuestion:
    name = "duration"
    callback_prefix = "duration_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_duration(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_duration_selection(ctx, call)


def ask_duration(ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
    try:
        ctx.sessions.set_data(user_id, "duration_visit", "")
        ctx.sessions.set_data(user_id, "current_question", "duration")

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        for idx, option in enumerate(messages[language]["duration_options"]):
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=option,
                    callback_data=f"duration_{idx}",
                )
            )

        safe_send_message(
            ctx,
            chat_id,
            messages[language]["duration_question"],
            reply_markup=inline_kb,
        )
    except Exception as exc:
        logging.exception(f"Error in ask_duration: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def handle_duration_selection(ctx: AppContext, call: Any) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        options = messages[language]["duration_options"]

        try:
            idx = callback_index(call.data, "duration", options)
        except (ValueError, IndexError):
            safe_answer_callback(ctx, call, messages[language]["invalid_selection"])
            return

        selected_duration = options[idx]
        ctx.sessions.set_data(user_id, "temp_duration_visit", selected_duration)

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        for option_idx, option in enumerate(options):
            text = f"✅ {option}" if option_idx == idx else option
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=text,
                    callback_data=f"duration_{option_idx}",
                )
            )
        inline_kb.add(
            types.InlineKeyboardButton(
                text=messages[language]["done_button"],
                callback_data="confirm_duration",
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
                raise

        safe_answer_callback(
            ctx,
            call,
            f"{messages[language]['selected']} {selected_duration}",
        )
    except Exception as exc:
        logging.exception(f"Error in handle_duration_selection: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def confirm_duration(
    ctx: AppContext,
    call: Any,
    callbacks: DurationCallbacks,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        selected_duration = ctx.sessions.get_data(user_id, "temp_duration_visit")

        if selected_duration:
            ctx.sessions.set_data(user_id, "duration_visit", selected_duration)
            ctx.sessions.remove_data(user_id, "temp_duration_visit")
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
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_duration)}</i>",
                parse_mode="HTML",
            )
            hide_keyboard(ctx, chat_id)

            if ctx.sessions.get_data(user_id, "modifying"):
                ctx.sessions.remove_data(user_id, "modifying")
                ctx.sessions.remove_data(user_id, "modifying_field")
                callbacks.ask_final_confirmation(chat_id, user_id, language)
            else:
                callbacks.ask_accessibility(chat_id, user_id, language)
        else:
            safe_answer_callback(ctx, call, messages[language]["select_option_first"])
    except Exception as exc:
        logging.exception(f"Error in confirm_duration: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])
