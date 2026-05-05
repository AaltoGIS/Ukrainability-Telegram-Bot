"""Purpose-of-visit question handlers."""

from __future__ import annotations

import logging
import time
from typing import Any

import telebot
from telebot import types

from ...app import AppContext
from ...messages import messages
from ...telegram_io import (
    callback_index,
    callback_suffix,
    edit_keyboard,
    escape_html,
    get_message_id,
    handle_callback_error,
    hide_keyboard,
    safe_answer_callback,
    safe_send_message,
    send_keyboard_message,
)
from .base import PurposeCallbacks, register, resolve_actions


def callbacks_from_context(ctx: AppContext, actions: Any | None = None) -> PurposeCallbacks:
    actions = resolve_actions(ctx, actions)
    return PurposeCallbacks(
        ask_enjoyment=actions.ask_enjoyment,
        ask_final_confirmation=actions.ask_final_confirmation,
        clear_callback_state=actions.clear_callback_state,
    )


@register("purpose")
class PurposeQuestion:
    name = "purpose"
    callback_prefix = "purpose_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_purpose_visit(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_purpose_selection(ctx, call)


def ask_purpose_visit(ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
    try:
        ctx.sessions.set_data(user_id, "purpose_visit", [])
        ctx.sessions.set_data(user_id, "custom_purposes", [])
        ctx.sessions.set_data(user_id, "awaiting_multiple_select", "purpose_visit")

        options = messages[language]["options"]["purpose_visit"][:-1]
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"purpose_{idx}")
            for idx, option in enumerate(options)
        ]
        done_button = types.InlineKeyboardButton(
            text=messages[language]["done_button"],
            callback_data="purpose_done",
        )
        inline_kb.add(*buttons)
        inline_kb.add(done_button)

        instruction_text = (
            f"{messages[language]['purpose_visit']}\n\n"
            f"{messages[language]['purpose_visit_custom_instruction']}"
        )
        send_keyboard_message(
            ctx,
            chat_id,
            user_id,
            instruction_text,
            inline_kb,
            "purpose_visit",
        )
    except Exception as exc:
        logging.exception(f"Error in ask_purpose_visit: {exc}")
        safe_send_message(
            ctx,
            chat_id,
            messages[language].get(
                "error_occurred",
                "An error occurred. Please try again later.",
            ),
        )


def handle_purpose_selection(
    ctx: AppContext,
    call: Any,
    callbacks: PurposeCallbacks | None = None,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language")
        data = callback_suffix(call.data, "purpose")

        if data == "done":
            purpose_visit = ctx.sessions.get_data(user_id, "purpose_visit", [])
            custom_purposes = ctx.sessions.get_data(user_id, "custom_purposes", [])
            if not purpose_visit and not custom_purposes:
                safe_answer_callback(
                    ctx,
                    call,
                    messages[language].get(
                        "please_select_at_least_one",
                        "Please select at least one option or type your own.",
                    ),
                )
                return

            edit_keyboard(ctx, user_id, chat_id, "purpose_visit", None)
            all_purposes = purpose_visit + custom_purposes
            safe_answer_callback(
                ctx,
                call,
                messages[language]["selections_saved"],
            )
            purposes = "; ".join(escape_html(p) for p in all_purposes)
            safe_send_message(
                ctx,
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{purposes}</i>",
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
                time.sleep(0.5)
                callbacks.ask_enjoyment(chat_id, user_id, language)
        else:
            options = messages[language]["options"]["purpose_visit"][:-1]
            try:
                idx = callback_index(call.data, "purpose", options)
            except (ValueError, IndexError):
                safe_answer_callback(
                    ctx,
                    call,
                    messages[language].get("invalid_selection", "Invalid selection."),
                )
                return

            selected_option = options[idx]
            purpose_visit = ctx.sessions.get_data(user_id, "purpose_visit", [])
            if selected_option in purpose_visit:
                purpose_visit.remove(selected_option)
                safe_answer_callback(
                    ctx,
                    call,
                    f"{messages[language]['unselected']} {selected_option}",
                )
            else:
                purpose_visit.append(selected_option)
                safe_answer_callback(
                    ctx,
                    call,
                    f"{messages[language]['selected']} {selected_option}",
                )
            ctx.sessions.set_data(user_id, "purpose_visit", purpose_visit)
            update_purpose_selection_keyboard(ctx, call.message, user_id, language)
    except Exception as exc:
        handle_callback_error(
            ctx,
            call,
            exc,
            "handle_purpose_selection",
            clear_callback_state=callbacks.clear_callback_state if callbacks else None,
        )


def update_purpose_selection_keyboard(
    ctx: AppContext,
    message: Any,
    user_id: int,
    language: str,
) -> None:
    try:
        options = messages[language]["options"]["purpose_visit"][:-1]
        selected_options = ctx.sessions.get_data(user_id, "purpose_visit", [])
        custom_options = ctx.sessions.get_data(user_id, "custom_purposes", [])

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = []
        for idx, option in enumerate(options):
            button_text = f"✅ {option}" if option in selected_options else option
            callback_data = f"purpose_{idx}"
            buttons.append(
                types.InlineKeyboardButton(text=button_text, callback_data=callback_data)
            )

        if selected_options or custom_options:
            done_button = types.InlineKeyboardButton(
                text=messages[language]["done_button"],
                callback_data="purpose_done",
            )
            inline_kb.add(*buttons)
            inline_kb.add(done_button)
        else:
            inline_kb.add(*buttons)

        message_id = get_message_id(ctx, user_id, "purpose_visit")
        if message_id:
            try:
                ctx.bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=message_id,
                    reply_markup=inline_kb,
                )
            except telebot.apihelper.ApiTelegramException as exc:
                if "message is not modified" not in str(exc):
                    logging.exception(f"Error in update_purpose_selection_keyboard: {exc}")
        else:
            try:
                ctx.bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_markup=inline_kb,
                )
            except telebot.apihelper.ApiTelegramException as exc:
                if "message is not modified" not in str(exc):
                    logging.exception(f"Error in update_purpose_selection_keyboard: {exc}")
    except Exception as exc:
        logging.exception(f"Error in update_purpose_selection_keyboard: {exc}")
