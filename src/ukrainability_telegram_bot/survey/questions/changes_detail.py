"""Changes-detail question handlers."""

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
from .base import register, resolve_actions


@dataclass(frozen=True)
class ChangesDetailCallbacks:
    ask_wishlist: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]
    get_anonymous_id: Callable[[int], str]


def callbacks_from_context(ctx: AppContext, actions: Any | None = None) -> ChangesDetailCallbacks:
    actions = resolve_actions(ctx, actions)
    return ChangesDetailCallbacks(
        ask_wishlist=actions.ask_wishlist,
        ask_final_confirmation=actions.ask_final_confirmation,
        get_anonymous_id=actions.get_anonymous_id,
    )


@register("changes_detail")
class ChangesDetailQuestion:
    name = "changes_detail"
    callback_prefix = "changes_detail_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_changes_detail(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_changes_detail_selection(ctx, call)


def ask_changes_detail(ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
    try:
        ctx.flow_logger.info("Asking changes_detail question")

        ctx.sessions.set_data(user_id, "changes_detail", [])
        ctx.sessions.set_data(user_id, "custom_changes", [])
        ctx.sessions.set_data(user_id, "awaiting_multiple_select", "changes_detail")

        options = messages[language]["options"]["changes_detail"][:-1]
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton(
                text=option,
                callback_data=f"changes_detail_{idx}",
            )
            for idx, option in enumerate(options)
        ]
        inline_kb.add(*buttons)
        inline_kb.add(
            types.InlineKeyboardButton(
                text=messages[language]["done_button"],
                callback_data="changes_detail_done",
            )
        )

        instruction_text = (
            f"{messages[language]['changes_detail_question']}\n\n"
            f"{messages[language]['changes_detail_custom_instruction']}"
        )
        safe_send_message(ctx, chat_id, instruction_text, reply_markup=inline_kb)
    except Exception as exc:
        logging.exception(f"Error in ask_changes_detail: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def handle_changes_detail_selection(
    ctx: AppContext,
    call: Any,
    callbacks: ChangesDetailCallbacks | None = None,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        anon_id = callbacks.get_anonymous_id(user_id) if callbacks else "unknown"
        options = messages[language]["options"]["changes_detail"][:-1]
        data = callback_suffix(call.data, "changes_detail")

        if data == "done":
            selected = ctx.sessions.get_data(user_id, "changes_detail", [])
            custom = ctx.sessions.get_data(user_id, "custom_changes", [])
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
            all_changes = selected + custom
            changes = "; ".join(escape_html(change) for change in all_changes)
            ctx.flow_logger.info(
                "User %s: Completed changes_detail with selections: %s",
                anon_id,
                all_changes,
            )
            safe_send_message(
                ctx,
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{changes}</i>",
                parse_mode="HTML",
            )
            ctx.sessions.remove_data(user_id, "awaiting_multiple_select")
            hide_keyboard(ctx, chat_id)

            if callbacks is None:
                return
            if ctx.sessions.get_data(user_id, "modifying"):
                ctx.sessions.remove_data(user_id, "modifying")
                ctx.sessions.remove_data(user_id, "modifying_field")
                ctx.flow_logger.info(
                    "User %s: In modification flow, returning to final confirmation",
                    anon_id,
                )
                callbacks.ask_final_confirmation(chat_id, user_id, language)
            else:
                ctx.flow_logger.info("User %s: Proceeding to wishlist question", anon_id)
                callbacks.ask_wishlist(chat_id, user_id, language)
            return

        try:
            idx = callback_index(call.data, "changes_detail", options)
        except (ValueError, IndexError):
            safe_answer_callback(ctx, call, messages[language]["invalid_selection"])
            return

        selected_option = options[idx]
        selected = ctx.sessions.get_data(user_id, "changes_detail", [])
        if selected_option in selected:
            selected.remove(selected_option)
            safe_answer_callback(
                ctx,
                call,
                f"{messages[language]['unselected']} {selected_option}",
            )
            ctx.flow_logger.info(
                "User %s: Unselected changes_detail option: %s",
                anon_id,
                selected_option,
            )
        else:
            selected.append(selected_option)
            safe_answer_callback(
                ctx,
                call,
                f"{messages[language]['selected']} {selected_option}",
            )
            ctx.flow_logger.info(
                "User %s: Selected changes_detail option: %s",
                anon_id,
                selected_option,
            )
        ctx.sessions.set_data(user_id, "changes_detail", selected)
        update_changes_detail_selection_keyboard(ctx, call.message, user_id, language)
    except Exception as exc:
        logging.exception(f"Error in handle_changes_detail_selection: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def update_changes_detail_selection_keyboard(
    ctx: AppContext,
    message: Any,
    user_id: int,
    language: str,
) -> None:
    try:
        options = messages[language]["options"]["changes_detail"][:-1]
        selected = ctx.sessions.get_data(user_id, "changes_detail", [])
        custom = ctx.sessions.get_data(user_id, "custom_changes", [])

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = []
        for idx, option in enumerate(options):
            button_text = f"✅ {option}" if option in selected else option
            buttons.append(
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"changes_detail_{idx}",
                )
            )

        if selected or custom:
            inline_kb.add(*buttons)
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=messages[language]["done_button"],
                    callback_data="changes_detail_done",
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
                logging.exception(f"Error in update_changes_detail_selection_keyboard: {exc}")
    except Exception as exc:
        logging.exception(f"Error in update_changes_detail_selection_keyboard: {exc}")
        safe_send_message(ctx, message.chat.id, messages[language]["error_occurred"])
