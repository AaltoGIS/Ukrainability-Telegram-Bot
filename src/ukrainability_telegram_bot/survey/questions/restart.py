"""Post-submission continue/stop and save orchestration."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from telebot import types

from ...app import AppContext
from ...messages import messages
from ...survey.persistence import (
    DatabaseSaveError,
    EncryptionUnavailableError,
    save_response,
)
from ...telegram_io import (
    callback_suffix,
    escape_html,
    safe_answer_callback,
    safe_send_message,
    send_next_step_prompt,
)
from .base import register


EXPERIENCE_KEYS = [
    "location",
    "enjoyment",
    "purpose_visit",
    "regularity",
    "noticed_changes",
    "changes_detail",
    "wishlist",
    "kremenchuk",
    "description",
    "voice_submitted",
    "visitor_type",
    "duration_visit",
    "accessibility",
    "description_done",
]


@dataclass(frozen=True)
class RestartCallbacks:
    location_handler: Callable[..., Any]
    send_welcome: Callable[..., Any]
    get_user_hash: Callable[[int], str]
    get_user_nickname: Callable[[str], str | None]
    generate_unique_nickname: Callable[[], str]
    save_user_nickname: Callable[[str, str], Any]
    clear_message_ids: Callable[[int], Any]


@register("continue")
class ContinueQuestion:
    name = "continue"
    callback_prefix = "continue_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_continue_or_stop(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_continue_or_stop_selection(ctx, call)


def ask_continue_or_stop(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
) -> None:
    try:
        options = messages[language]["continue_options"]
        inline_kb = types.InlineKeyboardMarkup(row_width=2)
        inline_kb.add(
            *[
                types.InlineKeyboardButton(
                    text=option,
                    callback_data=f"continue_{idx}",
                )
                for idx, option in enumerate(options)
            ]
        )
        nickname = ctx.sessions.get_data(user_id, "nickname")
        safe_send_message(
            ctx,
            chat_id,
            f"<b>{messages[language]['thank_you']}</b>",
            parse_mode="HTML",
        )
        time.sleep(0.8)
        continue_msg = messages[language]["continue_question"].format(
            nickname=f"<b>{escape_html(nickname)}</b>"
        )
        safe_send_message(
            ctx,
            chat_id,
            continue_msg,
            reply_markup=inline_kb,
            parse_mode="HTML",
        )
    except Exception as exc:
        logging.exception(f"Error in ask_continue_or_stop: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def handle_continue_or_stop_selection(
    ctx: AppContext,
    call: Any,
    callbacks: RestartCallbacks | None = None,
) -> None:
    language = "en"
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        ctx.sessions.update_activity(user_id)
        language = _language_for_user(ctx, chat_id, user_id)
        if language is None:
            return

        options = messages[language]["continue_options"]
        data = callback_suffix(call.data, "continue")
        if data == "0":
            safe_answer_callback(ctx, call, f"{messages[language]['selected']} {options[0]}")
            ctx.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None,
            )
            if callbacks is not None:
                save_data_and_restart(ctx, chat_id, user_id, language, False, callbacks)
                send_next_step_prompt(
                    ctx,
                    chat_id,
                    messages[language]["send_location"],
                    callbacks.location_handler,
                )
        elif data == "1":
            safe_answer_callback(ctx, call, f"{messages[language]['selected']} {options[1]}")
            ctx.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None,
            )
            inline_kb = types.InlineKeyboardMarkup()
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=messages[language]["restart_button"],
                    callback_data="restart",
                )
            )
            safe_send_message(
                ctx,
                chat_id,
                messages[language]["consent_denied"],
                reply_markup=inline_kb,
                parse_mode="HTML",
            )
            if callbacks is not None:
                save_data_and_restart(ctx, chat_id, user_id, language, False, callbacks)
        else:
            safe_answer_callback(ctx, call, messages[language]["invalid_selection"])
    except Exception as exc:
        logging.exception(f"Error in handle_continue_or_stop_selection: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def save_data_and_restart(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
    restart_survey: bool,
    callbacks: RestartCallbacks,
) -> bool:
    try:
        user_consent = ctx.sessions.profile_snapshot(user_id).get("consent", False)
        if not user_consent:
            ctx.flow_logger.info("Consent denied; skipping response row insert")
            callbacks.clear_message_ids(user_id)
            if restart_survey:
                callbacks.send_welcome(
                    chat_id=chat_id,
                    user_id=user_id,
                    start_param="restart",
                )
            return True

        def nickname_provider() -> str:
            user_hash = callbacks.get_user_hash(user_id)
            nickname = callbacks.get_user_nickname(user_hash)
            if not nickname:
                nickname = callbacks.generate_unique_nickname()
                callbacks.save_user_nickname(user_hash, nickname)
            return nickname

        try:
            save_response(
                ctx,
                user_id,
                language,
                nickname_provider=nickname_provider,
            )
        except EncryptionUnavailableError:
            ctx.flow_logger.error("Encryption not initialized. Cannot save data securely.")
            safe_send_message(
                ctx,
                chat_id,
                (
                    "A security error occurred. Your data could not be saved securely. Please contact support."
                    if language == "en"
                    else "Сталася помилка безпеки. Ваші дані не могли бути збережені надійно. Зверніться до служби підтримки."
                ),
            )
            return False
        except DatabaseSaveError:
            safe_send_message(
                ctx,
                chat_id,
                (
                    "A database error occurred. Your data could not be saved. Please try again later."
                    if language == "en"
                    else "Сталася помилка бази даних. Ваші дані не могли бути збережені. Будь ласка, спробуйте пізніше."
                ),
            )
            return False

        for key in EXPERIENCE_KEYS:
            ctx.sessions.remove_data(user_id, key)
        callbacks.clear_message_ids(user_id)

        if restart_survey:
            callbacks.send_welcome(
                chat_id=chat_id,
                user_id=user_id,
                start_param="restart",
            )
        return True
    except Exception as exc:
        error_msg = f"Error in save_data_and_restart: {exc}"
        logging.exception(error_msg)
        ctx.flow_logger.error(error_msg)
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])
        return False


def _language_for_user(ctx: AppContext, chat_id: int, user_id: int) -> str | None:
    language = ctx.sessions.get_data(user_id, "language")
    if language:
        return language
    profile_language = ctx.sessions.get_profile(user_id, "language")
    if profile_language:
        ctx.sessions.set_data(user_id, "language", profile_language)
        return profile_language
    safe_send_message(ctx, chat_id, messages["en"]["please_use_start"])
    return None
