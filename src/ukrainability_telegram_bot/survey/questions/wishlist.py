"""Wishlist question handlers."""

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
class WishlistCallbacks:
    ask_age: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]
    get_anonymous_id: Callable[[int], str]


@register("wishlist")
class WishlistQuestion:
    name = "wishlist"
    callback_prefix = "wishlist_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_wishlist(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_wishlist_selection(ctx, call)


def ask_wishlist(ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
    try:
        ctx.flow_logger.info("Asking wishlist question")
        ctx.sessions.set_data(user_id, "wishlist", [])
        ctx.sessions.set_data(user_id, "custom_wishlist", [])
        ctx.sessions.set_data(user_id, "awaiting_multiple_select", "wishlist")

        options = messages[language]["options"]["wishlist"][:-1]
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"wishlist_{idx}")
            for idx, option in enumerate(options)
        ]
        inline_kb.add(*buttons)
        inline_kb.add(
            types.InlineKeyboardButton(
                text=messages[language]["done_button"],
                callback_data="wishlist_done",
            )
        )
        instruction_text = (
            f"{messages[language]['wishlist_question']}\n\n"
            f"{messages[language]['wishlist_custom_instruction']}"
        )
        safe_send_message(ctx, chat_id, instruction_text, reply_markup=inline_kb)
    except Exception as exc:
        logging.exception(f"Error in ask_wishlist: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def handle_wishlist_selection(
    ctx: AppContext,
    call: Any,
    callbacks: WishlistCallbacks | None = None,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        data = callback_suffix(call.data, "wishlist")
        options = messages[language]["options"]["wishlist"][:-1]

        if data == "done":
            selected = ctx.sessions.get_data(user_id, "wishlist", [])
            custom = ctx.sessions.get_data(user_id, "custom_wishlist", [])
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
            all_wishlist = selected + custom
            selected_text = "; ".join(escape_html(option) for option in all_wishlist)
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
                callbacks.ask_age(chat_id, user_id, language)
            return

        try:
            idx = callback_index(call.data, "wishlist", options)
        except (ValueError, IndexError):
            safe_answer_callback(ctx, call, messages[language]["invalid_selection"])
            return

        choice = options[idx]
        selected = ctx.sessions.get_data(user_id, "wishlist", [])
        if choice in selected:
            selected.remove(choice)
            safe_answer_callback(ctx, call, f"{messages[language]['unselected']} {choice}")
        else:
            selected.append(choice)
            safe_answer_callback(ctx, call, f"{messages[language]['selected']} {choice}")
        ctx.sessions.set_data(user_id, "wishlist", selected)
        update_wishlist_keyboard(ctx, call.message, user_id, language, options)
    except Exception as exc:
        logging.exception(f"Error in handle_wishlist_selection: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def update_wishlist_keyboard(
    ctx: AppContext,
    message: Any,
    user_id: int,
    language: str,
    options: list[str],
) -> None:
    try:
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        selected = ctx.sessions.get_data(user_id, "wishlist", [])
        custom = ctx.sessions.get_data(user_id, "custom_wishlist", [])

        buttons = []
        for idx, option in enumerate(options):
            button_text = f"✅ {option}" if option in selected else option
            buttons.append(
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"wishlist_{idx}",
                )
            )

        if selected or custom:
            inline_kb.add(*buttons)
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=messages[language]["done_button"],
                    callback_data="wishlist_done",
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
                logging.exception(f"Error in update_wishlist_keyboard: {exc}")
    except Exception as exc:
        logging.exception(f"Error in update_wishlist_keyboard: {exc}")
