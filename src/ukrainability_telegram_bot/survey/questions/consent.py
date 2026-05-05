"""Consent question handlers."""

from __future__ import annotations

import logging
from typing import Any

from telebot import types

from ...app import AppContext
from ...messages import messages
from ...telegram_io import (
    callback_index,
    escape_html,
    safe_answer_callback,
    safe_send_message,
    send_next_step_prompt,
)
from .base import ConsentCallbacks, register


@register("consent")
class ConsentQuestion:
    name = "consent"
    callback_prefix = "consent_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        options = messages[language]["consent_options"]
        inline_kb = types.InlineKeyboardMarkup(row_width=2)
        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"consent_{idx}")
            for idx, option in enumerate(options)
        ]
        inline_kb.add(*buttons)
        safe_send_message(
            ctx,
            chat_id,
            messages[language]["project_intro"],
            parse_mode="HTML",
            reply_markup=inline_kb,
        )

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_consent(ctx, call)


def handle_consent(ctx: AppContext, call: Any) -> None:
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
                safe_send_message(
                    ctx,
                    chat_id,
                    messages["en"]["please_use_start"],
                )
                return

        consent_options = messages[language]["consent_options"]
        try:
            idx = callback_index(call.data, "consent", consent_options)
        except (ValueError, IndexError):
            safe_answer_callback(ctx, call, messages[language]["invalid_selection"])
            return

        consent_response = consent_options[idx]
        ctx.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None,
        )

        if consent_response == consent_options[0]:
            nickname = ctx.sessions.get_data(user_id, "nickname")
            consent_message = messages[language]["consent_given"].format(
                nickname=f"<b>{escape_html(nickname)}</b>"
            )
            ctx.sessions.set_profile(user_id, "consent", True)
            safe_answer_callback(
                ctx,
                call,
                messages[language]["consent_acknowledgement"],
            )
            inline_kb = types.InlineKeyboardMarkup()
            continue_button = types.InlineKeyboardButton(
                messages[language]["continue_button"],
                callback_data="post_consent_continue",
            )
            inline_kb.add(continue_button)
            safe_send_message(
                ctx,
                chat_id,
                consent_message,
                parse_mode="HTML",
                reply_markup=inline_kb,
            )
        elif consent_response == consent_options[1]:
            ctx.sessions.set_profile(user_id, "consent", False)
            inline_kb = types.InlineKeyboardMarkup()
            restart_button = types.InlineKeyboardButton(
                text=messages[language]["restart_button"], callback_data="restart"
            )
            inline_kb.add(restart_button)
            safe_answer_callback(
                ctx,
                call,
                messages[language]["consent_thanks"],
            )
            safe_send_message(
                ctx,
                chat_id,
                messages[language]["consent_denied"],
                reply_markup=inline_kb,
            )
        else:
            safe_answer_callback(ctx, call, messages[language]["invalid_selection"])
    except Exception as exc:
        logging.exception(f"Error in handle_consent: {exc}")
        safe_send_message(ctx, chat_id, messages["en"]["error_occurred"])


def handle_post_consent_continue(
    ctx: AppContext,
    call: Any,
    callbacks: ConsentCallbacks,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        ctx.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
        send_next_step_prompt(
            ctx,
            chat_id,
            messages[language]["send_location"],
            callbacks.location_handler,
        )
    except Exception as exc:
        logging.exception(f"Error in handle_post_consent_continue: {exc}")
        safe_send_message(ctx, chat_id, messages["en"]["error_occurred"])
