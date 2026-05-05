"""Visitor-type question handlers."""

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


@dataclass(frozen=True)
class VisitorTypeCallbacks:
    ask_duration: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]


@register("visitor_type")
class VisitorTypeQuestion:
    name = "visitor_type"
    callback_prefix = "visitor_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_visitor_type(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_visitor_type_selection(ctx, call)


def ask_visitor_type(ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
    try:
        ctx.sessions.set_data(user_id, "visitor_type", [])
        ctx.sessions.set_data(user_id, "custom_visitor_types", [])
        ctx.sessions.set_data(user_id, "awaiting_multiple_select", "visitor_type")

        options = messages[language]["visitor_type_options"][:-1]
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"visitor_{idx}")
            for idx, option in enumerate(options)
        ]
        inline_kb.add(*buttons)
        inline_kb.add(
            types.InlineKeyboardButton(
                text=messages[language]["done_button"],
                callback_data="visitor_done",
            )
        )

        instruction_text = (
            f"{messages[language]['visitor_type_question']}\n\n"
            f"{messages[language]['visitor_type_custom_instruction']}"
        )
        safe_send_message(ctx, chat_id, instruction_text, reply_markup=inline_kb)
    except Exception as exc:
        logging.exception(f"Error in ask_visitor_type: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def handle_visitor_type_selection(
    ctx: AppContext,
    call: Any,
    callbacks: VisitorTypeCallbacks | None = None,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        data = callback_suffix(call.data, "visitor")
        options = messages[language]["visitor_type_options"][:-1]

        if data == "done":
            selected = ctx.sessions.get_data(user_id, "visitor_type", [])
            custom = ctx.sessions.get_data(user_id, "custom_visitor_types", [])
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

            all_visitor_types = selected + custom
            escaped = "; ".join(escape_html(option) for option in all_visitor_types)
            safe_send_message(
                ctx,
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escaped}</i>",
                parse_mode="HTML",
            )
            ctx.sessions.remove_data(user_id, "awaiting_multiple_select")
            hide_keyboard(ctx, chat_id)

            if ctx.sessions.get_data(user_id, "modifying"):
                ctx.sessions.remove_data(user_id, "modifying")
                ctx.sessions.remove_data(user_id, "modifying_field")
                if callbacks is not None:
                    callbacks.ask_final_confirmation(chat_id, user_id, language)
            elif callbacks is not None:
                callbacks.ask_duration(chat_id, user_id, language)
            return

        try:
            idx = callback_index(call.data, "visitor", options)
        except (ValueError, IndexError):
            safe_answer_callback(ctx, call, messages[language]["invalid_selection"])
            return

        choice = options[idx]
        selected = ctx.sessions.get_data(user_id, "visitor_type", [])
        if choice in selected:
            selected.remove(choice)
            safe_answer_callback(ctx, call, f"{messages[language]['unselected']} {choice}")
        else:
            selected.append(choice)
            safe_answer_callback(ctx, call, f"{messages[language]['selected']} {choice}")

        ctx.sessions.set_data(user_id, "visitor_type", selected)
        update_visitor_type_keyboard(ctx, call.message, user_id, language, options)
    except Exception as exc:
        logging.exception(f"Error in handle_visitor_type_selection: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def update_visitor_type_keyboard(
    ctx: AppContext,
    message: Any,
    user_id: int,
    language: str,
    options: list[str],
) -> None:
    try:
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        selected = ctx.sessions.get_data(user_id, "visitor_type", [])
        custom = ctx.sessions.get_data(user_id, "custom_visitor_types", [])

        buttons = []
        for idx, option in enumerate(options):
            prefix = "✅ " if option in selected else ""
            buttons.append(
                types.InlineKeyboardButton(
                    text=prefix + option,
                    callback_data=f"visitor_{idx}",
                )
            )

        if selected or custom:
            inline_kb.add(*buttons)
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=messages[language]["done_button"],
                    callback_data="visitor_done",
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
                logging.exception(f"Error in update_visitor_type_keyboard: {exc}")
    except Exception as exc:
        logging.exception(f"Error in update_visitor_type_keyboard: {exc}")
