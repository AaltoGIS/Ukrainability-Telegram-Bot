"""Consent question handlers."""

from __future__ import annotations

import logging
from typing import Any

from telebot import types

from ...app import AppContext
from ...messages import messages
from ...telegram_io import callback_index, escape_html, send_next_step_prompt
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
        ctx.bot.send_message(
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

        if user_id not in ctx.sessions.data or "language" not in ctx.sessions.data[user_id]:
            if user_id in ctx.sessions.profiles and "language" in ctx.sessions.profiles[user_id]:
                ctx.sessions.data.setdefault(user_id, {})["language"] = (
                    ctx.sessions.profiles[user_id]["language"]
                )
            else:
                ctx.bot.send_message(
                    chat_id,
                    "Please use /start to begin.\nБудь ласка, використайте /start для початку.",
                )
                return

        language = ctx.sessions.data[user_id]["language"]
        consent_options = messages[language]["consent_options"]
        try:
            idx = callback_index(call.data, "consent", consent_options)
        except (ValueError, IndexError):
            ctx.bot.answer_callback_query(call.id, messages[language]["invalid_selection"])
            return

        consent_response = consent_options[idx]
        ctx.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None,
        )

        if consent_response == consent_options[0]:
            nickname = ctx.sessions.data[user_id]["nickname"]
            consent_message = messages[language]["consent_given"].format(
                nickname=f"<b>{escape_html(nickname)}</b>"
            )
            ctx.sessions.profiles.setdefault(user_id, {})["consent"] = True
            ctx.bot.answer_callback_query(
                call.id,
                "Thank you for agreeing to participate!"
                if language == "en"
                else "Дякуємо за вашу згоду на участь!",
            )
            continue_text = "Continue" if language == "en" else "Продовжити"
            inline_kb = types.InlineKeyboardMarkup()
            continue_button = types.InlineKeyboardButton(
                continue_text, callback_data="post_consent_continue"
            )
            inline_kb.add(continue_button)
            ctx.bot.send_message(
                chat_id,
                consent_message,
                parse_mode="HTML",
                reply_markup=inline_kb,
            )
        elif consent_response == consent_options[1]:
            ctx.sessions.profiles.setdefault(user_id, {})["consent"] = False
            inline_kb = types.InlineKeyboardMarkup()
            restart_button = types.InlineKeyboardButton(
                text=messages[language]["restart_button"], callback_data="restart"
            )
            inline_kb.add(restart_button)
            ctx.bot.answer_callback_query(
                call.id,
                "Thank you for your time." if language == "en" else "Дякуємо за ваш час.",
            )
            ctx.bot.send_message(
                chat_id,
                messages[language]["consent_denied"],
                reply_markup=inline_kb,
            )
        else:
            ctx.bot.answer_callback_query(call.id, messages[language]["invalid_selection"])
    except Exception as exc:
        logging.exception(f"Error in handle_consent: {exc}")
        ctx.bot.send_message(chat_id, "An error occurred. Please try again later.")


def handle_post_consent_continue(
    ctx: AppContext,
    call: Any,
    callbacks: ConsentCallbacks,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.data[user_id]["language"]
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
        ctx.bot.send_message(chat_id, "An error occurred. Please try again later.")
