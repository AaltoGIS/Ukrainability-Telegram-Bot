"""Kremenchuk residency question handlers."""

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
    callback_suffix,
    escape_html,
    hide_keyboard,
    safe_answer_callback,
    safe_send_message,
)
from .base import register


OTHER_OPTION_INDEX = 6


@dataclass(frozen=True)
class KremenchukCallbacks:
    ask_description: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]


def callbacks_from_bridge(bridge: Any) -> KremenchukCallbacks:
    return KremenchukCallbacks(
        ask_description=bridge.ask_description,
        ask_final_confirmation=bridge.ask_final_confirmation,
    )


@register("kremenchuk")
class KremenchukQuestion:
    name = "kremenchuk"
    callback_prefix = "kremenchuk_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_kremenchuk(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_kremenchuk_selection(ctx, call)


def _options(language: str) -> list[str]:
    all_options = messages[language]["options"]["kremenchuk"]
    return [
        option
        for idx, option in enumerate(all_options)
        if idx != OTHER_OPTION_INDEX
    ]


def ask_kremenchuk(ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
    try:
        ctx.sessions.set_data(user_id, "kremenchuk", "")
        ctx.sessions.set_data(user_id, "custom_kremenchuk", [])
        ctx.sessions.set_data(user_id, "awaiting_multiple_select", "kremenchuk")

        options = _options(language)
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"kremenchuk_{idx}")
            for idx, option in enumerate(options)
        ]
        inline_kb.add(*buttons)
        inline_kb.add(
            types.InlineKeyboardButton(
                text=messages[language]["done_button"],
                callback_data="kremenchuk_done",
            )
        )
        instruction_text = (
            f"{messages[language]['kremenchuk_question']}\n\n"
            f"{messages[language]['kremenchuk_custom_instruction']}"
        )
        safe_send_message(ctx, chat_id, instruction_text, reply_markup=inline_kb)
    except Exception as exc:
        logging.exception(f"Error in ask_kremenchuk: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def handle_kremenchuk_selection(
    ctx: AppContext,
    call: Any,
    callbacks: KremenchukCallbacks | None = None,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        data = callback_suffix(call.data, "kremenchuk")
        options = _options(language)

        if data == "done":
            selected = ctx.sessions.get_data(user_id, "kremenchuk", "")
            custom = ctx.sessions.get_data(user_id, "custom_kremenchuk", [])
            if not selected and not custom:
                safe_answer_callback(
                    ctx,
                    call,
                    messages[language]["please_select_at_least_one"],
                )
                return

            ctx.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None,
            )

            all_values = []
            if selected:
                all_values.append(selected)
                ctx.sessions.set_profile(user_id, "kremenchuk", selected)
            all_values.extend(custom)
            selected_text = "; ".join(escape_html(value) for value in all_values)
            safe_send_message(
                ctx,
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{selected_text}</i>",
                parse_mode="HTML",
            )
            ctx.sessions.remove_data(user_id, "awaiting_multiple_select")
            hide_keyboard(ctx, chat_id)

            if callbacks is None:
                return
            if ctx.sessions.get_data(user_id, "modifying"):
                ctx.sessions.remove_data(user_id, "modifying")
                ctx.sessions.remove_data(user_id, "modifying_field")
                callbacks.ask_final_confirmation(chat_id, user_id, language)
            else:
                callbacks.ask_description(chat_id, user_id, language)
            return

        try:
            idx = callback_index(call.data, "kremenchuk", options)
        except (ValueError, IndexError):
            safe_answer_callback(ctx, call, messages[language]["invalid_selection"])
            return

        selected_kremenchuk = options[idx]
        ctx.sessions.set_data(user_id, "kremenchuk", selected_kremenchuk)
        safe_answer_callback(
            ctx,
            call,
            f"{messages[language]['selected']} {selected_kremenchuk}",
        )
        update_kremenchuk_keyboard(ctx, call.message, user_id, language, options)
    except Exception as exc:
        logging.exception(f"Error in handle_kremenchuk_selection: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def update_kremenchuk_keyboard(
    ctx: AppContext,
    message: Any,
    user_id: int,
    language: str,
    options: list[str],
) -> None:
    try:
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        selected = ctx.sessions.get_data(user_id, "kremenchuk", "")
        custom = ctx.sessions.get_data(user_id, "custom_kremenchuk", [])

        buttons = []
        for idx, option in enumerate(options):
            button_text = f"✅ {option}" if option == selected else option
            buttons.append(
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"kremenchuk_{idx}",
                )
            )

        if selected or custom:
            inline_kb.add(*buttons)
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=messages[language]["done_button"],
                    callback_data="kremenchuk_done",
                )
            )
        else:
            inline_kb.add(*buttons)

        try:
            ctx.bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=inline_kb,
            )
        except telebot.apihelper.ApiTelegramException as exc:
            if "message is not modified" not in str(exc):
                logging.exception(f"Error in update_kremenchuk_keyboard: {exc}")
    except Exception as exc:
        logging.exception(f"Error in update_kremenchuk_keyboard: {exc}")
